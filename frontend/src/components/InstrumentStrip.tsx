// Live gauges for a run: steps, LLM calls, tokens and agent time.

import type { Step } from '@/types/contract'

export function InstrumentStrip({ steps }: { steps: Step[] }) {
  return <Gauges items={instruments(steps)} />
}

function instruments(steps: Step[]): GaugeItem[] {
  const calls = steps.filter((s) => s.llm)
  const tokensIn = calls.reduce((n, s) => n + s.llm!.tokens_in, 0)
  const tokensOut = calls.reduce((n, s) => n + s.llm!.tokens_out, 0)
  const ms = steps.reduce((n, s) => n + (s.llm?.latency_ms ?? 0) + s.tool_latency_ms, 0)
  return [
    { k: 'Steps', v: String(steps.length) },
    { k: 'LLM calls', v: String(calls.length) },
    { k: 'Tokens in / out', v: tokensIn.toLocaleString(), sub: `/ ${tokensOut.toLocaleString()}` },
    { k: 'Agent time', v: (ms / 1000).toFixed(1), sub: 's' },
  ]
}

export interface GaugeItem {
  k: string
  v: string
  sub?: string
}

/** A row of four instrument readings (condensed numerals, expanded labels). */
export function Gauges({ items }: { items: GaugeItem[] }) {
  return (
    <div className="grid grid-cols-2 border-b sm:grid-cols-4" aria-label="Instruments">
      {items.map(({ k, v, sub }) => (
        <div key={k} className="grid min-w-0 gap-px border-r px-3.5 py-2 last:border-r-0 max-sm:[&:nth-child(-n+2)]:border-b max-sm:[&:nth-child(2)]:border-r-0">
          <span className="bb-label">{k}</span>
          <span className="bb-gauge text-[22px] leading-tight font-semibold">
            {v} {sub && <small className="font-sans text-xs font-normal text-muted-foreground">{sub}</small>}
          </span>
        </div>
      ))}
    </div>
  )
}
