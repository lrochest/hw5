export const money = (n: number) =>
  n.toLocaleString('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 })

export const shopDate = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })

export const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', second: '2-digit' })

/** 1 -> "1st", 2 -> "2nd": queue positions, so "#" only ever means a ticket */
export const ordinal = (n: number) => {
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100
  return `${n}${s[(v - 20) % 10] || s[v] || s[0]}`
}

export const titleCase = (s: string) => s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

/** Parse a JSON string that may have been clipped by the audit trail. */
export function tryJson(value: unknown): unknown {
  if (typeof value !== 'string') return value
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

const HIDDEN_ARGS = new Set(['reason', 'body', 'note', 'task'])

/** "sku CC-HOOD-NAVY · size M · qty_needed 20" — the short version of a tool's arguments. */
export function argSummary(detail: unknown): string {
  const args = tryJson(detail)
  if (!args || typeof args !== 'object') return ''
  return Object.entries(args as Record<string, unknown>)
    .filter(([k, v]) => !HIDDEN_ARGS.has(k) && v !== null && v !== '')
    .map(([k, v]) => `${k.replace(/_id$/, '').replace(/_/g, ' ')} ${String(v)}`)
    .join(' · ')
}

export const STATUS_WORDS: Record<string, string> = {
  open: 'Open',
  in_progress: 'In progress',
  waiting_on_approval: 'Waiting on your approval',
  waiting_on_vendor: 'Waiting on the vendor',
  resolved: 'Closed',
  declined: 'Declined',
}

export const TICKET_TYPES: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Price request',
}
