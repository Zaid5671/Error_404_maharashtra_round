// What one step did: its label, the steps it used, timings, error, input and output.

import type { Step } from '@/types/contract'

interface Props {
  step: Step | null
  label: (step: Step) => string
  onSelect: (id: number) => void
  emptyText: string
}

export function StepDetails({ step, label, onSelect, emptyText }: Props) {
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
      <Json title="Input" value={step.input} />
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
