// Training: import traces recorded elsewhere, see what data the agent has, and train + evaluate
// its diagnosis model in the background with a live log.

import { useEffect, useRef, useState } from 'react'
import { Upload } from 'lucide-react'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { useAgent } from '@/layout/agentContext'
import { ago, pct } from '@/lib/format'
import { cn } from '@/lib/utils'
import type { ImportResult, TrainJob } from '@/types/dashboard'

export function Training() {
  const { agent } = useAgent()
  const [version, setVersion] = useState(0) // bump to reload the data summary
  return (
    <div className="grid gap-4">
      <div>
        <span className="bb-label">Training</span>
        <h1 className="m-0 font-display text-2xl font-bold">Training</h1>
        <p className="m-0 max-w-[80ch] text-[13px] text-muted-foreground">
          Bring in an agent’s traces, then train its diagnosis model. Runs need the Black Box trace format; failed runs with a <span className="font-mono">fault</span> label
          are the known failures the model learns from and is scored on.
        </p>
      </div>
      <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="grid gap-4">
          <ImportPanel agent={agent} onImported={() => setVersion((v) => v + 1)} />
          <DataSummary agent={agent} version={version} />
        </div>
        <TrainPanel agent={agent} />
      </div>
    </div>
  )
}

/** Read .json (one run or a list) and .jsonl files into runs, naming each by its file. */
async function readFiles(files: File[]): Promise<{ runs: unknown[]; names: string[]; errors: string[] }> {
  const runs: unknown[] = [], names: string[] = [], errors: string[] = []
  for (const f of files) {
    const text = await f.text()
    try {
      if (f.name.endsWith('.jsonl')) {
        text.split('\n').filter((l) => l.trim()).forEach((l, i) => { runs.push(JSON.parse(l)); names.push(`${f.name}:${i + 1}`) })
      } else {
        const parsed = JSON.parse(text)
        for (const [i, r] of (Array.isArray(parsed) ? parsed : [parsed]).entries()) { runs.push(r); names.push(Array.isArray(parsed) ? `${f.name}[${i}]` : f.name) }
      }
    } catch {
      errors.push(`${f.name}: not valid JSON`)
    }
  }
  return { runs, names, errors }
}

function ImportPanel({ agent, onImported }: { agent: string; onImported: () => void }) {
  const [over, setOver] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<(ImportResult & { fileErrors: string[] }) | null>(null)
  const [error, setError] = useState<string | null>(null)
  const input = useRef<HTMLInputElement>(null)

  async function handle(files: File[]) {
    if (!files.length) return
    setBusy(true); setError(null); setResult(null)
    try {
      const { runs, names, errors } = await readFiles(files)
      const res = runs.length ? await api.importRuns(agent, runs, names) : { imported: 0, run_ids: [], rejected: [] }
      setResult({ ...res, fileErrors: errors })
      if (res.imported) onImported()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel title="Import traces" sub={<span className="font-mono">.json · .jsonl</span>}>
      <div className="grid gap-3 p-3.5">
        <label htmlFor="trace-files"
          onDragOver={(e) => { e.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); handle([...e.dataTransfer.files]) }}
          className={cn('grid cursor-pointer place-items-center gap-1.5 rounded-lg border-2 border-dashed px-4 py-8 text-center text-sm',
            over ? 'border-recorder bg-recorder-soft' : 'bg-sunk')}>
          <Upload className="size-5 text-muted-foreground" aria-hidden="true" />
          <span><strong>{busy ? 'Importing…' : 'Drop trace files here'}</strong> or click to choose</span>
          <span className="text-xs text-muted-foreground">Each run is checked against the trace format; the rest still import if some fail.</span>
          <input ref={input} id="trace-files" type="file" accept=".json,.jsonl,application/json" multiple className="sr-only"
            onChange={(e) => { handle([...(e.target.files ?? [])]); if (input.current) input.current.value = '' }} />
        </label>
        {error && <p className="m-0 text-sm text-bad" role="alert">{error}</p>}
        {result && (
          <div className="grid gap-1.5 text-[13px]" role="status">
            <span className={result.imported ? 'text-good' : 'text-muted-foreground'}><strong>{result.imported}</strong> run{result.imported === 1 ? '' : 's'} imported</span>
            {[...result.fileErrors.map((e) => ({ where: e.split(':')[0], error: e.split(': ').slice(1).join(': ') })), ...result.rejected].slice(0, 8).map((r, i) => (
              <span key={i} className="font-mono text-xs text-bad break-all">✗ {r.where}: {r.error}</span>
            ))}
            {result.rejected.length + result.fileErrors.length > 8 && <span className="text-xs text-muted-foreground">…and {result.rejected.length + result.fileErrors.length - 8} more rejected</span>}
          </div>
        )}
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium">What a trace looks like</summary>
          <pre className="mt-2 max-h-56 overflow-auto rounded-md border bg-sunk p-2.5 font-mono text-[11.5px]">{`{
  "run_id": "order_0412",
  "template_id": "two_items_coupon",      // task family; decides the train/test split
  "task": {...}, "request_text": "...",
  "expected": {...}, "actual": {...},
  "outcome": "failure",                    // or "success"
  "fault": { "type": "wrong_discount", "family": "tool",
             "step_id": 8, "detail": "..." }, // the known culprit (or null)
  "steps": [ { "id": 1, "kind": "llm", "name": "parse_order",
               "input": {...}, "output": {...},
               "reads": [...], "writes": [...], "uses": [...],
               "llm": {...}, "tool_latency_ms": 0, "error": null,
               "state_after": {...}, "msg_index": 3 }, ... ]
}`}</pre>
        </details>
      </div>
    </Panel>
  )
}

function DataSummary({ agent, version }: { agent: string; version: number }) {
  const data = useApi(() => api.dataset(agent), [agent, version])
  const d = data.data
  const count = (split: 'train' | 'test', key: 'success' | 'failure', clean: boolean) =>
    (d?.kinds ?? []).filter((k) => (k.kind === 'clean') === clean).reduce((n, k) => n + k[`${split}_${key}`], 0)
  const cleanTrain = count('train', 'success', true)
  const casesTrain = count('train', 'failure', false)
  const enough = cleanTrain >= 10 && casesTrain >= 10
  return (
    <Panel title="Data for this agent">
      {!d ? <p className="m-0 p-3.5 text-sm text-muted-foreground">{data.error ?? 'Loading…'}</p> : (
        <div className="grid gap-3 p-3.5 text-[13px]">
          <dl className="m-0 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-4">
            {([['Dataset runs', d.total], ['Training split', d.train], ['Clean successes (train)', cleanTrain], ['Known failures (train)', casesTrain]] as const).map(([k, v]) => (
              <div key={k}><dt className="text-xs text-muted-foreground">{k}</dt><dd className="bb-gauge m-0 text-2xl font-semibold">{v}</dd></div>
            ))}
          </dl>
          <p className={cn('m-0 rounded-md border px-3 py-2 text-xs', enough ? 'border-good bg-good-soft' : 'border-dashed text-muted-foreground')}>
            {enough ? '✓ Enough data to train.' : 'Training needs at least 10 clean successful runs and 10 failed runs with a known culprit in the training split.'}
          </p>
        </div>
      )}
    </Panel>
  )
}

function TrainPanel({ agent }: { agent: string }) {
  const [job, setJob] = useState<TrainJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const logEnd = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let live = true
    let timer: ReturnType<typeof setTimeout>
    const poll = async () => {
      try {
        const j = await api.trainStatus(agent)
        if (!live) return
        setJob(j)
        if (j.status === 'running') timer = setTimeout(poll, 700)
      } catch (e) {
        if (live) setError((e as Error).message)
      }
    }
    poll()
    return () => { live = false; clearTimeout(timer) }
  }, [agent, job?.started, job?.status === 'running'])
  useEffect(() => { logEnd.current?.scrollIntoView({ block: 'nearest' }) }, [job?.log.length])

  async function start() {
    setError(null)
    try { setJob(await api.train(agent)) } catch (e) { setError((e as Error).message) }
  }

  const running = job?.status === 'running'
  return (
    <Panel title="Train & evaluate" sub={running ? <span className="text-recorder-ink">● running</span> : undefined}>
      <div className="grid gap-3 p-3.5">
        <p className="m-0 text-[13px] text-muted-foreground">
          Learns what normal looks like from this agent’s successful runs, trains the model on its known failures, then scores it on the test split.
          Takes a few seconds to a minute. The new model is used for every diagnosis right away.
        </p>
        <button type="button" onClick={start} disabled={running}
          className="w-fit rounded-[7px] bg-recorder px-4 py-2.5 font-display font-bold tracking-[0.03em] text-white disabled:opacity-60">
          {running ? 'Training…' : 'Train & evaluate'}
        </button>
        {error && <p className="m-0 text-sm text-bad" role="alert">{error}</p>}
        {job && job.log.length > 0 && (
          <div className="max-h-64 overflow-auto rounded-md border bg-sunk p-2.5 font-mono text-[11.5px] leading-relaxed" aria-live="polite">
            {job.log.map((l, i) => <div key={i} className={cn(l.includes('stopped:') && 'text-bad')}>{l}</div>)}
            <div ref={logEnd} />
          </div>
        )}
        {job?.status === 'done' && job.result && (
          <div className="grid grid-cols-3 gap-3 rounded-md border border-good bg-good-soft p-3">
            {([['Top-1', pct(job.result.top1)], ['Top-3', pct(job.result.top3)], ['Unseen top-1', job.result.unseen_n ? pct(job.result.unseen_top1) : '—']] as const).map(([k, v]) => (
              <div key={k}><span className="bb-label">{k}</span><div className="bb-gauge text-2xl font-bold">{v}</div></div>
            ))}
          </div>
        )}
        {job && job.history.length > 0 && (
          <div className="grid gap-1.5">
            <span className="bb-label">History</span>
            <ul className="m-0 grid list-none gap-1 p-0 text-xs">
              {job.history.slice(0, 6).map((h) => (
                <li key={h.started} className="flex flex-wrap justify-between gap-2 rounded-md bg-sunk px-2.5 py-1.5">
                  <span className={h.status === 'done' ? 'text-good' : 'text-bad'}>{h.status === 'done' ? '✓ trained' : '✗ stopped'}</span>
                  <span className="font-mono">{h.result ? `top-1 ${pct(h.result.top1)} · ${h.result.n_train_runs} train runs` : h.error}</span>
                  <span className="text-muted-foreground">{ago(h.started)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  )
}
