// Fault picker for Live Run: None / Surprise me / Choose… from the agent's own fault catalogue
// (GET /faults/{agent}). Tool faults can be hidden in a live run; LLM faults need a re-run from
// step 1, so they are listed but disabled. The model is never told what was picked.

import { api } from '@/api/client'
import { useApi } from '@/api/useApi'
import { cn } from '@/lib/utils'
import { useSession, type FaultMode } from '@/store/runStore'
import type { FaultInfo } from '@/types/contract'

const MODES: [FaultMode, string][] = [['none', 'None'], ['surprise', 'Surprise me'], ['choose', 'Choose…']]
const HINT: Record<FaultMode, string> = {
  none: 'Runs the agent as normal.',
  surprise: 'Secretly breaks one step. Can the Black Box find it later?',
  choose: 'Hide this fault in the run. The model is never told which one you picked.',
}

export function FaultPicker({ agent }: { agent: string }) {
  const { faultMode, faultType, setFault } = useSession()
  const faults = useApi(() => api.faults(agent), [agent])
  const list = faults.data ?? []
  const live = list.filter((f) => f.live)
  const other = list.filter((f) => !f.live)

  return (
    <div className="grid gap-2">
      <div className="grid gap-1 text-xs font-medium text-muted-foreground">
        Fault
        <div className="grid grid-cols-3 rounded-[7px] border bg-sunk p-[3px]" role="group" aria-label="Fault mode">
          {MODES.map(([m, label]) => (
            <button key={m} type="button" aria-pressed={faultMode === m}
              onClick={() => setFault(m, m === 'choose' ? (faultType ?? live[0]?.type ?? null) : null)}
              className={cn('rounded-[5px] px-1 py-1.5 text-sm font-medium whitespace-nowrap text-muted-foreground',
                faultMode === m && 'bg-card text-foreground shadow-[0_0_0_1px_var(--border)]')}>
              {label}
            </button>
          ))}
        </div>
      </div>
      {faultMode === 'choose' && (
        <div className="grid gap-1" role="radiogroup" aria-label="Fault to hide">
          {faults.error && <p className="m-0 text-xs text-bad">{faults.error}</p>}
          {live.length > 0 && <span className="mt-1 font-mono text-[10.5px] font-semibold tracking-wider text-muted-foreground uppercase">Tool faults · hidden during the run</span>}
          {live.map((f) => <Row key={f.type} fault={f} checked={faultType === f.type} onPick={() => setFault('choose', f.type)} />)}
          {other.length > 0 && <span className="mt-1 font-mono text-[10.5px] font-semibold tracking-wider text-muted-foreground uppercase">LLM faults · need a re-run from step 1</span>}
          {other.map((f) => <Row key={f.type} fault={f} checked={false} />)}
        </div>
      )}
      <p className="m-0 text-xs text-muted-foreground">{HINT[faultMode]}</p>
    </div>
  )
}

function Row({ fault, checked, onPick }: { fault: FaultInfo; checked: boolean; onPick?: () => void }) {
  const id = `fault-${fault.type}`
  return (
    <label htmlFor={id} className={cn('grid grid-cols-[16px_minmax(0,1fr)_auto] items-center gap-2 rounded-md border bg-sunk px-2 py-1.5 text-[12.5px]',
      onPick ? 'cursor-pointer' : 'cursor-not-allowed opacity-55', checked && 'border-recorder bg-recorder-soft')}>
      <input id={id} type="radio" name="fault" className="m-0 accent-[var(--recorder)]" checked={checked} disabled={!onPick} onChange={onPick} />
      <span className="min-w-0">
        <span className="block font-mono text-xs font-medium break-words">{fault.type}</span>
        <span className="block text-[11.5px] text-muted-foreground">
          breaks <span className="font-mono">{fault.step_name}</span>{onPick ? '' : ' · see the prepared runs'}
        </span>
      </span>
      <SeenBadge seen={fault.seen} />
    </label>
  )
}

export function SeenBadge({ seen }: { seen: boolean }) {
  return (
    <span className={cn('rounded-[3px] border px-1.5 py-0.5 font-mono text-[9.5px] font-semibold tracking-wider whitespace-nowrap',
      seen ? 'text-muted-foreground' : 'border-llm bg-llm-soft text-llm')}
      title={seen ? 'The model trained on this fault type' : 'The model never saw this fault type in training'}>
      {seen ? 'SEEN' : 'UNSEEN'}
    </span>
  )
}
