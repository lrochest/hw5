import type { AgentName } from './types'

/** Each agent has its own colour, mark, and voice so you can tell who is talking at a glance. */
export const AGENTS: Record<AgentName, { label: string; role: string; color: string; tint: string }> = {
  boss: { label: 'Boss', role: 'Routes tickets · makes the call', color: '#00356b', tint: '#e3ebf5' },
  inventory: { label: 'Inventory', role: 'Stock · shortfalls · vendors', color: '#2f7a55', tint: '#e2f1e8' },
  accounting: { label: 'Accounting', role: 'Cash · invoices · discounts', color: '#9a6a06', tint: '#f8eed6' },
  facilities: { label: 'Facilities', role: 'Lease · rent · the space', color: '#a8472f', tint: '#f7e5df' },
  customer_support: { label: 'Customer Support', role: 'Drafts to customers', color: '#5f4597', tint: '#ece6f6' },
}
export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_support']

export const isAgent = (x: unknown): x is AgentName => typeof x === 'string' && x in AGENTS

const PATHS: Record<AgentName, string> = {
  // star: the boss makes the call
  boss: 'M12 3.5l2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8L3.5 9.7l5.9-.9z',
  // box: stock
  inventory: 'M4 8l8-4 8 4v8l-8 4-8-4zM4 8l8 4 8-4M12 12v8',
  // ledger: money
  accounting: 'M6 4h11a1 1 0 011 1v15H7a2 2 0 01-2-2V5a1 1 0 011-1zM5 18a2 2 0 012-2h11M9 8h6M9 11h4',
  // key: the space
  facilities: 'M14.5 4a5 5 0 11-3.9 8.1L4 18.7V21h3v-2h2v-2h2l1.5-1.5A5 5 0 0114.5 4zM16 8.5h.01',
  // speech bubble: customers
  customer_support: 'M5 5h14a1 1 0 011 1v9a1 1 0 01-1 1h-7l-5 4v-4H5a1 1 0 01-1-1V6a1 1 0 011-1z',
}

export function AgentMark({ agent, size = 32, pulse = false }: { agent: AgentName; size?: number; pulse?: boolean }) {
  const a = AGENTS[agent]
  return (
    <span
      className={`mark${pulse ? ' mark--pulse' : ''}`}
      style={{ width: size, height: size, background: a.color, ['--ring' as string]: a.color }}
      title={a.label}
    >
      <svg viewBox="0 0 24 24" width={size * 0.56} height={size * 0.56} fill="none" stroke="#fff"
           strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d={PATHS[agent]} />
      </svg>
    </span>
  )
}

/** Plain-English verbs for each MCP tool, so the floor reads like people working, not function calls. */
export const TOOL_PHRASES: Record<string, string> = {
  list_tickets: 'Looking over the board',
  list_open_tickets: 'Scanning the open tickets',
  get_ticket: 'Reading the ticket',
  check_stock: 'Checking the shelf',
  list_stock: 'Checking every size',
  list_vendors: 'Looking up vendors',
  check_vendor_invoices: "Checking the vendor's open bills",
  get_invoice: 'Pulling the invoice',
  get_rent_due: 'Checking the lease',
  get_cash_balance: 'Counting the cash',
  check_discount: 'Checking the discount',
  check_margin: 'Checking the discount',  // older runs in the audit trail
  list_payment_requests: 'Checking what is waiting for approval',
  request_invoice_payment: 'Asking a human to pay an invoice',
  request_rent_payment: 'Asking a human to pay rent',
  request_purchase_order: 'Writing up a purchase order',
  draft_customer_message: 'Drafting a message',
  update_ticket_status: 'Updating the ticket',
}
export const toolPhrase = (tool?: string) => (tool && TOOL_PHRASES[tool]) || tool || 'Working'

/** Tools that change something (shown with a stronger chip). */
export const WRITE_TOOLS = new Set([
  'request_invoice_payment', 'request_rent_payment', 'request_purchase_order',
  'draft_customer_message', 'update_ticket_status',
])
