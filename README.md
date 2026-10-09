# Campus Customs Multi-Agent Operations

An agent team that runs the Campus Customs shop's ticket board: customer orders, rent, unpaid bills, and discount requests. It has three pieces that talk to each other:

| Piece | Folder | What it does |
|---|---|---|
| **MCP server** | `mcp_server/` | FastMCP tools over the shop database. Every agent gets its facts here. |
| **Backend + agent team** | `backend/` | FastAPI routes plus five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Support) that delegate to each other. All of them run on `gpt-6-luna` through Portkey. |
| **Dashboard** | `frontend/` | React + Vite + TypeScript desk where a human sends tickets, watches the agents work, and approves or rejects payments. |

Agents can only **prepare** payments. Every payment needs a human to approve it on the dashboard, and the server refuses anything that would make cash go negative. Customer messages are saved as drafts and never sent.

## Setup

You need Python 3.11+ and Node 20+.

```bash
git clone https://github.com/lrochest/hw5.git
cd hw5

python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp .env.example .env          # then put your PORTKEY_API_KEY in .env

cd frontend && npm install && cd ..
```

`.env` is ignored by git. Never commit your real key.

## The databases

| File | Role |
|---|---|
| `data/campus_customs.db` | The original shop data. Never written to; it's the reset point. |
| `data/campus_customs_new.db` | The working copy. The MCP server, agents, and backend read and write only this file. |

The repo ships the working copy as it was after the final run (checking $160.00). **To get a clean run, copy the original over the working copy:**

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

If the backend is already running, use the dashboard's **Reset shop** button or `POST /api/reset` instead. They do the same thing safely: they stop any run, clear the queue, and restore the data with SQLite's backup API.

## Run it

Use three terminals from the `hw5/` folder.

**1. MCP server** (optional on its own; the backend starts its own copy automatically)

```bash
./.venv/bin/python mcp_server/server.py
```

Claude Code picks the server up from `.mcp.json` when opened in this folder.

**2. FastAPI backend** (http://localhost:8000)

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

**3. React board** (http://localhost:5173)

```bash
cd frontend
npm run dev
```

## A full three-ticket run

1. **Reset the database first.** Click **Reset shop** on the board (or copy the original DB as above). Checking goes back to $3,400.00.
2. Type your name in **Signing as**.
3. Pick ticket **101** and click **Send to the team**. Pick **102** and **103** and click **Add to the queue**. They run one at a time, in order.
4. Watch the agents on the floor. Each ticket gets a RESOLVED stamp and a payment tag when its run finishes.
5. Approve or reject what's under **Needs your signature**. Payments that can't go through yet (vendor blocked, or not enough cash) sit under **Can't be paid yet** with the reason.

Without the board, the same run works from the command line (it resets first):

```bash
./.venv/bin/python -m backend.runner --all
```

## Project layout

```
hw5/
├── AI_prompts.md            prompt log, Problems 2–10
├── requirements.txt
├── .env.example             copy to .env and add PORTKEY_API_KEY
├── .mcp.json                Claude Code connection to the MCP server
├── data/                    original DB + working copy
├── mcp_server/              server.py (19 tools), README.md
├── backend/
│   ├── main.py              FastAPI routes
│   ├── models.py            data types
│   ├── agents/              one file per agent + shared loop and delegation
│   ├── prompts/             boss.md, inventory.md, accounting.md, facilities.md, customer_service.md, shop_rules.md
│   ├── config.py, audit.py, runner.py
├── frontend/                React + Vite + TypeScript dashboard
└── output/
    ├── harness.md           tables, MCP tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json       MCP tool tests from Claude Code
    ├── desk_tickets.html    Expected vs Actual, Cash, Reflection
    ├── design.md            dashboard design choices
    ├── resolved_tickets.json
    ├── resolved_board.html  screenshots of the board for each resolved ticket
    ├── audit_trail.json     append-only log of every agent step and human decision
    └── github_url.txt
```

`output/harness.md` is the full reference for the tables, tools, agents, routes, and safety rules.
