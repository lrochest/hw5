"""The Campus Customs agent team. Importing this package registers all five agents."""

from backend.agents.accounting import accounting_agent
from backend.agents.base import AGENTS, run_agent, shop_mcp
from backend.agents.boss import boss_agent
from backend.agents.customer_support import customer_support_agent
from backend.agents.facilities import facilities_agent
from backend.agents.inventory import inventory_agent

__all__ = [
    "AGENTS",
    "accounting_agent",
    "boss_agent",
    "customer_support_agent",
    "facilities_agent",
    "inventory_agent",
    "run_agent",
    "shop_mcp",
]
