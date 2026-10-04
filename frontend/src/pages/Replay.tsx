// Replay: pick a step (the culprit by default), correct its output, and re-run the agent from that
// step. Steps before it are reused from the recording (greyed out, no LLM calls); the rest run
// again live. Tool steps: the edit replaces the tool's result. LLM steps: it replaces what the LLM chose.

import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { getPlugin } from '@/agents/registry'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Gauges } from '@/components/InstrumentStrip'
import { Panel } from '@/components/Panel'
import { RecorderTrack, type Tick } from '@/components/RecorderTrack'
import { Loading, Problem } from '@/components/StateBox'
import { RunGraph } from '@/components/graph/RunGraph'
import type { Tag } from '@/components/graph/StepNode'
import { cn } from '@/lib/utils'
import { useAgent } from '@/layout/agentContext'
import { createRunStore, useSession } from '@/store/runStore'
import type { Diagnosis, Run, Step } from '@/types/contract'
import { pct } from '@/lib/format'

type Json = Record<string, unknown>

export function Replay() {
  const { agent = 'pizza', runId = '' } = useParams()
  const { canRun } = useAgent()
  const data = useApi(() => Promise.all([api.run(agent, runId), api.diagnose(agent, runId)]), [agent, runId])
  if (!canRun) {
    return <Problem message={`“${agent}” is an imported agent: replaying needs the agent itself, which runs outside the app. Its diagnosis still works.`}
      back={{ to: `/${agent}/runs/${runId}/diagnosis`, label: 'Back to the diagnosis' }} />
  }
  if (data.loading) return <Loading what="the run" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} back={{ to: `/${agent}/runs`, label: 'Back to runs' }} />
  return <ReplayScreen agent={agent} run={data.data[0]} diag={data.data[1]} key={runId} />
}

function ReplayScreen({ agent, run, diag }: { agent: string; run: Run; diag: Diagnosis }) {
  const plugin = getPlugin(agent)
  const [useReplay] = useState(createRunStore)
  const replay = useReplay()
  const setLastReplay = useSession((s) => s.setLastReplay)
  const abort = useRef<AbortController | null>(null)
  const [stepId, setStepId] = useState<number>(diag.culprit ?? run.steps.at(-1)!.id)
  const target = run.steps.find((s) => s.id === stepId)!
  const [edits, setEdits] = useState<Json>(() => structuredClone(target.output))
  const [bad, setBad] = useState<Set<string>>(new Set())

  useEffect(() => () => abort.current?.abort(), [])
  useEffect(() => {
    if (replay.status === 'done' && replay.result) setLastReplay({ agent, original: run.run_id, replay: replay.result.run_id })
  }, [replay.status, replay.result, agent, run.run_id, setLastReplay])

  const started = replay.status !== 'idle'
  const running = replay.status === 'running'
  const changedKeys = Object.keys(edits).filter((k) => JSON.stringify(edits[k]) !== JSON.stringify(target.output[k]))

  function pickStep(id: number) {
    const s = run.steps.find((x) => x.id === id)!
    setStepId(id)
    setEdits(structuredClone(s.output))
    setBad(new Set())
  }

  async function go() {
    abort.current?.abort()
    abort.current = new AbortController()
    replay.begin()
    await api.replay({ agent, run_id: run.run_id, step_id: stepId, new_output: edits }, replay.applyEvent, abort.current.signal)
  }

  // Before replaying: the original run, marked up. During and after: reused steps + the new ones.
  const steps: Step[] = started ? [...run.steps.filter((s) => s.id < stepId), ...replay.steps] : run.steps
  const reused = run.steps.filter((s) => s.id < stepId).map((s) => s.id)
  const doneIds = new Set(replay.steps.map((s) => s.id))
  const tags = (s: Step): Tag[] =>
    s.id < stepId ? [['plain', 'REUSED']] : s.id === stepId ? [['accent', 'EDITED']]
      : !started ? [['plain', 'WILL RE-RUN']] : doneIds.has(s.id) ? [['good', 'RE-RUN']] : []
  const llmSaved = run.steps.filter((s) => s.id < stepId && s.llm).length
  const llmMade = replay.steps.filter((s) => s.id > stepId && s.llm).length
  const result = replay.result
  const fixed = result?.outcome === 'success' && run.outcome === 'failure'

  const ticks: Tick[] = steps.map((s) => ({
    id: s.id, name: s.name,
    kind: s.id < stepId ? 'reused' : s.id === stepId ? 'edited' : started ? 'rerun' : 'same',
  }))
  if (replay.running && !doneIds.has(replay.running.id)) ticks.push({ ...replay.running, kind: 'running' })

  return (
    <div className="grid items-start gap-4 grid-cols-1 lg:grid-cols-[340px_minmax(0,1fr)]">
      <Panel title="Edit a step" sub="then replay from it">
        <div className="grid gap-3.5 p-3.5">
          <label className="grid gap-1 text-xs font-medium text-muted-foreground" htmlFor="replay-step">
            Step to fix
            <select id="replay-step" className="h-8 min-w-0 rounded-md border bg-sunk px-2 text-sm text-foreground" value={stepId}
              disabled={started} onChange={(e) => pickStep(Number(e.target.value))}>
              {run.steps.map((s) => (
                <option key={s.id} value={s.id}>
                  #{s.id} {s.name}{s.id === diag.culprit ? ` · culprit ${pct(diag.scores[String(s.id)])}` : ''}{s.kind === 'llm' ? ' · LLM' : ''}
                </option>
              ))}
            </select>
          </label>
          {stepId === diag.culprit && diag.reasons[0] && (
            <div className="grid gap-0.5 rounded-md border bg-sunk px-2.5 py-2 text-[12.5px]">
              <span className="bb-label">From the diagnosis</span>
              <span className="break-words">{diag.reasons[0].label}</span>
            </div>
          )}
          <div className="grid gap-2.5">
            <span className="bb-label">{target.kind === 'llm' ? `What the LLM chose at step ${stepId}` : `Output of step ${stepId} · ${target.name}`}</span>
            {Object.entries(target.output).map(([k, original]) => (
              <Field key={`${stepId}-${k}`} name={k} original={original} value={edits[k]} disabled={started}
                onChange={(v) => setEdits((e) => ({ ...e, [k]: v }))}
                onValid={(ok) => setBad((b) => { const n = new Set(b); if (ok) n.delete(k); else n.add(k); return n })} />
            ))}
          </div>
          <p className="m-0 text-xs text-muted-foreground">
            Your edit replaces this step’s {target.kind === 'llm' ? 'choice' : 'output'} exactly, so fix every value that is wrong.{' '}
            {stepId > 1 ? `Steps 1–${stepId - 1} are reused from the recording; the rest` : 'Every step'} run again with the real LLM.
          </p>
          {started ? (
            <button type="button" className="rounded-[7px] border bg-sunk p-2 font-medium" disabled={running}
              onClick={() => useReplay.setState({ status: 'idle', meta: null, steps: [], running: null, reusedIds: [], result: null, error: null })}>
              Edit again
            </button>
          ) : (
            <button type="button" onClick={go} disabled={bad.size > 0 || changedKeys.length === 0}
              className="rounded-[7px] bg-recorder p-2.5 font-display text-[15px] font-bold tracking-[0.03em] text-white disabled:opacity-50">
              {changedKeys.length === 0 ? 'Change a value to replay' : `Replay from step ${stepId}`}
            </button>
          )}
        </div>
      </Panel>

      <Panel>
        <div className="flex min-h-[58px] flex-wrap items-center gap-3 border-b px-3.5 py-3" role="status">
          {!started && <><State tone="idle">Ready</State><span className="min-w-[200px] flex-1">Correct the wrong value on the left, then replay. Greyed steps will be reused, not re-run.</span></>}
          {running && <><State tone="running">● Replaying</State><span className="min-w-[200px] flex-1">
            {replay.running ? <>Step <strong>#{replay.running.id}</strong> · <span className="font-mono">{replay.running.name}</span></> : 'Restoring the checkpoint…'}
            {stepId > 1 && <span className="mt-0.5 block text-[12.5px] text-muted-foreground">Steps 1–{stepId - 1} came from the checkpoint instantly.</span>}</span></>}
          {replay.status === 'error' && <><State tone="bad">Error</State><span className="min-w-[200px] flex-1">{replay.error}</span></>}
          {replay.status === 'done' && result && (
            <>
              <State tone={result.outcome === 'success' ? 'good' : 'bad'}>
                {run.outcome === 'failure' ? (result.outcome === 'success' ? '✗ → ✓ Fixed' : '✗ → ✗ Still wrong') : result.outcome === 'success' ? '✓ → ✓' : '✓ → ✗'}
              </State>
              <span className="min-w-[200px] flex-1">
                {plugin.resultLine(result)}
                <span className="mt-0.5 block text-[12.5px] text-muted-foreground">
                  {fixed ? 'The fix is confirmed: changing only this step made the run correct.' : result.outcome === 'failure' ? 'This change wasn’t enough. Try another value or another step.' : ''}
                </span>
              </span>
              <Link to={`/${agent}/compare/${run.run_id}/${result.run_id}`} className="rounded-md bg-foreground px-3 py-2 font-semibold whitespace-nowrap text-background">
                Compare runs →
              </Link>
            </>
          )}
        </div>
        <Gauges items={[
          { k: 'Steps reused', v: String(reused.length) },
          { k: 'Steps re-run', v: String(started ? replay.steps.length : 0), sub: started ? undefined : `/ ${run.steps.length - reused.length}` },
          { k: 'LLM calls saved', v: String(llmSaved) },
          { k: 'LLM calls made', v: String(llmMade) },
        ]} />
        <RunGraph steps={steps} label={plugin.stepLabel} cachedIds={reused} editedId={stepId} tags={tags}
          runningId={running ? (replay.steps.at(-1)?.id ?? null) : null}
          final={replay.status === 'done' && result ? (result.outcome === 'success' ? 'good' : 'bad') : null} />
        <RecorderTrack title="Replay" ticks={ticks}
          right={started ? `${reused.length} reused · ${replay.steps.length} re-run` : `checkpoint after step ${stepId - 1}`} />
      </Panel>
    </div>
  )
}

function State({ tone, children }: { tone: 'idle' | 'running' | 'good' | 'bad'; children: React.ReactNode }) {
  return (
    <span className={cn('rounded px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wider whitespace-nowrap uppercase',
      tone === 'idle' && 'bg-sunk text-muted-foreground', tone === 'running' && 'bg-recorder-soft text-recorder-ink',
      tone === 'good' && 'bg-good-soft text-good', tone === 'bad' && 'bg-bad-soft text-bad')}>{children}</span>
  )
}

/** One output field, edited by its type: text, number, true/false, or JSON for lists and objects. */
function Field({ name, original, value, disabled, onChange, onValid }: {
  name: string; original: unknown; value: unknown; disabled: boolean
  onChange: (v: unknown) => void; onValid: (ok: boolean) => void
}) {
  const changed = JSON.stringify(value) !== JSON.stringify(original)
  const json = typeof original === 'object' && original !== null
  const [text, setText] = useState(() => (json ? JSON.stringify(value, null, 2) : ''))
  const [error, setError] = useState(false)
  const id = `edit-${name}`
  const control = cn('min-w-0 rounded-md border bg-sunk px-2 text-sm text-foreground', changed && 'border-recorder bg-recorder-soft')
  const was = useMemo(() => (json ? null : String(original)), [json, original])

  let input: React.ReactNode
  if (typeof original === 'boolean') {
    input = (
      <div className="inline-grid w-fit grid-flow-col overflow-hidden rounded-md border" role="group" aria-label={name}>
        {[true, false].map((b) => (
          <button key={String(b)} type="button" disabled={disabled} aria-pressed={value === b} onClick={() => onChange(b)}
            className={cn('px-3 py-1 font-mono text-xs text-muted-foreground', value === b && 'bg-card text-foreground shadow-[inset_0_0_0_1px_var(--border)]',
              value === b && changed && 'bg-recorder-soft')}>{String(b)}</button>
        ))}
      </div>
    )
  } else if (json) {
    input = (
      <textarea id={id} disabled={disabled} rows={Math.min(8, text.split('\n').length)} value={text}
        className={cn(control, 'py-1.5 font-mono text-xs', error && 'border-bad')}
        onChange={(e) => {
          setText(e.target.value)
          try { onChange(JSON.parse(e.target.value)); setError(false); onValid(true) } catch { setError(true); onValid(false) }
        }} />
    )
  } else if (typeof original === 'number') {
    input = <input id={id} type="number" disabled={disabled} className={cn(control, 'h-8')} value={String(value ?? '')}
      onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />
  } else {
    input = <input id={id} type="text" disabled={disabled} className={cn(control, 'h-8')} value={value == null ? '' : String(value)}
      onChange={(e) => onChange(original === null && e.target.value === '' ? null : e.target.value)} />
  }

  return (
    <div className={cn('grid gap-2 text-[12.5px]', json ? 'grid-cols-1' : 'grid-cols-[96px_minmax(0,1fr)] items-center')}>
      <label htmlFor={id} className="truncate font-mono text-muted-foreground">{name}</label>
      {input}
      {changed && was !== null && <span className="col-start-2 -mt-1 font-mono text-[11.5px] text-recorder-ink">was {was}</span>}
      {error && <span className="font-mono text-[11.5px] text-bad">not valid JSON yet</span>}
    </div>
  )
}
