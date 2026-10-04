// One step in the run graph. Visual states for every screen: running, final good/bad and selected
// (Live Run); suspicion heat, culprit and impact (Diagnosis); reused and edited (Replay); changed
// (Compare). Every state also carries a word tag, so nothing relies on colour alone.

import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import type { Step } from '@/types/contract'
import { NODE_H, NODE_W } from './layout'

export type TagTone = 'plain' | 'bad' | 'score' | 'accent' | 'good'
export type Tag = [TagTone, string]

export interface StepNodeData extends Record<string, unknown> {
  step: Step
  label: string
  running?: boolean
  selected?: boolean
  final?: 'good' | 'bad'
  culprit?: boolean
  heat?: number // 0..1 suspicion score
  cached?: boolean
  edited?: boolean
  changed?: boolean
  tags?: Tag[]
}

export type StepNodeType = Node<StepNodeData, 'step'>

const hidden = '!size-1 !min-w-0 !border-0 !bg-transparent'
const TONE: Record<TagTone, string> = {
  plain: 'border bg-sunk text-muted-foreground',
  bad: 'bg-bad text-white',
  score: 'border border-bad bg-card text-bad',
  accent: 'bg-recorder text-white',
  good: 'bg-good text-white',
}

export function StepNode({ data }: NodeProps<StepNodeType>) {
  const { step, label, running, selected, final, culprit, heat, cached, edited, changed, tags } = data
  const heatBg = heat ? `color-mix(in oklab, var(--heat) ${Math.round(heat * 30)}%, var(--card))` : undefined
  return (
    <div
      style={{ width: NODE_W, height: NODE_H, background: heatBg }}
      className={cn(
        'grid cursor-pointer content-start gap-0.5 overflow-hidden rounded-md border bg-card px-2.5 py-2 text-left transition-[border-color,box-shadow]',
        running && 'bb-running border-recorder',
        final === 'good' && 'border-good shadow-[0_0_0_3px_var(--good-soft)]',
        final === 'bad' && 'border-bad shadow-[0_0_0_3px_var(--bad-soft)]',
        changed && 'border-bad',
        culprit && 'border-2 border-bad shadow-[0_0_0_4px_var(--bad-soft),0_0_18px_var(--bad-soft)]',
        cached && 'border-dashed !bg-sunk opacity-60',
        edited && 'border-2 border-recorder !bg-recorder-soft',
        selected && 'shadow-[0_0_0_2px_var(--recorder)]',
      )}
    >
      <Handle type="target" position={Position.Top} className={hidden} isConnectable={false} />
      <Handle type="target" position={Position.Left} id="l" className={hidden} isConnectable={false} />
      <div className="flex items-center justify-between gap-1.5">
        <span className="font-mono text-[11px] text-muted-foreground">#{step.id}</span>
        <Pill className={step.kind === 'llm' ? 'bg-llm-soft text-llm' : 'border bg-sunk text-muted-foreground'}>
          {step.kind.toUpperCase()}
        </Pill>
      </div>
      <div className="truncate font-mono text-[12.5px] font-semibold">{step.name}</div>
      <div className={cn('line-clamp-2 text-xs leading-snug text-foreground/80', step.error && 'text-bad')}>{label}</div>
      {tags && tags.length > 0 && (
        <div className="mt-0.5 flex flex-wrap gap-1">
          {tags.map(([tone, text]) => <Pill key={text} className={TONE[tone]}>{text}</Pill>)}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} className={hidden} isConnectable={false} />
      <Handle type="source" position={Position.Right} id="r" className={hidden} isConnectable={false} />
    </div>
  )
}

function Pill({ className, children }: { className: string; children: string }) {
  return <span className={cn('rounded-[3px] px-1.5 py-px font-mono text-[9.5px] font-semibold tracking-wide whitespace-nowrap', className)}>{children}</span>
}
