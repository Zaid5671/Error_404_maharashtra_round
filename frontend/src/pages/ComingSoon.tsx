// Stand-in for the screens built in P6.

import { Panel } from '@/components/Panel'
import { useRunStore, type Page } from '@/store/runStore'

const ABOUT: Record<Exclude<Page, 'live'>, { title: string; text: string }> = {
  diagnosis: { title: 'Diagnosis', text: 'The trained model scores every step of this run, highlights the most likely culprit, and explains why.' },
  replay: { title: 'Replay', text: 'Edit a suspected step and re-run from there. Earlier steps are reused from the checkpoint, not re-run.' },
  compare: { title: 'Compare', text: 'The original run and the replayed run side by side, with exactly what changed.' },
  report: { title: 'Model Report', text: 'How well the diagnosis model finds known faults, including fault types it never saw in training.' },
}

export function ComingSoon({ page }: { page: Exclude<Page, 'live'> }) {
  const setPage = useRunStore((s) => s.setPage)
  const { title, text } = ABOUT[page]
  return (
    <Panel title={title} sub="built in Phase 6">
      <div className="grid max-w-[60ch] gap-3 p-6">
        <p className="m-0 text-[15px]">{text}</p>
        <button type="button" onClick={() => setPage('live')} className="w-fit rounded-md border bg-sunk px-3 py-1.5 font-medium">
          ← Back to Live Run
        </button>
      </div>
    </Panel>
  )
}
