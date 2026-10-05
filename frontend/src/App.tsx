// Routes. The agent comes first: each agent has its own runs, model and report.

import { useMemo, useState } from 'react'
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useParams } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { AgentContext } from '@/layout/agentContext'
import { JourneyBar } from '@/layout/JourneyBar'
import { Sidebar } from '@/layout/Sidebar'
import { Agents } from '@/pages/Agents'
import { Compare } from '@/pages/Compare'
import { ComparePicker } from '@/pages/ComparePicker'
import { Diagnosis } from '@/pages/Diagnosis'
import { LiveRun } from '@/pages/LiveRun'
import { Model } from '@/pages/Model'
import { Overview } from '@/pages/Overview'
import { Replay } from '@/pages/Replay'
import { Replays } from '@/pages/Replays'
import { Runs } from '@/pages/Runs'
import { Training } from '@/pages/Training'

/** Sidebar + page. Checks the agent in the URL against the server's list. */
function AgentLayout() {
  const { agent = '' } = useParams()
  const [version, setVersion] = useState(0)
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('bb.sidebar') === 'collapsed' } catch { return false }
  })
  const toggleSidebar = () => setCollapsed((c) => {
    try { localStorage.setItem('bb.sidebar', c ? 'open' : 'collapsed') } catch { /* private window: not remembered */ }
    return !c
  })
  const list = useApi(() => api.agents(), [version])
  const agents = list.data?.items ?? []
  const info = agents.find((a) => a.name === agent) ?? null
  const ctx = useMemo(() => ({
    agent, info, agents, canRun: info ? info.kind === 'connected' : true, online: !!list.data, refresh: () => setVersion((v) => v + 1),
  }), [agent, info, agents, list.data])

  return (
    <AgentContext.Provider value={ctx}>
      <div className={collapsed ? 'lg:grid lg:min-h-dvh lg:grid-cols-[60px_minmax(0,1fr)]' : 'lg:grid lg:min-h-dvh lg:grid-cols-[240px_minmax(0,1fr)]'}>
        <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />
        <main className="min-w-0 px-4 pt-4 pb-8 lg:px-6 lg:pt-5">
          {list.error && <p className="mb-4 rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm" role="alert">{list.error}</p>}
          {list.data && !info ? <NotFound what={`agent “${agent}”`} /> : (
            <>
              <JourneyBar />
              <Outlet />
            </>
          )}
        </main>
      </div>
    </AgentContext.Provider>
  )
}

function NotFound({ what = 'page' }: { what?: string }) {
  return (
    <div className="mx-auto mt-16 grid max-w-md justify-items-start gap-3 rounded-lg border bg-card p-6">
      <span className="bb-label">Not found</span>
      <p className="m-0">There is no {what} here.</p>
      <Link to="/pizza" className="rounded-md bg-recorder px-3 py-1.5 font-semibold text-white">Go to the overview</Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/pizza" replace />} />
        <Route path="/:agent" element={<AgentLayout />}>
          <Route index element={<Overview />} />
          <Route path="new" element={<LiveRun />} />
          <Route path="runs" element={<Runs key="runs" mode="runs" />} />
          <Route path="runs/:runId" element={<LiveRun />} />
          <Route path="runs/:runId/diagnosis" element={<Diagnosis />} />
          <Route path="runs/:runId/replay" element={<Replay />} />
          <Route path="diagnoses" element={<Runs key="diagnoses" mode="diagnoses" />} />
          <Route path="replays" element={<Replays />} />
          <Route path="compare" element={<ComparePicker />} />
          <Route path="compare/:originalId/:replayId" element={<Compare />} />
          <Route path="model" element={<Model tab="accuracy" />} />
          <Route path="model/data" element={<Model tab="data" />} />
          <Route path="model/faults" element={<Model tab="faults" />} />
          <Route path="report" element={<Navigate to="../model" replace />} />
          <Route path="training" element={<Training />} />
          <Route path="agents" element={<Agents />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<div className="p-4"><NotFound /></div>} />
      </Routes>
    </BrowserRouter>
  )
}
