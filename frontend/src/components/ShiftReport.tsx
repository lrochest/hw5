import { AGENT_ORDER, AGENTS, AgentMark, isAgent, toolPhrase } from '../agents'
import { STATUS_WORDS } from '../format'
import type { PayTag } from '../payments'
import type { AgentEvent, AgentName, AgentReport, BossDecision, Draft, LastRun } from '../types'

/** One card per ticket run: the boss's call, then one line per agent on what they actually did. */
export function ShiftReport({ events, run, drafts, tag }: { events: AgentEvent[]; run: LastRun; drafts: Draft[]; tag: PayTag }) {
  const reports = new Map<AgentName, AgentReport | BossDecision>()
  const tools = new Map<AgentName, Map<string, number>>()
  const directReport = new Set<AgentName>()
  for (const e of events) {
    if (!isAgent(e.agent)) continue
    if (e.type === 'report') {
      // An agent can be called more than once (e.g. by a teammate). Show the report it gave the Boss
      // directly (chain boss > agent); fall back to its first report.
      const direct = (e.chain?.length ?? 0) <= 2
      if (!reports.has(e.agent) || (direct && !directReport.has(e.agent))) {
        reports.set(e.agent, e.detail as AgentReport | BossDecision)
        if (direct) directReport.add(e.agent)
      }
    }
    if (e.type === 'tool_call' && e.tool) {
      const m = tools.get(e.agent) ?? new Map<string, number>()
      m.set(e.tool, (m.get(e.tool) ?? 0) + 1)
      tools.set(e.agent, m)
    }
  }
  const decision = (reports.get('boss') as BossDecision | undefined) ?? run.decision ?? null
  const called = AGENT_ORDER.filter((a) => reports.has(a) || tools.has(a))
  const benched = AGENT_ORDER.filter((a) => !called.includes(a))

  return (
    <section className="report">
      <header className="report__head">
        <div>
          <span className="eyebrow">Shift report</span>
          <h3>
            <span className={`paytag paytag--${tag.tone} paytag--big`}>{tag.text}</span>
            {tag.note && <span className="paytag__note"> {tag.note}</span>}
          </h3>
          {decision && (
            <span className="report__boss-status">
              Boss's call at the end of the run: {STATUS_WORDS[decision.final_status] ?? decision.final_status}
            </span>
          )}
        </div>
        <span className="report__meta">
          {run.requests ?? 0} model calls · {run.tool_calls ?? 0} tool calls · {(run.tokens ?? 0).toLocaleString()} tokens
        </span>
      </header>

      {decision && <p className="report__verdict">“{decision.decision}”</p>}

      {decision && decision.human_actions_needed.length > 0 && (
        <div className="report__todo">
          <span className="eyebrow">{tag.tone === 'waiting' || tag.tone === 'blocked' ? 'Needs you' : 'The Boss asked you to'}</span>
          <ul>{decision.human_actions_needed.map((a, i) => <li key={i}>{a}</li>)}</ul>
        </div>
      )}

      <ul className="report__agents">
        {called.map((a) => {
          const r = reports.get(a)
          const text = r ? ('summary' in r ? r.summary : r.decision) : 'Worked on it but did not report back.'
          const used = [...(tools.get(a)?.entries() ?? [])]
          return (
            <li key={a} style={{ ['--agent' as string]: AGENTS[a].color, ['--tint' as string]: AGENTS[a].tint }}>
              <AgentMark agent={a} size={30} />
              <div>
                <span className="report__name">{AGENTS[a].label}</span>
                <p>{a === 'boss' ? 'Routed the ticket, weighed the cash, and set the final status.' : text}</p>
                {r && 'blockers' in r && r.blockers.length > 0 && (
                  <p className="report__blocker">Blocked by: {r.blockers.join(' · ')}</p>
                )}
                <div className="chips">
                  {used.map(([t, n]) => (
                    <span key={t} className="chip" title={t}>{toolPhrase(t)}{n > 1 ? ` ×${n}` : ''}</span>
                  ))}
                </div>
              </div>
            </li>
          )
        })}
      </ul>
      {benched.length > 0 && (
        <p className="report__bench">
          Not needed on this ticket: {benched.map((a) => AGENTS[a].label).join(', ')}
        </p>
      )}

      {drafts.length > 0 && (
        <div className="drafts">
          {drafts.map((d) => (
            <article key={d.id} className="letter">
              <span className="letter__flag">Draft · not sent</span>
              <p className="letter__to"><b>To:</b> {d.recipient}</p>
              <p className="letter__subject"><b>Subject:</b> {d.subject}</p>
              <p className="letter__body">{d.body}</p>
              <span className="letter__sig">Drafted by {isAgent(d.drafted_by) ? AGENTS[d.drafted_by].label : d.drafted_by} for a human to send</span>
            </article>
          ))}
        </div>
      )}
    </section>
  )
}
