import { AGENT_ORDER, AGENTS, AgentMark, isAgent, toolPhrase } from '../agents'
import type { AgentEvent, AgentName } from '../types'

type Status = { kind: 'idle' | 'active' | 'waiting' | 'done'; text: string }

/** Work out what each agent is doing right now from the current run's events. */
export function agentStatuses(events: AgentEvent[], running: boolean): Record<AgentName, Status> {
  const out = Object.fromEntries(
    AGENT_ORDER.map((a) => [a, { kind: 'idle', text: events.length ? 'Not called' : 'Off the floor' }]),
  ) as Record<AgentName, Status>
  const last = [...events].reverse().find((e) => isAgent(e.agent))

  for (const e of events) {
    if (!isAgent(e.agent)) continue
    const s = out[e.agent]
    if (e.type === 'report') out[e.agent] = { kind: 'done', text: 'Reported back' }
    else if (e.type === 'delegate' && e.to) out[e.agent] = { kind: 'waiting', text: `Waiting on ${AGENTS[e.to].label}` }
    else if (s.kind !== 'done') out[e.agent] = { kind: 'waiting', text: toolPhrase(e.tool) }
  }
  if (running && last && isAgent(last.agent) && out[last.agent].kind !== 'done') {
    const text = last.type === 'tool_call' ? `${toolPhrase(last.tool)}…`
      : last.type === 'delegate' && last.to ? `Handing off to ${AGENTS[last.to].label}`
      : 'Thinking…'
    out[last.agent] = { kind: 'active', text }
  }
  if (running && last?.type === 'delegate' && last.to) out[last.to] = { kind: 'active', text: 'Picking it up…' }
  return out
}

export function Roster({ events, running }: { events: AgentEvent[]; running: boolean }) {
  const statuses = agentStatuses(events, running)
  return (
    <div className="roster" aria-label="Agent team">
      {AGENT_ORDER.map((a) => {
        const s = statuses[a]
        return (
          <div key={a} className={`plate plate--${s.kind}`} style={{ ['--agent' as string]: AGENTS[a].color }}>
            <AgentMark agent={a} size={34} pulse={s.kind === 'active'} />
            <div className="plate__text">
              <span className="plate__name">{AGENTS[a].label}</span>
              <span className="plate__status">
                {s.kind === 'done' && '✓ '}{s.text}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
