// The app's one navigation list, in the order of the problem statement: capture runs, find and
// explain the failing step, replay and try fixes, compare, evaluate, then training and the agents.

import { useEffect, useState } from 'react'
import { Bot, FlaskConical, Gauge, GitCompareArrows, History, LayoutDashboard, ListTree, Menu, PanelLeftClose, PanelLeftOpen, Search, X } from 'lucide-react'
import { NavLink, useLocation, useNavigate } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { applyTheme, loadTheme, onSystemThemeChange, THEME_ORDER, type ThemeChoice } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { OnlineDot } from '@/components/AgentBadges'
import { useAgent } from './agentContext'

/** On wide screens the sidebar can collapse to a strip of icons (`collapsed`); phones use the drawer. */
export function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const { agent, agents, info, online } = useAgent()
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

  const wide = collapsed && 'lg:hidden' // shown only when the sidebar is open (or in the phone drawer)
  const brand = (compact: boolean) => (
    <div className="flex items-center gap-2.5">
      <div className="grid size-[26px] flex-none place-items-center rounded-[5px] bg-recorder" aria-hidden="true">
        <BoxMark className="size-[19px]" />
      </div>
      <div className={cn('leading-tight', compact && wide)}>
        <div className="font-display text-lg font-extrabold tracking-[0.01em]">Black Box</div>
        <div className="text-[11.5px] whitespace-nowrap text-muted-foreground">Flight recorder for AI agents</div>
      </div>
    </div>
  )

  return (
    <>
      {/* phone: a bar with the menu button */}
      <div className="sticky top-[env(safe-area-inset-top,0px)] z-20 flex items-center justify-between border-b bg-background px-4 py-3 lg:hidden">
        {brand(false)}
        <button type="button" onClick={() => setOpen(true)} className="rounded-md border bg-card p-2" aria-label="Open menu"><Menu className="size-4" /></button>
      </div>
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} aria-hidden="true" />}

      <aside className={cn(
        'z-40 flex flex-col gap-5 overflow-y-auto border-r bg-card px-4 py-5',
        collapsed && 'lg:items-center lg:px-2',
        'fixed inset-y-0 left-0 w-[260px] transition-transform lg:sticky lg:top-0 lg:h-dvh lg:w-auto lg:translate-x-0',
        open ? 'translate-x-0' : '-translate-x-full',
      )} aria-label="Main">
        <div className={cn('flex items-start justify-between gap-1', collapsed && 'lg:flex-col lg:items-center lg:gap-3')}>
          {brand(true)}
          <button type="button" onClick={() => setOpen(false)} className="rounded-md p-1 lg:hidden" aria-label="Close menu"><X className="size-4" /></button>
          <button type="button" onClick={onToggle} className={cn('hidden rounded-md p-0.5 text-muted-foreground hover:bg-sunk hover:text-foreground lg:inline-flex', !collapsed && '-mr-2')}
            aria-label={collapsed ? 'Open the sidebar' : 'Close the sidebar'} title={collapsed ? 'Open the sidebar' : 'Close the sidebar'}>
            {collapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
          </button>
        </div>

        <label className={cn('grid gap-1 text-xs font-medium text-muted-foreground', wide)} htmlFor="agent-switch">
          <span className="flex items-center justify-between gap-2">Agent
            {info?.via === 'sdk' && (
              <span className="inline-flex items-center gap-1.5 font-normal" title={info.url}>
                <OnlineDot online={info.online} />{info.online ? 'online' : 'offline'}
              </span>
            )}
          </span>
          <select id="agent-switch" className="h-9 rounded-md border bg-sunk px-2 text-sm text-foreground" value={agent}
            onChange={(e) => { setOpen(false); navigate(`/${e.target.value}`) }}>
            {(agents.length ? agents : [{ name: agent, kind: 'connected' as const }]).map((a) => (
              <option key={a.name} value={a.name}>{a.name}{a.kind === 'imported' ? ' (imported)' : ''}</option>
            ))}
          </select>
        </label>

        <nav className="grid gap-0.5">
          {items.map(({ to, label, icon: Icon, end, count }) => (
            <NavLink key={label} to={`/${agent}${to ? `/${to}` : ''}`} end={end} onClick={() => setOpen(false)} title={collapsed ? label : undefined}
              className={({ isActive }) => cn('flex items-center gap-2.5 rounded-md px-2.5 py-2 font-medium text-muted-foreground hover:bg-sunk hover:text-foreground',
                collapsed && 'lg:justify-center',
                isActive && 'bg-recorder-soft text-recorder-ink hover:bg-recorder-soft hover:text-recorder-ink')}>
              <Icon className="size-4 flex-none" aria-hidden="true" />
              <span className={cn('flex-1', wide)}>{label}</span>
              {count ? <span className={cn('rounded-full bg-sunk px-1.5 font-mono text-[11px] text-muted-foreground tabular-nums', wide)}>{count}</span> : null}
            </NavLink>
          ))}
        </nav>

        <div className={cn('mt-auto grid gap-2 border-t pt-4 text-xs', collapsed && 'lg:justify-items-center')}>
          <button type="button" className={cn('w-fit rounded-md border bg-card px-2.5 py-1', wide)}
            onClick={() => setTheme(THEME_ORDER[(THEME_ORDER.indexOf(theme) + 1) % THEME_ORDER.length])}>
            Theme: {theme}
          </button>
          <span className="inline-flex items-center gap-1.5 text-muted-foreground" role="status" title={`API ${online ? 'connected' : 'not reachable'}`}>
            <span className={cn('size-2 rounded-full', online ? 'bg-good' : 'bg-bad')} />
            <span className={cn(wide)}>API {online ? 'connected' : 'not reachable'}</span>
          </span>
        </div>
      </aside>
    </>
  )
}

/** The brand mark: a solid cube in three faces, split by thin gaps in the tile colour. */
function BoxMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="white" stroke="var(--recorder)" strokeWidth={1.4} strokeLinejoin="round">
      <path d="M12 1.5 21.1 6.75 12 12 2.9 6.75Z" />
      <path d="M2.9 6.75 12 12v10.5L2.9 17.25Z" />
      <path d="M21.1 6.75 12 12v10.5l9.1-5.25Z" />
    </svg>
  )
}
