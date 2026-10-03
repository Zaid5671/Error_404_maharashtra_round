// Brand, agent, the five screens (locked until a run exists), the current run and the theme.

import { useEffect, useState } from 'react'
import { Lock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { applyTheme, loadTheme, onSystemThemeChange, THEME_ORDER, type ThemeChoice } from '@/lib/theme'
import { useRunStore, type Page } from '@/store/runStore'

const SCREENS: { page: Page; label: string }[] = [
  { page: 'live', label: 'Live Run' },
  { page: 'diagnosis', label: 'Diagnosis' },
  { page: 'replay', label: 'Replay' },
  { page: 'compare', label: 'Compare' },
  { page: 'report', label: 'Model Report' },
]

export function TopBar() {
  const { page, setPage, hasRun, agent, status, meta, result } = useRunStore()
  const [theme, setTheme] = useState<ThemeChoice>(loadTheme)

  useEffect(() => {
    applyTheme(theme)
    return onSystemThemeChange(() => applyTheme(theme))
  }, [theme])

  const chip = status === 'running' ? 'running' : result ? (result.outcome === 'success' ? 'good' : 'bad') : 'idle'
  const chipText = meta ? `${meta.run_id}${result ? (result.outcome === 'success' ? ' · ✓' : ' · ✗') : ''}` : 'no run yet'

  return (
    <header className="sticky top-[env(safe-area-inset-top,0px)] z-10 flex flex-wrap items-center gap-x-5 gap-y-3 border-b bg-background py-3.5">
      <div className="flex items-center gap-2.5">
        <div className="grid size-[26px] place-items-center rounded-[5px] bg-recorder" aria-hidden="true">
          <span className="size-2.5 rounded-full border-2 border-card" />
        </div>
        <h1 className="m-0 font-display text-lg leading-none font-extrabold tracking-[0.01em]">Black Box</h1>
        <span className="rounded border px-1.5 py-0.5 font-mono text-xs text-muted-foreground">agent: {agent}</span>
      </div>

      <nav className="flex flex-1 flex-wrap gap-1 max-md:order-last max-md:basis-full" aria-label="Screens">
        {SCREENS.map(({ page: p, label }) => {
          const locked = p !== 'live' && !hasRun
          return (
            <button key={p} type="button" disabled={locked} aria-current={page === p ? 'page' : undefined}
              title={locked ? 'Run an order first' : undefined} onClick={() => setPage(p)}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md border border-transparent px-3 py-1.5 font-medium text-muted-foreground',
                page === p && 'border-border bg-card text-foreground',
                locked ? 'cursor-not-allowed opacity-55' : 'hover:text-foreground',
              )}>
              {locked && <Lock className="size-3" aria-hidden="true" />}
              {label}
            </button>
          )
        })}
      </nav>

      <span className="inline-flex max-w-full items-center gap-2 rounded-full border bg-card px-2.5 py-0.5 font-mono text-xs">
        <span className={cn('size-2 flex-none rounded-full bg-muted-foreground',
          chip === 'running' && 'bg-recorder', chip === 'good' && 'bg-good', chip === 'bad' && 'bg-bad')} />
        <span className="truncate">{chipText}</span>
      </span>

      <button type="button" className="rounded-md border bg-card px-2.5 py-1 text-xs"
        onClick={() => setTheme(THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length])}>
        Theme: {theme}
      </button>
    </header>
  )
}
