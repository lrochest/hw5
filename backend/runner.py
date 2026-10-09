"""Run the agent team on tickets.

    ./.venv/bin/python -m backend.runner --ticket 102     # one ticket, on the current working copy
    ./.venv/bin/python -m backend.runner --all            # full run: resets the working copy first
    ./.venv/bin/python -m backend.runner --reset          # only reset the working copy
"""

import argparse
import asyncio
import sqlite3
import uuid

from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import RunUsage

from backend.agents import run_agent, shop_mcp
from backend.audit import append_event
from backend.config import ORIGINAL_DB, WORKING_DB
from backend.models import BossDecision, TeamDeps, TicketRunResult


def reset_working_db() -> None:
    """Replace the working copy's contents with the original. The original is only ever read.

    Uses SQLite's backup API rather than a file copy: it takes the database lock, so it waits for any
    write still finishing (e.g. a tool call from a run that was just stopped) instead of copying the
    file out from under it, which can corrupt the working copy."""
    src = sqlite3.connect(f"file:{ORIGINAL_DB}?mode=ro", uri=True)
    dst = sqlite3.connect(WORKING_DB, timeout=30)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    append_event({"event": "reset_db", "from": ORIGINAL_DB.name, "to": WORKING_DB.name})


async def run_ticket(ticket_id: int, run_id: str | None = None) -> TicketRunResult:
    """Hand one ticket to the boss. The boss and everyone it delegates to share one usage budget."""
    run_id = run_id or uuid.uuid4().hex[:12]
    deps = TeamDeps(run_id=run_id, ticket_id=ticket_id, agent="boss", chain=["boss"])
    usage = RunUsage()
    append_event({"event": "ticket_start", "run_id": run_id, "ticket_id": ticket_id})

    result = TicketRunResult(run_id=run_id, ticket_id=ticket_id)
    stopped = False
    try:
        async with shop_mcp:
            output = await run_agent(
                "boss",
                f"Handle ticket {ticket_id}. Read it, delegate to the right teammates, make the final call, "
                "and set its status before you finish.",
                deps,
                usage=usage,
            )
        assert isinstance(output, BossDecision)
        result.decision = output
    except UsageLimitExceeded as e:
        result.error = f"Token/usage limit hit: {e}"
    except asyncio.CancelledError:
        # A human pressed Stop (or Reset). Anything already prepared stays pending for review.
        result.error = "Stopped by a human before the team finished."
        stopped = True
    except Exception as e:  # recorded in the audit trail rather than lost
        result.error = f"{type(e).__name__}: {e}"

    result.requests = usage.requests
    result.tool_calls = usage.tool_calls
    result.input_tokens = usage.input_tokens
    result.output_tokens = usage.output_tokens
    append_event({"event": "ticket_end", **result.model_dump()})
    if stopped:
        raise asyncio.CancelledError
    return result


async def open_ticket_ids() -> list[int]:
    async with shop_mcp:
        board = await shop_mcp.direct_call_tool("list_open_tickets", {})
    return [t["id"] for t in board["tickets"]]


async def run_board() -> list[TicketRunResult]:
    """Full run: reset to the original data, then work every open ticket in order (one at a time,
    so each ticket sees the cash and requests left by the one before)."""
    reset_working_db()
    return [await run_ticket(tid) for tid in await open_ticket_ids()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable)")
    group.add_argument("--all", action="store_true", help="reset the working copy, then run every open ticket")
    group.add_argument("--reset", action="store_true", help="reset the working copy and exit")
    args = parser.parse_args()

    if args.reset:
        reset_working_db()
        print(f"Reset {WORKING_DB.name} from {ORIGINAL_DB.name}.")
        return

    async def go():
        return await run_board() if args.all else [await run_ticket(t) for t in args.ticket]

    for r in asyncio.run(go()):
        print(r.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
