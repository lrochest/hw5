"""Paths, model, and limits for the agent team."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

PROJECT_DIR = Path(__file__).resolve().parents[1]
# PORTKEY_API_KEY: a .env in this project (see .env.example) wins; otherwise the parent folder's .env
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(PROJECT_DIR.parent / ".env")

ORIGINAL_DB = PROJECT_DIR / "data" / "campus_customs.db"
WORKING_DB = PROJECT_DIR / "data" / "campus_customs_new.db"
MCP_SERVER = PROJECT_DIR / "mcp_server" / "server.py"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
AUDIT_TRAIL = PROJECT_DIR / "output" / "audit_trail.json"

MODEL_NAME = "gpt-6-luna"  # the only model any agent uses
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Token guardrails. One budget is shared by the boss and every agent it delegates to on a ticket.
TICKET_LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=250_000)
MAX_DELEGATION_DEPTH = 3  # boss -> specialist -> specialist, no deeper
MAX_OUTPUT_TOKENS = 4_000  # per model response
AUDIT_TEXT_LIMIT = 2_000  # characters kept per text field in the audit trail


def build_model() -> OpenAIResponsesModel:
    # Responses API: gpt-6-luna rejects function tools on /chat/completions. No temperature (rejected).
    provider = OpenAIProvider(base_url=PORTKEY_BASE_URL, api_key=os.environ["PORTKEY_API_KEY"])
    return OpenAIResponsesModel(MODEL_NAME, provider=provider)


MODEL_SETTINGS = OpenAIResponsesModelSettings(max_tokens=MAX_OUTPUT_TOKENS)
