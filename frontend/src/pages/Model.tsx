// Model: how well the agent's diagnosis model works (Accuracy), what it learned from (Training
// data), and how it does on each fault type, with a shortcut to run one (Faults).

import { NavLink, useNavigate } from 'react-router'
import { getPlugin } from '@/agents/registry'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { SeenBadge } from '@/components/FaultPicker'
import { Panel } from '@/components/Panel'
import { Loading, Problem } from '@/components/StateBox'
import { useAgent } from '@/layout/agentContext'
import { pct } from '@/lib/format'
import { cn } from '@/lib/utils'
import { useSession } from '@/store/runStore'
import { Report } from './Report'

type Tab = 'accuracy' | 'data' | 'faults'

export function Model({ tab }: { tab: Tab }) {
  const { agent } = useAgent()
  const tabs: [Tab, string, string][] = [['accuracy', 'Accuracy', ''], ['data', 'Training data', '/data'], ['faults', 'Faults', '/faults']]
  return (
    <div className="grid gap-4">
      <div>
        <span className="bb-label">Model evaluation</span>
        <h1 className="m-0 font-display text-2xl font-bold">Model</h1>
        <p className="m-0 text-[13px] text-muted-foreground">The diagnosis model for <span className="font-mono">{agent}</span>: trained on this agent’s runs, scored on runs it never saw.</p>
      </div>
      <nav className="flex w-fit gap-1 rounded-[7px] border bg-sunk p-[3px] text-sm" aria-label="Model sections">
        {tabs.map(([key, label, path]) => (
          <NavLink key={key} to={`/${agent}/model${path}`} end
            className={cn('rounded-[5px] px-3 py-1.5 font-medium whitespace-nowrap text-muted-foreground', tab === key && 'bg-card text-foreground shadow-[0_0_0_1px_var(--border)]')}>
            {label}
          </NavLink>
        ))}
      </nav>
      {tab === 'accuracy' && <Report />}
      {tab === 'data' && <TrainingData agent={agent} />}
      {tab === 'faults' && <Faults agent={agent} />}
    </div>
  )
}

function TrainingData({ agent }: { agent: string }) {
  const data = useApi(() => api.dataset(agent), [agent])
  if (data.loading) return <Loading what="the training data" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} />
  const d = data.data
  const used = (split: 'train' | 'test') => d.kinds.reduce((n, k) => n + (k.kind === 'clean' ? k[`${split}_success`] : 0) + (k.kind === 'clean' ? 0 : k[`${split}_failure`]), 0)
  const failed = d.kinds.reduce((n, k) => n + (k.kind === 'clean' ? 0 : k.test_failure), 0)
  const th = 'border-b px-3 py-2 text-right font-mono text-[10.5px] font-semibold tracking-wider whitespace-nowrap text-muted-foreground uppercase first:text-left'
  const td = 'border-b px-3 py-1.5 text-right font-mono tabular-nums first:text-left'
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {([
          ['Dataset runs', d.total, 'generated or imported; runs made in the app are never used'],
          ['Training split', d.train, `${d.templates.train.length} templates · ${used('train')} used: clean successes and failures with a known culprit`],
          ['Test split', d.test, `${d.templates.test.length} templates the model never saw · ${failed} failures scored`],
        ] as const).map(([k, v, note]) => (
          <Panel key={k} className="grid gap-1 p-4">
            <span className="bb-label">{k}</span>
            <span className="bb-gauge text-[40px] leading-none font-bold">{v}</span>
            <p className="m-0 text-[12.5px] text-muted-foreground">{note}</p>
          </Panel>
        ))}
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Panel title="Runs by kind" sub="successful / failed, per split">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead><tr><th className={th}>Kind</th><th className={th}>Train ✓</th><th className={th}>Train ✗</th><th className={th}>Test ✓</th><th className={th}>Test ✗</th></tr></thead>
              <tbody>
                {d.kinds.map((k) => (
                  <tr key={k.kind}>
                    <td className={td}>{k.kind === 'clean' ? 'clean (no fault)' : k.kind}</td>
                    <td className={td}>{k.train_success || '·'}</td><td className={td}>{k.train_failure || '·'}</td>
                    <td className={td}>{k.test_success || '·'}</td><td className={td}>{k.test_failure || '·'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="m-0 px-3.5 py-3 text-xs text-muted-foreground">
            The model learns “normal” from clean successful runs and the culprit from failed runs with a planted fault. A faulted run that still succeeded
            (the agent recovered) is kept but not used as a failure.
          </p>
        </Panel>
        <Panel title="Split by template" sub="no test task was seen in training">
          <div className="grid gap-3 p-3.5 text-xs">
            {(['train', 'test'] as const).map((s) => (
              <div key={s} className="grid gap-1.5">
                <span className="bb-label">{s === 'train' ? 'Training templates' : 'Test templates'}</span>
                <div className="flex flex-wrap gap-1">
                  {d.templates[s].map((t) => <span key={t} className="rounded border bg-sunk px-1.5 py-0.5 font-mono">{t}</span>)}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function Faults({ agent }: { agent: string }) {
  const { canRun } = useAgent()
  const navigate = useNavigate()
  const setFault = useSession((s) => s.setFault)
  const data = useApi(() => Promise.all([api.faults(agent), api.report(agent).catch(() => null), api.dataset(agent).catch(() => null)]), [agent])
  if (data.loading) return <Loading what="the faults" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} />
  const [allFaults, report, dataset] = data.data
  const faults = allFaults.filter((f) => !getPlugin(agent).hiddenFaults.includes(f.type))
  const acc = Object.fromEntries((report?.by_type ?? []).map((t) => [t.type, t]))
  const kinds = Object.fromEntries((dataset?.kinds ?? []).map((k) => [k.kind, k]))
  return (
    <Panel title="Fault catalogue" sub="from the agent; accuracy from the test runs">
      <div className="grid gap-2 p-3.5">
        {faults.map((f) => {
          const a = acc[f.type]
          return (
            <div key={f.type} className="grid grid-cols-1 items-center gap-x-4 gap-y-1.5 rounded-md border bg-sunk px-3 py-2.5 text-[13px] sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto]">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2"><span className="font-mono font-medium">{f.type}</span><SeenBadge seen={f.seen} />
                  <span className="rounded-[3px] border px-1.5 font-mono text-[9.5px] font-semibold text-muted-foreground">{f.family.toUpperCase()}</span></div>
                {f.step_name && <div className="text-xs text-muted-foreground">breaks <span className="font-mono">{f.step_name}</span></div>}
              </div>
              <div className="text-xs">
                {a ? <>Culprit found first in <strong className="font-mono">{pct(a.top1)}</strong> of {a.n} test runs · top 3 <span className="font-mono">{pct(a.top3)}</span></>
                  : <span className="text-muted-foreground">{notScored(kinds[f.type])}</span>}
              </div>
              {canRun && f.live ? (
                <button type="button" onClick={() => { setFault('choose', f.type); navigate(`/${agent}/new`) }}
                  className="w-fit rounded-md border border-recorder px-2.5 py-1 text-xs font-semibold whitespace-nowrap text-recorder-ink hover:bg-recorder-soft">
                  Run with this fault →
                </button>
              ) : <span className="text-xs text-muted-foreground">{f.family === 'llm' ? 'needs a re-run from step 1' : 'imported label'}</span>}
            </div>
          )
        })}
        {faults.length === 0 && <p className="m-0 text-sm text-muted-foreground">No fault types yet.</p>}
      </div>
    </Panel>
  )
}

/** Why a fault type has no accuracy, from the runs that have it. */
function notScored(k?: { train_success: number; train_failure: number; test_success: number; test_failure: number }) {
  const n = k ? k.train_success + k.train_failure + k.test_success + k.test_failure : 0
  if (!k || n === 0) return 'Not scored: the dataset has no runs with this fault'
  if (k.test_success + k.test_failure === 0) return `Not scored: its ${n} runs are all training runs`
  return `Not scored: the agent still got all ${k.test_success} test runs with it right, so there was no failure to find`
}
