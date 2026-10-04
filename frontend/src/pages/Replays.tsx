// Replays: every fix that was tried, what it changed, and whether it turned ✗ into ✓.

import { useNavigate } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { Loading, Problem } from '@/components/StateBox'
import { useAgent } from '@/layout/agentContext'
import { ago } from '@/lib/format'
import { cn } from '@/lib/utils'

export function Replays() {
  const { agent, canRun } = useAgent()
  const navigate = useNavigate()
  const data = useApi(() => api.replays(agent), [agent])
  const th = 'border-b px-3 py-2 text-left font-mono text-[10.5px] font-semibold tracking-wider whitespace-nowrap text-muted-foreground uppercase'
  const td = 'border-b px-3 py-2 align-top'

  return (
    <div className="grid gap-4">
      <div>
        <span className="bb-label">Checkpointed replay · alternative execution</span>
        <h1 className="m-0 font-display text-2xl font-bold">Replays</h1>
        <p className="m-0 text-[13px] text-muted-foreground">Each replay edited one step and re-ran the agent from there, reusing every step before it. Open one to compare it with the original.</p>
      </div>
      <Panel>
        {data.loading ? <Loading what="replays" /> : data.error || !data.data ? <Problem message={data.error ?? 'No data'} /> : data.data.length === 0 ? (
          <p className="m-0 p-4 text-sm text-muted-foreground">
            {canRun ? 'No replays yet. Open a failed run’s diagnosis and press “Fix it in Replay”.' : 'Imported agents run outside the app, so they can’t be replayed here.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr>
                  <th className={th}>Original run</th><th className={th}>Edited step</th><th className={th}>Result</th>
                  <th className={cn(th, 'text-right')}>Reused</th><th className={cn(th, 'text-right')}>Re-run</th>
                  <th className={cn(th, 'text-right')}>LLM calls saved</th><th className={th}>When</th>
                </tr>
              </thead>
              <tbody>
                {data.data.map((r) => {
                  const open = () => r.parent_run_id && navigate(`/${agent}/compare/${r.parent_run_id}/${r.run_id}`)
                  const fixed = r.parent_outcome === 'failure' && r.outcome === 'success'
                  return (
                    <tr key={r.run_id} tabIndex={0} onClick={open} onKeyDown={(e) => e.key === 'Enter' && open()} className="cursor-pointer hover:bg-sunk focus-visible:bg-sunk">
                      <td className={cn(td, 'max-w-[300px]')}>
                        <div className="truncate font-mono text-xs">{r.parent_run_id}</div>
                        <div className="truncate text-xs text-muted-foreground">{r.request_text}</div>
                      </td>
                      <td className={cn(td, 'font-mono text-xs whitespace-nowrap')}>
                        <span className="rounded border border-recorder bg-recorder-soft px-1.5 text-recorder-ink">#{r.edited_step} {r.edited_name}</span>
                      </td>
                      <td className={td}>
                        <span className={cn('rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold whitespace-nowrap',
                          r.outcome === 'success' ? 'bg-good-soft text-good' : 'bg-bad-soft text-bad')}>
                          {r.parent_outcome === 'failure' ? '✗' : '✓'} → {r.outcome === 'success' ? '✓' : '✗'}{fixed ? ' fixed' : ''}
                        </span>
                      </td>
                      <td className={cn(td, 'text-right font-mono tabular-nums')}>{r.reused}</td>
                      <td className={cn(td, 'text-right font-mono tabular-nums')}>{r.rerun}</td>
                      <td className={cn(td, 'text-right font-mono tabular-nums')}>{r.llm_calls_saved}</td>
                      <td className={cn(td, 'text-xs whitespace-nowrap text-muted-foreground')}>{ago(r.created)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}
