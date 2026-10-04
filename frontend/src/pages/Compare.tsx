// Compare: two runs side by side (usually a failed run and its replay). Steps are lined up by what
// they did, not by number (lib/align.ts), so a detour one run took shows as "only in original"
// instead of shifting every later step out of line.

import { useParams } from 'react-router'
import { getPlugin } from '@/agents/registry'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { RecorderTrack, type TickKind } from '@/components/RecorderTrack'
import { Loading, Problem } from '@/components/StateBox'
import { RunGraph } from '@/components/graph/RunGraph'
import type { Tag } from '@/components/graph/StepNode'
import { alignRuns, type Pair, type PairKind } from '@/lib/align'
import { cn } from '@/lib/utils'
import type { Run, Step } from '@/types/contract'

const TICK: Record<PairKind, TickKind> = { same: 'same', changed: 'diff', moved: 'diff', onlyA: 'only', onlyB: 'only' }
const stepName = (s: Step) => `#${s.id} ${s.name}`

export function Compare() {
  const { agent = 'pizza', originalId = '', replayId = '' } = useParams()
  const plugin = getPlugin(agent)
  const data = useApi(() => Promise.all([api.run(agent, originalId), api.run(agent, replayId)]), [agent, originalId, replayId])
  if (data.loading) return <Loading what="both runs" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} back={{ to: `/${agent}/runs`, label: 'Back to runs' }} />
  const [a, b] = data.data

  const pairs = alignRuns(a.steps, b.steps)
  const isReplay = b.parent_run_id === a.run_id && b.replayed_from_step != null
  const edited = isReplay ? b.replayed_from_step! : null
  const reused = isReplay ? b.steps.filter((s) => s.id < edited!).map((s) => s.id) : []
  const bName = isReplay ? 'replay' : 'other run'

  const kindOf = (which: 'a' | 'b') => new Map(pairs.flatMap((p) => (p[which] ? [[p[which]!.id, p.kind] as const] : [])))
  const kinds = { a: kindOf('a'), b: kindOf('b') }
  const firstDiff = pairs.findIndex((p) => p.kind !== 'same')
  const markerOf = (which: 'a' | 'b') => (firstDiff < 0 ? null : pairs.slice(firstDiff).find((p) => p[which])?.[which]?.id ?? null)
  const count = (k: PairKind) => pairs.filter((p) => p.kind === k).length
  const onlyA = pairs.filter((p) => p.kind === 'onlyA').map((p) => p.a!)
  const onlyB = pairs.filter((p) => p.kind === 'onlyB').map((p) => p.b!)

  const side = (run: Run, which: 'a' | 'b') => {
    const k = kinds[which]
    const tags = (s: Step): Tag[] => {
      if (which === 'b' && reused.includes(s.id)) return [['plain', 'REUSED']]
      if (which === 'b' && s.id === edited) return [['accent', 'EDITED']]
      const kind = k.get(s.id)
      return kind === 'onlyA' || kind === 'onlyB' ? [['bad', `ONLY IN ${which === 'a' ? 'ORIGINAL' : bName.toUpperCase()}`]]
        : kind === 'changed' ? [['bad', 'CHANGED']] : kind === 'moved' ? [['bad', 'MOVED']] : []
    }
    const ok = run.outcome === 'success'
    const marker = markerOf(which)
    return (
      <Panel title={which === 'a' ? 'Original' : isReplay ? 'Replay' : 'Other run'}
        sub={<span className={cn('rounded px-2 py-0.5 font-mono text-[11px] font-semibold', ok ? 'bg-good-soft text-good' : 'bg-bad-soft text-bad')}>{ok ? '✓ correct' : '✗ wrong'} · {run.steps.length} steps</span>}>
        <div className="border-b border-dashed px-3.5 py-2 font-mono text-xs break-all text-muted-foreground">{run.run_id}</div>
        <div className="border-b px-3.5 py-2 text-[13px]">{plugin.resultLine(run)}</div>
        <RunGraph steps={run.steps} label={plugin.stepLabel} final={ok ? 'good' : 'bad'} tags={tags}
          changedIds={run.steps.filter((s) => k.get(s.id) !== 'same').map((s) => s.id)}
          cachedIds={which === 'b' ? reused : undefined} editedId={which === 'b' ? edited : null} />
        <RecorderTrack title="Track" right={marker ? `differs from step ${marker} ▸` : 'identical'} markerAt={marker} markerLabel="First difference"
          ticks={run.steps.map((s) => ({ id: s.id, name: s.name, kind: TICK[k.get(s.id) ?? 'same'] }))} />
      </Panel>
    )
  }

  const rows = pairs.filter((p) => p.kind !== 'same')
  const editRows = rows.filter((p) => edited != null && p.b?.id === edited)
  const changedRows = rows.filter((p) => !editRows.includes(p) && (p.kind === 'changed' || p.kind === 'moved'))
  const onlyRows = rows.filter((p) => p.kind === 'onlyA' || p.kind === 'onlyB')
  const sections: [string, Pair[]][] = ([
    ['Your edit', editRows],
    [isReplay ? 'Knock-on changes' : 'Changed steps', changedRows],
    ['Steps in only one run', onlyRows],
  ] as [string, Pair[]][]).filter(([, ps]) => ps.length > 0)
  const idFields = [...new Set(pairs.flatMap((p) => p.changes.filter((c) => c.id).map((c) => c.field.split('.').pop()!.replace(/\[\d+\]$/, ''))))]
  const summary = [
    `${count('same')} identical`, count('changed') && `${count('changed')} changed`, count('moved') && `${count('moved')} moved`,
    onlyA.length && `${onlyA.length} only in the original`, onlyB.length && `${onlyB.length} only in the ${bName}`,
  ].filter(Boolean).join(' · ')

  return (
    <div className="grid gap-4">
      <div className="grid items-start gap-4 grid-cols-1 lg:grid-cols-2">{side(a, 'a')}{side(b, 'b')}</div>
      <Panel title="What changed" sub={rows.length === 0 ? 'the two runs did the same thing' : summary}>
        {(onlyA.length > 0 || onlyB.length > 0) && (
          <div className="grid gap-1 border-b bg-sunk px-3.5 py-2.5 text-[13px]">
            {onlyA.length > 0 && <span>The original took <strong>{onlyA.length} step{onlyA.length > 1 ? 's' : ''}</strong> the {bName} didn’t: <span className="font-mono">{onlyA.map(stepName).join(', ')}</span>.</span>}
            {onlyB.length > 0 && <span>The {bName} took <strong>{onlyB.length} step{onlyB.length > 1 ? 's' : ''}</strong> the original didn’t: <span className="font-mono">{onlyB.map(stepName).join(', ')}</span>.</span>}
          </div>
        )}
        {rows.length === 0 ? <p className="m-0 p-3.5 text-sm text-muted-foreground">No step differs.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="text-left">
                  {['Step', 'Field', 'Original', isReplay ? 'Replay' : 'Other'].map((h) => (
                    <th key={h} className="border-b px-3 py-2 font-mono text-[10.5px] font-semibold tracking-wider whitespace-nowrap text-muted-foreground uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              {sections.map(([title, ps]) => (
                <tbody key={title}>
                  <tr>
                    <td colSpan={4} className="border-b bg-sunk px-3 py-1.5">
                      <span className="bb-label">{title}</span>
                      <span className="ml-2 text-xs text-muted-foreground">{ps.length} step{ps.length > 1 ? 's' : ''}</span>
                    </td>
                  </tr>
                  {ps.flatMap((p, i) => rowsFor(p, `${title}-${i}`, edited, plugin.stepLabel))}
                </tbody>
              ))}
            </table>
          </div>
        )}
        {idFields.length > 0 && (
          <p className="m-0 px-3.5 py-2 text-xs text-muted-foreground">
            Not shown: <span className="font-mono">{idFields.join(', ')}</span>. IDs are new on every run, so a different value isn’t a real change.
          </p>
        )}
      </Panel>
    </div>
  )
}

function rowsFor(p: Pair, key: string, edited: number | null, label: (s: Step) => string) {
  const td = 'border-b px-3 py-1.5 align-top'
  const isEdit = p.b?.id === edited
  const where = p.a && p.b ? (p.a.id === p.b.id ? stepName(p.a) : `#${p.a.id} ↔ #${p.b.id} ${p.a.name}`) : stepName((p.a ?? p.b)!)
  if (p.kind === 'onlyA' || p.kind === 'onlyB') {
    return [(
      <tr key={key} className="bg-bad-soft/40">
        <td className={cn(td, 'font-mono whitespace-nowrap')}>{where}</td>
        <td className={cn(td, 'text-xs')}>{p.kind === 'onlyA' ? 'only in the original' : 'only in this run'}</td>
        <td className={cn(td, 'text-xs', p.a && 'text-bad line-through decoration-1')}>{p.a ? label(p.a) : '—'}</td>
        <td className={cn(td, 'text-xs', p.b && 'font-semibold text-good')}>{p.b ? label(p.b) : '—'}</td>
      </tr>
    )]
  }
  const real = p.changes.filter((c) => !c.id)
  const fields = real.length ? real : [{ field: '(called at a different point)', before: '', after: '' }]
  return fields.map((c, j) => (
    <tr key={`${key}-${j}`} className={cn(isEdit && 'bg-recorder-soft')}>
      <td className={cn(td, 'font-mono whitespace-nowrap')}>{j === 0 ? <>{where}{p.kind === 'moved' && <span className="ml-1.5 font-sans text-xs text-muted-foreground">moved</span>}</> : ''}</td>
      <td className={cn(td, 'font-mono')}>{c.field}{isEdit && j === 0 && <span className="ml-2 font-sans text-xs text-recorder-ink">your edit</span>}</td>
      <td className={cn(td, 'font-mono break-all text-bad line-through decoration-1')}>{c.before}</td>
      <td className={cn(td, 'font-mono font-semibold break-all text-good')}>{c.after}</td>
    </tr>
  ))
}
