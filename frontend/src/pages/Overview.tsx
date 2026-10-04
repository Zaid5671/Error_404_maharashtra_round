// Overview: start a run, the agent's numbers at a glance (all real: counted from saved runs and
// the model report), recent runs, prepared demo runs, and how the Black Box works.

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Link } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { SeenBadge } from '@/components/FaultPicker'
import { Panel } from '@/components/Panel'
import { RunsTable } from '@/components/RunsTable'
import { Loading, Problem } from '@/components/StateBox'
import { useAgent } from '@/layout/agentContext'
import { pct } from '@/lib/format'
import { cn } from '@/lib/utils'

export function Overview() {
  const { agent, info, canRun } = useAgent()
  const [scope, setScope] = useState<'app' | 'all'>('app')
  const data = useApi(() => Promise.all([api.overview(agent, scope), api.runs(agent, { source: scope, limit: 8 })]), [agent, scope])

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="bb-label">Overview</span>
          <h1 className="m-0 font-display text-2xl font-bold">{info?.title ?? agent}</h1>
          {info?.description && <p className="m-0 max-w-[70ch] text-[13px] text-muted-foreground">{info.description}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="grid grid-cols-2 rounded-[7px] border bg-sunk p-[3px] text-sm" role="group" aria-label="Which runs to count">
            {(['app', 'all'] as const).map((s) => (
              <button key={s} type="button" aria-pressed={scope === s} onClick={() => setScope(s)}
                className={cn('rounded-[5px] px-2.5 py-1 font-medium whitespace-nowrap text-muted-foreground', scope === s && 'bg-card text-foreground shadow-[0_0_0_1px_var(--border)]')}>
                {s === 'app' ? 'Runs from the app' : 'Including dataset'}
              </button>
            ))}
          </div>
          {canRun ? (
            <Link to={`/${agent}/new`} className="inline-flex items-center gap-1.5 rounded-[7px] bg-recorder px-4 py-2.5 font-display font-bold tracking-[0.03em] text-white">
              <Plus className="size-4" strokeWidth={3} /> New Run
            </Link>
          ) : (
            <span className="rounded-[7px] border border-dashed px-3 py-2 text-xs text-muted-foreground" title="Imported agents run outside the app">
              Imported agent: import traces in Training
            </span>
          )}
        </div>
      </div>

      {data.loading ? <Loading what="the overview" /> : data.error || !data.data ? <Problem message={data.error ?? 'No data'} /> : (() => {
        const [o, recent] = data.data
        return (
          <>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <Stat label="Runs" value={String(o.total_runs)} note={scope === 'app' ? 'Live runs and replays made in the app' : 'App runs plus the generated dataset'}>
                <Split parts={[[o.total_runs - o.failed_runs, 'bg-good/70', 'succeeded'], [o.failed_runs, 'bg-bad', 'failed']]} />
              </Stat>
              <Stat label="Failed runs" value={String(o.failed_runs)} tone="bad" note={`${pct(o.failed_share)} of runs · each has a diagnosis`}>
                <Split parts={[[o.failed_runs, 'bg-bad', 'failed'], [o.total_runs - o.failed_runs, 'bg-border', 'other']]} />
              </Stat>
              <Stat label="Diagnosis accuracy" value={o.top1 == null ? '—' : pct(o.top1)}
                note={o.top1 == null ? 'No model trained yet' : `Culprit ranked #1 on test runs · unseen faults ${pct(o.unseen_top1 ?? 0)}`}>
                {o.top1 != null && <Split parts={[[o.top1, 'bg-foreground', 'found'], [1 - o.top1, 'bg-border', 'missed']]} />}
              </Stat>
              <Stat label="Replay success" value={o.replays ? `${o.replays_fixed} / ${o.replays}` : '—'} tone="good"
                note={o.replays ? `replays turned ✗ into ✓ (${pct(o.replay_success ?? 0)})` : 'No fixes replayed yet'}>
                {o.replays > 0 && <Split parts={[[o.replays_fixed, 'bg-good', 'fixed'], [o.replays - o.replays_fixed, 'bg-bad/60', 'still wrong']]} />}
              </Stat>
            </div>

            <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
              <Panel title="Recent runs" sub={<Link to={`/${agent}/runs`} className="font-medium text-recorder-ink">View all →</Link>}>
                <RunsTable agent={agent} rows={recent.items} compact
                  empty={canRun ? 'No runs yet. Press New Run to start one.' : 'No runs yet. Import traces in Training.'} />
              </Panel>
              <div className="grid gap-4">
                {o.demo_runs.length > 0 && (
                  <Panel title="Demo runs" sub="prepared failures · fault hidden until Reveal">
                    <ul className="m-0 grid list-none gap-1.5 p-3.5">
                      {o.demo_runs.map((d, i) => (
                        <li key={d.run_id}>
                          <Link to={`/${agent}/runs/${d.run_id}/diagnosis`} className="grid gap-0.5 rounded-md border bg-sunk px-2.5 py-2 hover:border-recorder">
                            <span className="flex items-center justify-between gap-2">
                              <span className="text-xs font-semibold">Demo run {i + 1}</span><SeenBadge seen={d.seen} />
                            </span>
                            <span className="truncate text-xs text-muted-foreground">{d.request_text}</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </Panel>
                )}
                <Panel title="How it works">
                  <ol className="m-0 grid list-none gap-2.5 p-3.5 text-[13px]">
                    {[
                      ['Record', 'every step the agent takes: inputs, outputs, and which earlier steps it used'],
                      ['Learn normal', 'from successful runs: usual values, ranges, and what the request words mean'],
                      ['Diagnose', 'a failed run: score every step, name the culprit, explain why'],
                      ['Replay', 'from the culprit with a fix, reusing every step before it'],
                    ].map(([k, v], i) => (
                      <li key={k} className="grid grid-cols-[22px_minmax(0,1fr)] gap-2">
                        <span className="grid size-5 place-items-center rounded-full border font-mono text-[11px] font-semibold">{i + 1}</span>
                        <span><strong>{k}</strong> {v}.</span>
                      </li>
                    ))}
                  </ol>
                </Panel>
              </div>
            </div>
          </>
        )
      })()}
    </div>
  )
}

function Stat({ label, value, note, tone, children }: { label: string; value: string; note: string; tone?: 'bad' | 'good'; children?: React.ReactNode }) {
  return (
    <Panel className="grid content-start gap-1.5 p-4">
      <span className="bb-label">{label}</span>
      <span className={cn('bb-gauge text-[40px] leading-none font-bold', tone === 'bad' && 'text-bad', tone === 'good' && 'text-good')}>{value}</span>
      {children}
      <p className="m-0 text-[12.5px] text-muted-foreground">{note}</p>
    </Panel>
  )
}

/** A thin proportion bar: [amount, colour class, label] parts. */
function Split({ parts }: { parts: [number, string, string][] }) {
  const total = parts.reduce((n, [v]) => n + v, 0)
  if (!total) return null
  return (
    <div className="flex h-2 overflow-hidden rounded-full bg-sunk" role="img" aria-label={parts.map(([v, , l]) => `${l} ${Math.round((v / total) * 100)}%`).join(', ')}>
      {parts.map(([v, cls, l]) => v > 0 && <span key={l} className={cls} style={{ width: `${(v / total) * 100}%` }} />)}
    </div>
  )
}
