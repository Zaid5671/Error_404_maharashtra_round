// The app's one navigation list, in the order of the problem statement: capture runs, find and
// explain the failing step, replay and try fixes, compare, evaluate, then training and the agents.

import { useEffect, useState } from 'react'
import { Activity, Bot, FlaskConical, Gauge, GitCompareArrows, History, LayoutDashboard, ListTree, Menu, Search, X } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { applyTheme, loadTheme, onSystemThemeChange, THEME_ORDER, type ThemeChoice } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { useAgent } from './agentContext'

export function Sidebar() {
  const { agent, agents, online } = useAgent()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const [theme, setTheme] = useState<ThemeChoice>(loadTheme)
  const counts = useApi(() => api.overview(agent), [agent, location.pathname])

  useEffect(() => {
    applyTheme(theme)
    return onSystemThemeChange(() => applyTheme(theme))
  }, [theme])

  const items = [
    { to: '', label: 'Overview', icon: LayoutDashboard, end: true },
    { to: 'runs', label: 'Runs', icon: ListTree },
    { to: 'diagnoses', label: 'Diagnoses', icon: Search, count: counts.data?.failed_runs },
    { to: 'replays', label: 'Replays', icon: History, count: counts.data?.replays },
    { to: 'compare', label: 'Compare', icon: GitCompareArrows },
    { to: 'model', label: 'Model', icon: Gauge },
    { to: 'training', label: 'Training', icon: FlaskConical },
    { to: 'agents', label: 'Agents', icon: Bot },
  ]

  const brand = (
    <div className="flex items-center gap-2.5">
      <div className="grid size-[26px] flex-none place-items-center rounded-[5px] bg-recorder" aria-hidden="true">
        <Activity className="size-4 text-white" strokeWidth={2.75} />
      </div>
      <div className="leading-tight">
        <div className="font-display text-lg font-extrabold tracking-[0.01em]">Black Box</div>
        <div className="text-[11.5px] text-muted-foreground">Flight recorder for AI agents</div>
      </div>
    </div>
  )

  return (
    <>
      {/* phone: a bar with the menu button */}
      <div className="sticky top-[env(safe-area-inset-top,0px)] z-20 flex items-center justify-between border-b bg-background px-4 py-3 lg:hidden">
        {brand}
        <button type="button" onClick={() => setOpen(true)} className="rounded-md border bg-card p-2" aria-label="Open menu"><Menu className="size-4" /></button>
      </div>
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}

      <aside className={cn(
        'z-40 flex flex-col gap-5 overflow-y-auto border-r bg-card px-4 py-5',
        'fixed inset-y-0 left-0 w-[260px] transition-transform lg:sticky lg:top-0 lg:h-dvh lg:w-auto lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full',
      )} aria-label="Main">
        <div className="flex items-start justify-between gap-2">
          {brand}
          <button type="button" onClick={() => setOpen(false)} className="rounded-md p-1 lg:hidden" aria-label="Close menu"><X className="size-4" /></button>
        </div>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground" htmlFor="agent-switch">
          Agent
          <select id="agent-switch" className="h-9 rounded-md border bg-sunk px-2 text-sm text-foreground" value={agent}
            onChange={(e) => { setOpen(false); navigate(`/${e.target.value}`) }}>
            {(agents.length ? agents : [{ name: agent, kind: 'connected' as const }]).map((a) => (
              <option key={a.name} value={a.name}>{a.name}{a.kind === 'imported' ? ' (imported)' : ''}</option>
            ))}
          </select>
        </label>

        <nav className="grid gap-0.5">
          {items.map(({ to, label, icon: Icon, end, count }) => (
            <NavLink key={label} to={`/${agent}${to ? `/${to}` : ''}`} end={end} onClick={() => setOpen(false)}
              className={({ isActive }) => cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 font-medium text-muted-foreground hover:bg-sunk hover:text-foreground',
                isActive && 'bg-recorder-soft text-recorder-ink hover:bg-recorder-soft hover:text-recorder-ink')}>
              <Icon className="size-4 flex-none" aria-hidden="true" />
              <span className="flex-1">{label}</span>
              {count ? <span className="rounded-full bg-sunk px-1.5 font-mono text-[11px] text-muted-foreground tabular-nums">{count}</span> : null}
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto grid gap-2 border-t pt-4 text-xs">
          <button type="button" className="w-fit rounded-md border bg-card px-2.5 py-1"
            onClick={() => setTheme(THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length])}>
            Theme: {theme}
          </button>
          <span className="inline-flex items-center gap-1.5 text-muted-foreground" role="status">
            <span className={cn('size-2 rounded-full', online ? 'bg-good' : 'bg-bad')} />
            API {online ? 'connected' : 'not reachable'}
          </span>
        </div>
      </aside>
    </>
  )
}
