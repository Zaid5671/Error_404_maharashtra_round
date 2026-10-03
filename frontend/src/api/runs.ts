// Starting a run. Until the API exists (P5), a mock stream plays a real recorded run as the same
// SSE events POST /run will send. P6 swaps the body of startRun for fetch-event-source.

import type { Run, RunEvent } from '@/types/contract'
import type { FaultMode } from '@/store/runStore'
import { SAMPLE_RUNS } from '@/sample'

type Json = Record<string, unknown>

export interface StartRunOptions {
  agent: string
  task: Json
  faultMode: FaultMode
  onEvent: (event: RunEvent) => void
  signal?: AbortSignal
}

export async function startRun({ agent, faultMode, onEvent, signal }: StartRunOptions): Promise<void> {
  const samples = SAMPLE_RUNS[agent]
  if (!samples) {
    onEvent({ event: 'error', data: { message: `No recorded run to play for agent "${agent}".` } })
    return
  }
  await playRun(faultMode === 'surprise' ? samples.faulted : samples.clean, onEvent, signal)
}

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, reducedMotion() ? ms / 3 : ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('aborted', 'AbortError'))
    })
  })
}

/** Play a saved run as live events: LLM steps take a little longer, like the real agent. */
export async function playRun(run: Run, onEvent: (event: RunEvent) => void, signal?: AbortSignal): Promise<void> {
  onEvent({
    event: 'run_started',
    data: { run_id: run.run_id, agent: run.agent, task: run.task, request_text: run.request_text },
  })
  await sleep(300, signal)
  for (const step of run.steps) {
    onEvent({ event: 'step_started', data: { id: step.id, name: step.name } })
    await sleep(step.llm ? 700 : 350, signal)
    onEvent({ event: 'step_done', data: { step } })
  }
  onEvent({
    event: 'run_done',
    data: { run_id: run.run_id, outcome: run.outcome, actual: run.actual, expected: run.expected },
  })
}
