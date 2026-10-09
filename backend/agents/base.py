"""Shared wiring for every agent: the model, the MCP toolset, delegation, and the audited agent loop."""

import copy
from dataclasses import replace

from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.usage import RunUsage

from backend.audit import _clip, append_event, describe_part
from backend.config import (
    MAX_DELEGATION_DEPTH,
    MCP_SERVER,
    MODEL_SETTINGS,
    PROMPTS_DIR,
    TICKET_LIMITS,
    build_model,
)
from backend.models import AGENT_NAMES, AgentName, TeamDeps

# Moving money is a human decision: these MCP tools are never given to any agent.
HUMAN_ONLY_TOOLS = frozenset({"approve_payment", "reject_payment"})

# Identity fields the backend fills in from the running agent, so an agent cannot sign as someone else.
IDENTITY_ARGS = {
    "request_invoice_payment": "requested_by",
    "request_rent_payment": "requested_by",
    "request_purchase_order": "requested_by",
    "draft_customer_message": "drafted_by",
    "update_ticket_status": "updated_by",
}


async def _stamp_identity(ctx: RunContext[TeamDeps], call_tool, name: str, args: dict):
    if field := IDENTITY_ARGS.get(name):
        args = {**args, field: ctx.deps.agent}
    return await call_tool(name, args)


def _hide_identity_args(ctx: RunContext[TeamDeps], tool_defs: list[ToolDefinition]) -> list[ToolDefinition]:
    """Remove identity fields from the schema the model sees; _stamp_identity fills them instead."""
    out = []
    for td in tool_defs:
        if field := IDENTITY_ARGS.get(td.name):
            schema = copy.deepcopy(td.parameters_json_schema)
            schema.get("properties", {}).pop(field, None)
            schema["required"] = [r for r in schema.get("required", []) if r != field]
            td = replace(td, parameters_json_schema=schema)
        out.append(td)
    return out


# One MCP server process shared by the whole team. Every shop fact comes through here.
shop_mcp = MCPToolset(MCP_SERVER, process_tool_call=_stamp_identity)

MODEL = build_model()
AGENTS: dict[AgentName, Agent] = {}


# Prompt file per agent (Customer Support's prompt is named for its customer service role)
PROMPT_FILES: dict[AgentName, str] = {
    "boss": "boss.md",
    "inventory": "inventory.md",
    "accounting": "accounting.md",
    "facilities": "facilities.md",
    "customer_support": "customer_service.md",
}


def load_instructions(name: AgentName) -> str:
    return (PROMPTS_DIR / PROMPT_FILES[name]).read_text() + "\n\n" + (PROMPTS_DIR / "shop_rules.md").read_text()


async def delegate(ctx: RunContext[TeamDeps], to: AgentName, task: str) -> str:
    """Hand part of the current ticket to another team member and get their report back.

    Args:
        to: The teammate: boss, inventory, accounting, facilities, or customer_support.
        task: A specific, self-contained request. Include the ticket id and the facts they need,
            and say exactly what you want back.
    """
    me = ctx.deps.agent
    if to == me:
        return "Refused: you cannot delegate to yourself. Use your own tools."
    if to in ctx.deps.chain:
        return (f"Refused: {to} is already waiting on this chain ({' -> '.join(ctx.deps.chain)}). "
                "Finish with what you have and report back.")
    if len(ctx.deps.chain) >= MAX_DELEGATION_DEPTH:
        return f"Refused: delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Finish with what you have."

    child = TeamDeps(run_id=ctx.deps.run_id, ticket_id=ctx.deps.ticket_id, agent=to, chain=[*ctx.deps.chain, to])
    append_event({"event": "delegate", "run_id": ctx.deps.run_id, "ticket_id": ctx.deps.ticket_id,
                  "from": me, "to": to, "chain": child.chain, "task": _clip(task)})
    report = await run_agent(to, task, child, usage=ctx.usage)
    return report.model_dump_json()


def build_agent(name: AgentName, tools: set[str], output_type: type[BaseModel]) -> Agent[TeamDeps, BaseModel]:
    """Create one team member with only its own MCP tools, plus delegation to any other agent."""
    allowed = frozenset(tools) - HUMAN_ONLY_TOOLS
    toolset = shop_mcp.filtered(lambda ctx, td: td.name in allowed).prepared(_hide_identity_args)
    agent = Agent(
        MODEL,
        name=name,
        deps_type=TeamDeps,
        output_type=output_type,
        instructions=load_instructions(name),
        toolsets=[toolset],
        tools=[delegate],
        model_settings=MODEL_SETTINGS,
        retries=2,
    )
    AGENTS[name] = agent
    return agent


def _describe_node(node) -> dict:
    if Agent.is_user_prompt_node(node):
        return {"node": "user_prompt", "prompt": _clip(node.user_prompt)}
    if Agent.is_model_request_node(node):
        return {"node": "model_request", "parts": [describe_part(p) for p in node.request.parts]}
    if Agent.is_call_tools_node(node):
        r = node.model_response
        return {"node": "model_response", "model": r.model_name,
                "parts": [describe_part(p) for p in r.parts],
                "tokens": {"input": r.usage.input_tokens, "output": r.usage.output_tokens}}
    if Agent.is_end_node(node):
        return {"node": "end", "output": node.data.output.model_dump()}
    return {"node": type(node).__name__}


async def run_agent(name: AgentName, task: str, deps: TeamDeps, *, usage: RunUsage | None = None) -> BaseModel:
    """Run one agent's loop, appending every step to the audit trail. All agents on a ticket share usage limits."""
    if name not in AGENT_NAMES:
        raise ValueError(f"Unknown agent {name!r}")
    agent = AGENTS[name]
    async with agent.iter(task, deps=deps, usage=usage, usage_limits=TICKET_LIMITS) as run:
        step = 0
        async for node in run:
            step += 1
            append_event({"event": "agent_step", "run_id": deps.run_id, "ticket_id": deps.ticket_id,
                          "agent": name, "chain": deps.chain, "step": step, **_describe_node(node),
                          "run_usage": {"requests": run.usage.requests, "tool_calls": run.usage.tool_calls,
                                        "input_tokens": run.usage.input_tokens,
                                        "output_tokens": run.usage.output_tokens}})
        return run.result.output
