"""Facilities: handles the shop space side, such as leases, rent, and the landlord."""

from backend.agents.base import build_agent
from backend.models import AgentReport

TOOLS = {
    "get_ticket",
    "get_rent_due",
    "get_cash_balance",
    "list_payment_requests",
}

facilities_agent = build_agent("facilities", TOOLS, AgentReport)
