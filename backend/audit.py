"""Append-only audit trail at output/audit_trail.json.

The file is a JSON array. Each event is appended (read, add, atomic rewrite), so
earlier runs are never wiped.
"""

import json
import os
import threading
from datetime import datetime, timezone

from pydantic_ai import messages as m

from backend.config import AUDIT_TEXT_LIMIT, AUDIT_TRAIL

_lock = threading.Lock()


def _clip(value):
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= AUDIT_TEXT_LIMIT else text[:AUDIT_TEXT_LIMIT] + f"... [{len(text)} chars]"


def append_event(event: dict) -> None:
    event = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), **event}
    with _lock:
        AUDIT_TRAIL.parent.mkdir(parents=True, exist_ok=True)
        events = json.loads(AUDIT_TRAIL.read_text()) if AUDIT_TRAIL.exists() and AUDIT_TRAIL.stat().st_size else []
        events.append(event)
        tmp = AUDIT_TRAIL.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(events, indent=2, default=str))
        os.replace(tmp, AUDIT_TRAIL)


def describe_part(part) -> dict:
    """Turn one message part into a small, auditable dict."""
    if isinstance(part, m.ToolCallPart):
        return {"kind": "tool_call", "tool": part.tool_name, "tool_call_id": part.tool_call_id,
                "args": _clip(part.args_as_dict())}
    if isinstance(part, m.ToolReturnPart):
        return {"kind": "tool_return", "tool": part.tool_name, "tool_call_id": part.tool_call_id,
                "content": _clip(part.content)}
    if isinstance(part, m.RetryPromptPart):
        return {"kind": "retry", "tool": part.tool_name, "content": _clip(part.content)}
    if isinstance(part, m.TextPart):
        return {"kind": "text", "content": _clip(part.content)}
    if isinstance(part, m.UserPromptPart):
        return {"kind": "user_prompt", "content": _clip(part.content)}
    if isinstance(part, m.ThinkingPart):
        return {"kind": "thinking"}  # reasoning text is not logged
    return {"kind": getattr(part, "part_kind", type(part).__name__)}
