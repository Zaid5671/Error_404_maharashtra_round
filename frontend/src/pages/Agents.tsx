// Agents: every agent the Black Box knows, adding an imported agent, and the selected agent's
// profile (its tools as seen in its runs, its task templates, its trained model).

import { useState } from 'react'
import { Plus } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { Loading, Problem } from '@/components/StateBox'
import { useAgent } from '@/layout/agentContext'
import { cn } from '@/lib/utils'

export function Agents() {
  const { agent, agents, refresh } = useAgent()
  const navigate = useNavigate()
  const [adding, setAdding] = useState(false)

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <span className="bb-label">Agents</span>
          <h1 className="m-0 font-display text-2xl font-bold">Agents</h1>
          <p className="m-0 max-w-[80ch] text-[13px] text-muted-foreground">
            The Black Box works with any agent. <strong>Connected</strong> agents plug in with code and can run, inject faults and replay here.
            <strong> Imported</strong> agents run somewhere else: import their traces, train a model, and diagnose their failures.
          </p>
        </div>
        <button type="button" onClick={() => setAdding((a) => !a)} className="inline-flex items-center gap-1.5 rounded-[7px] border border-recorder px-3.5 py-2 font-semibold text-recorder-ink hover:bg-recorder-soft">
          <Plus className="size-4" strokeWidth={3} /> Add agent
        </button>
      </div>

      {adding && <AddAgent onDone={(name) => { setAdding(false); refresh(); navigate(`/${name}/training`) }} />}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((a) => (
          <Link key={a.name} to={`/${a.name}/agents`}
            className={cn('grid gap-1.5 rounded-lg border bg-card p-4 hover:border-recorder', a.name === agent && 'border-recorder shadow-[0_0_0_1px_var(--recorder)]')}>
            <span className="flex items-center justify-between gap-2">
              <span className="font-mono font-semibold">{a.name}</span>
              <span className={cn('rounded-[3px] px-1.5 py-0.5 font-mono text-[9.5px] font-semibold tracking-wider',
                a.kind === 'connected' ? 'bg-good-soft text-good' : 'bg-llm-soft text-llm')}>{a.kind.toUpperCase()}</span>
            </span>
            <span className="font-medium">{a.title}</span>
            {a.description && <span className="line-clamp-2 text-xs text-muted-foreground">{a.description}</span>}
          </Link>
        ))}
      </div>

      <AgentProfile agent={agent} />
    </div>
  )
}

function AddAgent({ onDone }: { onDone: (name: string) => void }) {
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const control = 'h-9 rounded-md border bg-sunk px-3 text-sm text-foreground'

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try { onDone((await api.addAgent({ name, title, description })).name) } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  return (
    <Panel title="Add an imported agent">
      <form className="grid gap-3 p-3.5 md:grid-cols-[200px_minmax(0,1fr)]" onSubmit={submit}>
        <label htmlFor="new-name" className="grid gap-1 text-xs font-medium text-muted-foreground">Name (used in links)
          <input id="new-name" required value={name} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="support_bot" className={cn(control, 'font-mono')} />
        </label>
        <label htmlFor="new-title" className="grid gap-1 text-xs font-medium text-muted-foreground">Title
          <input id="new-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Customer support agent" className={control} />
        </label>
        <label htmlFor="new-desc" className="grid gap-1 text-xs font-medium text-muted-foreground md:col-span-2">What it does
          <input id="new-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Answers order questions using lookup and refund tools" className={control} />
        </label>
        <div className="flex flex-wrap items-center gap-3 md:col-span-2">
          <button type="submit" disabled={busy || !name} className="rounded-md bg-recorder px-3.5 py-2 font-semibold text-white disabled:opacity-50">Create and import traces →</button>
          {error && <span className="text-sm text-bad" role="alert">{error}</span>}
        </div>
      </form>
    </Panel>
  )
}

function AgentProfile({ agent }: { agent: string }) {
  const data = useApi(() => api.agent(agent), [agent])
  if (data.loading) return <Loading what="the agent" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} />
  const a = data.data
  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Panel title={`${a.title} · tools`} sub={`${a.tools.length} step types, as seen in ${a.n_runs} runs`}>
        {a.tools.length === 0 ? <p className="m-0 p-3.5 text-sm text-muted-foreground">No runs yet. Import traces in Training to see this agent’s steps.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr>{['Step', 'Kind', 'Reads', 'Writes'].map((h) => <th key={h} className="border-b px-3 py-2 text-left font-mono text-[10.5px] font-semibold tracking-wider text-muted-foreground uppercase">{h}</th>)}</tr>
              </thead>
              <tbody>
                {a.tools.map((t) => (
                  <tr key={t.name}>
                    <td className="border-b px-3 py-2 align-top">
                      <div className="font-mono font-medium">{t.name}</div>
                      {t.description && <div className="max-w-[46ch] text-xs text-muted-foreground">{t.description}</div>}
                    </td>
                    <td className="border-b px-3 py-2 align-top">
                      <span className={cn('rounded-[3px] px-1.5 py-px font-mono text-[10px] font-semibold', t.kind === 'llm' ? 'bg-llm-soft text-llm' : 'border bg-sunk text-muted-foreground')}>{t.kind.toUpperCase()}</span>
                    </td>
                    <td className="border-b px-3 py-2 align-top font-mono text-xs">{t.reads.join(', ') || '—'}</td>
                    <td className="border-b px-3 py-2 align-top font-mono text-xs">{t.writes.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <div className="grid gap-4">
        <Panel title="Profile">
          <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 p-3.5 text-[13px]">
            <dt className="text-muted-foreground">Kind</dt><dd className="m-0">{a.kind === 'connected' ? 'Connected: runs and replays in the app' : 'Imported: traces only'}</dd>
            {a.llm && <><dt className="text-muted-foreground">LLM</dt><dd className="m-0 font-mono text-xs break-words">{a.llm}</dd></>}
            <dt className="text-muted-foreground">Runs</dt><dd className="m-0"><span className="font-mono">{a.n_runs}</span> <span className="text-xs text-muted-foreground">({a.n_dataset_runs} dataset · {a.n_runs - a.n_dataset_runs} from the app)</span></dd>
            <dt className="text-muted-foreground">Templates</dt><dd className="m-0 font-mono">{a.templates.train.length} train · {a.templates.test.length} test</dd>
          </dl>
        </Panel>
        <Panel title="Diagnosis model" sub={<Link to={`/${agent}/training`} className="font-medium text-recorder-ink">Train →</Link>}>
          {a.model ? (
            <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 p-3.5 text-[13px]">
              <dt className="text-muted-foreground">Trained on</dt><dd className="m-0"><span className="font-mono">{a.model.n_train_runs}</span> <span className="text-xs text-muted-foreground">training runs ({a.model.n_train_runs - a.model.n_train_cases} clean successes · {a.model.n_train_cases} failures with a known culprit)</span></dd>
              <dt className="text-muted-foreground">Features</dt><dd className="m-0 font-mono">{a.model.features.length}</dd>
              <dt className="text-muted-foreground">Seen faults</dt><dd className="m-0 font-mono text-xs break-words">{a.model.seen_fault_types.join(', ') || '—'}</dd>
            </dl>
          ) : <p className="m-0 p-3.5 text-sm text-muted-foreground">Not trained yet.</p>}
        </Panel>
      </div>
    </div>
  )
}
