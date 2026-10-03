// The shared run state for every screen. Runs arrive as the SSE events from the contract
// (mock stream now, POST /run later), so applyEvent is the only way a run changes.

import { create } from 'zustand'
import type { Outcome, RunEvent, Step } from '@/types/contract'

export type Page = 'live' | 'diagnosis' | 'replay' | 'compare' | 'report'
export type Status = 'idle' | 'running' | 'done' | 'error'
export type FaultMode = 'none' | 'surprise'
type Json = Record<string, unknown>

export interface RunMeta {
  run_id: string
  agent: string
  task: Json
  request_text: string
}

export interface RunResult {
  run_id: string
  outcome: Outcome
  actual: Json | null
  expected: Json | null
}

interface RunState {
  page: Page
  agent: string
  faultMode: FaultMode
  status: Status
  runFaultMode: FaultMode // the mode the current run was started with
  meta: RunMeta | null
  steps: Step[]
  running: { id: number; name: string } | null // the step being executed right now
  reusedIds: number[]
  result: RunResult | null
  error: string | null
  selectedId: number | null
  hasRun: boolean
  setPage: (page: Page) => void
  setFaultMode: (mode: FaultMode) => void
  select: (id: number | null) => void
  beginRun: () => void
  applyEvent: (event: RunEvent) => void
}

export const useRunStore = create<RunState>()((set, get) => ({
  page: 'live',
  agent: 'pizza',
  faultMode: 'none',
  status: 'idle',
  runFaultMode: 'none',
  meta: null,
  steps: [],
  running: null,
  reusedIds: [],
  result: null,
  error: null,
  selectedId: null,
  hasRun: false,

  setPage: (page) => set({ page }),
  setFaultMode: (faultMode) => set({ faultMode }),
  select: (selectedId) => set({ selectedId }),

  beginRun: () =>
    set({
      status: 'running',
      runFaultMode: get().faultMode,
      meta: null,
      steps: [],
      running: null,
      reusedIds: [],
      result: null,
      error: null,
      selectedId: null,
    }),

  applyEvent: (event) => {
    switch (event.event) {
      case 'run_started':
        set({ meta: event.data, status: 'running' })
        break
      case 'step_started':
        set({ running: event.data })
        break
      case 'step_done': {
        const step = event.data.step
        set((s) => ({ steps: [...s.steps.filter((x) => x.id !== step.id), step], running: null }))
        break
      }
      case 'step_reused':
        set((s) => ({ reusedIds: [...s.reusedIds, event.data.id] }))
        break
      case 'run_done': {
        const steps = get().steps
        set({ result: event.data, status: 'done', hasRun: true, selectedId: steps.at(-1)?.id ?? null })
        break
      }
      case 'error':
        set({ status: 'error', error: event.data.message, running: null })
        break
    }
  },
}))
