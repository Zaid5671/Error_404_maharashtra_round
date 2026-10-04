// The Black Box API (plan.md section 6). Vite proxies /api to the FastAPI server on :8000.
// /run and /replay stream SSE events; everything else is plain JSON.

import { fetchEventSource } from '@microsoft/fetch-event-source'
import type { Diagnosis, FaultInfo, ReplayRequest, Report, Run, RunEvent, RunRequest } from '@/types/contract'

const BASE = '/api'
type Json = Record<string, unknown>

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function detail(res: Response): Promise<string> {
  try {
    const body = await res.json()
    return typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body)
  } catch {
    return res.status === 502 || res.status === 504
      ? 'The Black Box server is not reachable. Start it with: .venv\\Scripts\\python -m uvicorn blackbox.api:app --port 8000'
      : `${res.status} ${res.statusText}`
  }
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, body === undefined ? undefined : {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'The Black Box server is not reachable. Is it running on port 8000?')
  }
  if (!res.ok) throw new ApiError(res.status, await detail(res))
  return res.json() as Promise<T>
}

/** Stream SSE events from a POST. Resolves when the stream ends; HTTP errors become an `error` event. */
async function stream(path: string, body: unknown, onEvent: (e: RunEvent) => void, signal?: AbortSignal) {
  class Stop extends Error {}
  try {
    await fetchEventSource(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
      openWhenHidden: true, // keep streaming when the tab is in the background
      async onopen(res) {
        if (!res.ok) {
          onEvent({ event: 'error', data: { message: await detail(res) } })
          throw new Stop()
        }
      },
      onmessage(msg) {
        if (msg.event) onEvent({ event: msg.event, data: JSON.parse(msg.data) } as RunEvent)
      },
      onerror(err) {
        throw err // no automatic retries: a retry would start a second agent run
      },
    })
  } catch (err) {
    if (err instanceof Stop || (err as Error).name === 'AbortError') return
    onEvent({ event: 'error', data: { message: 'Lost the connection to the Black Box server. Is it running on port 8000?' } })
  }
}

// Saved runs never change, so they are cached for the session.
const runs = new Map<string, Promise<Run>>()

export const api = {
  agents: () => request<{ agents: string[] }>('/agents'),
  catalog: (agent: string) => request<Json>(`/catalog/${agent}`),
  faults: (agent: string) => request<FaultInfo[]>(`/faults/${agent}`),
  report: (agent: string) => request<Report>(`/report/${agent}`),
  diagnose: (agent: string, runId: string) => request<Diagnosis>('/diagnose', { agent, run_id: runId }),
  run(agent: string, runId: string): Promise<Run> {
    const key = `${agent}/${runId}`
    if (!runs.has(key)) {
      const p = request<Run>(`/runs/${agent}/${encodeURIComponent(runId)}`)
      p.catch(() => runs.delete(key))
      runs.set(key, p)
    }
    return runs.get(key)!
  },
  startRun: (body: RunRequest, onEvent: (e: RunEvent) => void, signal?: AbortSignal) => stream('/run', body, onEvent, signal),
  replay: (body: ReplayRequest, onEvent: (e: RunEvent) => void, signal?: AbortSignal) => stream('/replay', body, onEvent, signal),
}
