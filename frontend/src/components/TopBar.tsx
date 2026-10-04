// Brand, agent, the investigation journey (Run → Diagnose → Fix → Compare), Model Report,
// the current run and the theme. Every link is a URL, so refresh and the back button work.

import { useEffect, useState } from 'react'
import { Check } from 'lucide-react'
import { Link, useLocation, useParams } from 'react-router'
import { cn } from '@/lib/utils'
import { applyTheme, loadTheme, onSystemThemeChange, THEME_ORDER, type ThemeChoice } from '@/lib/theme'
import { useLiveRun, useSession } from '@/store/runStore'

type Screen = 'live' | 'diagnosis' | 'replay' | 'compare' | 'report' | 'other'

function screenOf(path: string): Screen {
  if (/\/report$/.test(path)) return 'report'
  if (/\/diagnosis$/.test(path)) return 'diagnosis'
  if (/\/replay$/.test(path)) return 'replay'
  if (/\/compare\//.test(path)) return 'compare'
  if (/^\/[^/]+(\/runs\/[^/]+)?\/?$/.test(path)) return 'live'
  return 'other'
}

export function TopBar() {
  const { agent = 'pizza', runId, originalId, replayId } = useParams()
  const screen = screenOf(useLocation().pathname)
  const lastReplay = useSession((s) => s.lastReplay)
  const live = useLiveRun()
  const [theme, setTheme] = useState<ThemeChoice>(loadTheme)

  useEffect(() => {
    applyTheme(theme)
    return onSystemThemeChange(() => applyTheme(theme))
  }, [theme])

  const run = runId ?? originalId ?? null
  const compareTo = replayId ?? (lastReplay && lastReplay.agent === agent && lastReplay.original === run ? lastReplay.replay : null)
  const steps: { key: Screen; label: string; to: string | null }[] = [
    { key: 'live', label: 'Run', to: run ? `/${agent}/runs/${run}` : `/${agent}` },
    { key: 'diagnosis', label: 'Diagnose', to: run ? `/${agent}/runs/${run}/diagnosis` : null },
    { key: 'replay', label: 'Fix', to: run ? `/${agent}/runs/${run}/replay` : null },
    { key: 'compare', label: 'Compare', to: run && compareTo ? `/${agent}/compare/${run}/${compareTo}` : null },
  ]
  const at = steps.findIndex((s) => s.key === screen)

  const isLive = live.meta?.run_id === runId
  const outcome = isLive ? live.result?.outcome : undefined
  const dot = isLive && live.status === 'running' ? 'bg-recorder' : outcome === 'success' ? 'bg-good' : outcome === 'failure' ? 'bg-bad' : 'bg-muted-foreground'
  const chip = replayId ?? run

  return (
    <header className="sticky top-[env(safe-area-inset-top,0px)] z-10 flex flex-wrap items-center gap-x-5 gap-y-3 border-b bg-background py-3">
      <Link to={`/${agent}`} className="flex items-center gap-2.5">
        <div className="grid size-[26px] place-items-center rounded-[5px] bg-recorder" aria-hidden="true">
          <span className="size-2.5 rounded-full border-2 border-card" />
        </div>
        <h1 className="m-0 font-display text-lg leading-none font-extrabold tracking-[0.01em]">Black Box</h1>
      </Link>
      <span className="rounded border px-1.5 py-0.5 font-mono text-xs text-muted-foreground">agent: {agent}</span>

      <nav className="flex flex-1 flex-wrap items-center gap-x-3.5 gap-y-2 max-md:order-last max-md:basis-full" aria-label="Investigation">
        <ol className="m-0 flex list-none flex-wrap items-center gap-0.5 p-0">
          {steps.map((s, i) => {
            const done = at > i
            const current = at === i
            const body = (
              <>
                <span className={cn('grid size-5 place-items-center rounded-full border-[1.5px] font-mono text-[11px] font-semibold',
                  done && 'border-foreground bg-foreground text-background',
                  current && 'border-recorder bg-recorder-soft text-recorder-ink')}>
                  {done ? <Check className="size-3" strokeWidth={3} /> : i + 1}
                </span>
                {s.label}
              </>
            )
            const cls = cn('inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 font-medium text-muted-foreground',
              current && 'bg-card text-foreground shadow-[0_0_0_1px_var(--border)]')
            return (
              <li key={s.key} className="flex items-center gap-0.5">
                {i > 0 && <span className="h-[1.5px] w-4 bg-border" aria-hidden="true" />}
                {s.to && !current ? (
                  <Link to={s.to} className={cn(cls, 'hover:text-foreground')}>{body}</Link>
                ) : (
                  <span className={cn(cls, !s.to && 'opacity-50')} aria-current={current ? 'step' : undefined}
                    title={s.to ? undefined : s.key === 'compare' ? 'Replay a fix first' : 'Run the agent first'}>
                    {body}
                  </span>
                )}
              </li>
            )
          })}
        </ol>
        <Link to={`/${agent}/report`} aria-current={screen === 'report' ? 'page' : undefined}
          className={cn('rounded-md border px-2.5 py-1.5 font-medium text-muted-foreground hover:text-foreground',
            screen === 'report' && 'bg-card text-foreground')}>
          Model Report
        </Link>
      </nav>

      {chip && (
        <span className="inline-flex max-w-full min-w-0 items-center gap-2 rounded-full border bg-card px-2.5 py-0.5 font-mono text-xs">
          <span className={cn('size-2 flex-none rounded-full', dot)} />
          <span className="truncate">{chip}{outcome ? (outcome === 'success' ? ' · ✓' : ' · ✗') : ''}</span>
        </span>
      )}
      <button type="button" className="rounded-md border bg-card px-2.5 py-1 text-xs"
        onClick={() => setTheme(THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length])}>
        Theme: {theme}
      </button>
    </header>
  )
}
