# AI Prompts Log

Log of the prompts typed to the AI assistant for each problem (Problems 2–10).

---

## Problem 2: Study the Campus Customs database

**Prompt:**

> Open data/campus_customs.db and look through eveyr table and its fields. copy the original file to data/campus_customs_new.db
> later problems will update the working copy
>
> study the three open tickets to see how they link other tables
> start output/harness.md
> for each table, list the fields and one short line on why that table matters for the agents
> we will keep growing this harness file in later problems

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---

## Problem 3: Build the MCP server

**Prompt:**

> write an MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db we do not need to connect or run it in this problem every agent in this homework uses the tools in this MCP server. we will add more tools to it later, for now write the following three read-only tools, one for each open ticket, keep the names clear., never invent any data, only use information in the database:,if a row is missing, return an error instead of guessing:
> -check_vendor_invoices(vendor_id) reads vendors, invoices, and desk. return the vendor's lead time, every open invoice with days overdue measured from desk.date_today, and can_ship (false when any invoice is open). this helps resolve ticket 101
>
> -get_rent_due(lease_id) reads leases and desk. return the rent amount, landlord, next due date, and days until due from desk.date_today. this helps resolve ticket 102
>
> -check_stock(sku, size, qty_needed) reads inventory. return the on-hand qty and location, and when qty_needed is given, the shortfall and whether the shelf can fill the order. this helps resolve ticket 103
>
> In output/harness.md list each of the three MCP tools. For eveyr tool include: which tagble it reads, which ticket it helps unlock (101, 102, or 103) and one stennce on why that tool is the right one for thiat ticket
> we need to tie the tool to the ticket
>
> also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---

## Problem 4: Add the MCP server to vibe coder and test each tool

**Prompt:**

> lets add the MCP server to this project so that you (claude code) can call the tools. save the conenction JSON text in .mcp.json at the project root
>
> test each of the three mcp tools. save the evidence in  output/mcp_smoke.json
>
> For every tool include
> -the prompt I asked you
> -the tool name
> -the tool output (must match values in data/campus_customs_new.db)
>
> use these prompts, one for each tool:
>
> -Use the campus-customs MCP server to call check_vendor_invoices for vendor 1. Show me the raw tool output.
>
> -Use the campus-customs MCP server to call get_rent_due for lease 1. Show me the raw tool output.
>
> -Use the campus-customs MCP server to call check_stock for sku CC-HOOD-NAVY, size M, with qty_needed 20. Show me the raw tool output.

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**

> Build the agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Support. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity.
>
> Put the agent prompts in backend/prompts_  as one file per agent
> Put data types in backend/models.py
> and the agent files under backend/ (ensure the five roles are clear)
> below is what each agent should needs
>
> Boss: reads every ticket and what has already been done on it, decides which specialists to delegate to and in what order, weighs the whole board's cash before agreeing to any payment (rent first, then overdue invoices that block customer orders, then new purchase orders), makes the final call on discounts (at most 10%), never approves money itself, and is the only agent that sets a ticket's status, with a note listing the exact payment requests and drafts a human must act on
>
> Inventory: checks stock by SKU and size with the quantity needed, reports the shortfall and other sizes in stock as options, matches the product to a vendor by specialty, reports that vendor's lead time and whether an open invoice blocks it from shipping, gives an arrival estimate only as today plus lead days after the block is cleared, and never changes stock levels
>
> Accounting: starts from cash on hand and pending requests, checks invoices and how overdue they are, checks rent against the lease, checks that any discount is at most 10%, prepares invoice, rent, and purchase order payment requests for human approval with amounts taken from the database, never duplicates a request, flags any request that does not fit in cash, and never approves or moves money or counts future sales as cash
>
> Facilities: verifies the landlord's rent notice against the lease record (amount, due date, days until due), reports any mismatch, checks whether a rent request already exists, asks accounting to request rent when it is due, within 7 days or overdue, and flags rent as top priority if cash cannot cover it
>
> Customer Support: drafts short, warm messages to the requester using only confirmed facts (stock, timing, and the exact terms the boss approved), offers only real options, never promises a date, refund, discount, or product that was not confirmed, and saves drafts on the board without ever sending them
>
> Use PORTKEY_API_KEY and only gpt-6-luna for eveyr agent
> do not ivnent data
>
> shop facts come from the mcp server over data/campus_customs_new.db (do not inventory a second shop-tools layer that bypasses MCP)
>
> wire the agents so they append to output/audit_trail.json as they run: for each agent-loops tep record enough to audit later. append to this file, do not wipe it each run
>
> in output/harness.md list each agent and each mcp tool (included the ones we added in this problem) along with which table the tool uses. Also add a short safety section: cover the guardrails a real business would want when agents touch real customers and real money like human approval for every payment, no negative cash, amounts from the database, no duplicate payments, drafts only and never sent, append-only audit trail, protect data. keep token use in check by having a shared per-ticket budget, max output per response, and a limit on how many times agents can hand work to each other so they never loop
>
> Update mcp_server/README.md so the tool list matches what we have now

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---

## Problem 6: Plan the three tickets

**Prompt:**

> build output/desk_tickets.html a page that can be double clicked with one tab per ticket (101, 102, 103)
>
> also add cash adn reflectiont abds for later problems - leave blank for now
> on each ticket tab fill an expected section only (leave room for an actual section you will fill afte rthe agents run)
>
> for each ticket's expected section include who the boss should call first and why, all the agent delegation i expect (not "boss calls everyone"), and which mcp tools i expect that run to use. dont invent values
>
> Expected
>
> 101: boss calls inventory first to see if the size S tee is in stock (it isnt). inventory finds the vendor cant ship until its overdue $840 bill is paid, accounting asks a human to approve paying it, and customer support drafts an update to the customer with no promised date. facilities is not needed. tools: check_stock, get_invoice, request_invoice_payment, draft_customer_message
>
> 102: boss calls facilities first because rent is their area and the email should be checked against the lease. facilities confirms $2,400 is due in 2 days and accounting asks a human to approve paying it. inventory and customer support are not needed. tools: get_rent_due, request_rent_payment
>
> 103: boss calls inventory first because a discount doesnt matter until we know how many hoodies we have (8 of 20). inventory reports 12 short, accounting checks the price at 10% off and finds there isnt enough cash to restock the 12, the boss approves up to 10% off on the 8 in stock, and customer support drafts a reply. tools: check_stock, check_discount, get_cash_balance, draft_customer_message

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---

## Problem 7: Backend routes

**Prompt:**

> The React frontend dashboard (the next problem) needs a backend it can call. In backend/main.py, use FastAPI and add these routes
>
> -make a route that shows the three tickets and if each one is open or resolved
>
> -make a route that runs the agent team on a ticket
>
> -make a route that shows recent agent events, what each agent said and which tools they used, so the board can refresh
>
> -make a route that approves a payment or purchase after a human clicks approve (agents only prepare the pay, this is what actually changes cash)
>
> -make a route that shows the current checking balance from cash_accounts
>
> -make a route that resets the database to the original values when you want to try a fresh run
>
> From the backend/ folder, start the server with: uvicorn main:app --reload --port 8000
>
> In output/harness.md list each route in one line (what url/what it does) based on the above

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---

## Problem 8: Agent dashboard

**Prompt:**

> Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes built in Problem 7. At minimum the board should:
>
> -List all three tickets
>
> -Let me pick one ticket and start the agent team on it
>
> -Show each agent and what they are saying/doing while the ticket runs
>
> -Mark a ticket resolved when the run finishes
>
> -Show a short summary of what each agent did on that ticket
>
> -Let a human approve a pay or purchase when asked
>
> -Show the checking balance (it should drop after an approved pay)
>
> Tell the front end to talk to the backend at http://localhost:8000
> On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes
>
> start the board with npm run dev
> this opens the React desk in the browser so you can pick tickets and watch agents
>
> write output/design.md with the layout and design choices below and why
>
> make it look and feel like a real shop desk people would want to sit at, not an admin panel. use warm paper colors with yale blue for the shop and brass for money, a classic book style font for what the shop and agents say and a typewriter style font for every dollar amount. lay it out in three columns: tickets on the left as a stack of paper slips, the live agent floor in the middle, and the till on the right with the checking balance, payments waiting for my signature, and a receipt tape of what was paid. put the five agents across the top as nameplates that light up and say what they are doing, fade the ones not called, and check off the ones that reported back. give each agent its own color and icon so i can follow who is talking, show tool calls like "checking the shelf" with the answer underneath, show handoffs as cards, and indent work done for another agent. when a run finishes, stamp the ticket resolved and add a tag for where its money stands that updates on its own as payments change: paid, awaiting signature, blocked (and why, like invoice 501 unpaid or not enough cash), partly paid, cleared, or no payment needed. show a shift report with the boss's decision, what needs me, one line per agent with the tools they used, and drafts that look like unsent letters. make the balance roll down and flash when a payment is approved, put the dollar amount on the approve button, and request that i sign with my name before i can approve. put payments that can't be paid yet in their own section with the reason, like the vendor's unpaid invoice, and a button to clear them from the desk

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---

## Problem 9: Resolve the tickets

**Prompt:**

> Before testing the agents ona. full run over the three ticekts, reset the working database data/campus_customs_new.db again so we can start clean. Note the starting checking balance. then run all three tickets ont he board (101, 102, 103) until each is resolved
>
> open output/desk_tickets.html from Problem 6. On each ticket tab, fill the Actual section from this run: which agents worked, what they delegated, and which tools they used. keep your expected section so we can compare the two.
>
> On the Cash tab of the same output/desk_tickets.html, itemize the money:
> -starting checking balance (after the reset)
> -for each ticket, how cash changed when that ticket resolved, and why. which pay/purchase, dollar amount
> -ending checking balance. it must match cash_accounts in the working database
>
> save
> -output/resolved_tickets.json for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals
> -output/resolved_board.html a page that can be double clicked with a screenshot of the React board for each resolved ticket (101, 102, and 103)
>
> Append real runs to output/audit_trail.json
> Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules

**Follow-up prompt (if needed):**

> I want to change the message when a payment is too big. Say it exceeds the dollar amount in checking instead of "the till will refuse it". Let's change "why not" to a drop down of reasons, one of which could be other, and if that is selected then a written box appears
>
> lets also add the ability to queue up the tickets. i don't like that i cant begin sending tickets to the team before they finish reviewing another

**What was lacking after the first prompt:**

The warning on a payment that was too big didn't say the actual amount in checking, and rejecting a payment needed a typed reason every time instead of a quick choice. The board also only let one ticket be sent at a time, so I had to wait for the team to finish before sending the next ticket.

---

## Problem 10: Reflection

**Prompt:**

> Open output/desk_tickets.html and fill the Reflection tab.
> i will give the answers to questions i'm to answer. each asnwer with have - before it
>
> 1. - 101 (Bulldog tee) was good. it saw invoice 501 is the tee's reprint, so it asked me to pay the $840 instead of ordering again. the only waste was customer support rechecking stock (19 tool calls). 102 (rent) was the best. the boss went to facilities, facilities checked the lease ($2,400 due 9/2) and accounting made one rent request. cheapest run (15 tool calls). 103 (bulk hoodies) made the right calls but cost too much. 10% off ($52.20) on the 8 in stock and the $264 order for 12 sent to me, which was refused at payment with only $160 left. extra double-checking and the draft mentioned the vendor's unpaid invoice (30 tool calls).
>
> 2. - 101 matched, except the boss sent customer support before accounting. 102 was an exact match. facilities went first, then accounting asked to pay the $2,400 rent. 103 had the same first call and 10% off on the 8. i expected the $264 order held back, but accounting wrote it, the payment was refused and i cleared it. cash still ended at $160.
>
> 3. - the simple one step jobs, like checking rent against the lease and requesting it, or checking stock and drafting a reply. one agent with all the tools does those in a couple of calls, but our team passed them through two or three agents (102 took 12 model calls for one lookup and one request). the repeat stock checks on 101 and 103 were handoff cost too. splitting still made sense for money since only accounting can request a payment and no agent can approve one.
>
> 4. - a crest mug order. 0 on hand, so inventory finds Elm City Gifts (3 day lead), accounting writes the order ($3.50 each) for me to sign and customer support drafts. next month's rent. lease 1 is now due 2026-10-02, so it's the same path as 102, checked against the $160 left. bulk caps for another club. 40 on hand, the boss offers up to 10% off ($19.80 instead of $22.00) with check_discount and customer support drafts.
>
> 5. - money coming in. if Yale AI Club pays $417.60 for the 8 hoodies, cash can't go up. needs a record_sale tool and a sales agent. stock arriving. when Bulldog Print Co ships, nothing updates inventory. needs a receive_shipment tool with a human confirming the count. talking to people. drafts to Tauhid and Yale AI Club never leave the board and no one reads replies. needs an approval-gated send tool, an inbox tool and a communications agent.

**Follow-up prompt (if needed):**

> 

**What was lacking after the first prompt:**

---
