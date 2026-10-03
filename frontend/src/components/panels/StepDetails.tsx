// What one step did: its label, the steps it used, the values it read from them, timings, error,
// input (the arguments the LLM passed) and output.

import type { Step } from '@/types/contract'

interface Props {
  step: Step | null
  steps: Step[] // the whole run, to look up what this step read
  label: (step: Step) => string
  onSelect: (id: number) => void
  emptyText: string
}

export function StepDetails({ step, steps, label, onSelect, emptyText }: Props) {
  if (!step) return <p className="m-0 text-[13px] text-muted-foreground">{emptyText}</p>
  return (
    <div className="grid gap-3.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-[3px] px-1.5 py-px font-mono text-[10px] font-semibold tracking-wide ${step.kind === 'llm' ? 'bg-llm-soft text-llm' : 'border bg-sunk text-muted-foreground'}`}>
          {step.kind.toUpperCase()}
        </span>
        <strong className="font-mono">{step.name}</strong>
      </div>
      <p className="m-0 text-[13px]">{label(step)}</p>
      <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[12.5px]">
        <dt className="text-muted-foreground">Used</dt>
        <dd className="m-0 flex flex-wrap gap-1">
          {step.uses.length === 0 && <span className="font-mono">nothing (first step)</span>}
          {step.uses.map((u) => (
            <button key={u} type="button" onClick={() => onSelect(u)}
              className="rounded border bg-sunk px-1.5 font-mono text-[11.5px] hover:border-recorder">#{u}</button>
          ))}
        </dd>
        <dt className="text-muted-foreground">Tool time</dt>
        <dd className="m-0 font-mono tabular-nums">{step.tool_latency_ms} ms</dd>
        <dt className="text-muted-foreground">LLM call</dt>
        <dd className="m-0 font-mono tabular-nums">
          {step.llm
            ? `${step.llm.latency_ms} ms · ${step.llm.tokens_in.toLocaleString()} in / ${step.llm.tokens_out} out`
            : 'same call as the step before'}
        </dd>
      </dl>
      {step.error && <p className="m-0 font-mono text-[12.5px] text-bad">{step.error}</p>}
      <ReadValues step={step} steps={steps} onSelect={onSelect} />
      <Json title="Input (arguments from the LLM)" value={step.input} />
      <Json title="Output" value={step.output} />
    </div>
  )
}

function Json({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="grid gap-1">
      <p className="m-0 font-mono text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">{title}</p>
      <pre className="m-0 max-h-60 overflow-auto rounded-md border bg-sunk p-2.5 font-mono text-xs leading-relaxed">
        {JSON.stringify(value, null, 2)}
      </pre>
    </div>
  )
}

/** A state key's value. Keys like "menu:pepperoni" address state.menu["pepperoni"]. */
function lookup(state: Record<string, unknown>, key: string): unknown {
  if (key in state) return state[key]
  const cut = key.indexOf(':')
  if (cut < 0) return undefined
  const group = state[key.slice(0, cut)]
  return group && typeof group === 'object' ? (group as Record<string, unknown>)[key.slice(cut + 1)] : undefined
}

function brief(value: unknown): string {
  if (Array.isArray(value)) return `${value.length} item${value.length === 1 ? '' : 's'}`
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.every(([, v]) => v === null || typeof v !== 'object')) {
      return entries.map(([k, v]) => `${k} ${String(v)}`).join(' · ') // e.g. S 279 · M 379 · L 479
    }
    return entries.map(([k, v]) => `${k}: ${Array.isArray(v) ? `${v.length} items` : typeof v === 'object' && v ? '{…}' : String(v)}`).join(' · ')
  }
  return String(value)
}

function ReadValues({ step, steps, onSelect }: { step: Step; steps: Step[]; onSelect: (id: number) => void }) {
  const before = steps.filter((s) => s.id < step.id)
  const state = before.at(-1)?.state_after ?? {}
  const rows = step.reads.flatMap((key) => {
    const writer = before.findLast((s) => s.writes.includes(key))
    return writer ? [{ key, writer: writer.id, value: lookup(state, key) }] : []
  })
  if (rows.length === 0) return null
  return (
    <div className="grid gap-1">
      <p className="m-0 font-mono text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Read from earlier steps</p>
      <ul className="m-0 grid list-none rounded-md border bg-sunk p-0 font-mono text-xs">
        {rows.map((r) => (
          <li key={r.key} className="grid gap-0.5 border-b px-2.5 py-1.5 last:border-b-0">
            <span className="flex justify-between gap-2">
              <span className="truncate text-muted-foreground">{r.key}</span>
              <button type="button" onClick={() => onSelect(r.writer)} className="shrink-0 text-recorder-ink hover:underline">← #{r.writer}</button>
            </span>
            <span className="break-words tabular-nums">{brief(r.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
