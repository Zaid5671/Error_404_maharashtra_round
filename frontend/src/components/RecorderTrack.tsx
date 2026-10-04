// The recorder track: the run as one tick per step, like a flight-data recorder readout. The same
// strip appears on every screen and shows that screen's story: progress (Live Run), suspicion
// (Diagnosis), reused vs re-run (Replay), and where two runs part ways (Compare).

import { cn } from '@/lib/utils'

export type TickKind = 'pending' | 'running' | 'done' | 'ok' | 'bad' | 'culprit' | 'reused' | 'edited' | 'rerun' | 'same' | 'diff' | 'heat'

export interface Tick {
  id: number
  name: string
  kind: TickKind
  heat?: number // 0..1, for kind "heat"
}

const KIND: Record<TickKind, string> = {
  pending: 'border border-dashed bg-transparent',
  running: 'bg-recorder bb-blink',
  done: 'bg-muted-foreground/55',
  ok: 'bg-good/75',
  bad: 'bg-bad',
  culprit: 'bg-bad shadow-[0_0_0_2px_var(--bad-soft)]',
  reused: 'bb-reused border',
  edited: 'bg-recorder',
  rerun: 'bg-good',
  same: 'bg-border',
  diff: 'bg-bad',
  heat: '',
}

interface Props {
  title: string
  right?: string
  ticks: Tick[]
  /** Draw a line before this step id (e.g. where two runs start to differ). */
  markerAt?: number | null
  markerLabel?: string
}

export function RecorderTrack({ title, right, ticks, markerAt, markerLabel }: Props) {
  const markerIndex = markerAt != null ? ticks.findIndex((t) => t.id === markerAt) : -1
  return (
    <div className="grid gap-1.5 border-t px-3.5 pt-2.5 pb-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="bb-label inline-flex items-center gap-1.5 before:size-[7px] before:rounded-full before:bg-recorder">{title}</span>
        {right && <span className="bb-label">{right}</span>}
      </div>
      <div className="relative grid auto-cols-fr grid-flow-col gap-[3px] rounded-[5px] border bg-sunk p-[5px]" role="img"
        aria-label={`${title}: ${ticks.map((t) => `step ${t.id} ${t.kind}`).join(', ')}`}>
        {ticks.map((t) => (
          <div key={t.id} title={`#${t.id} ${t.name}`} className={cn('h-5 rounded-[2px]', KIND[t.kind])}
            style={t.kind === 'heat' ? { background: `color-mix(in oklab, var(--heat) ${Math.round((t.heat ?? 0) * 100)}%, var(--border))` } : undefined} />
        ))}
        {markerIndex >= 0 && (
          <div className="absolute -top-[7px] -bottom-[7px] w-0.5 bg-bad" title={markerLabel}
            style={{ left: `calc(5px + (100% - 10px) * ${markerIndex / ticks.length} - 1.5px)` }} />
        )}
      </div>
      <div className="grid auto-cols-fr grid-flow-col gap-[3px] px-[5px] text-center font-mono text-[10px] text-muted-foreground">
        {ticks.map((t) => <span key={t.id}>{t.id}</span>)}
      </div>
    </div>
  )
}
