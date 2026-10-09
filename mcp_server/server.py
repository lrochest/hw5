"""Campus Customs MCP server.

Shared toolbox for every agent on the team. All tools read and write the working
copy data/campus_customs_new.db; the original data/campus_customs.db is never touched.
Tools only return what is in the database. If a row is missing they say so
instead of guessing, and money amounts always come from the database, never
from the caller.

Agent tools can read, prepare payment requests, draft messages, and update
tickets. Moving money is human-only: approve_payment and reject_payment are
filtered out of every agent's toolset by the backend, and approve_payment also
refuses any approver that is an agent name.
"""

import calendar
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "campus_customs_new.db"

AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_support"}
TICKET_STATUSES = ("open", "in_progress", "waiting_on_approval", "waiting_on_vendor", "resolved", "declined")

# Shop discount policy for price overrides (documented in output/harness.md)
MAX_DISCOUNT_PCT = 10.0

mcp = FastMCP("campus-customs")

# Tables the agent workflow adds to the working copy. The original DB has none of
# these, so a reset (copying the original over the working copy) clears them too.
WORKFLOW_SCHEMA = """
CREATE TABLE IF NOT EXISTS payment_requests (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER,
    kind TEXT NOT NULL,              -- invoice | rent | purchase_order
    ref_id INTEGER,                  -- invoices.id or leases.id (NULL for purchase_order)
    vendor_id INTEGER,
    sku TEXT,
    size TEXT,
    qty INTEGER,
    amount REAL NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- pending | paid | rejected
    created_at TEXT NOT NULL,
    decided_by TEXT,
    decided_at TEXT,
    decision_note TEXT,
    payment_id INTEGER
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    drafted_by TEXT NOT NULL,
    status TEXT NOT NULL,            -- always 'draft': nothing is ever sent
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ticket_updates (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    note TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def connect() -> sqlite3.Connection:
    # mode=rw: fail loudly if the working copy is missing instead of creating an empty DB
    # timeout: wait for a reset or another write to finish instead of failing
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=rw", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(WORKFLOW_SCHEMA)
    return conn


def shop_today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_one_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def open_invoices_for(conn: sqlite3.Connection, vendor_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, amount, due_date, status, description FROM invoices "
        "WHERE vendor_id = ? AND status = 'open' ORDER BY due_date",
        (vendor_id,),
    ).fetchall()


def cash_snapshot(conn: sqlite3.Connection) -> dict:
    accounts = [dict(r) for r in conn.execute("SELECT name, balance, date FROM cash_accounts")]
    balance = sum(a["balance"] for a in accounts)
    pending = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS n FROM payment_requests WHERE status = 'pending'"
    ).fetchone()
    return {
        "accounts": accounts,
        "total_balance": balance,
        "pending_requests": pending["n"],
        "pending_total": pending["total"],
        "available_after_pending": balance - pending["total"],
    }


def find_request(conn: sqlite3.Connection, kind: str, ref_id: int | None, statuses: tuple[str, ...]) -> sqlite3.Row | None:
    marks = ",".join("?" * len(statuses))
    return conn.execute(
        f"SELECT * FROM payment_requests WHERE kind = ? AND ref_id IS ? AND status IN ({marks})",
        (kind, ref_id, *statuses),
    ).fetchone()


def insert_request(conn: sqlite3.Connection, **fields) -> dict:
    fields.update(status="pending", created_at=now_utc())
    cols = ", ".join(fields)
    cur = conn.execute(
        f"INSERT INTO payment_requests ({cols}) VALUES ({', '.join('?' * len(fields))})",
        tuple(fields.values()),
    )
    row = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (cur.lastrowid,)).fetchone()
    cash = cash_snapshot(conn)
    return {
        "payment_request": dict(row),
        "cash": cash,
        "fits_in_cash_after_pending": cash["available_after_pending"] >= 0,
        "note": "Pending human approval. No money has moved.",
    }


# ---------------------------------------------------------------------------
# Read tools
# ---------------------------------------------------------------------------


@mcp.tool
def list_tickets() -> dict:
    """List every ticket on the board, open or closed, plus the shop's today date."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY created_at").fetchall()
        return {"today": shop_today(conn).isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket on the board that is not resolved or declined, plus the shop's today date."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status NOT IN ('resolved', 'declined') ORDER BY created_at"
        ).fetchall()
        return {"today": shop_today(conn).isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with everything the team has done on it so far:
    status updates, payment requests, and customer message drafts."""
    with connect() as conn:
        ticket = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if ticket is None:
            return {"error": f"No ticket with id={ticket_id}."}
        return {
            "today": shop_today(conn).isoformat(),
            "ticket": dict(ticket),
            "updates": [dict(r) for r in conn.execute(
                "SELECT * FROM ticket_updates WHERE ticket_id = ? ORDER BY id", (ticket_id,))],
            "payment_requests": [dict(r) for r in conn.execute(
                "SELECT * FROM payment_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,))],
            "drafts": [dict(r) for r in conn.execute(
                "SELECT * FROM drafts WHERE ticket_id = ? ORDER BY id", (ticket_id,))],
        }


@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int | None = None) -> dict:
    """Look up on-hand stock for one SKU and size in the inventory table.

    Pass qty_needed to get the shortfall (how many units are missing).
    """
    with connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            return {"error": f"No inventory row for sku={sku!r}, size={size!r}."}

        result = dict(row)
        if qty_needed is not None:
            result["qty_needed"] = qty_needed
            result["shortfall"] = max(qty_needed - row["qty"], 0)
            result["can_fill_from_shelf"] = row["qty"] >= qty_needed
        return result


@mcp.tool
def list_stock(sku: str) -> dict:
    """List on-hand stock for every size of one SKU (useful for offering another size)."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? ORDER BY rowid", (sku,)
        ).fetchall()
        if not rows:
            return {"error": f"No inventory rows for sku={sku!r}."}
        return {"sku": sku, "name": rows[0]["name"], "sizes": [dict(r) for r in rows],
                "total_qty": sum(r["qty"] for r in rows)}


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty, lead time, open invoice total, and whether it can ship.

    The vendors table has no SKU column: match a product to a vendor by specialty.
    """
    with connect() as conn:
        vendors = []
        for v in conn.execute("SELECT id, name, specialty, lead_days FROM vendors ORDER BY id"):
            open_inv = open_invoices_for(conn, v["id"])
            vendors.append({**dict(v), "open_invoice_ids": [i["id"] for i in open_inv],
                            "open_total": sum(i["amount"] for i in open_inv), "can_ship": not open_inv})
        return {"vendors": vendors}


@mcp.tool
def check_vendor_invoices(vendor_id: int) -> dict:
    """Show a vendor's lead time and every open invoice they have, with days overdue.

    A vendor will not ship new product while any invoice is still open, so
    can_ship is False whenever open_invoices is not empty. "Overdue" is measured
    against desk.date_today, not the real clock.
    """
    with connect() as conn:
        vendor = conn.execute(
            "SELECT id, name, specialty, lead_days FROM vendors WHERE id = ?",
            (vendor_id,),
        ).fetchone()
        if vendor is None:
            return {"error": f"No vendor with id={vendor_id}."}

        today = shop_today(conn)
        open_invoices = []
        for inv in open_invoices_for(conn, vendor_id):
            days_overdue = (today - date.fromisoformat(inv["due_date"])).days
            open_invoices.append({**dict(inv), "days_overdue": max(days_overdue, 0)})

        return {
            "vendor": dict(vendor),
            "today": today.isoformat(),
            "open_invoices": open_invoices,
            "open_total": sum(inv["amount"] for inv in open_invoices),
            "can_ship": not open_invoices,
        }


@mcp.tool
def get_invoice(invoice_id: int) -> dict:
    """Get one invoice with its vendor and how many days overdue it is (from desk.date_today)."""
    with connect() as conn:
        inv = conn.execute(
            "SELECT i.*, v.name AS vendor_name, v.specialty AS vendor_specialty, v.lead_days AS vendor_lead_days "
            "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (invoice_id,),
        ).fetchone()
        if inv is None:
            return {"error": f"No invoice with id={invoice_id}."}
        today = shop_today(conn)
        days_past_due = (today - date.fromisoformat(inv["due_date"])).days
        return {**dict(inv), "today": today.isoformat(),
                "days_overdue": max(days_past_due, 0) if inv["status"] == "open" else 0,
                "overdue": inv["status"] == "open" and days_past_due > 0}


@mcp.tool
def get_rent_due(lease_id: int) -> dict:
    """Show a lease's rent amount, landlord, next due date, and days until it is due.

    days_until_due is measured from desk.date_today; a negative number means overdue.
    """
    with connect() as conn:
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"error": f"No lease with id={lease_id}."}

        today = shop_today(conn)
        days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
        return {
            **dict(lease),
            "today": today.isoformat(),
            "days_until_due": days_until_due,
            "overdue": days_until_due < 0,
        }


@mcp.tool
def get_cash_balance() -> dict:
    """Show cash on hand, the total of payment requests still waiting for approval,
    and what would be left if every pending request were approved."""
    with connect() as conn:
        return {"today": shop_today(conn).isoformat(), **cash_snapshot(conn)}


@mcp.tool
def check_discount(sku: str, qty: int, unit_price: float | None = None) -> dict:
    """Check a sale price against the shop discount policy: at most 10% off list price.

    Leave unit_price out to get the list price and the best price the shop can offer (10% off),
    which is then checked as the proposed price."""
    with connect() as conn:
        p = conn.execute("SELECT sku, list_price FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if p is None:
            return {"error": f"No pricing row for sku={sku!r}."}
        if unit_price is None:
            unit_price = round(p["list_price"] * (1 - MAX_DISCOUNT_PCT / 100), 2)
        if unit_price <= 0 or qty <= 0:
            return {"error": "unit_price and qty must be positive."}

        lowest = round(p["list_price"] * (1 - MAX_DISCOUNT_PCT / 100), 2)
        return {
            **dict(p),
            "unit_price": unit_price,
            "qty": qty,
            "discount_pct": round((p["list_price"] - unit_price) / p["list_price"] * 100, 2),
            "total_price": round(unit_price * qty, 2),
            "policy": {"max_discount_pct": MAX_DISCOUNT_PCT, "lowest_allowed_unit_price": lowest},
            # Compare in cents so exactly 10% off (e.g. 25.20 on a 28.00 tee) isn't lost to float rounding
            "within_policy": round(unit_price, 2) >= lowest,
        }


@mcp.tool
def list_payment_requests(status: Literal["pending", "paid", "rejected"] | None = None) -> dict:
    """List payment requests (optionally only one status) so nobody requests the same payment twice.
    Each purchase order also lists the vendor's open invoices that would block it (blocked_by_invoices)."""
    with connect() as conn:
        if status:
            rows = conn.execute("SELECT * FROM payment_requests WHERE status = ? ORDER BY id", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM payment_requests ORDER BY id").fetchall()
        out = []
        for r in rows:
            req = dict(r)
            if req["kind"] == "purchase_order" and req["vendor_id"] is not None:
                vendor = conn.execute("SELECT name FROM vendors WHERE id = ?", (req["vendor_id"],)).fetchone()
                req["vendor_name"] = vendor["name"] if vendor else None
                req["blocked_by_invoices"] = [dict(i) for i in open_invoices_for(conn, req["vendor_id"])]
            elif req["kind"] == "invoice" and req["ref_id"] is not None:
                inv = conn.execute(
                    "SELECT i.id, i.amount, i.due_date, i.status, i.description, v.name AS vendor_name "
                    "FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?", (req["ref_id"],)).fetchone()
                if inv:
                    days = (shop_today(conn) - date.fromisoformat(inv["due_date"])).days
                    req["invoice"] = {**dict(inv), "days_overdue": max(days, 0) if inv["status"] == "open" else 0}
            out.append(req)
        return {"payment_requests": out}


# ---------------------------------------------------------------------------
# Agent write tools (prepare work; never move money, never contact anyone)
# ---------------------------------------------------------------------------


@mcp.tool
def request_invoice_payment(invoice_id: int, ticket_id: int, reason: str, requested_by: str) -> dict:
    """Queue payment of an open vendor invoice for human approval. The amount comes from the invoice.
    No money moves until a human approves it."""
    with connect() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if inv is None:
            return {"error": f"No invoice with id={invoice_id}."}
        if inv["status"] != "open":
            return {"error": f"Invoice {invoice_id} is {inv['status']!r}, not open. Nothing to pay."}
        if dup := find_request(conn, "invoice", invoice_id, ("pending", "paid")):
            return {"error": f"Invoice {invoice_id} already has payment request {dup['id']} ({dup['status']})."}
        return insert_request(conn, ticket_id=ticket_id, kind="invoice", ref_id=invoice_id,
                              vendor_id=inv["vendor_id"], amount=inv["amount"], reason=reason,
                              requested_by=requested_by)


@mcp.tool
def request_rent_payment(lease_id: int, ticket_id: int, reason: str, requested_by: str) -> dict:
    """Queue this month's rent for a lease for human approval. The amount is the lease's monthly_rent.
    No money moves until a human approves it."""
    with connect() as conn:
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            return {"error": f"No lease with id={lease_id}."}
        if dup := find_request(conn, "rent", lease_id, ("pending",)):
            return {"error": f"Lease {lease_id} rent already has pending payment request {dup['id']}."}
        return insert_request(conn, ticket_id=ticket_id, kind="rent", ref_id=lease_id, amount=lease["monthly_rent"],
                              reason=f"Rent due {lease['next_due']}. {reason}", requested_by=requested_by)


@mcp.tool
def request_purchase_order(vendor_id: int, sku: str, size: str, qty: int, ticket_id: int,
                           reason: str, requested_by: str) -> dict:
    """Queue a restock purchase order for human approval. Amount = qty x pricing.unit_cost.
    The vendor will not ship while it has an open invoice, so approval is refused until that is paid."""
    with connect() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"error": f"No vendor with id={vendor_id}."}
        if conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone() is None:
            return {"error": f"No inventory row for sku={sku!r}, size={size!r}."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"error": f"No pricing row for sku={sku!r}; cannot cost the order."}
        if qty <= 0:
            return {"error": "qty must be positive."}

        result = insert_request(conn, ticket_id=ticket_id, kind="purchase_order", ref_id=None, vendor_id=vendor_id,
                                sku=sku, size=size, qty=qty, amount=round(qty * price["unit_cost"], 2),
                                reason=reason, requested_by=requested_by)
        blocking = open_invoices_for(conn, vendor_id)
        result["vendor_lead_days"] = vendor["lead_days"]
        result["blocked_by_open_invoices"] = [i["id"] for i in blocking]
        if blocking:
            result["note"] += f" {vendor['name']} will not ship until invoice(s) {[i['id'] for i in blocking]} are paid."
        return result


@mcp.tool
def draft_customer_message(ticket_id: int, recipient: str, subject: str, body: str, drafted_by: str) -> dict:
    """Save a message draft on the board for a human to review. It is never sent."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id={ticket_id}."}
        cur = conn.execute(
            "INSERT INTO drafts (ticket_id, recipient, subject, body, drafted_by, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, 'draft', ?)",
            (ticket_id, recipient, subject, body, drafted_by, now_utc()),
        )
        row = conn.execute("SELECT * FROM drafts WHERE id = ?", (cur.lastrowid,)).fetchone()
        return {"draft": dict(row), "note": "Saved as a draft on the board. Nothing was sent."}


@mcp.tool
def update_ticket_status(ticket_id: int, status: Literal[TICKET_STATUSES], note: str, updated_by: str) -> dict:
    """Set a ticket's status and record why. The original ticket notes are kept; the note goes in ticket_updates."""
    with connect() as conn:
        if conn.execute("SELECT 1 FROM tickets WHERE id = ?", (ticket_id,)).fetchone() is None:
            return {"error": f"No ticket with id={ticket_id}."}
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        conn.execute(
            "INSERT INTO ticket_updates (ticket_id, status, note, updated_by, created_at) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, status, note, updated_by, now_utc()),
        )
        return {"ticket": dict(conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone())}


# ---------------------------------------------------------------------------
# Human-only tools (never exposed to agents)
# ---------------------------------------------------------------------------


@mcp.tool
def approve_payment(request_id: int, approved_by: str) -> dict:
    """HUMAN ONLY. Pay an approved request: refuses if cash would go negative or the vendor is blocked.
    On success writes payments, lowers cash_accounts, and marks the invoice paid or moves the lease's next_due."""
    if not approved_by.strip() or approved_by.strip().lower() in AGENT_NAMES:
        return {"error": "approve_payment requires a human approver name, not an agent."}

    with connect() as conn:
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"No payment request with id={request_id}."}
        if req["status"] != "pending":
            return {"error": f"Payment request {request_id} is {req['status']!r}, not pending."}

        today = shop_today(conn)
        amount = req["amount"]
        if req["kind"] == "invoice":
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
            if inv is None or inv["status"] != "open":
                return {"error": f"Invoice {req['ref_id']} is no longer open; refusing to pay twice."}
            amount = inv["amount"]
        elif req["kind"] == "rent":
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
            if lease is None:
                return {"error": f"Lease {req['ref_id']} not found."}
            amount = lease["monthly_rent"]
        elif req["kind"] == "purchase_order":
            if blocking := open_invoices_for(conn, req["vendor_id"]):
                return {"error": f"Vendor {req['vendor_id']} has open invoice(s) {[i['id'] for i in blocking]}; "
                                 "it will not ship until they are paid."}

        account = conn.execute("SELECT * FROM cash_accounts ORDER BY balance DESC LIMIT 1").fetchone()
        if account is None or account["balance"] < amount:
            have = account["balance"] if account else 0
            return {"error": f"Refused: ${amount:,.2f} exceeds the ${have:,.2f} in checking. "
                             "No negative balances allowed."}

        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (req["kind"], req["ref_id"] if req["kind"] != "purchase_order" else request_id,
             amount, account["name"], today.isoformat(), approved_by.strip()),
        )
        conn.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                     (amount, today.isoformat(), account["name"]))

        note = None
        if req["kind"] == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
        elif req["kind"] == "rent":
            new_due = add_one_month(date.fromisoformat(lease["next_due"])).isoformat()
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (new_due, req["ref_id"]))
            note = f"Lease next_due moved to {new_due}."
        else:
            lead = conn.execute("SELECT lead_days FROM vendors WHERE id = ?", (req["vendor_id"],)).fetchone()
            note = f"Order placed; expected in {lead['lead_days']} days. Inventory updates when stock arrives."

        conn.execute(
            "UPDATE payment_requests SET status = 'paid', decided_by = ?, decided_at = ?, decision_note = ?, "
            "payment_id = ? WHERE id = ?",
            (approved_by.strip(), now_utc(), note, cur.lastrowid, request_id),
        )
        return {
            "payment": dict(conn.execute("SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)).fetchone()),
            "payment_request": dict(conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()),
            "cash": cash_snapshot(conn),
            "note": note,
        }


@mcp.tool
def reject_payment(request_id: int, rejected_by: str, reason: str) -> dict:
    """HUMAN ONLY. Reject a pending payment request. No money moves."""
    with connect() as conn:
        req = conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"error": f"No payment request with id={request_id}."}
        if req["status"] != "pending":
            return {"error": f"Payment request {request_id} is {req['status']!r}, not pending."}
        conn.execute(
            "UPDATE payment_requests SET status = 'rejected', decided_by = ?, decided_at = ?, decision_note = ? "
            "WHERE id = ?",
            (rejected_by, now_utc(), reason, request_id),
        )
        return {"payment_request": dict(conn.execute("SELECT * FROM payment_requests WHERE id = ?", (request_id,)).fetchone())}


if __name__ == "__main__":
    mcp.run(show_banner=False)
