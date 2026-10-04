// Routes (plan.md P6). The agent comes first: each agent has its own runs, model and report.

import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useParams } from 'react-router'
import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { TopBar } from '@/components/TopBar'
import { Compare } from '@/pages/Compare'
import { Diagnosis } from '@/pages/Diagnosis'
import { LiveRun } from '@/pages/LiveRun'
import { Replay } from '@/pages/Replay'
import { Report } from '@/pages/Report'

function Shell({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto max-w-[1480px] px-4 pb-6">{children}</div>
}

/** Checks the agent in the URL against the server's list, then shows the screen. */
function AgentLayout() {
  const { agent = '' } = useParams()
  const agents = useApi(() => api.agents(), [])
  const unknown = agents.data && !agents.data.agents.includes(agent)
  return (
    <Shell>
      <TopBar />
      <main className="pt-4">
        {agents.error && (
          <p className="mb-4 rounded-md border border-bad bg-bad-soft px-3 py-2 text-sm" role="alert">{agents.error}</p>
        )}
        {unknown ? <NotFound what={`agent “${agent}”`} /> : <Outlet />}
      </main>
    </Shell>
  )
}

function NotFound({ what = 'page' }: { what?: string }) {
  return (
    <div className="mx-auto mt-16 grid max-w-md justify-items-start gap-3 rounded-lg border bg-card p-6">
      <span className="bb-label">Not found</span>
      <p className="m-0">There is no {what} here.</p>
      <Link to="/pizza" className="rounded-md bg-recorder px-3 py-1.5 font-semibold text-white">Go to Live Run</Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/pizza" replace />} />
        <Route path="/:agent" element={<AgentLayout />}>
          <Route index element={<LiveRun />} />
          <Route path="runs/:runId" element={<LiveRun />} />
          <Route path="runs/:runId/diagnosis" element={<Diagnosis />} />
          <Route path="runs/:runId/replay" element={<Replay />} />
          <Route path="compare/:originalId/:replayId" element={<Compare />} />
          <Route path="report" element={<Report />} />
          <Route path="*" element={<NotFound />} />
        </Route>
        <Route path="*" element={<Shell><NotFound /></Shell>} />
      </Routes>
    </BrowserRouter>
  )
}
