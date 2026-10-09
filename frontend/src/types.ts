export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_support'

export interface LastRun {
  run_id: string
  started_at: string
  finished: boolean
  finished_at?: string
  error?: string | null
  decision?: BossDecision | null
  tokens?: number
  requests?: number
  tool_calls?: number
}

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: string
  notes: string | null
  created_at: string
  state: 'open' | 'queued' | 'running' | 'resolved'
  queue_position?: number
  last_run: LastRun | null
}

export interface TicketsResponse {
  today: string
  tickets: Ticket[]
  running_ticket_id: number | null
  queue: number[]
}

export interface BossDecision {
  ticket_id: number
  final_status: string
  decision: string
  delegated_to: AgentName[]
  payment_request_ids: number[]
  draft_ids: number[]
  human_actions_needed: string[]
}

export interface AgentReport {
  agent: AgentName
  summary: string
  facts: string[]
  actions_taken: string[]
  payment_request_ids: number[]
  draft_ids: number[]
  blockers: string[]
  needs_human: boolean
}

export type EventType =
  | 'tool_call' | 'tool_result' | 'message' | 'delegate' | 'report'
  | 'ticket_start' | 'ticket_end' | 'reset_db' | 'payment_approved' | 'payment_rejected' | 'payment_refused' | 'run_stopped'

export interface AgentEvent {
  ts: string
  run_id: string | null
  ticket_id: number | null
  agent: AgentName | string | null
  type: EventType
  tool?: string
  to?: AgentName
  chain?: AgentName[]
  detail: unknown
}

export interface EventsResponse {
  running_ticket_id: number | null
  events: AgentEvent[]
}

export interface PaymentRequest {
  id: number
  ticket_id: number | null
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  vendor_id: number | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  reason: string
  requested_by: AgentName
  status: 'pending' | 'paid' | 'rejected'
  created_at: string
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  vendor_name?: string | null
  /** purchase orders: the vendor's open invoices that stop it shipping */
  blocked_by_invoices?: { id: number; amount: number; due_date: string; status: string; description: string | null }[]
  /** invoice payments: the invoice being paid */
  invoice?: { id: number; amount: number; due_date: string; status: string; description: string | null; vendor_name: string; days_overdue: number }
}

export interface Cash {
  today: string
  checking_balance: number
  as_of: string
  pending_total: number
  available_after_pending: number
}

export interface Draft {
  id: number
  ticket_id: number
  recipient: string
  subject: string
  body: string
  drafted_by: AgentName
  status: string
  created_at: string
}

export interface TicketDetail {
  today: string
  ticket: Ticket
  updates: { id: number; status: string; note: string; updated_by: string; created_at: string }[]
  payment_requests: PaymentRequest[]
  drafts: Draft[]
}
