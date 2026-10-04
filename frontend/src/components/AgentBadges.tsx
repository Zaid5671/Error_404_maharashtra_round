// Small marks for an agent: what kind it is, and whether an agent connected by URL is answering.

import { cn } from '@/lib/utils'
import type { AgentInfo } from '@/types/dashboard'

export function KindBadge({ a }: { a: Pick<AgentInfo, 'kind' | 'via'> }) {
  const [label, cls] = a.kind === 'imported' ? ['IMPORTED', 'border bg-sunk text-muted-foreground']
    : a.via === 'sdk' ? ['CONNECTED', 'bg-recorder-soft text-recorder-ink'] : ['BUILT-IN', 'bg-good-soft text-good']
  return <span className={cn('rounded-[3px] px-1.5 py-0.5 font-mono text-[9.5px] font-semibold tracking-wider whitespace-nowrap', cls)}>{label}</span>
}

export function OnlineDot({ online }: { online?: boolean }) {
  return <span className={cn('inline-block size-2 flex-none rounded-full', online ? 'bg-good' : 'bg-bad')} aria-hidden="true" />
}
