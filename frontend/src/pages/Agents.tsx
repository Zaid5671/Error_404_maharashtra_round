// Agents: every agent the Black Box knows, adding one (connect an SDK agent by URL, or create an
// imported agent for traces), and the selected agent's profile: its tools, connection, templates
// and trained model.

import { useEffect, useState } from 'react'
import { Plus, X } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { KindBadge, OnlineDot } from '@/components/AgentBadges'
import { Panel } from '@/components/Panel'
import { Loading, Problem } from '@/components/StateBox'
import { useAgent } from '@/layout/agentContext'
import { cn } from '@/lib/utils'
import type { ProbeInfo } from '@/types/dashboard'

const control = 'h-9 rounded-md border bg-sunk px-3 text-sm text-foreground'

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
            The Black Box works with any agent. <strong>Built-in</strong> and <strong>connected</strong> agents can run, have faults planted and be replayed here.
            <strong> Imported</strong> agents run somewhere else: bring their traces to diagnose them.
          </p>
        </div>
        <button type="button" onClick={() => setAdding(true)} className="inline-flex items-center gap-1.5 rounded-[7px] border border-recorder px-3.5 py-2 font-semibold text-recorder-ink hover:bg-recorder-soft">
          <Plus className="size-4" strokeWidth={3} /> Add agent
        </button>
      </div>

      {adding && <AddAgentDialog onClose={() => setAdding(false)} onDone={(name) => { setAdding(false); refresh(); navigate(`/${name}/training`) }} />}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {agents.map((a) => (
          <Link key={a.name} to={`/${a.name}/agents`}
            className={cn('grid content-start gap-1.5 rounded-lg border bg-card p-4 hover:border-recorder', a.name === agent && 'border-recorder shadow-[0_0_0_1px_var(--recorder)]')}>
            <span className="flex items-center justify-between gap-2">
              <span className="font-mono font-semibold">{a.name}</span>
              <KindBadge a={a} />
            </span>
            <span className="font-medium">{a.title}</span>
            {a.description && <span className="line-clamp-2 text-xs text-muted-foreground">{a.description}</span>}
            {a.via === 'sdk' && (
              <span className="flex items-center gap-1.5 text-xs">
                <OnlineDot online={a.online} /><span className="truncate font-mono">{a.url}</span>
                <span className="text-muted-foreground">· {a.online ? 'online' : 'offline'}</span>
              </span>
            )}
          </Link>
        ))}
      </div>

      <AgentProfile agent={agent} onRemoved={() => { refresh(); navigate('/pizza/agents') }} />
    </div>
  )
}

// --- adding an agent -----------------------------------------------------------------------------

function AddAgentDialog({ onClose, onDone }: { onClose: () => void; onDone: (name: string) => void }) {
  const [mode, setMode] = useState<'connect' | 'import'>('connect')
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 grid place-items-start overflow-y-auto bg-black/45 px-4 py-10" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="add-agent-title" onClick={(e) => e.stopPropagation()}
        className="mx-auto w-full max-w-[640px] overflow-hidden rounded-lg border bg-card shadow-2xl">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 id="add-agent-title" className="m-0 font-display text-[13px] font-bold tracking-[0.07em] uppercase">Add an agent</h2>
          <button type="button" onClick={onClose} className="rounded p-1 text-muted-foreground hover:bg-sunk" aria-label="Close"><X className="size-4" /></button>
        </div>
        <div className="grid gap-4 p-4">
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2" role="radiogroup" aria-label="How to add the agent">
            {([['connect', 'Connect an agent', 'Your agent runs with our SDK. Everything works here: live runs, faults, replay, generating data.'],
              ['import', 'Import traces only', 'You only have log files. Diagnose and compare; no live runs or replay.']] as const).map(([m, title, text]) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
                className={cn('grid gap-1 rounded-lg border p-3 text-left', mode === m ? 'border-2 border-recorder bg-recorder-soft' : 'bg-sunk')}>
                <strong className="text-sm">{title}</strong>
                <span className="text-xs text-muted-foreground">{text}</span>
              </button>
            ))}
          </div>
          {mode === 'connect' ? <ConnectForm onDone={onDone} onCancel={onClose} /> : <ImportForm onDone={onDone} />}
        </div>
      </div>
    </div>
  )
}

const SNIPPET = `import blackbox_sdk as bb

@bb.tool                      # every tool you wrap is recorded
def search_flights(origin, dest, date): ...

client = bb.llm(OpenAI(...))  # every LLM call is recorded

bb.serve(run_agent, name="travel", port=8100,
         examples=[{"kind": "one_way", "task": {"request": "..."}}, ...],
         check=is_right)              # optional: says if a result is correct`

function ConnectForm({ onDone, onCancel }: { onDone: (name: string) => void; onCancel: () => void }) {
  const [name, setName] = useState('')
  const [url, setUrl] = useState('http://127.0.0.1:8100')
  const [probe, setProbe] = useState<ProbeInfo | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'test' | 'connect' | null>(null)

  async function test() {
    setBusy('test'); setError(null); setProbe(null)
    try {
      const info = await api.probeAgent(url)
      setProbe(info)
      if (!name) setName(info.name.toLowerCase().replace(/[^a-z0-9_-]/g, '_'))
    } catch (e) { setError((e as Error).message) } finally { setBusy(null) }
  }

  async function connect(e: React.FormEvent) {
    e.preventDefault()
    setBusy('connect'); setError(null)
    try { onDone((await api.connectAgent({ name, url })).name) } catch (err) { setError((err as Error).message) } finally { setBusy(null) }
  }

  const llmSteps = probe?.tools.filter((t) => t.kind === 'llm').length ?? 0
  return (
    <form className="grid gap-3.5" onSubmit={connect}>
      <details className="text-[13px]">
        <summary className="cursor-pointer font-semibold">1 · Add the SDK to your agent (a few lines)</summary>
        <pre className="mt-2 overflow-x-auto rounded-md bg-[#141820] p-3 font-mono text-xs leading-relaxed text-[#e5e9f0]">{SNIPPET}</pre>
        <p className="m-0 mt-1.5 text-xs text-muted-foreground">The SDK is in <span className="font-mono">sdk/blackbox_sdk</span>. Start your agent, then connect it here.</p>
      </details>
      <span className="text-[13px] font-semibold">2 · Connect it</span>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <label htmlFor="agent-url" className="grid gap-1 text-xs font-medium text-muted-foreground">Agent URL
          <input id="agent-url" required value={url} onChange={(e) => { setUrl(e.target.value); setProbe(null) }} className={cn(control, 'font-mono')} />
        </label>
        <label htmlFor="agent-name" className="grid gap-1 text-xs font-medium text-muted-foreground">Name (used in links)
          <input id="agent-name" required value={name} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="travel" className={cn(control, 'font-mono')} />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        <button type="button" onClick={test} disabled={!!busy || !url} className="rounded-md border bg-sunk px-3 py-1.5 text-sm font-semibold disabled:opacity-50">
          {busy === 'test' ? 'Testing…' : 'Test connection'}
        </button>
        <span className="text-xs text-muted-foreground">The Black Box asks the agent who it is.</span>
      </div>
      {probe && (
        <div className="grid gap-1 rounded-md border border-good bg-good-soft px-3 py-2.5 text-[13px]" role="status">
          <strong className="text-good">✓ Reached “{probe.title}”</strong>
          <span className="text-xs">
            {probe.tools.length} step types ({llmSteps} LLM, {probe.tools.length - llmSteps} tools) · {probe.examples.length} example tasks in {probe.kinds.length} kinds · {probe.sdk}
            {probe.has_check ? ' · checks its own results' : ''}
          </span>
          {probe.kinds.length < 4 && <span className="text-xs text-bad">Only {probe.kinds.length} kinds of task: the test split will be small. 4 or more is better.</span>}
        </div>
      )}
      {error && <p className="m-0 text-sm text-bad" role="alert">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2">
        <button type="button" onClick={onCancel} className="rounded-md border bg-sunk px-3.5 py-2 font-semibold">Cancel</button>
        <button type="submit" disabled={!!busy || !probe || !name} className="rounded-md bg-recorder px-3.5 py-2 font-semibold text-white disabled:opacity-50">
          {busy === 'connect' ? 'Connecting…' : 'Connect agent'}
        </button>
      </div>
      <p className="m-0 rounded-r-md border-l-[3px] border-recorder bg-recorder-soft px-3 py-2 text-xs">
        After connecting, go to <strong>Training → Generate data</strong>: the app runs the agent, breaks steps on purpose, and trains its diagnosis model.
      </p>
    </form>
  )
}

function ImportForm({ onDone }: { onDone: (name: string) => void }) {
  const [name, setName] = useState('')
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true); setError(null)
    try { onDone((await api.addAgent({ name, title, description })).name) } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  return (
    <form className="grid gap-3 sm:grid-cols-[200px_minmax(0,1fr)]" onSubmit={submit}>
      <label htmlFor="new-name" className="grid gap-1 text-xs font-medium text-muted-foreground">Name (used in links)
        <input id="new-name" required value={name} onChange={(e) => setName(e.target.value.toLowerCase())} placeholder="support_bot" className={cn(control, 'font-mono')} />
      </label>
      <label htmlFor="new-title" className="grid gap-1 text-xs font-medium text-muted-foreground">Title
        <input id="new-title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Customer support agent" className={control} />
      </label>
      <label htmlFor="new-desc" className="grid gap-1 text-xs font-medium text-muted-foreground sm:col-span-2">What it does
        <input id="new-desc" value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Answers order questions using lookup and refund tools" className={control} />
      </label>
      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <button type="submit" disabled={busy || !name} className="rounded-md bg-recorder px-3.5 py-2 font-semibold text-white disabled:opacity-50">Create and import traces →</button>
        {error && <span className="text-sm text-bad" role="alert">{error}</span>}
      </div>
    </form>
  )
}

// --- the selected agent ----------------------------------------------------------------------------

function AgentProfile({ agent, onRemoved }: { agent: string; onRemoved: () => void }) {
  const [version, setVersion] = useState(0)
  const [removeError, setRemoveError] = useState<string | null>(null)
  const data = useApi(() => api.agent(agent), [agent, version])
  if (data.loading && !data.data) return <Loading what="the agent" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} />
  const a = data.data
  const kindText = a.kind === 'imported' ? 'Imported: traces only' : a.via === 'sdk' ? 'Connected through the Black Box SDK' : 'Built in: runs and replays in the app'
  const removable = a.kind === 'imported' || a.via === 'sdk'
  async function remove() {
    if (!window.confirm(`Remove “${agent}” from the app? Its runs and model stay on disk: connecting it again under the same name brings them back.`)) return
    setRemoveError(null)
    try { await api.removeAgent(agent); onRemoved() } catch (e) { setRemoveError((e as Error).message) }
  }
  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
      <Panel title={`${a.title} · tools`} sub={a.n_runs ? `${a.tools.length} step types, as seen in ${a.n_runs} runs` : `${a.tools.length} step types, reported by the agent`}>
        {a.tools.length === 0 ? <p className="m-0 p-3.5 text-sm text-muted-foreground">No runs yet. {a.kind === 'imported' ? 'Import traces in Training to see this agent’s steps.' : 'Start the agent to see its tools.'}</p> : (
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
        {a.remote && (
          <Panel title="Connection" sub={
            <button type="button" onClick={() => setVersion((v) => v + 1)} className="rounded-md border bg-sunk px-2 py-0.5 text-xs font-semibold">
              {data.loading ? 'Testing…' : 'Test again'}
            </button>}>
            <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 p-3.5 text-[13px]">
              <dt className="text-muted-foreground">URL</dt><dd className="m-0 font-mono text-xs break-all">{a.remote.url}</dd>
              <dt className="text-muted-foreground">Status</dt>
              <dd className="m-0 flex items-center gap-1.5"><OnlineDot online={a.remote.online} />{a.remote.online ? 'Online' : 'Offline: start the agent, then test again'}</dd>
              {a.remote.online && <>
                <dt className="text-muted-foreground">Examples</dt><dd className="m-0">{a.remote.examples} example tasks · {a.remote.kinds?.length} kinds</dd>
                <dt className="text-muted-foreground">Checks results</dt><dd className="m-0">{a.remote.has_check ? 'Yes, with its own check()' : 'No: compared with a reference run'}</dd>
                <dt className="text-muted-foreground">SDK</dt><dd className="m-0 font-mono text-xs">{a.remote.sdk}</dd>
              </>}
            </dl>
          </Panel>
        )}
        <Panel title="Profile">
          <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 p-3.5 text-[13px]">
            <dt className="text-muted-foreground">Kind</dt><dd className="m-0">{kindText}</dd>
            {a.llm && <><dt className="text-muted-foreground">LLM</dt><dd className="m-0 font-mono text-xs break-words">{a.llm}</dd></>}
            <dt className="text-muted-foreground">Runs</dt><dd className="m-0"><span className="font-mono">{a.n_runs}</span> <span className="text-xs text-muted-foreground">({a.n_dataset_runs} dataset · {a.n_runs - a.n_dataset_runs} from the app)</span></dd>
            <dt className="text-muted-foreground">Templates</dt><dd className="m-0 font-mono">{a.templates.train.length} train · {a.templates.test.length} test</dd>
          </dl>
          {removable && (
            <div className="grid gap-1.5 border-t px-3.5 py-3">
              <button type="button" onClick={remove} className="w-fit rounded-md border border-bad px-3 py-1.5 text-sm font-semibold text-bad hover:bg-bad-soft">
                {a.via === 'sdk' ? 'Disconnect agent' : 'Remove agent'}
              </button>
              <span className="text-xs text-muted-foreground">Its runs and model stay on disk; add it again under the same name to get them back.</span>
              {removeError && <span className="text-sm text-bad" role="alert">{removeError}</span>}
            </div>
          )}
        </Panel>
        <Panel title="Diagnosis model" sub={<Link to={`/${agent}/training`} className="font-medium text-recorder-ink">Train →</Link>}>
          {a.model ? (
            <dl className="m-0 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1.5 p-3.5 text-[13px]">
              <dt className="text-muted-foreground">Trained on</dt><dd className="m-0"><span className="font-mono">{a.model.n_train_runs}</span> <span className="text-xs text-muted-foreground">training runs ({a.model.n_train_runs - a.model.n_train_cases} clean successes · {a.model.n_train_cases} failures with a known culprit)</span></dd>
              <dt className="text-muted-foreground">Features</dt><dd className="m-0 font-mono">{a.model.features.length}</dd>
              <dt className="text-muted-foreground">Seen faults</dt><dd className="m-0 font-mono text-xs break-words">{a.model.seen_fault_types.join(', ') || '—'}</dd>
            </dl>
          ) : <p className="m-0 p-3.5 text-sm text-muted-foreground">Not trained yet.{a.via === 'sdk' ? ' Generate data in Training: it trains automatically.' : ''}</p>}
        </Panel>
      </div>
    </div>
  )
}
