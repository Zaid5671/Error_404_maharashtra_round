// The line above the graph: idle, running (which step), or the result in the agent's own words.

import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { ResolvedPlugin } from '@/agents/types'
import type { RunResult, Status } from '@/store/runStore'
import type { Step } from '@/types/contract'

interface Props {
  status: Status
  plugin: ResolvedPlugin
  result: RunResult | null
  steps: Step[]
  runningStep: { id: number; name: string } | null
  hiddenFault: boolean
  error: string | null
  action?: ReactNode
}

export function ResultBanner({ status, plugin, result, steps, runningStep, hiddenFault, error, action }: Props) {
  let tone: 'idle' | 'running' | 'good' | 'bad' = 'idle'
  let state = 'Idle'
  let message: ReactNode = (
    <>Fill in the task and press <strong>Run</strong>. Each step the agent takes appears below as it happens.</>
  )
  let note: ReactNode = null

  if (status === 'running') {
    tone = 'running'
    state = 'Running'
    message = runningStep
      ? <>Step <strong>#{runningStep.id}</strong> · <span className="font-mono">{runningStep.name}</span></>
      : 'Starting the agent…'
    if (hiddenFault) note = 'A fault is hidden in one of these steps.'
  } else if (status === 'error') {
    tone = 'bad'
    state = 'Error'
    message = error
  } else if (status === 'done' && result) {
    const ok = result.outcome === 'success'
    tone = ok ? 'good' : 'bad'
    state = ok ? '✓ Correct' : '✗ Wrong result'
    message = plugin.resultLine(result)
    note = ok
      ? hiddenFault
        ? 'A fault was injected, but it didn’t change the result: the agent recovered.'
        : <>Try <strong>Surprise me</strong> to hide a fault in the next run.</>
      : hiddenFault
        ? `A fault was secretly injected into one of these ${steps.length} steps. Can the Black Box find which one?`
        : 'Something went wrong in one of these steps.'
  }

  return (
    <div className="flex min-h-[58px] flex-wrap items-center gap-3 border-b px-3.5 py-3" role="status">
      <span className={cn('rounded px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wider whitespace-nowrap uppercase',
        tone === 'idle' && 'bg-sunk text-muted-foreground',
        tone === 'running' && 'bg-recorder-soft text-recorder-ink',
        tone === 'good' && 'bg-good-soft text-good',
        tone === 'bad' && 'bg-bad-soft text-bad')}>
        {state}
      </span>
      <span className="min-w-[220px] flex-1">
        {message}
        {note && <span className="mt-0.5 block text-[12.5px] text-muted-foreground">{note}</span>}
      </span>
      {action}
    </div>
  )
}
