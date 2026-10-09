"""Accounting: watches cash and invoices, checks discounts, and prepares payments and purchase orders
for human approval. It can request payments but can never approve or execute them."""

from backend.agents.base import build_agent
from backend.models import AgentReport

TOOLS = {
    "get_ticket",
    "get_cash_balance",
    "list_payment_requests",
    "get_invoice",
    "check_vendor_invoices",
    "list_vendors",
    "get_rent_due",
    "check_discount",
    "request_invoice_payment",
    "request_rent_payment",
    "request_purchase_order",
}

accounting_agent = build_agent("accounting", TOOLS, AgentReport)
