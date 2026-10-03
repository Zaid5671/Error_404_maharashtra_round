// One step in the run graph. Visual states for every screen: running, final good/bad and selected
// (Live Run); culprit, heat, cached and edited (Diagnosis and Replay, P6).

import { Handle, Position, type Node, type NodeProps } from '@xyflow/react'
import { cn } from '@/lib/utils'
import type { Step } from '@/types/contract'
import { NODE_H, NODE_W } from './layout'

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
}

export type StepNodeType = Node<StepNodeData, 'step'>

const hidden = '!size-1 !min-w-0 !border-0 !bg-transparent'

export function StepNode({ data }: NodeProps<StepNodeType>) {
  const { step, label, running, selected, final, culprit, heat, cached, edited } = data
  const heatBg = heat !== undefined ? `color-mix(in oklab, var(--bad-soft) ${Math.round(heat * 100)}%, var(--card))` : undefined
  return (
    <div
      style={{ width: NODE_W, height: NODE_H, background: heatBg }}
      className={cn(
        'grid cursor-pointer content-start gap-0.5 overflow-hidden rounded-md border bg-card px-2.5 py-2 text-left transition-[border-color,box-shadow]',
        running && 'bb-running border-recorder',
        final === 'good' && 'border-good shadow-[0_0_0_3px_var(--good-soft)]',
        final === 'bad' && 'border-bad shadow-[0_0_0_3px_var(--bad-soft)]',
        culprit && 'border-bad shadow-[0_0_0_4px_var(--bad-soft)]',
        cached && 'border-dashed bg-sunk opacity-70',
        edited && 'border-recorder bg-recorder-soft',
        selected && 'shadow-[0_0_0_2px_var(--recorder)]',
      )}
    >
      <Handle type="target" position={Position.Top} className={hidden} isConnectable={false} />
      <Handle type="target" position={Position.Left} id="l" className={hidden} isConnectable={false} />
      <div className="flex items-center justify-between gap-1.5">
        <span className="font-mono text-[11px] text-muted-foreground">#{step.id}</span>
        <span className="flex items-center gap-1">
          {cached && <Pill className="border bg-sunk text-muted-foreground">CACHED</Pill>}
          {edited && <Pill className="bg-recorder text-white">EDITED</Pill>}
          <Pill className={step.kind === 'llm' ? 'bg-llm-soft text-llm' : 'border bg-sunk text-muted-foreground'}>
            {step.kind.toUpperCase()}
          </Pill>
        </span>
      </div>
      <div className="truncate font-mono text-[12.5px] font-semibold">{step.name}</div>
      <div className={cn('line-clamp-2 text-xs leading-snug text-foreground/80', step.error && 'text-bad')}>{label}</div>
      <Handle type="source" position={Position.Bottom} className={hidden} isConnectable={false} />
      <Handle type="source" position={Position.Right} id="r" className={hidden} isConnectable={false} />
    </div>
  )
}

function Pill({ className, children }: { className: string; children: string }) {
  return <span className={cn('rounded-[3px] px-1.5 py-px font-mono text-[10px] font-semibold tracking-wide', className)}>{children}</span>
}
