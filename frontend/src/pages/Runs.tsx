// Runs (every captured run, with search and filters) and Diagnoses (failed runs only, most
// suspicious first, each with its culprit and the top reason).

import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { RunsTable } from '@/components/RunsTable'
import { Loading, Problem } from '@/components/StateBox'
import { useAgent } from '@/layout/agentContext'
import { cn } from '@/lib/utils'
import type { SourceFilter } from '@/types/dashboard'

const PAGE = 25
const SOURCES: [SourceFilter, string][] = [['app', 'From the app'], ['live', 'Live'], ['replay', 'Replays'], ['generated', 'Dataset'], ['imported', 'Imported'], ['all', 'All']]

export function Runs({ mode }: { mode: 'runs' | 'diagnoses' }) {
  const { agent, canRun } = useAgent()
  const diagnoses = mode === 'diagnoses'
  const [source, setSource] = useState<SourceFilter>(canRun ? 'app' : 'imported')
  const [outcome, setOutcome] = useState<'' | 'success' | 'failure'>('')
  const [q, setQ] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)

  useEffect(() => { const t = setTimeout(() => { setQuery(q); setPage(0) }, 300); return () => clearTimeout(t) }, [q])

  const data = useApi(() => api.runs(agent, {
    source, q: query, limit: PAGE, offset: page * PAGE,
    outcome: diagnoses ? 'failure' : outcome || undefined, sort: diagnoses ? 'suspicion' : 'recent',
  }), [agent, source, outcome, query, page, mode])

  const seg = (active: boolean) => cn('rounded-[5px] px-2.5 py-1 font-medium whitespace-nowrap text-muted-foreground', active && 'bg-card text-foreground shadow-[0_0_0_1px_var(--border)]')

  return (
    <div className="grid gap-4">
      <div>
        <span className="bb-label">{diagnoses ? 'Failure diagnosis' : 'Execution data'}</span>
        <h1 className="m-0 font-display text-2xl font-bold">{diagnoses ? 'Diagnoses' : 'Runs'}</h1>
        <p className="m-0 text-[13px] text-muted-foreground">
          {diagnoses ? 'Every failed run with the step the model blames, most suspicious first. Open one to see the full finding.'
            : 'Every run the Black Box recorded. Open a run to see its graph, or a failed one to see its diagnosis.'}
        </p>
      </div>
      <Panel>
        <div className="flex flex-wrap items-center gap-3 border-b px-3.5 py-3">
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search run id, task or request…" aria-label="Search runs"
            className="h-9 min-w-[220px] flex-1 rounded-md border bg-sunk px-3 text-sm" />
          <div className="flex max-w-full overflow-x-auto rounded-[7px] border bg-sunk p-[3px] text-sm" role="group" aria-label="Source">
            {SOURCES.map(([s, label]) => <button key={s} type="button" aria-pressed={source === s} onClick={() => { setSource(s); setPage(0) }} className={seg(source === s)}>{label}</button>)}
          </div>
          {!diagnoses && (
            <div className="flex rounded-[7px] border bg-sunk p-[3px] text-sm" role="group" aria-label="Outcome">
              {([['', 'Any'], ['failure', 'Failed'], ['success', 'Succeeded']] as const).map(([o, label]) => (
                <button key={o} type="button" aria-pressed={outcome === o} onClick={() => { setOutcome(o); setPage(0) }} className={seg(outcome === o)}>{label}</button>
              ))}
            </div>
          )}
        </div>
        {data.loading ? <Loading what="runs" /> : data.error || !data.data ? <Problem message={data.error ?? 'No data'} /> : (
          <>
            <RunsTable agent={agent} rows={data.data.items} showReason={diagnoses}
              empty={diagnoses ? 'No failed runs here.' : 'No runs match.'} />
            <div className="flex flex-wrap items-center justify-between gap-2 px-3.5 py-2.5 text-xs text-muted-foreground">
              <span>{data.data.total} run{data.data.total === 1 ? '' : 's'}{data.data.total > PAGE ? ` · page ${page + 1} of ${Math.ceil(data.data.total / PAGE)}` : ''}</span>
              {data.data.total > PAGE && (
                <span className="flex gap-2">
                  <button type="button" disabled={page === 0} onClick={() => setPage(page - 1)} className="rounded-md border bg-card px-2.5 py-1 disabled:opacity-40">← Previous</button>
                  <button type="button" disabled={(page + 1) * PAGE >= data.data.total} onClick={() => setPage(page + 1)} className="rounded-md border bg-card px-2.5 py-1 disabled:opacity-40">Next →</button>
                </span>
              )}
            </div>
          </>
        )}
      </Panel>
    </div>
  )
}
