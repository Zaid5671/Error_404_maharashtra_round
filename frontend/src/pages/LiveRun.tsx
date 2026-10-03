// Live Run: fill in a task, pick a fault mode, watch the agent's steps arrive as a graph.

import { useEffect, useMemo, useRef, useState } from 'react'
import { getPlugin } from '@/agents/registry'
import type { Json } from '@/agents/types'
import { startRun } from '@/api/runs'
import { InstrumentStrip } from '@/components/InstrumentStrip'
import { Panel } from '@/components/Panel'
import { ResultBanner } from '@/components/ResultBanner'
import { RunGraph } from '@/components/graph/RunGraph'
import { StepDetails } from '@/components/panels/StepDetails'
import { cn } from '@/lib/utils'
import { useRunStore } from '@/store/runStore'

export function LiveRun() {
  const s = useRunStore()
  const plugin = useMemo(() => getPlugin(s.agent), [s.agent])
  const [task, setTask] = useState<Json>(plugin.defaultTask)
  const [editing, setEditing] = useState(true)
  const abort = useRef<AbortController | null>(null)

  useEffect(() => () => abort.current?.abort(), [])

  const running = s.status === 'running'
  const selected = s.steps.find((x) => x.id === s.selectedId) ?? null

  async function run(e: React.FormEvent) {
    e.preventDefault()
    if (running) return
    abort.current?.abort()
    abort.current = new AbortController()
    setEditing(false)
    s.beginRun()
    try {
      await startRun({ agent: s.agent, task, faultMode: s.faultMode, onEvent: s.applyEvent, signal: abort.current.signal })
    } catch (err) {
      if ((err as Error).name !== 'AbortError') s.applyEvent({ event: 'error', data: { message: String(err) } })
    }
  }

  const showForm = editing || s.status === 'idle'
  const final = s.status === 'done' && s.result ? (s.result.outcome === 'success' ? 'good' : 'bad') : null
  const hiddenFault = s.runFaultMode === 'surprise'

  return (
    <div className={cn('grid items-start gap-4 transition-[grid-template-columns] duration-300',
      showForm ? 'xl:grid-cols-[300px_minmax(0,1fr)_320px]' : 'xl:grid-cols-[220px_minmax(0,1fr)_320px]',
      'lg:grid-cols-[260px_minmax(0,1fr)] grid-cols-1')}>

      <Panel title={plugin.title} sub={`${plugin.name} agent`}>
        {showForm ? (
          <form className="grid gap-3.5 p-3.5" onSubmit={run}>
            <plugin.TaskForm task={task} onChange={setTask} />
            <div className="grid gap-1 text-xs font-medium text-muted-foreground">
              Fault mode
              <div className="grid grid-cols-2 rounded-[7px] border bg-sunk p-[3px]" role="group" aria-label="Fault mode">
                {(['none', 'surprise'] as const).map((m) => (
                  <button key={m} type="button" aria-pressed={s.faultMode === m} onClick={() => s.setFaultMode(m)}
                    className={cn('rounded-[5px] px-1 py-1.5 text-sm font-medium text-muted-foreground',
                      s.faultMode === m && 'bg-card text-foreground shadow-[0_0_0_1px_var(--border)]')}>
                    {m === 'none' ? 'None' : 'Surprise me'}
                  </button>
                ))}
              </div>
            </div>
            <p className="m-0 text-xs text-muted-foreground">
              {s.faultMode === 'none' ? 'Runs the agent as normal.' : 'Secretly breaks one step. Can the Black Box find it later?'}
            </p>
            <button type="submit" disabled={running}
              className="rounded-[7px] bg-recorder p-2.5 font-display text-[15px] font-bold tracking-[0.03em] text-white disabled:cursor-progress disabled:opacity-60">
              {running ? 'Running…' : 'Run'}
            </button>
            <p className="m-0 text-xs text-muted-foreground">Until the API is connected, Run plays a recorded run of this agent.</p>
          </form>
        ) : (
          <div className="grid gap-3 p-3.5">
            {s.meta && <plugin.TaskSummary task={s.meta.task} />}
            <span className="font-mono text-[11px] font-semibold tracking-wider text-recorder-ink uppercase">
              Fault mode: {s.runFaultMode === 'surprise' ? 'surprise' : 'none'}
            </span>
            <button type="button" disabled={running} onClick={() => setEditing(true)}
              className="w-fit rounded-md border bg-sunk px-2.5 py-1.5 text-sm font-medium disabled:opacity-50">
              Edit and run again
            </button>
          </div>
        )}
      </Panel>

      <Panel>
        <h2 className="sr-only">Run graph</h2>
        <ResultBanner status={s.status} plugin={plugin} result={s.result} steps={s.steps}
          runningStep={s.running}
          hiddenFault={hiddenFault} error={s.error}
          action={s.status === 'done' && s.result?.outcome === 'failure' && (
            <button type="button" onClick={() => s.setPage('diagnosis')}
              className="rounded-md bg-foreground px-3 py-2 font-semibold whitespace-nowrap text-background">
              Diagnose this run →
            </button>
          )} />
        <InstrumentStrip steps={s.steps} />
        {s.meta && (
          <div className="border-b border-dashed px-3.5 py-2.5 text-[13px] text-muted-foreground">
            Request: <q className="text-foreground italic">{s.meta.request_text}</q>
          </div>
        )}
        {s.steps.length > 0 || running ? (
          <RunGraph steps={s.steps} label={plugin.stepLabel} selectedId={s.selectedId} onSelect={s.select}
            runningId={running ? (s.steps.at(-1)?.id ?? null) : null} final={final} />
        ) : (
          <div className="grid h-[320px] place-items-center px-6 text-center text-sm text-muted-foreground">
            The agent’s steps will appear here, grouped by LLM turn, with arrows showing which earlier steps each one used.
          </div>
        )}
        <Legend />
      </Panel>

      <Panel title="Step details" sub={selected ? `step #${selected.id}` : 'click a step'} className="lg:col-span-2 xl:col-span-1">
        <div className="p-3.5">
          <StepDetails step={selected} label={plugin.stepLabel} onSelect={s.select}
            emptyText={running ? 'Steps appear as the agent takes them. Click one to inspect it.'
              : 'Run the agent, then click any step to see what went in, what came out, and which earlier steps it used.'} />
        </div>
      </Panel>
    </div>
  )
}

function Legend() {
  const chip = 'inline-flex items-center gap-1.5'
  const sw = 'h-3.5 w-[22px] rounded-[3px] border bg-card'
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t px-3.5 py-3 text-xs text-muted-foreground">
      <b className="font-mono text-[11px] tracking-wider uppercase">Later screens</b>
      <span className={chip}><span className={cn(sw, 'border-bad shadow-[0_0_0_3px_var(--bad-soft)]')} />culprit</span>
      <span className={chip}><span className={cn(sw, 'bg-gradient-to-r from-card to-bad-soft')} />suspicion heat</span>
      <span className={chip}><span className={cn(sw, 'border-dashed bg-sunk opacity-70')} />cached on replay</span>
      <span className={chip}><span className={cn(sw, 'border-recorder bg-recorder-soft')} />edited step</span>
    </div>
  )
}
