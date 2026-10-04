// Compare any two runs: pick them by id (with suggestions from the agent's runs), or start from a replay.

import { useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { useAgent } from '@/layout/agentContext'

export function ComparePicker() {
  const { agent } = useAgent()
  const navigate = useNavigate()
  const runs = useApi(() => api.runs(agent, { source: 'all', limit: 200 }), [agent])
  const replays = useApi(() => api.replays(agent), [agent])
  const [a, setA] = useState('')
  const [b, setB] = useState('')
  const ids = runs.data?.items ?? []
  const valid = a && b && a !== b

  return (
    <div className="grid gap-4">
      <div>
        <span className="bb-label">Trace comparison</span>
        <h1 className="m-0 font-display text-2xl font-bold">Compare</h1>
        <p className="m-0 text-[13px] text-muted-foreground">Put two runs side by side: the steps that changed, where they first part ways, and every value that differs.</p>
      </div>
      <div className="grid items-start gap-4 lg:grid-cols-2">
        <Panel title="Pick two runs">
          <form className="grid gap-3 p-3.5" onSubmit={(e) => { e.preventDefault(); if (valid) navigate(`/${agent}/compare/${a}/${b}`) }}>
            <datalist id="run-ids">{ids.map((r) => <option key={r.run_id} value={r.run_id}>{r.outcome === 'success' ? '✓' : '✗'} {r.request_text}</option>)}</datalist>
            {([['First run (original)', a, setA, 'cmp-a'], ['Second run', b, setB, 'cmp-b']] as const).map(([label, value, set, id]) => (
              <label key={id} htmlFor={id} className="grid gap-1 text-xs font-medium text-muted-foreground">
                {label}
                <input id={id} list="run-ids" value={value} onChange={(e) => set(e.target.value.trim())} placeholder="type or pick a run id"
                  className="h-9 rounded-md border bg-sunk px-3 font-mono text-sm text-foreground" />
              </label>
            ))}
            <p className="m-0 text-xs text-muted-foreground">Tip: compare a failed run with a successful run of a similar task, or a run with its replay.</p>
            <button type="submit" disabled={!valid} className="w-fit rounded-md bg-recorder px-3.5 py-2 font-semibold text-white disabled:opacity-50">Compare</button>
          </form>
        </Panel>
        <Panel title="From a replay" sub="original vs fixed">
          <ul className="m-0 grid list-none gap-1.5 p-3.5">
            {(replays.data ?? []).slice(0, 8).map((r) => (
              <li key={r.run_id}>
                <button type="button" onClick={() => navigate(`/${agent}/compare/${r.parent_run_id}/${r.run_id}`)}
                  className="grid w-full gap-0.5 rounded-md border bg-sunk px-2.5 py-2 text-left hover:border-recorder">
                  <span className="truncate font-mono text-xs">{r.parent_run_id}</span>
                  <span className="text-xs text-muted-foreground">edited #{r.edited_step} {r.edited_name} · {r.outcome === 'success' ? '✓ fixed' : '✗ still wrong'}</span>
                </button>
              </li>
            ))}
            {replays.data?.length === 0 && <li className="text-sm text-muted-foreground">No replays yet.</li>}
          </ul>
        </Panel>
      </div>
    </div>
  )
}
