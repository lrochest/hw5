import { useEffect, useRef } from 'react'
import { AGENTS, AgentMark, isAgent, toolPhrase, WRITE_TOOLS } from '../agents'
import { argSummary, clock, money, STATUS_WORDS, tryJson } from '../format'
import type { AgentEvent, AgentReport, BossDecision } from '../types'

type Row =
  | { kind: 'start'; ev: AgentEvent }
  | { kind: 'end'; ev: AgentEvent }
  | { kind: 'tool'; ev: AgentEvent; result?: AgentEvent }
  | { kind: 'handoff'; ev: AgentEvent }
  | { kind: 'say'; ev: AgentEvent }
  | { kind: 'report'; ev: AgentEvent }
  | { kind: 'human'; ev: AgentEvent }

/** Pair each tool call with the result that came back, so one line tells the whole story. */
function toRows(events: AgentEvent[]): Row[] {
  const rows: Row[] = []
  const open: Row[] = []
  for (const ev of events) {
    switch (ev.type) {
      case 'ticket_start': rows.push({ kind: 'start', ev }); break
      case 'ticket_end': rows.push({ kind: 'end', ev }); break
      case 'delegate': rows.push({ kind: 'handoff', ev }); break
      case 'message': rows.push({ kind: 'say', ev }); break
      case 'report': rows.push({ kind: 'report', ev }); break
      case 'payment_approved':
      case 'payment_rejected':
      case 'payment_refused':
      case 'run_stopped': rows.push({ kind: 'human', ev }); break
      case 'tool_call': {
        const row: Row = { kind: 'tool', ev }
        rows.push(row)
        open.push(row)
        break
      }
      case 'tool_result': {
        // Match on the delegation chain too: two runs of the same agent can overlap
        const i = open.findIndex((r) => r.kind === 'tool' && r.ev.tool === ev.tool && r.ev.agent === ev.agent
          && (r.ev.chain ?? []).join('>') === (ev.chain ?? []).join('>'))
        if (i >= 0) {
          (open[i] as Extract<Row, { kind: 'tool' }>).result = ev
          open.splice(i, 1)
        }
        break
      }
    }
  }
  return rows
}

const depthOf = (ev: AgentEvent) => Math.max(0, (ev.chain?.length ?? 1) - (ev.type === 'delegate' ? 2 : 1))

function resultLine(tool: string | undefined, raw: unknown): string | null {
  const r = tryJson(raw) as Record<string, any> | string
  if (!r || typeof r !== 'object') return null
  if (r.error) return `Refused: ${r.error}`
  switch (tool) {
    case 'check_stock': return `${r.qty} on hand in ${r.location}${r.shortfall ? ` · ${r.shortfall} short` : ''}`
    case 'get_rent_due': return `${money(r.monthly_rent)} due ${r.next_due} · ${r.days_until_due} days away`
    case 'get_cash_balance': return `${money(r.total_balance)} on hand · ${money(r.available_after_pending)} after pending`
    case 'get_invoice': return `${r.vendor_name} · ${money(r.amount)} · ${r.status}${r.days_overdue ? ` · ${r.days_overdue} days overdue` : ''}`
    case 'check_discount':
    case 'check_margin': return `${r.discount_pct}% off · ${r.within_policy ? 'within the 10% limit' : 'over the 10% limit'}`
    case 'check_vendor_invoices': return `${r.vendor?.name} · ${r.can_ship ? 'can ship' : 'cannot ship'} · ${money(r.open_total ?? 0)} open`
    case 'request_invoice_payment':
    case 'request_rent_payment':
    case 'request_purchase_order':
      return r.payment_request ? `${money(r.payment_request.amount)} · waiting for a human to approve` : null
    case 'draft_customer_message': return r.draft ? `Draft to ${r.draft.recipient} · not sent` : null
    case 'update_ticket_status': return r.ticket ? `Ticket set to "${STATUS_WORDS[r.ticket.status] ?? r.ticket.status}"` : null
    default: return null
  }
}

export function Floor({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const rows = toRows(events)
  const bottom = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (running) bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [rows.length, running])

  if (!rows.length) {
    return (
      <div className="floor floor--empty">
        <p>The floor is quiet.</p>
        <p className="muted">Send this ticket to the team and you'll see every agent think, check, and hand off here, live.</p>
      </div>
    )
  }

  return (
    <div className="floor">
      {rows.map((row, i) => {
        const ev = row.ev
        const agent = isAgent(ev.agent) ? ev.agent : null
        const style = { ['--depth' as string]: depthOf(ev), ['--agent' as string]: agent ? AGENTS[agent].color : '#6b7280' }
        switch (row.kind) {
          case 'start':
            return <div key={i} className="floor__divider">Handed to the Boss · {clock(ev.ts)}</div>
          case 'end': {
            const d = ev.detail as { error?: string; decision?: BossDecision }
            return (
              <div key={i} className={`floor__divider floor__divider--end${d.error ? (d.error.startsWith('Stopped') ? ' is-stopped' : ' is-error') : ''}`}>
                {d.error ? `Run stopped: ${d.error}` : `Team finished · ${STATUS_WORDS[d.decision?.final_status ?? ''] ?? ''} · ${clock(ev.ts)}`}
              </div>
            )
          }
          case 'handoff': {
            const to = ev.to!
            return (
              <div key={i} className="line line--handoff" style={style}>
                <div className="handoff">
                  <AgentMark agent={agent!} size={26} />
                  <span className="handoff__arrow">→</span>
                  <AgentMark agent={to} size={26} />
                  <span className="handoff__who"><b>{AGENTS[agent!].label}</b> asks <b>{AGENTS[to].label}</b></span>
                </div>
                <blockquote className="handoff__task">{String(ev.detail)}</blockquote>
              </div>
            )
          }
          case 'tool': {
            const line = row.result ? resultLine(ev.tool, row.result.detail) : null
            const refused = line?.startsWith('Refused')
            return (
              <div key={i} className="line line--tool" style={style}>
                <AgentMark agent={agent!} size={22} />
                <div className="tool">
                  <span className={`tool__verb${WRITE_TOOLS.has(ev.tool ?? '') ? ' tool__verb--write' : ''}`}>{toolPhrase(ev.tool)}</span>
                  <span className="tool__args">{argSummary(ev.detail)}</span>
                  {row.result ? (
                    <details className="tool__result">
                      <summary className={refused ? 'is-refused' : ''}>{line ?? 'See what came back'}</summary>
                      <pre>{JSON.stringify(tryJson(row.result.detail), null, 2)}</pre>
                    </details>
                  ) : running ? <span className="tool__wait">waiting for the shop's answer…</span> : null}
                  <code className="tool__name">{ev.tool}</code>
                </div>
              </div>
            )
          }
          case 'say':
            return (
              <div key={i} className="line line--say" style={style}>
                <AgentMark agent={agent!} size={22} />
                <p className="say">{String(ev.detail)}</p>
              </div>
            )
          case 'report': {
            const d = ev.detail as AgentReport | BossDecision
            const text = 'summary' in d ? d.summary : d.decision
            const parent = ev.chain && ev.chain.length > 1 ? ev.chain[ev.chain.length - 2] : null
            return (
              <div key={i} className={`line line--report${agent === 'boss' ? ' line--verdict' : ''}`} style={style}>
                <AgentMark agent={agent!} size={30} />
                <div className="bubble">
                  <span className="bubble__who">
                    {AGENTS[agent!].label} {parent && isAgent(parent) ? `reports back to ${AGENTS[parent].label}` : 'makes the call'}
                  </span>
                  <p>{text}</p>
                </div>
              </div>
            )
          }
          case 'human': {
            const d = ev.detail as { approved_by?: string; rejected_by?: string; stopped_by?: string; amount?: number; reason?: string; request_id?: number }
            if (ev.type === 'run_stopped') {
              return (
                <div key={i} className="line line--human line--stopped">
                  <span className="human-mark">■</span>
                  <p><b>{d.stopped_by || 'A human'}</b> stopped the team. Anything already prepared stays pending for review.</p>
                </div>
              )
            }
            return (
              <div key={i} className="line line--human">
                <span className="human-mark">✍</span>
                <p>
                  {ev.type === 'payment_approved'
                    ? <><b>{d.approved_by}</b> approved a payment · {money(d.amount ?? 0)} paid</>
                    : ev.type === 'payment_refused'
                      ? <><b>{d.approved_by}</b> tried to approve a payment · {d.reason}</>
                      : <><b>{d.rejected_by}</b> rejected a payment · {d.reason}</>}
                </p>
              </div>
            )
          }
        }
      })}
      {running && <div className="floor__typing"><span /><span /><span /></div>}
      <div ref={bottom} />
    </div>
  )
}
