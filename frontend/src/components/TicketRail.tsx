import { ordinal, STATUS_WORDS, TICKET_TYPES } from '../format'
import { payTag } from '../payments'
import type { PaymentRequest, Ticket } from '../types'

// Boss outcomes worth showing beside the payment tag ("waiting on approval" is covered by the tag itself)
const EXTRA_STATUS = new Set(['waiting_on_vendor', 'in_progress', 'declined'])

function ask(t: Ticket) {
  if (t.sku) return `${t.qty ?? ''} × ${t.sku}${t.size ? ` · ${t.size}` : ''}`
  if (t.lease_id) return `Lease ${t.lease_id}`
  return t.notes ?? ''
}

export function TicketRail({ tickets, selected, onSelect, payments, balance }: {
  tickets: Ticket[]
  selected: number | null
  onSelect: (id: number) => void
  payments: PaymentRequest[]
  balance: number
}) {
  const resolved = tickets.filter((t) => t.state === 'resolved').length
  return (
    <aside className="rail">
      <div className="rail__head">
        <h2>Tickets</h2>
        <span className="rail__count">{resolved}/{tickets.length} resolved</span>
      </div>
      <div className="rail__progress"><span style={{ width: `${(resolved / Math.max(tickets.length, 1)) * 100}%` }} /></div>
      <ul className="rail__list">
        {tickets.map((t) => (
          <li key={t.id}>
            <button
              className={`slip slip--${t.state}${selected === t.id ? ' slip--selected' : ''}`}
              onClick={() => onSelect(t.id)}
            >
              <span className="slip__top">
                <span className="slip__id">#{t.id}</span>
                <span className="slip__type">{TICKET_TYPES[t.type] ?? t.type}</span>
              </span>
              <span className="slip__subject">{t.subject}</span>
              <span className="slip__who">{t.requester}</span>
              <span className="slip__ask">{ask(t)}</span>
              <span className="slip__status">
                {t.state === 'running' ? (
                  <><span className="dot dot--live" /> Team is working…</>
                ) : t.state === 'queued' ? (
                  <><span className="dot dot--queued" /> Queued · {ordinal(t.queue_position ?? 1)} in line</>
                ) : t.state === 'resolved' ? ((() => {
                  const tag = payTag(payments.filter((p) => p.ticket_id === t.id), balance)
                  return (
                    <>
                      <span className={`paytag paytag--${tag.tone}`}>{tag.text}</span>
                      {tag.note && <span className="paytag__note">{tag.note}</span>}
                      {EXTRA_STATUS.has(t.status) && <span className="paytag__note">{STATUS_WORDS[t.status]}</span>}
                    </>
                  )
                })()
                ) : t.last_run?.error ? (
                  <>{t.last_run.error.startsWith('Stopped') ? 'Stopped before finishing' : 'Run failed'}</>
                ) : (
                  <>Not started</>
                )}
              </span>
              {t.state === 'resolved' && <span className="stamp">Resolved</span>}
            </button>
          </li>
        ))}
      </ul>
    </aside>
  )
}
