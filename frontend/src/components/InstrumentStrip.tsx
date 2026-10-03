// Live gauges for a run: steps, LLM calls, tokens and agent time.

import type { Step } from '@/types/contract'

export function InstrumentStrip({ steps }: { steps: Step[] }) {
  const calls = steps.filter((s) => s.llm)
  const tokensIn = calls.reduce((n, s) => n + s.llm!.tokens_in, 0)
  const tokensOut = calls.reduce((n, s) => n + s.llm!.tokens_out, 0)
  const ms = steps.reduce((n, s) => n + (s.llm?.latency_ms ?? 0) + s.tool_latency_ms, 0)
  return (
    <div className="grid grid-cols-2 border-b sm:grid-cols-4" aria-label="Run instruments">
      <Gauge k="Steps" v={String(steps.length)} />
      <Gauge k="LLM calls" v={String(calls.length)} />
      <Gauge k="Tokens in / out" v={tokensIn.toLocaleString()} sub={`/ ${tokensOut.toLocaleString()}`} />
      <Gauge k="Agent time" v={(ms / 1000).toFixed(1)} sub="s" />
    </div>
  )
}

function Gauge({ k, v, sub }: { k: string; v: string; sub?: string }) {
  return (
    <div className="grid min-w-0 gap-px border-r px-3.5 py-2 last:border-r-0 max-sm:[&:nth-child(-n+2)]:border-b max-sm:[&:nth-child(2)]:border-r-0">
      <span className="font-mono text-[10.5px] font-semibold tracking-wider text-muted-foreground uppercase">{k}</span>
      <span className="font-mono text-lg font-medium tabular-nums">
        {v} {sub && <small className="text-xs text-muted-foreground">{sub}</small>}
      </span>
    </div>
  )
}
