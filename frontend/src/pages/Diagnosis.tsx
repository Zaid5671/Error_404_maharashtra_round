// Diagnosis: every step shaded by suspicion, the culprit and the path its output took, and the
// finding: why this step, the top suspects, and a button that reveals the planted fault (if any),
// so anyone can check the model's answer.

import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { getPlugin } from '@/agents/registry'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { RecorderTrack } from '@/components/RecorderTrack'
import { Loading, Problem } from '@/components/StateBox'
import { RunGraph } from '@/components/graph/RunGraph'
import { StepDetails } from '@/components/panels/StepDetails'
import { pct } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useAgent } from '@/layout/agentContext'
import type { Diagnosis as DiagnosisT, Run } from '@/types/contract'


export function Diagnosis() {
  const { agent = 'pizza', runId = '' } = useParams()
  const plugin = getPlugin(agent)
  const data = useApi(() => Promise.all([api.run(agent, runId), api.diagnose(agent, runId)]), [agent, runId])
  const [selected, setSelected] = useState<number | null>(null)

  if (data.loading) return <Loading what="the diagnosis" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} back={{ to: `/${agent}/runs`, label: 'Back to runs' }} />
  const [run, diag] = data.data
  const failed = run.outcome === 'failure'
  const step = run.steps.find((s) => s.id === selected) ?? null
  const final = failed ? 'bad' : 'good'

  return (
    <div className="grid items-start gap-4 grid-cols-1 xl:grid-cols-[minmax(0,1fr)_390px]">
      <Panel>
        <div className="flex min-h-[58px] flex-wrap items-center gap-3 border-b px-3.5 py-3">
          <span className={cn('rounded px-2 py-0.5 font-mono text-[11px] font-semibold tracking-wider uppercase',
            failed ? 'bg-bad-soft text-bad' : 'bg-good-soft text-good')}>{failed ? '✗ Failed' : '✓ No failure'}</span>
          <span className="min-w-[200px] flex-1">
            {failed ? <>{plugin.resultLine(run)} <span className="text-muted-foreground">Shading shows how suspicious each step is.</span></>
              : 'This run succeeded, so there is nothing to diagnose.'}
          </span>
        </div>
        <RunGraph steps={run.steps} label={plugin.stepLabel} final={final} selectedId={selected} onSelect={setSelected}
          scores={failed ? diag.scores : undefined} culpritId={diag.culprit} impactPath={diag.impact_path}
          tags={(s) => s.id === diag.culprit ? [['bad', 'CULPRIT'], ['score', pct(diag.scores[String(s.id)])]]
            : diag.impact_path.includes(s.id) ? [['plain', 'AFFECTED']] : []} />
        <RecorderTrack title="Suspicion" right={diag.culprit ? `culprit · step ${diag.culprit}` : 'all clear'}
          ticks={run.steps.map((s) => ({ id: s.id, name: s.name, kind: s.id === diag.culprit ? 'culprit' : 'heat', heat: failed ? diag.scores[String(s.id)] : 0 }))} />
        {failed && (
          <div className="flex flex-wrap gap-x-4 gap-y-2 border-t px-3.5 py-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-[2px] border bg-card" />innocent</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-[2px] bg-heat" />suspicious</span>
            <span className="inline-flex items-center gap-1.5"><span className="size-3 rounded-[2px] border-2 border-bad" />culprit</span>
            <span className="inline-flex items-center gap-1.5"><span className="h-[3px] w-3.5 bg-bad" />impact path</span>
          </div>
        )}
      </Panel>

      <div className="grid min-w-0 gap-4">
        {failed && diag.culprit ? <Finding agent={agent} run={run} diag={diag} />
          : (
            <Panel title="Diagnosis">
              <div className="grid gap-3 p-3.5">
                <p className="m-0 text-[13.5px]">The Black Box investigates failed runs. Every step of this one scored below 1% suspicion.</p>
                <Link to={`/${agent}/runs`} className="w-fit rounded-md bg-recorder px-3.5 py-2 font-semibold text-white">Back to runs</Link>
              </div>
            </Panel>
          )}
        {step && (
          <Panel title={`Step #${step.id}`} sub={failed ? `suspicion ${pct(diag.scores[String(step.id)])}` : undefined}>
            <div className="p-3.5">
              <StepDetails step={step} steps={run.steps} label={plugin.stepLabel} onSelect={setSelected} emptyText="" />
            </div>
          </Panel>
        )}
      </div>
    </div>
  )
}

function Finding({ agent, run, diag }: { agent: string; run: Run; diag: DiagnosisT }) {
  const [revealed, setRevealed] = useState(false)
  const { canRun } = useAgent()
  const name = Object.fromEntries(run.steps.map((s) => [s.id, s.name]))
  const culprit = diag.culprit!
  const max = Math.max(...diag.reasons.map((r) => r.shap), 1e-9)
  const label = 'bb-label block'

  return (
    <Panel className="border-bad" headerClassName="border-bad bg-bad-soft"
      title={<span className="text-bad">Finding · probable cause</span>} sub={<span className="font-mono">{run.run_id}</span>}>
      <div className="grid gap-4 p-3.5">
        <div className="grid gap-1.5">
          <span className={label}>Culprit</span>
          <div className="font-display text-xl leading-tight font-bold text-balance">
            Step {culprit} · <span className="font-mono text-[17px]">{name[culprit]}</span>
          </div>
          <div className="flex items-baseline gap-2">
            <span className="bb-gauge text-[34px] leading-none font-bold text-bad">{pct(diag.scores[String(culprit)])}</span>
            <span className="text-xs text-muted-foreground">suspicion score</span>
          </div>
        </div>
        <p className="m-0 text-[13.5px] leading-relaxed">{diag.explanation}</p>

        <div className="grid gap-2.5">
          <span className={label}>Why this step</span>
          {diag.reasons.map((r) => (
            <div key={r.feature} className="grid gap-1">
              <div className="flex justify-between gap-2.5 text-[12.5px]">
                <span className="min-w-0 break-words">{r.label}</span>
                <span className="font-mono text-muted-foreground">+{r.shap.toFixed(1)}</span>
              </div>
              <div className="h-[7px] overflow-hidden rounded bg-sunk"><div className="h-full rounded bg-bad" style={{ width: `${(r.shap / max) * 100}%` }} /></div>
            </div>
          ))}
        </div>

        <div className="grid gap-1.5">
          <span className={label}>Top suspects</span>
          <ol className="m-0 grid list-none gap-1 p-0">
            {diag.ranking.slice(0, 3).map((id, i) => (
              <li key={id} className={cn('grid grid-cols-[22px_minmax(0,1fr)_auto] items-center gap-2 rounded-md bg-sunk px-2 py-1.5 text-[13px]', i === 0 && 'bg-bad-soft')}>
                <span className="font-mono text-[11px] font-semibold text-muted-foreground">{i + 1}</span>
                <span className="truncate font-mono">#{id} {name[id]}</span>
                <span className="font-mono">{pct(diag.scores[String(id)])}</span>
              </li>
            ))}
          </ol>
        </div>

        {diag.impact_path.length > 0 && (
          <div className="grid gap-1.5">
            <span className={label}>Impact path</span>
            <div className="flex flex-wrap items-center gap-1.5 font-mono text-[12.5px]">
              {diag.impact_path.map((id, i) => (
                <span key={id} className="inline-flex items-center gap-1.5">
                  {i > 0 && <span aria-hidden="true">→</span>}
                  <span className="rounded border border-bad px-1.5 text-bad">#{id} {name[id]}</span>
                </span>
              ))}
              <span>→ wrong result</span>
            </div>
          </div>
        )}

        {revealed ? <Revealed run={run} diag={diag} /> : (
          <button type="button" onClick={() => setRevealed(true)} className="rounded-md border border-dashed px-2.5 py-2 text-left font-medium">
            Reveal hidden fault
            <span className="block text-xs font-normal text-muted-foreground">Check the model’s answer against the fault that was planted.</span>
          </button>
        )}
        {canRun ? (
          <Link to={`/${agent}/runs/${run.run_id}/replay`} className="w-fit rounded-md bg-recorder px-3.5 py-2 font-semibold text-white">
            Fix it in Replay →
          </Link>
        ) : <p className="m-0 text-xs text-muted-foreground">Replay isn’t available: this imported agent runs outside the app.</p>}
      </div>
    </Panel>
  )
}

function Revealed({ run, diag }: { run: Run; diag: DiagnosisT }) {
  const f = run.fault
  if (!f) {
    return (
      <div className="grid gap-1 rounded-md border bg-sunk px-3 py-2.5 text-[13px]">
        <span className="bb-label">Hidden fault</span>
        No fault was planted in this run: the agent went wrong on its own, so there is no answer key to check against.
      </div>
    )
  }
  const rank = diag.ranking.indexOf(f.step_id) + 1
  const found = rank === 1
  return (
    <div className={cn('grid gap-1 rounded-md border px-3 py-2.5 text-[13px]', found ? 'border-good bg-good-soft' : 'border-bad bg-bad-soft')}>
      <span className={cn('bb-label', found ? '!text-good' : '!text-bad')}>Hidden fault</span>
      <span><span className="font-mono">{f.type}</span> at <strong>step {f.step_id}</strong>: {f.detail}</span>
      <strong>{found ? '✓ The model found it (ranked #1).' : `✗ The model ranked it #${rank}.`}</strong>
    </div>
  )
}
