"""Inventory: checks stock by SKU and size, spots shortfalls, and finds which vendor can restock."""

from backend.agents.base import build_agent
from backend.models import AgentReport

TOOLS = {
    "get_ticket",
    "check_stock",
    "list_stock",
    "list_vendors",
    "check_vendor_invoices",
    "get_invoice",
}

inventory_agent = build_agent("inventory", TOOLS, AgentReport)
