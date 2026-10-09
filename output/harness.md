# Campus Customs Multi-Agent Operations — Harness

This is the reference for the Campus Customs agent system. It covers the databases and tables, the MCP tools, the five agents, the API routes, the dashboard, the safety rules, and the final run.

| Piece | Where | Start it |
|---|---|---|
| MCP server | `mcp_server/server.py` | Launched by the backend; Claude Code connects through `.mcp.json` |
| Backend + agent team | `backend/` | `cd backend && uvicorn main:app --reload --port 8000` |
| Dashboard | `frontend/` | `cd frontend && npm run dev` (http://localhost:5173) |

## Databases

| File | Role |
|---|---|
| `data/campus_customs.db` | Original. Never written to; it's the reset point. |
| `data/campus_customs_new.db` | Working copy. The MCP server and backend read and write this file. Before every full run, reset it (dashboard **Reset shop**, `POST /api/reset`, or `python -m backend.runner --reset`). The reset uses SQLite's backup API, so it waits for any write in progress instead of copying over it. |

---

## Tables

### `desk`
| Field | Type |
|---|---|
| `date_today` | TEXT, required |
| `notes` | TEXT |

**Why it matters:** `date_today` is the shop's "today" (`2026-08-31`). Agents use it, not the real clock, to decide what is overdue or due soon.

### `tickets`
| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `type` | TEXT, required (`customer_order`, `rent_notice`, `price_override`) |
| `requester` | TEXT, required |
| `subject` | TEXT, required |
| `sku` | TEXT |
| `size` | TEXT |
| `qty` | INTEGER |
| `lease_id` | INTEGER → `leases.id` |
| `invoice_id` | INTEGER → `invoices.id` |
| `status` | TEXT, required (`open`, …) |
| `notes` | TEXT |
| `created_at` | TEXT, required (ISO timestamp) |

**Why it matters:** This is the board. The boss reads each open ticket, uses `type` to decide which agent handles it, and the team closes the ticket by updating `status`.

### `inventory`
| Field | Type |
|---|---|
| `sku` | TEXT, required, part of primary key |
| `name` | TEXT, required |
| `size` | TEXT, required, part of primary key |
| `qty` | INTEGER, required |
| `location` | TEXT, required |

**Why it matters:** The inventory agent checks stock by `(sku, size)` to see whether an order can be filled from the shelf or has a shortfall.

### `pricing`
| Field | Type |
|---|---|
| `sku` | TEXT, primary key |
| `unit_cost` | REAL, required |
| `list_price` | REAL, required |

**Why it matters:** `list_price` is what discounts are measured against (at most 10% off), and `unit_cost` prices restock purchase orders.

### `vendors`
| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `name` | TEXT, required |
| `specialty` | TEXT, required |
| `lead_days` | INTEGER, required |

**Why it matters:** Inventory matches a SKU to a vendor through `specialty` (there's no SKU column), and `lead_days` says how long a restock takes.

### `invoices`
| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `vendor_id` | INTEGER, required → `vendors.id` |
| `amount` | REAL, required |
| `due_date` | TEXT, required |
| `status` | TEXT, required (`open`, …) |
| `description` | TEXT |

**Why it matters:** A vendor won't ship while it has an `open` invoice. Accounting compares `due_date` with `desk.date_today` to find overdue bills.

### `leases`
| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `space_name` | TEXT, required |
| `landlord` | TEXT, required |
| `monthly_rent` | REAL, required |
| `next_due` | TEXT, required |
| `notes` | TEXT |

**Why it matters:** Facilities uses this table for rent: how much (`monthly_rent`), when (`next_due`), and who it's owed to (`landlord`). After rent is paid, `next_due` moves forward.

### `cash_accounts`
| Field | Type |
|---|---|
| `name` | TEXT, primary key |
| `balance` | REAL, required |
| `date` | TEXT, required |

**Why it matters:** This is the only cash the shop has (`checking`, $3,400). The pay tool must refuse any payment that would push `balance` below zero, and cash only goes down.

### `payments`
| Field | Type |
|---|---|
| `id` | INTEGER, primary key |
| `kind` | TEXT, required (e.g. invoice, rent, purchase order) |
| `ref_id` | INTEGER (the invoice or lease being paid) |
| `amount` | REAL, required |
| `account` | TEXT, required → `cash_accounts.name` |
| `paid_at` | TEXT, required |
| `approved_by` | TEXT, required |

**Why it matters:** This is the audit trail. Every payment a human approves writes a row here, and `approved_by` proves the approval. It starts empty.

### Workflow tables (added to the working copy by the MCP server)

The original database has none of these. The server creates them in the working copy on first use, so a reset clears them too.

| Table | Fields | Why it matters |
|---|---|---|
| `payment_requests` | `id`, `ticket_id`, `kind` (invoice, rent, purchase_order), `ref_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `reason`, `requested_by`, `status` (pending, paid, rejected), `created_at`, `decided_by`, `decided_at`, `decision_note`, `payment_id` | Agents only ever *request* money here. A human's approval turns a row into a `payments` row; a rejection keeps the reason. |
| `drafts` | `id`, `ticket_id`, `recipient`, `subject`, `body`, `drafted_by`, `status` (always `draft`), `created_at` | Customer messages wait here for a human. Nothing is ever sent. |
| `ticket_updates` | `id`, `ticket_id`, `status`, `note`, `updated_by`, `created_at` | The Boss's status changes and why, without overwriting the original ticket notes. |

---

## Relationships

```
tickets.invoice_id ──► invoices.id ──► invoices.vendor_id ──► vendors.id
tickets.lease_id   ──► leases.id
tickets.(sku,size) ──► inventory.(sku,size)        (no declared FK)
tickets.sku        ──► pricing.sku                 (no declared FK)
payments.ref_id    ──► invoices.id or leases.id    (depends on payments.kind)
payments.account   ──► cash_accounts.name          (no declared FK)
```

---

## The three open tickets

Today is **2026-08-31**, and checking holds **$3,400**.

### Ticket 101 — `customer_order` from Tauhid Zaman
- **Asks for:** 1 × `CC-TEE-WHITE` (Classic Bulldog Tee), size **S**.
- **inventory:** `CC-TEE-WHITE / S` has **qty 0** (Aisle B), so it can't be filled from the shelf.
- **invoice_id 501:** Bulldog Print Co (vendor 1), $840, *"Rush reprint CC-TEE-WHITE S"*, due **2026-08-28**, status `open`. It's **3 days overdue**.
- **vendors:** Bulldog Print Co does apparel reprints with a **5-day** lead time. Because invoice 501 is unpaid, they won't ship the reprint until it's paid.
- **pricing:** unit cost $8.00, list price $28.00.
- **Agents involved:** inventory (shortfall), accounting (pay invoice 501, needs human approval), customer service (draft an ETA message to the customer).

### Ticket 102 — `rent_notice` from Elm City Properties
- **Asks for:** payment of shop rent, *"due in 2 days."*
- **lease_id 1:** Chapel Street shop, landlord Elm City Properties, **$2,400**, due **2026-09-02**.
- **Agents involved:** facilities (confirm the lease and amount), accounting (pay rent, needs human approval; then move `next_due` forward).

### Ticket 103 — `price_override` from Yale AI Club
- **Asks for:** 20 × `CC-HOOD-NAVY` (Basic Hoodie Big Yale), size **M**, at a bulk discount.
- **inventory:** `CC-HOOD-NAVY / M` has **qty 8**, a shortfall of **12** (other sizes: S 4, L 14, XL 6).
- **pricing:** list price $58.00, so the most the shop can offer is 10% off ($52.20). Unit cost $22.00 prices any restock.
- **vendors:** the restock comes from Bulldog Print Co (apparel, 5 days), which is blocked by the same open invoice 501.
- **Agents involved:** inventory (shortfall and vendor), accounting (discount check, purchase order), boss (approve or reject the discount), customer service (draft a reply).

### How the tickets compete for cash
| Item | Amount | Balance after |
|---|---|---|
| Start | — | $3,400 |
| Pay invoice 501 (unblocks Bulldog Print Co) | $840 | $2,560 |
| Pay rent, lease 1 | $2,400 | $160 |
| Restock 12 hoodies at cost (12 × $22) | $264 | **−$104, so the pay tool refuses** |

Invoice 501 sits behind both ticket 101 and ticket 103, and rent is the most urgent fixed cost. After both are paid, there isn't enough cash for a full hoodie restock, so the team will have to prioritize.

---

## MCP tools

Server: `mcp_server/server.py` (FastMCP, server name `campus-customs`). It reads `data/campus_customs_new.db`. Every agent shares these tools, and they never invent data: a missing row returns an `error`.

### `check_vendor_invoices(vendor_id)`
- **Reads:** `vendors`, `invoices`, `desk`
- **Unlocks ticket:** **101** (Tauhid's size S tee)
- **Why:** The tee is out of stock, and the only restock path is Bulldog Print Co. This tool shows that invoice 501 ($840) is 3 days overdue as of `desk.date_today` and that `can_ship` is false, which tells the team to pay that invoice before the tee can be reprinted.

### `get_rent_due(lease_id)`
- **Reads:** `leases`, `desk`
- **Unlocks ticket:** **102** (Elm City Properties rent notice)
- **Why:** The ticket's own text says "due in 2 days," but this tool checks it against lease 1 in the database ($2,400 to Elm City Properties, due 2026-09-02, 2 days from `desk.date_today`), so facilities and accounting act on the real amount and date instead of the email's claim.

### `check_stock(sku, size, qty_needed)`
- **Reads:** `inventory`
- **Unlocks ticket:** **103** (Yale AI Club, 20 hoodies in M)
- **Why:** The club's discount only matters if the shop can deliver. This tool shows 8 of the 20 `CC-HOOD-NAVY / M` on the shelf, a shortfall of 12, so the team knows to fill part of the order now and plan a restock before agreeing to a price.

---

## The five agents

Built with **PydanticAI**. Every agent uses **`gpt-6-luna`** through Portkey (`PORTKEY_API_KEY`, `https://api.portkey.ai/v1`), via the OpenAI **Responses** API. `gpt-6-luna` rejects function tools on `/chat/completions`, and no `temperature` is set. Shop facts come only from the `campus-customs` MCP server; there's no second data layer in the backend.

| Agent | File | Prompt | Returns | MCP tools it can use |
|---|---|---|---|---|
| **Boss** | `backend/agents/boss.py` | `backend/prompts/boss.md` | `BossDecision` | `list_open_tickets`, `get_ticket`, `get_cash_balance`, `list_payment_requests`, `check_discount`, `update_ticket_status` |
| **Inventory** | `backend/agents/inventory.py` | `backend/prompts/inventory.md` | `AgentReport` | `get_ticket`, `check_stock`, `list_stock`, `list_vendors`, `check_vendor_invoices`, `get_invoice` |
| **Accounting** | `backend/agents/accounting.py` | `backend/prompts/accounting.md` | `AgentReport` | `get_ticket`, `get_cash_balance`, `list_payment_requests`, `get_invoice`, `check_vendor_invoices`, `list_vendors`, `get_rent_due`, `check_discount`, `request_invoice_payment`, `request_rent_payment`, `request_purchase_order` |
| **Facilities** | `backend/agents/facilities.py` | `backend/prompts/facilities.md` | `AgentReport` | `get_ticket`, `get_rent_due`, `get_cash_balance`, `list_payment_requests` |
| **Customer Support** | `backend/agents/customer_support.py` | `backend/prompts/customer_service.md` | `AgentReport` | `get_ticket`, `check_stock`, `list_stock`, `draft_customer_message` |

`backend/prompts/shop_rules.md` holds the shop rules and is appended to every agent's prompt.

**Full connectivity:** every agent has a `delegate(to, task)` tool that can call any other agent. The child agent runs its own loop and returns its structured report as the tool result.

**Agent loop:** `backend/agents/base.py::run_agent` drives each agent with `agent.iter()`. It appends one audit event per loop step (prompt, model request, model response with tool calls, end) to `output/audit_trail.json`.

**Data types** (`backend/models.py`):
- `TeamDeps`: run id, ticket id, current agent, and delegation chain.
- `AgentReport`: a specialist's report.
- `BossDecision`: the final call on a ticket.
- `TicketRunResult`: the run outcome and token usage.

**Runner** (`backend/runner.py`):
- `--ticket N`: run one ticket.
- `--all`: reset the working copy, then run every open ticket in order.
- `--reset`: reset only.

---

## MCP tool catalog

Server: `mcp_server/server.py`, reading `data/campus_customs_new.db`. On connect, the server creates three workflow tables in the working copy: `payment_requests`, `drafts`, and `ticket_updates`. The original database never has them, so a reset clears them as well.

| # | Tool | Kind | Tables used | Who can call it |
|---|---|---|---|---|
| 1 | `list_open_tickets()` | read | `tickets`, `desk` | boss |
| 2 | `get_ticket(ticket_id)` | read | `tickets`, `ticket_updates`, `payment_requests`, `drafts`, `desk` | all agents |
| 3 | `check_stock(sku, size, qty_needed)` | read | `inventory` | inventory, customer_support |
| 4 | `list_stock(sku)` | read | `inventory` | inventory, customer_support |
| 5 | `list_vendors()` | read | `vendors`, `invoices` | inventory, accounting |
| 6 | `check_vendor_invoices(vendor_id)` | read | `vendors`, `invoices`, `desk` | inventory, accounting |
| 7 | `get_invoice(invoice_id)` | read | `invoices`, `vendors`, `desk` | inventory, accounting |
| 8 | `get_rent_due(lease_id)` | read | `leases`, `desk` | accounting, facilities |
| 9 | `get_cash_balance()` | read | `cash_accounts`, `payment_requests`, `desk` | boss, accounting, facilities |
| 10 | `check_discount(sku, qty, unit_price=None)` | read | `pricing` | boss, accounting |
| 11 | `list_payment_requests(status)` | read | `payment_requests` | boss, accounting, facilities |
| 12 | `request_invoice_payment(invoice_id, ticket_id, reason)` | write (pending only) | `invoices` → `payment_requests` | accounting |
| 13 | `request_rent_payment(lease_id, ticket_id, reason)` | write (pending only) | `leases` → `payment_requests` | accounting |
| 14 | `request_purchase_order(vendor_id, sku, size, qty, ticket_id, reason)` | write (pending only) | `vendors`, `inventory`, `pricing`, `invoices` → `payment_requests` | accounting |
| 15 | `draft_customer_message(ticket_id, recipient, subject, body)` | write (draft only) | `tickets` → `drafts` | customer_support |
| 16 | `update_ticket_status(ticket_id, status, note)` | write | `tickets`, `ticket_updates` | boss |
| 17 | `approve_payment(request_id, approved_by)` | **moves money** | `payment_requests`, `invoices`, `leases`, `vendors`, `cash_accounts`, `payments`, `desk` | **human only**, through the approve route |
| 18 | `reject_payment(request_id, rejected_by, reason)` | write | `payment_requests` | **human only**, through the reject route |
| 19 | `list_tickets()` | read | `tickets`, `desk` | backend only (dashboard ticket list) |

When `approve_payment` succeeds, it does all of the following in one transaction:
- adds a row to `payments`;
- lowers `cash_accounts.balance`;
- sets `invoices.status = 'paid'` (invoice payments) or moves `leases.next_due` forward one month (rent);
- marks the request `paid`.

Tools 3, 6, and 8 (`check_stock`, `check_vendor_invoices`, `get_rent_due`) are the Problem 3 tools and haven't changed. Tools 1, 2, 4, 5, 7, and 9–18 were added in Problem 5 so the agents can finish the open tickets. Tool 19 (`list_tickets`) was added in Problem 7 so the dashboard can list closed tickets too, through MCP like everything else.

---

## Safety

### Money
- **Agents can't move money.** `approve_payment` and `reject_payment` are filtered out of every agent's toolset in the backend. The only way to call them is when a human clicks Approve or Reject on the dashboard (`POST /api/payments/{id}/approve` or `/reject`). As a second line of defense, `approve_payment` refuses an approver whose name is one of the five agent names.
- **Amounts come from the database, not the model.** Invoice payments use `invoices.amount`, rent uses `leases.monthly_rent`, and purchase orders use `qty × pricing.unit_cost`. An agent can't type in a dollar figure.
- **No negative cash.** `approve_payment` refuses any payment larger than the account balance. `get_cash_balance` and every request report `available_after_pending`, so agents see over-commitment before a human does.
- **No paying twice.** A second request for an invoice that already has a pending or paid request is refused, as is a second pending rent request for the same lease. Approval re-checks that the invoice is still open.
- **Vendor block enforced in code.** A purchase order can't be approved while that vendor has an open invoice.
- **Held payments stay visible.** The dashboard shows payments the till would refuse under "Can't be paid yet", each with the reason (the vendor's unpaid invoice, or more than the balance). They are never auto-rejected, because a block can clear. A human clears them with one click, which records a rejection with the reason.
- **Refusals are audited too.** When the till refuses an approval (overdraft, blocked vendor, agent name), a `payment_refused` event goes into the audit trail with who tried and why.
- **Cash only goes out.** Prompts tell agents never to count sales or discounts as available cash.

### Customers and outside parties
- **Nothing is sent.** The only outbound tool is `draft_customer_message`, which saves a row with `status = 'draft'`. A human reviews and sends it.
- **No promises that haven't been confirmed.** Customer Support may only state availability, timing, and prices that were confirmed by a tool or decided by the boss. It never states a firm date while approvals are pending.
- **Discount policy:** the boss makes the final call on discounts of at most 10% off list, checked by `check_discount` (`within_policy`). Anything larger goes to a human. Agents talk about discounts only as a percent off list; they never report costs or margins.

### Data integrity and accountability
- **Never invent data.** Tools return `error` for missing rows instead of guessing, and prompts require every fact to come from a tool call in the same run.
- **Least privilege.** Each agent only sees the MCP tools its role needs (see the agent table). Only the boss changes ticket status.
- **Identity can't be spoofed.** `requested_by`, `drafted_by`, and `updated_by` are hidden from the model and filled in by the backend with the agent that's actually running.
- **Original data is protected.** The original `data/campus_customs.db` is never written to. The server opens the working copy in `mode=rw`, so it fails instead of silently creating an empty database. `--all` always resets before a full run.
- **Safe reset at any time.** Reset clears the queue, stops the team if it's working, and then restores the working copy with SQLite's backup API, which takes the database lock. A file copy made during a stopped run's last write once broke the working copy; the backup API prevents that. It was tested by resetting twice during a live run, and the database passed `PRAGMA integrity_check` both times.
- **A human can stop the team.** **Stop the team** cancels the current run immediately and records who stopped it. Anything already prepared (requests, drafts) stays pending for review.
- **Audit trail.** `output/audit_trail.json` is append-only and never wiped. It records every loop step, tool call with arguments, tool result, delegation, token count, reset, ticket outcome, and every human approval or rejection (who, which request, amount, balance after), with run id and ticket id. Reasoning text isn't logged, and long fields are clipped to 2,000 characters.
- **Secrets.** `PORTKEY_API_KEY` is read from the root `.env`, never printed or logged. `.gitignore` excludes `.env`, `.venv`, and the working database.

### Token and cost limits
- **One budget per ticket**, shared by the boss and every agent it delegates to: at most 40 model requests, 60 tool calls, and 250,000 tokens (`UsageLimits`). Going over stops the run and records the error in the audit trail.
- **At most 4,000 output tokens** per model response.
- **Delegation guard.** The chain can be at most 3 deep (boss → specialist → specialist). An agent can't delegate to itself or to anyone already waiting upstream, which prevents loops.
- **Tickets run one at a time** through a queue, so each run sees the cash and requests left by the one before. A human can send tickets at any time; they wait their turn, and can be taken out of the queue before they start.
- **Prompts tell agents to stay lean:** fetch each fact once, pass facts along when delegating, and keep reports short.
- **Smoke run (ticket 102):** 12 model requests, 14 tool calls, about 32k tokens, well under the budget.

---

## API routes

`backend/main.py` (FastAPI). Start from `backend/` with `uvicorn main:app --reload --port 8000`. Every route gets shop data through the `campus-customs` MCP server; the backend never opens the database itself, apart from the reset. CORS allows only the dashboard origin (`http://localhost:5173`).

- `GET /api/tickets`: every ticket with its status, its state (`open`, `queued`, `running`, or `resolved`), its queue position, and its latest run since the last reset, plus the running ticket and the queue.
- `GET /api/tickets/{id}`: one ticket with its status updates, payment requests, and drafts.
- `POST /api/tickets/{id}/run`: send a ticket to the team. It starts now if the team is idle; otherwise it joins the queue (`status: queued`, `position`).
- `POST /api/tickets/{id}/unqueue`: take a waiting ticket out of the queue before it starts.
- `POST /api/run/stop` `{stopped_by}`: stop the ticket the team is working on now; the queue carries on.
- `GET /api/events?limit=&ticket_id=&run_id=`: recent agent events from the audit trail (each message, tool call, tool result, handoff, report, and human decision), so the board can refresh.
- `GET /api/payments?status=pending`: payment and purchase-order requests the agents prepared, with each invoice's status and, for purchase orders, the vendor invoices blocking them.
- `POST /api/payments/{id}/approve` `{approved_by}`: a human approves. This is the only route that moves cash (it refuses agent names, overdrafts, and blocked vendors, and refusals are audited).
- `POST /api/payments/{id}/reject` `{rejected_by, reason}`: a human rejects or clears a payment; no money moves.
- `GET /api/cash`: current checking balance from `cash_accounts`, plus the pending total.
- `POST /api/reset` `{stopped_by}`: clear the queue, stop the team if it's working, and restore the working copy from the original.

---

## Dashboard

`frontend/` (React 19 + Vite + TypeScript), started with `npm run dev` on http://localhost:5173. It talks only to the backend at http://localhost:8000. The full design reasoning is in `output/design.md`.

| Area | What it shows | Routes |
|---|---|---|
| **Team strip** | Five agent nameplates, live: what each is doing, waiting on, done, or "Not called" | `/api/events` |
| **Ticket slips** (left) | Each ticket, its queue position or live status, a RESOLVED stamp, and a payment tag (Paid, Awaiting signature, Blocked · why, Partly paid, Cleared, No payment needed) that updates as payments change | `/api/tickets`, `/api/payments` |
| **The floor** (center) | The ticket, **Send to the team** / **Add to the queue** / **Stop the team**, then the live conversation: handoff cards, tool calls in plain words with their answers, and reports | `/run`, `/run/stop`, `/unqueue`, `/api/events` |
| **Shift report** | After a run: the live payment tag, the Boss's decision, what the Boss asked the human to do, one line per agent with the tools it used, who wasn't needed, unsent draft letters, and token use | `/api/events`, `/api/tickets/{id}` |
| **The till** (right) | Checking balance (rolls down when a payment clears), **Ready to sign** slips with Approve & pay $X / Reject (reason dropdown), **Can't be paid yet** with Clear, and a receipt tape | `/api/cash`, `/api/payments`, `/approve`, `/reject` |
| **Top bar** | Greeting, shop date (`desk.date_today`), the queue ("Up next"), Stop, and **Reset shop** | `/api/reset` |

A human must type a name in **Signing as** before anything can be approved, rejected, or cleared.

---

## Final run (Problem 9)

Reset on 2026-10-09 at 04:35 UTC, then tickets 101 → 102 → 103 through the queue. All three resolved with no errors. The human signed the payments on the dashboard.

| Ticket | Outcome | Money | Payment tag |
|---|---|---|---|
| 101 · Bulldog tee | Out of stock. Asked to pay invoice 501, the tee's reprint; no duplicate order. Draft to Tauhid. | −$840.00 (invoice 501, approved) | Paid |
| 102 · Rent due | Lease 1 confirmed; rent requested. | −$2,400.00 (rent, approved) | Paid |
| 103 · Bulk hoodie discount | 10% off ($52.20) on the 8 in stock. $264 order for 12 refused by the till (exceeds the $160 left) and cleared. Draft to Yale AI Club. | $0.00 | Cleared |

Checking went from **$3,400.00 to $160.00**, matching `cash_accounts` in the working copy. The details are in `output/desk_tickets.html` (Expected vs Actual and the Cash tab), `output/resolved_tickets.json`, `output/resolved_board.html` (dashboard screenshots), and `output/audit_trail.json`.
