import { useEffect, useRef, useState } from 'react'
import { AGENTS, AgentMark, isAgent } from '../agents'
import { money } from '../format'
import { blockers as whyBlocked } from '../payments'
import type { Cash, PaymentRequest, Ticket } from '../types'

const REJECT_REASONS = [
  'Not enough cash right now',
  'Pay other bills first',
  "Vendor can't ship yet",
  'Amount looks wrong',
  'Duplicate request',
  'Not needed anymore',
  'Other',
]

const KIND_LABEL: Record<PaymentRequest['kind'], string> = {
  invoice: 'Vendor invoice',
  rent: 'Rent',
  purchase_order: 'Purchase order',
}

/** Rolls the balance to its new value so a payment is something you watch happen. */
function useRolling(target: number) {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = performance.now()
    const a = from.current
    let raf = 0
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / 900)
      const eased = 1 - Math.pow(1 - t, 3)
      setShown(a + (target - a) * eased)
      if (t < 1) raf = requestAnimationFrame(step)
      else from.current = target
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target])
  return shown
}

export function Till({ cash, pending, history, tickets, signer, onSigner, onApprove, onReject, busyId }: {
  cash: Cash | null
  pending: PaymentRequest[]
  history: PaymentRequest[]
  tickets: Ticket[]
  signer: string
  onSigner: (name: string) => void
  onApprove: (req: PaymentRequest) => void
  onReject: (req: PaymentRequest, reason: string) => void
  busyId: number | null
}) {
  const balance = cash?.checking_balance ?? 0
  const rolling = useRolling(balance)
  const [dropped, setDropped] = useState(false)
  const last = useRef(balance)
  const [rejecting, setRejecting] = useState<number | null>(null)
  const [reason, setReason] = useState(REJECT_REASONS[0])
  const [otherReason, setOtherReason] = useState('')

  useEffect(() => {
    if (balance < last.current) {
      setDropped(true)
      const t = setTimeout(() => setDropped(false), 1600)
      last.current = balance
      return () => clearTimeout(t)
    }
    last.current = balance
  }, [balance])

  const subject = (id: number | null) => tickets.find((t) => t.id === id)?.subject ?? ''
  const after = cash?.available_after_pending ?? 0

  const blockers = (p: PaymentRequest) => whyBlocked(p, balance)
  const ready = pending.filter((p) => blockers(p).length === 0)
  const held = pending.filter((p) => blockers(p).length > 0)

  const voucher = (p: PaymentRequest, why: string[] = []) => (
    <article key={p.id} className={`voucher${why.length ? ' voucher--held' : ''}`}>
      <div className="voucher__top">
        <span className="voucher__kind">{KIND_LABEL[p.kind]}</span>
        <span className="voucher__amount">{money(p.amount)}</span>
      </div>
      <p className="voucher__ticket">For ticket {p.ticket_id} · {subject(p.ticket_id)}</p>
      {p.invoice && (
        <p className={`voucher__status${p.invoice.days_overdue ? ' is-overdue' : ''}`}>
          Invoice {p.invoice.id} · {p.invoice.vendor_name} · {p.invoice.status === 'open' ? 'unpaid' : p.invoice.status}
          {' · '}due {p.invoice.due_date}{p.invoice.days_overdue ? ` · ${p.invoice.days_overdue} days overdue` : ''}
        </p>
      )}
      {p.kind === 'purchase_order' && (
        <p className="voucher__status">
          {p.qty} × {p.sku}{p.size ? ` · ${p.size}` : ''} from {p.vendor_name ?? `vendor ${p.vendor_id}`}
        </p>
      )}
      <p className="voucher__reason">{p.reason}</p>
      <div className="voucher__by">
        {isAgent(p.requested_by) && <AgentMark agent={p.requested_by} size={20} />}
        <span>Prepared by {isAgent(p.requested_by) ? AGENTS[p.requested_by].label : p.requested_by}</span>
      </div>
      {why.map((w) => <p key={w} className="voucher__warn">⚠ {w}</p>)}
      {why.length > 0 ? (
        <div className="voucher__actions">
          <button
            className="btn btn--ghost"
            disabled={!signer.trim()}
            title={signer.trim() ? '' : 'Type your name above to sign'}
            onClick={() => onReject(p, `Cleared: ${why.join('; ')}`)}
          >
            Clear from the desk
          </button>
          <button className="btn btn--link" disabled={!signer.trim() || busyId === p.id} onClick={() => onApprove(p)}>
            Try to pay anyway
          </button>
        </div>
      ) : rejecting === p.id ? (
        <form
          className="voucher__reject"
          onSubmit={(e) => {
            e.preventDefault()
            onReject(p, reason === 'Other' ? otherReason.trim() : reason)
            setRejecting(null)
            setReason(REJECT_REASONS[0])
            setOtherReason('')
          }}
        >
          <label className="voucher__reason-pick">
            <span>Reason</span>
            <select autoFocus value={reason} onChange={(e) => setReason(e.target.value)}>
              {REJECT_REASONS.map((r) => <option key={r}>{r}</option>)}
            </select>
          </label>
          {reason === 'Other' && (
            <textarea
              autoFocus
              value={otherReason}
              onChange={(e) => setOtherReason(e.target.value)}
              placeholder="Write the reason"
              rows={2}
              required
            />
          )}
          <div className="voucher__reject-actions">
            <button type="submit" className="btn btn--ghost" disabled={!signer.trim() || (reason === 'Other' && !otherReason.trim())}>
              Reject
            </button>
            <button type="button" className="btn btn--link" onClick={() => setRejecting(null)}>Cancel</button>
          </div>
        </form>
      ) : (
        <div className="voucher__actions">
          <button
            className="btn btn--sign"
            disabled={!signer.trim() || busyId === p.id}
            title={signer.trim() ? '' : 'Type your name above to sign'}
            onClick={() => onApprove(p)}
          >
            {busyId === p.id ? 'Paying…' : `Approve & pay ${money(p.amount)}`}
          </button>
          <button className="btn btn--link" onClick={() => setRejecting(p.id)}>Reject</button>
        </div>
      )}
    </article>
  )

  return (
    <aside className="till">
      <section className={`register${dropped ? ' register--dropped' : ''}`}>
        <span className="eyebrow">Checking</span>
        <div className="register__amount">{money(rolling)}</div>
        <div className="register__meta">
          <span>{money(cash?.pending_total ?? 0)} waiting for approval</span>
          <span className={after < 0 ? 'is-negative' : ''}>{money(after)} if all approved</span>
        </div>
        <div className="register__bar">
          <span style={{ width: `${Math.max(0, Math.min(100, (after / Math.max(balance, 1)) * 100))}%` }} />
        </div>
        <p className="register__note">Cash only goes out. Nothing leaves without a human signature.</p>
      </section>

      <section className="approvals">
        <div className="approvals__head">
          <h2>Needs your signature</h2>
          {ready.length > 0 && <span className="badge">{ready.length}</span>}
        </div>
        <label className="signer">
          <span>Signing as</span>
          <input value={signer} onChange={(e) => onSigner(e.target.value)} placeholder="Your name" />
        </label>

        {pending.length === 0 && <p className="muted small">No payments waiting. The agents will put requests here.</p>}

        {ready.map((p) => voucher(p))}

        {held.length > 0 && (
          <div className="held">
            <div className="held__head">
              <h3>Can't be paid yet</h3>
              <span className="held__count">{held.length}</span>
            </div>
            <p className="held__note">The till would refuse these right now. Clear one to take it off the desk (it's recorded as rejected with the reason shown), or pay what's blocking it first.</p>
            {held.map((p) => voucher(p, blockers(p)))}
          </div>
        )}
      </section>

      {history.length > 0 && (
        <section className="tape" aria-label="Receipt tape">
          <span className="tape__title">— Campus Customs · receipts —</span>
          {history.map((p) => (
            <div key={p.id} className={`tape__line${p.status === 'rejected' ? ' tape__line--void' : ''}`}>
              <span>Ticket {p.ticket_id} · {KIND_LABEL[p.kind]}</span>
              <span>{p.status === 'paid' ? `-${money(p.amount)}` : 'VOID'}</span>
              <small>{p.status === 'paid' ? 'Signed' : 'Rejected'} by {p.decided_by}{p.decision_note ? ` · ${p.decision_note}` : ''}</small>
            </div>
          ))}
        </section>
      )}
    </aside>
  )
}
