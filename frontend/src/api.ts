import type { Cash, EventsResponse, PaymentRequest, TicketDetail, TicketsResponse } from './types'

// The desk talks to the FastAPI backend from Problem 7
export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `${res.status} ${res.statusText}`)
  return body as T
}

export const api = {
  tickets: () => call<TicketsResponse>('/api/tickets'),
  ticket: (id: number) => call<TicketDetail>(`/api/tickets/${id}`),
  run: (id: number) =>
    call<{ ticket_id: number; status: 'started' | 'queued'; position: number }>(`/api/tickets/${id}/run`, { method: 'POST' }),
  unqueue: (id: number) => call<{ status: string }>(`/api/tickets/${id}/unqueue`, { method: 'POST' }),
  stop: (stoppedBy: string) =>
    call<{ status: string; ticket_id: number }>('/api/run/stop', { method: 'POST', body: JSON.stringify({ stopped_by: stoppedBy }) }),
  events: (ticketId: number) => call<EventsResponse>(`/api/events?ticket_id=${ticketId}&limit=1000`),
  payments: (status: 'pending' | '' = 'pending') =>
    call<{ payment_requests: PaymentRequest[] }>(`/api/payments?status=${status}`),
  approve: (id: number, approvedBy: string) =>
    call<unknown>(`/api/payments/${id}/approve`, { method: 'POST', body: JSON.stringify({ approved_by: approvedBy }) }),
  reject: (id: number, rejectedBy: string, reason: string) =>
    call<unknown>(`/api/payments/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ rejected_by: rejectedBy, reason }),
    }),
  cash: () => call<Cash>('/api/cash'),
  reset: (stoppedBy: string) =>
    call<{ status: string; stopped_ticket_id: number | null }>('/api/reset', { method: 'POST', body: JSON.stringify({ stopped_by: stoppedBy }) }),
}
