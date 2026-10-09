# Campus Customs MCP Server

A [FastMCP](https://gofastmcp.com) server that gives the Campus Customs agent team (boss, inventory, accounting, facilities, customer support) shared tools for the shop database. Every agent gets its data through these tools instead of writing SQL. The tools only return what's in the database: if a row doesn't exist, they return an `error` instead of guessing, and dollar amounts always come from the database, never from the caller.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy that gets updated as tickets are resolved.
- **Never touches:** `data/campus_customs.db`, the original, kept as the reset point.

On connect, the server creates three workflow tables in the working copy if they're missing: `payment_requests`, `drafts`, and `ticket_updates`. The original has none of them, so a reset clears them too:

```bash
cp data/campus_customs.db data/campus_customs_new.db
# or: ./.venv/bin/python -m backend.runner --reset
```

"Today" for the shop is `desk.date_today`, not the real clock.

## Tools

### Read
| Tool | Reads | What it returns |
|---|---|---|
| `list_tickets()` | `tickets`, `desk` | Every ticket, open or closed, plus today's date (used by the dashboard) |
| `list_open_tickets()` | `tickets`, `desk` | Every ticket not resolved or declined, plus today's date |
| `get_ticket(ticket_id)` | `tickets`, `ticket_updates`, `payment_requests`, `drafts` | One ticket and everything done on it so far |
| `check_stock(sku, size, qty_needed=None)` | `inventory` | On-hand qty and location; with `qty_needed`, the shortfall and whether the shelf can fill the order |
| `list_stock(sku)` | `inventory` | Every size of a SKU |
| `list_vendors()` | `vendors`, `invoices` | Specialty, lead time, open invoices, `can_ship` |
| `check_vendor_invoices(vendor_id)` | `vendors`, `invoices`, `desk` | One vendor's open invoices with days overdue, and `can_ship` |
| `get_invoice(invoice_id)` | `invoices`, `vendors`, `desk` | One invoice with its vendor and days overdue |
| `get_rent_due(lease_id)` | `leases`, `desk` | Rent amount, landlord, next due date, days until due |
| `get_cash_balance()` | `cash_accounts`, `payment_requests` | Balance, pending total, `available_after_pending` |
| `check_discount(sku, qty, unit_price=None)` | `pricing` | Discount % off list and `within_policy` (at most 10% off list). Without a price, returns the list price and the 10%-off price |
| `list_payment_requests(status=None)` | `payment_requests`, `invoices`, `vendors` | Pending, paid, and rejected requests; invoice payments include the invoice's status, and purchase orders list the vendor invoices blocking them |

### Agent writes (nothing leaves the shop, no money moves)
| Tool | Writes | Notes |
|---|---|---|
| `request_invoice_payment(invoice_id, ticket_id, reason, requested_by)` | `payment_requests` | Amount from `invoices`; refuses non-open invoices and duplicates |
| `request_rent_payment(lease_id, ticket_id, reason, requested_by)` | `payment_requests` | Amount from `leases.monthly_rent`; refuses duplicate pending requests |
| `request_purchase_order(vendor_id, sku, size, qty, ticket_id, reason, requested_by)` | `payment_requests` | Amount = qty × `pricing.unit_cost`; reports blocking invoices |
| `draft_customer_message(ticket_id, recipient, subject, body, drafted_by)` | `drafts` | Saved with status `draft`; never sent |
| `update_ticket_status(ticket_id, status, note, updated_by)` | `tickets`, `ticket_updates` | Keeps the original ticket notes |

### Human only (the backend never gives these to an agent; only the dashboard's Approve and Reject routes call them)
| Tool | Writes | Notes |
|---|---|---|
| `approve_payment(request_id, approved_by)` | `payments`, `cash_accounts`, `invoices` or `leases`, `payment_requests` | Refuses agent names as approver, refuses a payment larger than the cash balance, and refuses purchase orders while the vendor has an open invoice |
| `reject_payment(request_id, rejected_by, reason)` | `payment_requests` | No money moves |

The backend fills in the `requested_by`, `drafted_by`, and `updated_by` arguments with whichever agent is actually running; the model never sees them.

## Run

```bash
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python mcp_server/server.py
```

Claude Code connects through `.mcp.json` at the project root.
