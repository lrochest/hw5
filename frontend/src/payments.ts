import { money } from './format'
import type { PaymentRequest } from './types'

/** Why the till would refuse this payment right now (empty = ready to sign). */
export function blockers(p: PaymentRequest, balance: number): string[] {
  const why: string[] = []
  for (const inv of p.blocked_by_invoices ?? []) {
    why.push(`${p.vendor_name ?? 'The vendor'} won't ship: invoice ${inv.id} (${money(inv.amount)}, due ${inv.due_date}) is unpaid`)
  }
  if (p.amount > balance) why.push(`Exceeds the ${money(balance)} in checking`)
  return why
}

export type PayTag = { tone: 'paid' | 'waiting' | 'blocked' | 'partial' | 'cleared' | 'none'; text: string; note?: string }

/** One tag per ticket saying where its money stands, worked out from its actual payment requests. */
export function payTag(reqs: PaymentRequest[], balance: number): PayTag {
  if (!reqs.length) return { tone: 'none', text: 'No payment needed' }
  const pending = reqs.filter((r) => r.status === 'pending')
  const held = pending.filter((r) => blockers(r, balance).length > 0)
  const ready = pending.length - held.length
  const paid = reqs.filter((r) => r.status === 'paid').length
  const blockedWhy = () => {
    const inv = held.flatMap((r) => r.blocked_by_invoices ?? [])[0]
    return inv ? `invoice ${inv.id} unpaid` : 'not enough cash'
  }

  if (ready > 0) {
    return { tone: 'waiting', text: 'Awaiting signature', note: held.length ? `${held.length} blocked` : undefined }
  }
  if (held.length > 0) return { tone: 'blocked', text: `Blocked · ${blockedWhy()}` }
  if (paid === reqs.length) return { tone: 'paid', text: 'Paid' }
  if (paid > 0) return { tone: 'partial', text: 'Partly paid', note: `${reqs.length - paid} cleared` }
  return { tone: 'cleared', text: 'Cleared' }
}
