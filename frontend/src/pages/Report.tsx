// Model Report: how well the agent's diagnosis model finds the culprit on test runs it never saw,
// split into fault types it trained on (seen) and types it never saw (unseen).

import { useParams } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { SeenBadge } from '@/components/FaultPicker'
import { Panel } from '@/components/Panel'
import { Loading, Problem } from '@/components/StateBox'
import { pct } from '@/lib/format'
import type { Accuracy, Report as ReportT } from '@/types/contract'


export function Report() {
  const { agent = 'pizza' } = useParams()
  const data = useApi(() => api.report(agent), [agent])
  if (data.loading) return <Loading what="the report" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No report'} back={{ to: `/${agent}`, label: 'Back to Live Run' }} />
  const r = data.data
  const blind = r.by_type.filter((t) => t.top3 === 0)

  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Big label="Top-1 accuracy" value={pct(r.overall.top1)} note="Culprit ranked #1 on failed test runs" />
        <Big label="Top-3 accuracy" value={pct(r.overall.top3)} note="Culprit among the top 3 suspects" />
        <Big label="Unseen faults · top-1" value={pct(r.unseen.top1)} note="Fault types the model never trained on" />
        <Big label="Test / train runs" value={String(r.n_test_runs)} sub={`/ ${r.n_train_runs}`} note="Test orders come from templates never seen in training" />
      </div>
      <div className="grid items-start gap-4 grid-cols-1 lg:grid-cols-2">
        <Panel title="Seen vs unseen faults" sub={<Legend />}>
          <div className="p-3.5"><SplitChart r={r} /></div>
        </Panel>
        <Panel title="By fault type" sub="top-1 · top-3 · runs">
          <div className="grid gap-2 p-3.5">
            {r.by_type.map((t) => (
              <div key={t.type} className="grid grid-cols-[minmax(0,1fr)_52px_40px] items-center gap-x-2.5 gap-y-1 text-[12.5px] sm:grid-cols-[minmax(150px,210px)_minmax(0,1fr)_52px_40px]">
                <span className="flex min-w-0 flex-wrap items-center gap-1.5 font-mono">{t.type}<SeenBadge seen={t.seen} /></span>
                <span className="relative h-2.5 overflow-hidden rounded-full bg-sunk max-sm:col-span-3 max-sm:row-start-2" role="img"
                  aria-label={`${t.type}: top-1 ${pct(t.top1)}, top-3 ${pct(t.top3)}`}>
                  <span className="absolute inset-y-0 left-0 bg-muted-foreground/30" style={{ width: pct(t.top3) }} />
                  <span className="absolute inset-y-0 left-0 bg-foreground" style={{ width: pct(t.top1) }} />
                </span>
                <span className="text-right font-mono tabular-nums">{pct(t.top1)}</span>
                <span className="text-right font-mono text-muted-foreground tabular-nums">{t.n}</span>
              </div>
            ))}
            {blind.length > 0 && (
              <p className="m-0 mt-2 rounded-md border border-dashed px-3 py-2.5 text-[12.5px] text-muted-foreground">
                Blind spot: <span className="font-mono">{blind.map((t) => t.type).join(', ')}</span> ({blind.reduce((n, t) => n + t.n, 0)} runs).
                The model only knows “normal” from successful training runs, so a fault in a situation that never appeared in training leaves no clue.
              </p>
            )}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function Big({ label, value, sub, note }: { label: string; value: string; sub?: string; note: string }) {
  return (
    <Panel className="grid gap-1 p-4">
      <span className="bb-label">{label}</span>
      <span className="bb-gauge text-[46px] leading-none font-bold">
        {value}{sub && <small className="text-xl text-muted-foreground"> {sub}</small>}
      </span>
      <p className="m-0 text-[12.5px] text-muted-foreground">{note}</p>
    </Panel>
  )
}

function Legend() {
  return (
    <span className="flex gap-3 text-xs">
      <span className="inline-flex items-center gap-1"><span className="size-3 rounded-[2px] bg-foreground" />top-1</span>
      <span className="inline-flex items-center gap-1"><span className="size-3 rounded-[2px] bg-muted-foreground/40" />top-3</span>
    </span>
  )
}

/** Grouped bars: top-1 and top-3 for seen faults, unseen faults and all. */
function SplitChart({ r }: { r: ReportT }) {
  const groups: [string, Accuracy, number][] = [['Seen faults', r.seen, r.seen.n], ['Unseen faults', r.unseen, r.unseen.n], ['All', r.overall, r.n_test_runs]]
  const W = 560, H = 240, left = 42, bottom = 36, top = 20, plotH = H - bottom - top, gw = (W - left - 10) / 3, bw = 46
  const y = (v: number) => top + plotH * (1 - v)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="block h-auto w-full" role="img" aria-label="Top-1 and top-3 accuracy for seen, unseen and all faults">
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line x1={left} x2={W - 6} y1={y(v)} y2={y(v)} stroke="var(--border)" />
          <text x={left - 6} y={y(v) + 4} textAnchor="end" className="fill-muted-foreground font-mono text-[11px]">{v * 100}%</text>
        </g>
      ))}
      {groups.map(([name, a, n], i) => {
        const x0 = left + i * gw + (gw - bw * 2 - 8) / 2
        return (
          <g key={name}>
            <rect x={x0} y={y(a.top1)} width={bw} height={plotH * a.top1} rx={2} className="fill-foreground" />
            <text x={x0 + bw / 2} y={y(a.top1) - 5} textAnchor="middle" className="fill-foreground font-mono text-[11px] font-semibold">{pct(a.top1)}</text>
            <rect x={x0 + bw + 8} y={y(a.top3)} width={bw} height={plotH * a.top3} rx={2} className="fill-muted-foreground/40" />
            <text x={x0 + bw * 1.5 + 8} y={y(a.top3) - 5} textAnchor="middle" className="fill-foreground font-mono text-[11px] font-semibold">{pct(a.top3)}</text>
            <text x={x0 + bw + 4} y={H - 16} textAnchor="middle" className="fill-muted-foreground font-mono text-[11px]">{name}</text>
            <text x={x0 + bw + 4} y={H - 2} textAnchor="middle" className="fill-muted-foreground font-mono text-[11px]">n={n}</text>
          </g>
        )
      })}
    </svg>
  )
}
