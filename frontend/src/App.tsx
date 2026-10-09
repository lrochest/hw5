import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import { Floor } from './components/Floor'
import { Roster } from './components/Roster'
import { ShiftReport } from './components/ShiftReport'
import { TicketRail } from './components/TicketRail'
import { Till } from './components/Till'
import { money, ordinal, shopDate, TICKET_TYPES } from './format'
import { payTag } from './payments'
import type { AgentEvent, Cash, PaymentRequest, TicketDetail, TicketsResponse } from './types'

type Toast = { id: number; tone: 'good' | 'bad' | 'info'; text: string }

function greetingFor() {
  const h = new Date().getHours()
  return h < 12 ? 'Good Morning' : h < 18 ? 'Good Afternoon' : 'Good Evening'
}

export default function App() {
  const [board, setBoard] = useState<TicketsResponse | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [cash, setCash] = useState<Cash | null>(null)
  const [pending, setPending] = useState<PaymentRequest[]>([])
  const [history, setHistory] = useState<PaymentRequest[]>([])
  const [offline, setOffline] = useState(false)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [signer, setSigner] = useState(() => localStorage.getItem('desk.signer') ?? '')
  const lastRunning = useRef<number | null>(null)

  const toast = useCallback((tone: Toast['tone'], text: string) => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, tone, text }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5200)
  }, [])

  const refreshBoard = useCallback(async () => {
    try {
      const [b, c, p, all] = await Promise.all([api.tickets(), api.cash(), api.payments('pending'), api.payments('')])
      setBoard(b)
      setCash(c)
      setPending(p.payment_requests)
      setHistory(all.payment_requests.filter((r) => r.status !== 'pending').reverse())
      setOffline(false)
      setSelected((s) => s ?? b.tickets[0]?.id ?? null)
      // A run just finished: say so, once
      if (lastRunning.current !== null && b.running_ticket_id !== lastRunning.current) {
        const done = b.tickets.find((t) => t.id === lastRunning.current)
        if (done?.last_run?.error?.startsWith('Stopped')) toast('info', `Ticket ${done.id} stopped. Anything already prepared is still waiting for review.`)
        else if (done?.last_run?.error) toast('bad', `Ticket ${done.id} stopped: ${done.last_run.error}`)
        else if (done) toast('good', `Ticket ${done.id} resolved by the team`)
      }
      lastRunning.current = b.running_ticket_id
    } catch {
      setOffline(true)
    }
  }, [toast])

  const ticket = board?.tickets.find((t) => t.id === selected) ?? null
  const running = ticket?.state === 'running'
  const queued = ticket?.state === 'queued'
  const anyRunning = board?.running_ticket_id != null
  const queue = board?.queue ?? []

  // The backend knows the latest run since the last reset; older runs stay in the audit trail but not on screen
  const runId = ticket?.last_run?.run_id ?? null
  const runStart = ticket?.last_run?.started_at ?? ''

  const refreshTicket = useCallback(async () => {
    if (selected == null) return
    try {
      const [ev, d] = await Promise.all([api.events(selected), api.ticket(selected)])
      setEvents(runId ? ev.events.filter((e) => e.run_id === runId
        || ((e.type.startsWith('payment_') || e.type === 'run_stopped') && e.ts > runStart)) : [])
      setDetail(d)
    } catch {
      /* the board poll reports offline */
    }
  }, [selected, runId, runStart])

  useEffect(() => {
    refreshBoard()
    const t = setInterval(refreshBoard, anyRunning ? 1500 : 4000)
    return () => clearInterval(t)
  }, [refreshBoard, anyRunning])

  useEffect(() => {
    refreshTicket()
    const t = setInterval(refreshTicket, running ? 1200 : 4000)
    return () => clearInterval(t)
  }, [refreshTicket, running])

  const runTeam = async () => {
    if (!ticket) return
    try {
      const r = await api.run(ticket.id)
      if (r.status === 'started') {
        toast('info', `Ticket ${ticket.id} is on the floor`)
        lastRunning.current = ticket.id
      } else {
        toast('info', `Ticket ${ticket.id} is ${ordinal(r.position)} in line. The team will pick it up after the run ahead of it.`)
      }
      await refreshBoard()
      await refreshTicket()
    } catch (e) {
      toast('bad', (e as Error).message)
    }
  }

  const approve = async (req: PaymentRequest) => {
    setBusyId(req.id)
    try {
      await api.approve(req.id, signer.trim())
      toast('good', `Paid ${money(req.amount)} for ticket ${req.ticket_id}`)
    } catch (e) {
      toast('bad', (e as Error).message)
    } finally {
      setBusyId(null)
      await Promise.all([refreshBoard(), refreshTicket()])
    }
  }

  const reject = async (req: PaymentRequest, reason: string) => {
    try {
      await api.reject(req.id, signer.trim(), reason)
      toast('info', `Rejected the ${money(req.amount)} payment for ticket ${req.ticket_id}. No money moved.`)
    } catch (e) {
      toast('bad', (e as Error).message)
    } finally {
      await Promise.all([refreshBoard(), refreshTicket()])
    }
  }

  const unqueue = async () => {
    if (!ticket) return
    try {
      await api.unqueue(ticket.id)
      toast('info', `Took ticket ${ticket.id} out of the queue`)
    } catch (e) {
      toast('bad', (e as Error).message)
    } finally {
      await refreshBoard()
    }
  }

  const stop = async () => {
    try {
      const r = await api.stop(signer.trim())
      toast('info', `Stopped the team on ticket ${r.ticket_id}`)
    } catch (e) {
      toast('bad', (e as Error).message)
    } finally {
      await Promise.all([refreshBoard(), refreshTicket()])
    }
  }

  const reset = async () => {
    const question = anyRunning
      ? `The team is working on ticket ${board?.running_ticket_id}${queue.length ? ` and ${queue.length} more ${queue.length === 1 ? 'is' : 'are'} queued` : ''}. Stop, clear the queue, and reset the shop to the original data?`
      : 'Reset the shop to the original data? Payments, drafts, and ticket progress will be cleared.'
    if (!window.confirm(question)) return
    try {
      await api.reset(signer.trim())
      setEvents([])
      toast('info', 'Shop reset to the original data')
      await refreshBoard()
      await refreshTicket()
    } catch (e) {
      toast('bad', (e as Error).message)
    }
  }

  const onSigner = (name: string) => {
    setSigner(name)
    localStorage.setItem('desk.signer', name)
  }

  // Greeting follows the computer's clock (not the shop date) and re-checks every 2 hours
  const [greeting, setGreeting] = useState(greetingFor)
  useEffect(() => {
    const t = setInterval(() => setGreeting(greetingFor()), 2 * 60 * 60 * 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <span className="brand__seal">CC</span>
          <div>
            <h1>Campus Customs <span>· The Desk</span></h1>
            <p>{greeting}{signer ? `, ${signer}` : ''}. Chapel Street · Shop Date {board ? shopDate(board.today) : '…'}</p>
          </div>
        </div>
        <div className="topbar__right">
          {offline && <span className="offline">Backend offline. Start it on :8000</span>}
          {queue.length > 0 && (
            <span className="queue-pill">Up next: {queue.map((id) => `Ticket ${id}`).join(' · ')}</span>
          )}
          {anyRunning && (
            <button className="btn btn--stop" onClick={stop}>■ Stop the team (#{board?.running_ticket_id})</button>
          )}
          <button className="btn btn--ghost" onClick={reset}>Reset shop</button>
        </div>
      </header>

      <Roster events={events} running={!!running} />

      <main className="layout">
        <TicketRail
          tickets={board?.tickets ?? []}
          selected={selected}
          onSelect={setSelected}
          payments={[...pending, ...history]}
          balance={cash?.checking_balance ?? 0}
        />

        <section className="center">
          {ticket ? (
            <>
              <div className="focus">
                <div>
                  <span className="eyebrow">{TICKET_TYPES[ticket.type] ?? ticket.type} · #{ticket.id}</span>
                  <h2>{ticket.subject}</h2>
                  <p className="focus__note">
                    <b>{ticket.requester}</b>: “{ticket.notes}”
                  </p>
                </div>
                {running ? (
                  <button className="btn btn--run btn--run-stop" onClick={stop}>■ Stop the team</button>
                ) : queued ? (
                  <div className="focus__queued">
                    <span>Waiting its turn · {ordinal(ticket.queue_position ?? 1)} in line</span>
                    <button className="btn btn--ghost" onClick={unqueue}>Remove from queue</button>
                  </div>
                ) : (
                  <button className="btn btn--run" onClick={runTeam}
                          title={anyRunning ? `The team is on ticket ${board?.running_ticket_id}; this one will wait its turn` : ''}>
                    {anyRunning ? 'Add to the queue' : ticket.last_run ? 'Run the team again' : 'Send to the team'}
                  </button>
                )}
              </div>

              {ticket.state === 'resolved' && ticket.last_run && (
                <ShiftReport
                  events={events}
                  run={ticket.last_run}
                  drafts={detail?.drafts ?? []}
                  tag={payTag([...pending, ...history].filter((p) => p.ticket_id === ticket.id), cash?.checking_balance ?? 0)}
                />
              )}

              <div className="floor-wrap">
                <div className="floor-wrap__head">
                  <h3>On the floor</h3>
                  {running && <span className="live"><span className="dot dot--live" /> Live</span>}
                </div>
                {queued && !events.length ? (
                  <div className="floor floor--empty">
                    <p>Waiting its turn.</p>
                    <p className="muted">{ordinal(ticket.queue_position ?? 1)} in line. The team picks it up as soon as ticket {board?.running_ticket_id} is done.</p>
                  </div>
                ) : (
                  <Floor events={events} running={!!running} />
                )}
              </div>
            </>
          ) : (
            <div className="floor floor--empty"><p>Loading the board…</p></div>
          )}
        </section>

        <Till
          cash={cash}
          pending={pending}
          history={history}
          tickets={board?.tickets ?? []}
          signer={signer}
          onSigner={onSigner}
          onApprove={approve}
          onReject={reject}
          busyId={busyId}
        />
      </main>

      <div className="toasts" role="status">
        {toasts.map((t) => <div key={t.id} className={`toast toast--${t.tone}`}>{t.text}</div>)}
      </div>
    </div>
  )
}
