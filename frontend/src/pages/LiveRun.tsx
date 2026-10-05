// Live Run: fill in a task, pick a fault, watch the agent's steps arrive as a graph.
// /:agent is the empty form; once the run starts the URL becomes /:agent/runs/:runId, which also
// opens any saved run (refresh, back button, shared links).

import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { getPlugin } from '@/agents/registry'
import type { Json } from '@/agents/types'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { FaultPicker } from '@/components/FaultPicker'
import { InstrumentStrip } from '@/components/InstrumentStrip'
import { Panel } from '@/components/Panel'
import { RecorderTrack, type Tick } from '@/components/RecorderTrack'
import { ResultBanner } from '@/components/ResultBanner'
import { Problem } from '@/components/StateBox'
import { RunGraph } from '@/components/graph/RunGraph'
import { StepDetails } from '@/components/panels/StepDetails'
import { cn } from '@/lib/utils'
import { useAgent } from '@/layout/agentContext'
import { useLiveRun, useSession } from '@/store/runStore'

// One live stream at a time. It lives outside the component, so moving from /:agent to
// /:agent/runs/:runId (a remount) doesn't cut the stream.
let stream: AbortController | null = null

export function LiveRun() {
  const { agent = 'pizza', runId } = useParams()
  const navigate = useNavigate()
  const live = useLiveRun()
  const session = useSession()
  const plugin = useMemo(() => getPlugin(agent), [agent])
  const formData = useApi(() => api.catalog(agent), [agent])
  const task = session.drafts[agent] ?? plugin.defaultTask
  const [loadError, setLoadError] = useState<string | null>(null)
  const { canRun } = useAgent()

  // on the form page: the run starting, or an error before it got a run id (e.g. a rejected order)
  const showingLive = runId ? live.meta?.run_id === runId : live.status === 'running' || (live.status === 'error' && !live.meta)
  const running = live.status === 'running'

  // A run opened by URL (refresh or link): load it unless it's the one streaming right now.
  useEffect(() => {
    setLoadError(null)
    if (!runId || live.meta?.run_id === runId) return
    api.run(agent, runId).then((run) => {
      if (useLiveRun.getState().status !== 'running') useLiveRun.getState().loadRun(run)
    }, (e: Error) => setLoadError(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agent, runId])

  // When the server names the new run, move to its URL.
  useEffect(() => {
    if (!runId && running && live.meta?.run_id) navigate(`/${agent}/runs/${live.meta.run_id}`)
  }, [agent, runId, running, live.meta?.run_id, navigate])

  async function run(e: React.FormEvent) {
    e.preventDefault()
    if (running) return
    stream?.abort()
    stream = new AbortController()
    const { faultMode, faultType } = session
    live.begin({ mode: faultMode, type: faultMode === 'choose' ? faultType : null })
    await api.startRun(
      { agent, task, fault_mode: faultMode === 'none' ? 'none' : 'surprise', fault_type: faultMode === 'choose' ? faultType : null },
      live.applyEvent, stream.signal,
    )
  }

  if (runId && loadError) return <Problem message={loadError} back={{ to: `/${agent}/runs`, label: 'Back to runs' }} />
  if (!runId && !canRun) {
    return <Problem message={`“${agent}” is an imported agent: it runs outside the app, so it can’t be run here. Import its traces in Training instead.`}
      back={{ to: `/${agent}/training`, label: 'Go to Training' }} />
  }

  const view = showingLive ? live : null
  const steps = view?.steps ?? []
  const selected = steps.find((x) => x.id === live.selectedId) ?? null
  const final = view?.status === 'done' && view.result ? (view.result.outcome === 'success' ? 'good' : 'bad') : null
  const runFault = showingLive ? live.startedWith : null
  const hidden = !!runFault && runFault.mode !== 'none'
  const showForm = !runId

  const ticks: Tick[] = steps.map((s, i) => ({
    id: s.id, name: s.name,
    kind: final && i === steps.length - 1 ? (final === 'good' ? 'ok' : 'bad') : 'done',
  }))
  if (view?.running && !steps.some((s) => s.id === view.running!.id)) ticks.push({ ...view.running, kind: 'running' })

  return (
    <div className={cn('grid items-start gap-4',
      showForm ? 'xl:grid-cols-[300px_minmax(0,1fr)_300px]' : 'xl:grid-cols-[220px_minmax(0,1fr)_300px]',
      'grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)]')}>

      <Panel title={plugin.title} sub={`${agent} agent`}>
        {showForm ? (
          <form className="grid grid-cols-[minmax(0,1fr)] gap-3.5 p-3.5" onSubmit={run}>
            <plugin.TaskForm task={task} onChange={(t: Json) => session.setDraft(agent, t)} formData={formData.data} />
            <FaultPicker agent={agent} />
            <button type="submit" disabled={running || (session.faultMode === 'choose' && !session.faultType)}
              className="rounded-[7px] bg-recorder p-2.5 font-display text-[15px] font-bold tracking-[0.03em] text-white disabled:cursor-progress disabled:opacity-60">
              {running ? 'Running…' : 'Run'}
            </button>
          </form>
        ) : (
          <div className="grid gap-3 p-3.5">
            {view?.meta && <plugin.TaskSummary task={view.meta.task} />}
            {runFault && (
              <span className="font-mono text-[11px] font-semibold tracking-wider text-recorder-ink uppercase">
                {runFault.mode === 'none' ? 'Fault: none' : runFault.mode === 'surprise' ? 'Fault: hidden (surprise)' : `Fault: ${runFault.type}`}
              </span>
            )}
            <Link to={`/${agent}/new`} aria-disabled={running}
              className={cn('w-fit rounded-md border bg-sunk px-2.5 py-1.5 text-sm font-medium', running && 'pointer-events-none opacity-50')}>
              New run
            </Link>
          </div>
        )}
      </Panel>

      <Panel>
        <h2 className="sr-only">Run graph</h2>
        <ResultBanner status={view?.status ?? 'idle'} plugin={plugin} result={view?.result ?? null} steps={steps}
          runningStep={view?.running ?? null} hiddenFault={hidden} error={view?.error ?? null}
          action={view?.status === 'done' && view.result?.outcome === 'failure' && runId && (
            <Link to={`/${agent}/runs/${runId}/diagnosis`}
              className="rounded-md bg-foreground px-3 py-2 font-semibold whitespace-nowrap text-background">
              Diagnose this run →
            </Link>
          )} />
        <InstrumentStrip steps={steps} />
        {view?.meta && (
          <div className="border-b border-dashed px-3.5 py-2.5 text-[13px] text-muted-foreground">
            Request: <q className="text-foreground italic">{view.meta.request_text}</q>
          </div>
        )}
        {steps.length > 0 ? (
          <RunGraph steps={steps} label={plugin.stepLabel} selectedId={live.selectedId} onSelect={live.select}
            runningId={running ? (steps.at(-1)?.id ?? null) : null} final={final} />
        ) : (
          <div className="grid h-[300px] place-items-center px-6 text-center text-sm text-muted-foreground">
            {runId && !view ? 'Loading the run…' : running ? 'Starting the agent…'
              : 'The agent’s steps will appear here as it works, grouped by LLM turn, with arrows showing which earlier steps each one used.'}
          </div>
        )}
        <RecorderTrack title="Recorder" ticks={ticks}
          right={running ? `recording · ${steps.length} steps` : final ? `${steps.length} steps · ${final === 'good' ? '✓' : '✗'}` : 'waiting'} />
      </Panel>

      <Panel title="Step details" sub={selected ? `step #${selected.id}` : 'click a step'} className="lg:col-span-2 xl:col-span-1">
        <div className="p-3.5">
          <StepDetails step={selected} steps={steps} label={plugin.stepLabel} onSelect={live.select}
            emptyText={running ? 'Steps appear as the agent takes them. Click one to inspect it.'
              : 'Run the agent, then click any step to see what went in, what came out, and which earlier steps it used.'} />
        </div>
      </Panel>
    </div>
  )
}
