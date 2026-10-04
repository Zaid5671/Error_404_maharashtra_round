// A table of runs (Overview, Runs, Diagnoses). A failed row opens its diagnosis, any other row its graph.

import { useNavigate } from 'react-router'
import { ago, duration, pct } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { RunRow } from '@/types/dashboard'

const SOURCE: Record<string, string> = { live: 'live', replay: 'replay', generated: 'dataset', imported: 'imported' }

export function StatusPill({ outcome }: { outcome: string }) {
  const ok = outcome === 'success'
  return (
    <span className={cn('rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold whitespace-nowrap', ok ? 'bg-good-soft text-good' : 'bg-bad-soft text-bad')}>
      {ok ? '✓ success' : '✗ failed'}
    </span>
  )
}

/** compact: no Source or Agent time columns, for narrow panels (Overview). With showReason the
 *  Why column takes Agent time's place. */
export function RunsTable({ agent, rows, showReason = false, compact = false, empty }: { agent: string; rows: RunRow[]; showReason?: boolean; compact?: boolean; empty: string }) {
  const navigate = useNavigate()
  if (rows.length === 0) return <p className="m-0 p-4 text-sm text-muted-foreground">{empty}</p>
  const showTime = !compact && !showReason
  const open = (r: RunRow) => navigate(`/${agent}/runs/${r.run_id}${r.outcome === 'failure' ? '/diagnosis' : ''}`)
  const th = 'border-b px-3 py-2 text-left font-mono text-[10.5px] font-semibold tracking-wider whitespace-nowrap text-muted-foreground uppercase'
  const td = 'border-b px-3 py-2 align-top'
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr>
            <th className={th}>Run</th>{!compact && <th className={th}>Source</th>}<th className={th}>Status</th>
            <th className={cn(th, 'text-right')}>Steps</th>{showTime && <th className={cn(th, 'text-right')}>Agent time</th>}
            <th className={th}>Suspected step · suspicion</th>{showReason && <th className={th}>Why</th>}<th className={th}>When</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.run_id} tabIndex={0} onClick={() => open(r)} onKeyDown={(e) => e.key === 'Enter' && open(r)}
              className="cursor-pointer hover:bg-sunk focus-visible:bg-sunk">
              <td className={cn(td, compact ? 'max-w-[240px]' : 'max-w-[320px]')}>
                <div className="truncate font-mono text-xs">{r.run_id}</div>
                <div className="truncate text-xs text-muted-foreground">{r.request_text}</div>
              </td>
              {!compact && <td className={cn(td, 'font-mono text-xs text-muted-foreground')}>{SOURCE[r.source] ?? r.source}</td>}
              <td className={td}><StatusPill outcome={r.outcome} /></td>
              <td className={cn(td, 'text-right font-mono tabular-nums')}>{r.n_steps}</td>
              {showTime && <td className={cn(td, 'text-right font-mono whitespace-nowrap tabular-nums')}>{duration(r.duration_ms)}</td>}
              <td className={td}>
                {r.suspect ? (
                  <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                    <span className="rounded border border-bad bg-bad-soft px-1.5 font-mono text-xs text-bad">#{r.suspect.step_id} {r.suspect.name}</span>
                    <span className="font-mono text-xs text-muted-foreground" title="Suspicion score: how likely the model thinks this step caused the failure">{pct(r.suspect.score)}</span>
                  </span>
                ) : <span className="text-muted-foreground">—</span>}
              </td>
              {showReason && <td className={cn(td, 'min-w-[220px] text-xs text-muted-foreground')}>{r.suspect?.reason ?? '—'}</td>}
              <td className={cn(td, 'text-xs whitespace-nowrap text-muted-foreground')}>{ago(r.created)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
