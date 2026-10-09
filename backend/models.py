"""Data types shared by the Campus Customs agent team."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_support"]
AGENT_NAMES: tuple[AgentName, ...] = ("boss", "inventory", "accounting", "facilities", "customer_support")

TicketStatus = Literal["open", "in_progress", "waiting_on_approval", "waiting_on_vendor", "resolved", "declined"]


@dataclass
class TeamDeps:
    """Per-run context passed to every agent (never shown to the model)."""

    run_id: str
    ticket_id: int | None
    agent: AgentName
    # Who asked whom, root first, e.g. ["boss", "accounting"]. Used to stop delegation loops.
    chain: list[AgentName] = field(default_factory=list)


class AgentReport(BaseModel):
    """What a specialist agent (inventory, accounting, facilities, customer_support) hands back."""

    agent: AgentName
    summary: str = Field(description="Two or three sentences answering the task you were given.")
    facts: list[str] = Field(
        default_factory=list,
        description="Facts you read from MCP tools, each with its source, e.g. 'inventory CC-TEE-WHITE/S qty 0'.",
    )
    actions_taken: list[str] = Field(
        default_factory=list, description="Writes you made through MCP tools (requests, drafts). Empty if read-only."
    )
    payment_request_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list, description="Anything stopping the ticket from being resolved.")
    needs_human: bool = Field(description="True if a human must approve or decide something before this can move.")


class BossDecision(BaseModel):
    """The boss's final call on one ticket."""

    ticket_id: int
    final_status: TicketStatus
    decision: str = Field(description="The call you made and why, in two to four sentences.")
    delegated_to: list[AgentName] = Field(default_factory=list)
    payment_request_ids: list[int] = Field(default_factory=list)
    draft_ids: list[int] = Field(default_factory=list)
    human_actions_needed: list[str] = Field(
        default_factory=list, description="Exactly what a human must approve or decide next, if anything."
    )


class TicketRunResult(BaseModel):
    """Outcome of running the team on one ticket (returned by the runner, written to the audit trail)."""

    run_id: str
    ticket_id: int
    decision: BossDecision | None = None
    error: str | None = None
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
