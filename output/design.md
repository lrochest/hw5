# The Desk: Campus Customs agent dashboard design

The dashboard (`frontend/`, React + Vite + TypeScript) is the human's seat at the shop. The agents prepare the work, and the person at the desk watches it happen and signs for anything that costs money. The design is built around that one relationship: **agents do the legwork, a human holds the pen.**

Start it with `npm run dev` from `frontend/`. It opens at `http://localhost:5173` and talks to the FastAPI backend at `http://localhost:8000`. The backend's CORS only allows the Vite origin (`localhost:5173` / `127.0.0.1:5173`).

## The concept: a real shop desk, not an admin panel

Campus Customs is a Yale apparel shop on Chapel Street, so the board borrows from a physical counter. It has paper tickets on a rail, a team you can see working, and a till with a receipt tape. The palette is warm paper (`#f5f0e6`) with **Yale blue** (`#00356b`) for the shop's own voice and **brass** for money. The type is set to match:
- A serif face (Iowan Old Style, Palatino, Georgia) for the shop's voice: headings, what agents say, letters.
- A clean sans for the work itself.
- Monospace for every dollar figure and SKU.

Everyone reads money the same way, so amounts line up and never look like prose.

## Layout

Three columns under a sticky team strip, ordered the way the eye moves through a shift:

| Area | What it is | Why it's there |
|---|---|---|
| **Top bar** | Shop seal, greeting with your name, the shop's date (`desk.date_today`), and **Reset shop** | Shows that the shop runs on its own date, not today's, and keeps reset out of the way so it isn't clicked by accident (it asks to confirm) |
| **Team strip** | Five nameplates, one per agent | You see who is working before you read anything else |
| **Left: ticket rail** | Tickets as paper slips with a perforated edge, and a progress bar of how many are resolved | Picking a ticket feels like pulling a slip off the rail |
| **Center: the floor** | The selected ticket, its **Send to the team** button, the **shift report** after a run, then the live **floor** feed | Where the work happens, so it gets the most space |
| **Right: the till** | Checking balance, payments waiting for your signature, and the receipt tape | Money stays in one place, always visible, and never mixed in with agent chatter |

On narrower screens the till drops below the floor, and the team strip wraps to three columns, then two.

## How each agent reads differently

Each agent has a **color, a mark, and a voice**, so you can follow a conversation without reading names:

| Agent | Color | Mark | Why |
|---|---|---|---|
| Boss | Yale blue | Star | The shop's own color; the one who makes the call |
| Inventory | Pine green | Box | Stock on the shelf |
| Accounting | Brass gold | Ledger | The same brass as the money in the till |
| Facilities | Brick red | Key | The building and the lease |
| Customer Support | Violet | Speech bubble | The only voice that talks to customers |

On the floor:
- **Tool calls read as people working, not function calls.** `check_stock` is shown as "Checking the shelf · sku CC-TEE-WHITE · size S", and the answer appears underneath in plain words ("0 on hand in Aisle B · 1 short"). The raw tool name sits small and grey at the right for anyone auditing, and the full JSON is one click away.
- **Writes look different from reads.** Tools that change something (payment requests, drafts, status updates) get a ✎ so you can spot them in a long run.
- **Handoffs are cards:** "Boss → Facilities", with the exact task quoted in that agent's color.
- **Indentation shows who is working for whom.** Work done on someone else's behalf is indented, with a thin rule in that agent's color, so a chain like Boss → Facilities → Accounting reads like a nested conversation. When the boss sends two agents off at once, their work stays visually separate.
- **Reports are speech bubbles** in the agent's color and the serif voice. The boss's final call is a solid Yale-blue bubble: it's the verdict.
- **Nameplates are live.** The agent working right now gets a pulsing ring and says what it is doing ("Checking the lease…"). Agents waiting on a teammate say "Waiting on Accounting". Finished agents show "✓ Reported back". Agents never called on this ticket fade to "Not called", which makes it easy to compare the run against the plan in `desk_tickets.html`.

## Resolved tickets

- **A rubber stamp.** When the team finishes a run, the slip gets a green **RESOLVED** stamp that thumps on (scales down with a slight rotation).
- **A payment tag** under the stamp says where the ticket's money stands. It's worked out live from the ticket's payment requests, so it changes the moment you sign or clear something. A resolved ticket can still need a human, and the desk never hides that.

  | Tag | When |
  |---|---|
  | **Paid** (green) | Every payment for the ticket was approved |
  | **Awaiting signature** (brass) | Something is ready to sign ("· 1 blocked" if another payment is held) |
  | **Blocked · invoice 501 unpaid** / **Blocked · not enough cash** (red) | Its waiting payment can't go through yet, and why |
  | **Partly paid** | Some approved, some cleared |
  | **Cleared** (grey) | Every payment was rejected or cleared |
  | **No payment needed** | The team didn't ask for money |

  The Boss's other outcomes, like "Waiting on the vendor", appear beside the tag. "Waiting on your approval" is left out because the tag already says it, and keeps saying it accurately after you sign.
- **The rail's progress bar** fills as tickets resolve ("1/3 resolved").
- **A shift report** appears above the floor:
  - the boss's decision as a pull quote;
  - a yellow **Needs you** box listing exactly what to approve or send;
  - one tinted row per agent: what they did, any blockers, and chips for the tools they used (e.g. "Checking the shelf ×3");
  - a line naming the agents who weren't needed;
  - the run's model calls, tool calls, and tokens, kept small, for anyone watching cost.
- **Drafts look like letters**, on lined paper with a violet "Draft #1 · not sent" flag and "Drafted by Customer Support for a human to send". That makes it obvious nothing went out.
- **A toast** says "Ticket 101 resolved by the team" when a run ends, even if you're looking at another ticket.

## Cash

- **The register** is a dark card holding a large monospace balance. It **rolls** to its new value when a payment clears, and glows red for a moment, so a payment is something you watch happen. It also shows what is waiting for approval and what would be left if everything were approved. That figure turns red if it would go negative, and a brass bar shows how much of the balance is already spoken for.
- **"Cash only goes out. Nothing leaves without a human signature."** sits under the balance, the shop's two money rules in one line.
- **Approvals are vouchers**, each with:
  - the kind (vendor invoice, rent, purchase order), the amount, and the ticket;
  - the agent's one-line reason;
  - which agent prepared it, with its mark.

  You type your name once in **Signing as** (it's remembered), and the button reads "Approve & pay $840.00". The actual dollar amount is on the button so nobody approves blind. Invoice payments also show the invoice's own status ("Invoice 501 · Bulldog Print Co · unpaid · due 2026-08-28 · 3 days overdue"). Reject asks for a reason from a dropdown (Other opens a text box), and no money moves.
- **"Can't be paid yet."** Payments the till would refuse sit in their own dashed section below the ready ones, each with a ⚠ line saying why: the vendor won't ship while an invoice is unpaid, or the payment exceeds the balance. **Clear from the desk** rejects one with that reason in a single click, and **Try to pay anyway** is still there to see the till refuse it. The section is recalculated live, so paying the blocking invoice moves an order up to the ready list by itself.
- **The receipt tape** (monospace on a torn-edge strip) lists every payment signed or voided, and who signed it. It doubles as the human side of the audit trail.

## Small things that make it pleasant to sit at

- It greets you by the name you sign with, and uses the shop's date, not the computer's.
- "The floor is quiet" when nothing has run yet, which invites the first click instead of showing an empty table.
- A typing indicator (three dots) shows while agents are thinking, and the floor scrolls itself during a live run.
- Every animation is short (≤ 0.9 s) and switched off for people who set "reduce motion".
- Polling is calm when idle (every 4 s) and quick while a run is live (about every 1.2 s), so the board feels live without hammering the backend.

## Honesty rules the design follows

- **Only real data.** Every number on screen comes from a backend route, which gets it from the MCP server and `data/campus_customs_new.db`. The floor and shift report come from `output/audit_trail.json`. The UI never makes up a status, amount, or date.
- **After a reset, the desk shows a clean shop.** Old runs stay in the audit trail but leave the screen.
- **Only one run at a time.** Run and Reset are disabled while the team is working, matching the backend's 409 guard.

## Route map

| UI piece | Backend route |
|---|---|
| Ticket rail, run state, last run | `GET /api/tickets` |
| Send to the team | `POST /api/tickets/{id}/run` |
| Floor, team strip, shift report | `GET /api/events?ticket_id=` |
| Drafts, ticket details | `GET /api/tickets/{id}` |
| Vouchers and receipt tape | `GET /api/payments?status=pending` and `GET /api/payments?status=` |
| Approve & pay / Reject | `POST /api/payments/{id}/approve` and `/reject` |
| Register | `GET /api/cash` |
| Reset shop | `POST /api/reset` |
