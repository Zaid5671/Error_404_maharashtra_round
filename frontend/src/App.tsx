import { TopBar } from '@/components/TopBar'
import { ComingSoon } from '@/pages/ComingSoon'
import { LiveRun } from '@/pages/LiveRun'
import { useRunStore } from '@/store/runStore'

function App() {
  const page = useRunStore((s) => s.page)
  return (
    <div className="mx-auto max-w-[1480px] px-4 pb-6">
      <TopBar />
      <main className="pt-4">{page === 'live' ? <LiveRun /> : <ComingSoon page={page} />}</main>
    </div>
  )
}

export default App
