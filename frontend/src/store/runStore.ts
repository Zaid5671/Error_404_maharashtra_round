// A run as it streams in. Runs arrive as the SSE events from the contract (POST /run or
// POST /replay), so applyEvent is the only way a streaming run changes; loadRun shows a saved run.
// Live Run uses the shared store (useLiveRun); Replay makes its own with createRunStore().

import { create } from 'zustand'
import type { Outcome, Run, RunEvent, Step } from '@/types/contract'

export type Status = 'idle' | 'running' | 'done' | 'error'
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

export interface RunState {
  status: Status
  meta: RunMeta | null
  steps: Step[]
  running: { id: number; name: string } | null // the step being executed right now
  reusedIds: number[]
  result: RunResult | null
  error: string | null
  selectedId: number | null
  /** The fault choice this run was started with (live runs only; a loaded run has null). */
  startedWith: { mode: FaultMode; type: string | null } | null
  select: (id: number | null) => void
  begin: (startedWith?: RunState['startedWith']) => void
  applyEvent: (event: RunEvent) => void
  loadRun: (run: Run) => void
}

const empty = { status: 'idle' as Status, meta: null, steps: [], running: null, reusedIds: [], result: null, error: null, selectedId: null, startedWith: null }

export function createRunStore() {
  return create<RunState>()((set, get) => ({
    ...empty,
    select: (selectedId) => set({ selectedId }),
    begin: (startedWith = null) => set({ ...empty, status: 'running', startedWith }),

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
        case 'run_done':
          set({ result: event.data, status: 'done', running: null, selectedId: get().steps.at(-1)?.id ?? null })
          break
        case 'error':
          set({ status: 'error', error: event.data.message, running: null })
          break
      }
    },

    loadRun: (run) =>
      set({
        ...empty,
        status: 'done',
        meta: { run_id: run.run_id, agent: run.agent, task: run.task, request_text: run.request_text },
        steps: run.steps,
        result: { run_id: run.run_id, outcome: run.outcome, actual: run.actual, expected: run.expected },
        selectedId: run.steps.at(-1)?.id ?? null,
      }),
  }))
}

export const useLiveRun = createRunStore()

// --- session: choices that outlive one screen --------------------------------------------------

export type FaultMode = 'none' | 'surprise' | 'choose'

interface Session {
  faultMode: FaultMode
  faultType: string | null // with "choose"
  /** The latest replay, so the journey bar can link to Compare. */
  lastReplay: { agent: string; original: string; replay: string } | null
  /** The task being edited in each agent's form, kept while the user moves between screens. */
  drafts: Record<string, Json>
  setDraft: (agent: string, task: Json) => void
  setFault: (mode: FaultMode, type?: string | null) => void
  setLastReplay: (r: Session['lastReplay']) => void
}

export const useSession = create<Session>()((set) => ({
  faultMode: 'none',
  faultType: null,
  lastReplay: null,
  drafts: {},
  setDraft: (agent, task) => set((s) => ({ drafts: { ...s.drafts, [agent]: task } })),
  setFault: (faultMode, faultType = null) => set({ faultMode, faultType }),
  setLastReplay: (lastReplay) => set({ lastReplay }),
}))
