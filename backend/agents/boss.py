"""Boss: reads each ticket, routes work to the right specialists, and makes the final call."""

from backend.agents.base import build_agent
from backend.models import BossDecision

TOOLS = {
    "list_open_tickets",
    "get_ticket",
    "get_cash_balance",
    "list_payment_requests",
    "check_discount",
    "update_ticket_status",  # only the boss changes a ticket's status
}

boss_agent = build_agent("boss", TOOLS, BossDecision)
