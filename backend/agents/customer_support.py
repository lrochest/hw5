"""Customer Support: drafts messages for customers and requesters. Drafts stay on the board; nothing is sent."""

from backend.agents.base import build_agent
from backend.models import AgentReport

TOOLS = {
    "get_ticket",
    "check_stock",
    "list_stock",
    "draft_customer_message",
}

customer_support_agent = build_agent("customer_support", TOOLS, AgentReport)
