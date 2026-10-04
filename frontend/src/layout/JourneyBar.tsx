// Inside one run: where you are in its investigation, Run → Diagnose → Fix → Compare.

import { Check } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router'
import { cn } from '@/lib/utils'
import { useLiveRun, useSession } from '@/store/runStore'

type Stage = 'live' | 'diagnosis' | 'replay' | 'compare'

function stageOf(path: string): Stage | null {
  if (/\/diagnosis$/.test(path)) return 'diagnosis'
  if (/\/replay$/.test(path)) return 'replay'
  if (/\/compare\/[^/]+\/[^/]+$/.test(path)) return 'compare'
  if (/\/runs\/[^/]+$/.test(path) || /\/new$/.test(path)) return 'live'
  return null
}

export function JourneyBar() {
  const { agent = 'pizza', runId, originalId, replayId } = useParams()
  const stage = stageOf(useLocation().pathname)
  const lastReplay = useSession((s) => s.lastReplay)
  const live = useLiveRun()
  if (!stage) return null

  const run = runId ?? originalId ?? null
  const compareTo = replayId ?? (lastReplay && lastReplay.agent === agent && lastReplay.original === run ? lastReplay.replay : null)
  const steps: { key: Stage; label: string; to: string | null }[] = [
    { key: 'live', label: 'Run', to: run ? `/${agent}/runs/${run}` : `/${agent}/new` },
    { key: 'diagnosis', label: 'Diagnose', to: run ? `/${agent}/runs/${run}/diagnosis` : null },
    { key: 'replay', label: 'Fix', to: run ? `/${agent}/runs/${run}/replay` : null },
    { key: 'compare', label: 'Compare', to: run && compareTo ? `/${agent}/compare/${run}/${compareTo}` : null },
  ]
  const at = steps.findIndex((s) => s.key === stage)
  const isLive = live.meta?.run_id === runId
  const outcome = isLive ? live.result?.outcome : undefined
  const chip = replayId ?? run

  return (
    <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-card px-3 py-2">
      <ol className="m-0 flex list-none flex-wrap items-center gap-0.5 p-0" aria-label="Investigation">
        {steps.map((s, i) => {
          const done = at > i
          const current = at === i
          const body = (
            <>
              <span className={cn('grid size-5 place-items-center rounded-full border-[1.5px] font-mono text-[11px] font-semibold',
                done && 'border-foreground bg-foreground text-background', current && 'border-recorder bg-recorder-soft text-recorder-ink')}>
                {done ? <Check className="size-3" strokeWidth={3} /> : i + 1}
              </span>
              {s.label}
            </>
          )
          const cls = cn('inline-flex items-center gap-1.5 rounded-md px-2 py-1 font-medium text-muted-foreground', current && 'bg-sunk text-foreground')
          return (
            <li key={s.key} className="flex items-center gap-0.5">
              {i > 0 && <span className="h-[1.5px] w-4 bg-border" aria-hidden="true" />}
              {s.to && !current ? <Link to={s.to} className={cn(cls, 'hover:text-foreground')}>{body}</Link> : (
                <span className={cn(cls, !s.to && 'opacity-50')} aria-current={current ? 'step' : undefined}
                  title={s.to ? undefined : s.key === 'compare' ? 'Replay a fix first' : 'Run the agent first'}>{body}</span>
              )}
            </li>
          )
        })}
      </ol>
      {chip && (
        <span className="ml-auto inline-flex max-w-full min-w-0 items-center gap-2 rounded-full border bg-sunk px-2.5 py-0.5 font-mono text-xs">
          <span className={cn('size-2 flex-none rounded-full', isLive && live.status === 'running' ? 'bg-recorder'
            : outcome === 'success' ? 'bg-good' : outcome === 'failure' ? 'bg-bad' : 'bg-muted-foreground')} />
          <span className="truncate">{chip}</span>
        </span>
      )}
    </div>
  )
}
