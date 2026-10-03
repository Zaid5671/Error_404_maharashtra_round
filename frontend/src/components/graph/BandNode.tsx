// Background band grouping the steps of one LLM turn.

import type { Node, NodeProps } from '@xyflow/react'

export interface BandNodeData extends Record<string, unknown> {
  index: number
  steps: number
  width: number
  height: number
}

export type BandNodeType = Node<BandNodeData, 'band'>

export function BandNode({ data }: NodeProps<BandNodeType>) {
  return (
    <div
      style={{ width: data.width, height: data.height }}
      className="pointer-events-none rounded-md border border-dashed bg-band"
    >
      <div className="px-2.5 pt-1 font-mono text-[10.5px] font-semibold tracking-wider text-llm uppercase">
        LLM turn {data.index + 1}{' '}
        <span className="font-medium tracking-normal text-muted-foreground normal-case">
          · 1 call → {data.steps} step{data.steps === 1 ? '' : 's'}
        </span>
      </div>
    </div>
  )
}
