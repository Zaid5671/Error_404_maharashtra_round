// Compare: two runs side by side (usually a failed run and its replay), the steps that changed,
// where they first part ways, and a table of every value that differs.

import { useParams } from 'react-router'
import { getPlugin } from '@/agents/registry'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { Panel } from '@/components/Panel'
import { RecorderTrack } from '@/components/RecorderTrack'
import { Loading, Problem } from '@/components/StateBox'
import { RunGraph } from '@/components/graph/RunGraph'
import type { Tag } from '@/components/graph/StepNode'
import { cn } from '@/lib/utils'
import type { Run, Step } from '@/types/contract'

interface Change {
  step: number
  name: string
  field: string
  before: string
  after: string
}

/** Every scalar in a value, by path: {cart: [{qty: 2}]} -> {"cart[0].qty": 2}. */
function flatten(value: unknown, path = '', out: Record<string, unknown> = {}) {
  if (Array.isArray(value)) value.forEach((v, i) => flatten(v, `${path}[${i}]`, out))
  else if (value !== null && typeof value === 'object') Object.entries(value).forEach(([k, v]) => flatten(v, path ? `${path}.${k}` : k, out))
  else out[path] = value
  return out
}

const show = (v: unknown) => (v === undefined ? '—' : JSON.stringify(v))

function diffRuns(a: Run, b: Run): Change[] {
  const ids = [...new Set([...a.steps, ...b.steps].map((s) => s.id))].sort((x, y) => x - y)
  const changes: Change[] = []
  for (const id of ids) {
    const sa = a.steps.find((s) => s.id === id)
    const sb = b.steps.find((s) => s.id === id)
    if (!sa || !sb) {
      changes.push({ step: id, name: (sa ?? sb)!.name, field: '(step)', before: sa ? sa.name : '—', after: sb ? sb.name : '—' })
      continue
    }
    if (sa.name !== sb.name) {
      changes.push({ step: id, name: sb.name, field: '(step)', before: sa.name, after: sb.name })
      continue
    }
    for (const part of ['input', 'output'] as const) {
      const fa = flatten(sa[part]), fb = flatten(sb[part])
      for (const key of [...new Set([...Object.keys(fa), ...Object.keys(fb)])]) {
        if (JSON.stringify(fa[key]) !== JSON.stringify(fb[key])) {
          changes.push({ step: id, name: sa.name, field: `${part === 'input' ? 'in.' : ''}${key}`, before: show(fa[key]), after: show(fb[key]) })
        }
      }
    }
  }
  return changes
}

export function Compare() {
  const { agent = 'pizza', originalId = '', replayId = '' } = useParams()
  const plugin = getPlugin(agent)
  const data = useApi(() => Promise.all([api.run(agent, originalId), api.run(agent, replayId)]), [agent, originalId, replayId])
  if (data.loading) return <Loading what="both runs" />
  if (data.error || !data.data) return <Problem message={data.error ?? 'No data'} back={{ to: `/${agent}`, label: 'Start a new run' }} />
  const [a, b] = data.data

  const changes = diffRuns(a, b)
  const changed = [...new Set(changes.map((c) => c.step))]
  const first = changed[0] ?? null
  const isReplay = b.parent_run_id === a.run_id && b.replayed_from_step != null
  const edited = isReplay ? b.replayed_from_step! : null
  const reused = isReplay ? b.steps.filter((s) => s.id < edited!).map((s) => s.id) : []
  const identical = first === null ? b.steps.length : first - 1

  const side = (run: Run, which: 'a' | 'b') => {
    const tags = (s: Step): Tag[] => which === 'b' && reused.includes(s.id) ? [['plain', 'REUSED']]
      : which === 'b' && s.id === edited ? [['accent', 'EDITED']] : changed.includes(s.id) ? [['bad', 'CHANGED']] : []
    const ok = run.outcome === 'success'
    return (
      <Panel title={which === 'a' ? 'Original' : isReplay ? 'Replay' : 'Other run'}
        sub={<span className={cn('rounded px-2 py-0.5 font-mono text-[11px] font-semibold', ok ? 'bg-good-soft text-good' : 'bg-bad-soft text-bad')}>{ok ? '✓ correct' : '✗ wrong'}</span>}>
        <div className="border-b border-dashed px-3.5 py-2 font-mono text-xs break-all text-muted-foreground">{run.run_id}</div>
        <div className="border-b px-3.5 py-2 text-[13px]">{plugin.resultLine(run)}</div>
        <RunGraph steps={run.steps} label={plugin.stepLabel} changedIds={changed} tags={tags} final={ok ? 'good' : 'bad'}
          cachedIds={which === 'b' ? reused : undefined} editedId={which === 'b' ? edited : null} />
        <RecorderTrack title="Track" right={first ? `differs from step ${first} ▸` : 'identical'} markerAt={first} markerLabel="First difference"
          ticks={run.steps.map((s) => ({ id: s.id, name: s.name, kind: changed.includes(s.id) ? 'diff' : 'same' }))} />
      </Panel>
    )
  }

  return (
    <div className="grid gap-4">
      <div className="grid items-start gap-4 grid-cols-1 lg:grid-cols-2">{side(a, 'a')}{side(b, 'b')}</div>
      <Panel title="What changed"
        sub={first === null ? 'the two runs are identical' : `steps 1–${identical} identical · first difference at step ${first}${first === edited ? ' (your edit)' : ''}`}>
        {changes.length === 0 ? <p className="m-0 p-3.5 text-sm text-muted-foreground">No step differs.</p> : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[13px]">
              <thead>
                <tr className="text-left">
                  {['Step', 'Field', 'Original', isReplay ? 'Replay' : 'Other'].map((h) => (
                    <th key={h} className="border-b px-3 py-2 font-mono text-[10.5px] font-semibold tracking-wider whitespace-nowrap text-muted-foreground uppercase">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {changes.map((c, i) => (
                  <tr key={i} className={cn(c.step === edited && 'bg-recorder-soft')}>
                    <td className="border-b px-3 py-1.5 font-mono whitespace-nowrap">#{c.step} {c.name}</td>
                    <td className="border-b px-3 py-1.5 font-mono">{c.field}{c.step === edited && <span className="ml-2 font-sans text-xs text-recorder-ink">your edit</span>}</td>
                    <td className="border-b px-3 py-1.5 font-mono break-all text-bad line-through decoration-1">{c.before}</td>
                    <td className="border-b px-3 py-1.5 font-mono font-semibold break-all text-good">{c.after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}
