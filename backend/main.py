"""Campus Customs backend for the React dashboard.

Start from the backend/ folder:
    uvicorn main:app --reload --port 8000

Every shop fact goes through the campus-customs MCP server; this file never opens the database.
"""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Started from backend/, so make the project root importable for `backend.*` imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend.agents import shop_mcp  # noqa: E402
from backend.audit import append_event  # noqa: E402
from backend.config import AUDIT_TRAIL  # noqa: E402
from backend.runner import reset_working_db, run_ticket  # noqa: E402

CLOSED_STATUSES = {"resolved", "declined"}

# Only one agent run (or reset) at a time, so cash and pending requests stay consistent.
# Tickets sent while the team is busy wait in _queue and run in order.
_busy = asyncio.Lock()
_running_ticket: int | None = None
_run_task: asyncio.Task | None = None
_queue: list[int] = []
_wake = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shop_mcp:  # one MCP server process for the life of the API
        worker = asyncio.create_task(_team_worker())
        try:
            yield
        finally:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)


app = FastAPI(title="Campus Customs Multi-Agent Operations", lifespan=lifespan)
# The React desk runs on the Vite dev server; the browser may only call these routes from there
FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def _read_audit() -> list[dict]:
    return json.loads(AUDIT_TRAIL.read_text()) if AUDIT_TRAIL.exists() and AUDIT_TRAIL.stat().st_size else []


def _latest_runs() -> dict[int, dict]:
    """Latest agent run per ticket since the last database reset, read from the audit trail."""
    raw = _read_audit()
    last_reset = max((i for i, e in enumerate(raw) if e["event"] == "reset_db"), default=-1)
    runs: dict[int, dict] = {}
    for e in raw[last_reset + 1:]:
        if e["event"] == "ticket_start":
            runs[e["ticket_id"]] = {"run_id": e["run_id"], "started_at": e["ts"], "finished": False}
        elif e["event"] == "ticket_end" and runs.get(e["ticket_id"], {}).get("run_id") == e["run_id"]:
            runs[e["ticket_id"]].update(
                finished=True, finished_at=e["ts"], error=e.get("error"), decision=e.get("decision"),
                tokens=e.get("input_tokens", 0) + e.get("output_tokens", 0), requests=e.get("requests", 0),
                tool_calls=e.get("tool_calls", 0))
    return runs


async def mcp(tool: str, **args) -> dict:
    result = await shop_mcp.direct_call_tool(tool, args)
    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=1, description="Name of the human approving the payment")


class StopBody(BaseModel):
    stopped_by: str = Field(default="", description="Name of the human stopping the team")


class RejectBody(BaseModel):
    rejected_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Tickets
# ---------------------------------------------------------------------------


@app.get("/api/tickets")
async def list_tickets():
    """Every ticket with its status and whether it is open, running, or resolved.

    A ticket counts as resolved once the agent team finishes a run on it without error (or the boss
    closed it). `status` keeps the boss's detailed outcome, e.g. waiting_on_approval."""
    board = await mcp("list_tickets")
    runs = _latest_runs()
    for t in board["tickets"]:
        run = runs.get(t["id"])
        t["last_run"] = run
        if t["id"] == _running_ticket:
            t["state"] = "running"
        elif t["id"] in _queue:
            t["state"] = "queued"
            t["queue_position"] = _queue.index(t["id"]) + 1
        elif t["status"] in CLOSED_STATUSES or (run and run["finished"] and not run.get("error")):
            t["state"] = "resolved"
        else:
            t["state"] = "open"
    return {**board, "running_ticket_id": _running_ticket, "queue": list(_queue)}


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """One ticket with its status updates, payment requests, and drafts."""
    return await mcp("get_ticket", ticket_id=ticket_id)


async def _team_worker() -> None:
    """Work the queue one ticket at a time, so each run sees the cash and requests left by the one before."""
    global _running_ticket, _run_task
    while True:
        _wake.clear()
        if not _queue:
            await _wake.wait()
            continue
        async with _busy:
            ticket_id = _queue.pop(0)
            _running_ticket = ticket_id
            _run_task = asyncio.create_task(run_ticket(ticket_id))
            try:
                # A Stop cancels only this run (run_ticket writes its ticket_end); the queue carries on
                await asyncio.gather(_run_task, return_exceptions=True)
            finally:
                _running_ticket = None
                _run_task = None


async def _stop_team(stopped_by: str) -> int | None:
    """Cancel the run in progress, if any, and wait until it has written its ticket_end."""
    task, ticket_id = _run_task, _running_ticket
    if task is None or task.done():
        return None
    append_event({"event": "run_stopped", "ticket_id": ticket_id, "stopped_by": stopped_by or "a human"})
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    return ticket_id


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_agents(ticket_id: int):
    """Send a ticket to the agent team. If the team is busy, the ticket waits in the queue and starts
    as soon as the runs ahead of it finish. Poll /api/events to watch it work."""
    await mcp("get_ticket", ticket_id=ticket_id)  # 400 if the ticket doesn't exist
    if ticket_id == _running_ticket:
        raise HTTPException(status_code=409, detail=f"The team is already working on ticket {ticket_id}.")
    if ticket_id in _queue:
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} is already #{_queue.index(ticket_id) + 1} in the queue.")
    idle = _running_ticket is None and not _queue and not _busy.locked()
    _queue.append(ticket_id)
    _wake.set()
    if idle:
        return {"ticket_id": ticket_id, "status": "started", "position": 0}
    append_event({"event": "ticket_queued", "ticket_id": ticket_id, "position": len(_queue)})
    return {"ticket_id": ticket_id, "status": "queued", "position": len(_queue)}


@app.post("/api/tickets/{ticket_id}/unqueue")
async def unqueue(ticket_id: int):
    """Take a waiting ticket back out of the queue before the team starts it."""
    if ticket_id not in _queue:
        raise HTTPException(status_code=409, detail=f"Ticket {ticket_id} isn't waiting in the queue.")
    _queue.remove(ticket_id)
    append_event({"event": "ticket_unqueued", "ticket_id": ticket_id})
    return {"ticket_id": ticket_id, "status": "removed", "queue": list(_queue)}


@app.post("/api/run/stop")
async def stop_team(body: StopBody | None = None):
    """Stop the ticket the team is working on now. Requests and drafts already prepared stay pending for a
    human. Tickets waiting in the queue carry on; remove them with /unqueue or clear them with /api/reset."""
    ticket_id = await _stop_team(body.stopped_by if body else "")
    if ticket_id is None:
        raise HTTPException(status_code=409, detail="The team isn't working on anything right now.")
    return {"status": "stopped", "ticket_id": ticket_id}


# ---------------------------------------------------------------------------
# Agent events
# ---------------------------------------------------------------------------


def _flatten(event: dict) -> list[dict]:
    """Turn raw audit events into board-friendly rows: who said what and which tools they used."""
    base = {"ts": event["ts"], "run_id": event.get("run_id"), "ticket_id": event.get("ticket_id"),
            "chain": event.get("chain")}
    kind = event["event"]
    if kind == "agent_step" and event.get("node") == "model_response":
        rows = []
        for part in event.get("parts", []):
            if part["kind"] == "tool_call" and part["tool"] in ("final_result", "delegate"):
                continue  # shown by the matching "report" (end) and "delegate" events
            elif part["kind"] == "tool_call":
                rows.append({**base, "agent": event["agent"], "type": "tool_call", "tool": part["tool"],
                             "detail": part["args"]})
            elif part["kind"] == "text":
                rows.append({**base, "agent": event["agent"], "type": "message", "detail": part["content"]})
        return rows
    if kind == "agent_step" and event.get("node") == "end":
        return [{**base, "agent": event["agent"], "type": "report", "detail": event["output"]}]
    if kind == "agent_step" and event.get("node") == "model_request":
        return [{**base, "agent": event["agent"], "type": "tool_result", "tool": p["tool"], "detail": p["content"]}
                for p in event.get("parts", []) if p["kind"] == "tool_return" and p["tool"] != "final_result"]
    if kind == "delegate":
        return [{**base, "agent": event["from"], "type": "delegate", "to": event["to"], "detail": event["task"]}]
    if kind in ("ticket_start", "ticket_end", "reset_db", "payment_approved", "payment_rejected", "payment_refused",
                "run_stopped"):
        detail = {k: v for k, v in event.items() if k not in ("ts", "event", "run_id", "ticket_id")}
        who = event.get("approved_by") or event.get("rejected_by") or event.get("stopped_by")
        return [{**base, "agent": who, "type": kind, "detail": detail}]
    return []


@app.get("/api/events")
async def recent_events(limit: int = 100, ticket_id: int | None = None, run_id: str | None = None):
    """Most recent agent activity (newest last), read from output/audit_trail.json."""
    rows = [row for e in _read_audit() for row in _flatten(e)]
    if ticket_id is not None:
        rows = [r for r in rows if r["ticket_id"] == ticket_id]
    if run_id is not None:
        rows = [r for r in rows if r["run_id"] == run_id]
    return {"running_ticket_id": _running_ticket, "queue": list(_queue), "events": rows[-max(1, min(limit, 1000)):]}


# ---------------------------------------------------------------------------
# Payments (human only)
# ---------------------------------------------------------------------------


@app.get("/api/payments")
async def list_payment_requests(status: str | None = "pending"):
    """Payment and purchase-order requests the agents prepared (pending by default)."""
    return await mcp("list_payment_requests", **({"status": status} if status else {}))


@app.post("/api/payments/{request_id}/approve")
async def approve_payment(request_id: int, body: ApproveBody):
    """A human clicked Approve. This is the only path that moves cash; the MCP tool refuses
    agent names, payments larger than the balance, and purchase orders to blocked vendors."""
    try:
        result = await mcp("approve_payment", request_id=request_id, approved_by=body.approved_by)
    except HTTPException as e:
        # Refusals (overdraft, blocked vendor, agent name) are part of the audit too
        reqs = (await shop_mcp.direct_call_tool("list_payment_requests", {}))["payment_requests"]
        ticket_id = next((r["ticket_id"] for r in reqs if r["id"] == request_id), None)
        append_event({"event": "payment_refused", "ticket_id": ticket_id, "request_id": request_id,
                      "approved_by": body.approved_by, "reason": e.detail})
        raise
    req = result["payment_request"]
    append_event({"event": "payment_approved", "ticket_id": req["ticket_id"], "request_id": request_id,
                  "approved_by": body.approved_by, "kind": req["kind"], "amount": result["payment"]["amount"],
                  "balance_after": result["cash"]["total_balance"]})
    return result


@app.post("/api/payments/{request_id}/reject")
async def reject_payment(request_id: int, body: RejectBody):
    """A human clicked Reject. No money moves."""
    result = await mcp("reject_payment", request_id=request_id, rejected_by=body.rejected_by, reason=body.reason)
    append_event({"event": "payment_rejected", "ticket_id": result["payment_request"]["ticket_id"],
                  "request_id": request_id, "rejected_by": body.rejected_by, "reason": body.reason})
    return result


# ---------------------------------------------------------------------------
# Cash and reset
# ---------------------------------------------------------------------------


@app.get("/api/cash")
async def cash():
    """Current checking balance from cash_accounts, plus what is waiting for approval."""
    snap = await mcp("get_cash_balance")
    checking = next((a for a in snap["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(status_code=404, detail="No checking account in cash_accounts.")
    return {"today": snap["today"], "checking_balance": checking["balance"], "as_of": checking["date"],
            "pending_total": snap["pending_total"], "available_after_pending": snap["available_after_pending"]}


@app.post("/api/reset")
async def reset(body: StopBody | None = None):
    """Copy the original database over the working copy for a fresh run. Clears the queue and stops the
    team first if it is working."""
    cleared = list(_queue)
    _queue.clear()
    stopped = await _stop_team(body.stopped_by if body else "") if _run_task else None
    async with _busy:
        reset_working_db()
    return {"status": "reset", "stopped_ticket_id": stopped, "cleared_queue": cleared,
            "message": "data/campus_customs_new.db now matches data/campus_customs.db."}
