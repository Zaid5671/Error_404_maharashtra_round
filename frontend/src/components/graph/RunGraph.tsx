// The run graph used by every screen: steps as nodes, `uses` as arrows, LLM turns as bands.
// Fits itself to the panel as steps arrive; zoom and pan with the mouse or the controls.

import { useEffect, useMemo, useRef, useState } from 'react'
import { Background, Controls, ReactFlow, ReactFlowProvider, useReactFlow, type Edge, type Node } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import type { Step } from '@/types/contract'
import { BandNode, type BandNodeType } from './BandNode'
import { layoutSteps, type GraphLayout } from './layout'
import { StepNode, type StepNodeData, type StepNodeType, type Tag } from './StepNode'

export interface RunGraphProps {
  steps: Step[]
  label: (step: Step) => string
  selectedId?: number | null
  onSelect?: (id: number) => void
  runningId?: number | null
  final?: 'good' | 'bad' | null
  /** Diagnosis: suspicion per step (0..1), the culprit and the path its output took */
  scores?: Record<string, number>
  culpritId?: number | null
  impactPath?: number[]
  /** Replay and Compare */
  cachedIds?: number[]
  editedId?: number | null
  changedIds?: number[]
  /** Word labels under each step, so no state relies on colour alone */
  tags?: (step: Step) => Tag[]
  height?: number
}

const nodeTypes = { step: StepNode, band: BandNode }

function Graph(props: RunGraphProps & { layout: GraphLayout }) {
  const { steps, label, selectedId, onSelect, runningId, final, scores, culpritId, impactPath, cachedIds, editedId, changedIds, tags, layout } = props
  const { fitView } = useReactFlow()

  const nodes = useMemo<Node[]>(() => {
    const bands: BandNodeType[] = layout.bands.map((b) => ({
      id: `band-${b.index}`,
      type: 'band',
      position: { x: 0, y: b.y },
      data: { index: b.index, steps: b.stepIds.length, width: layout.width, height: b.height },
      draggable: false,
      selectable: false,
      focusable: false,
      zIndex: -1,
    }))
    const last = steps.at(-1)?.id
    const stepNodes: StepNodeType[] = steps.map((s) => {
      const data: StepNodeData = {
        step: s,
        label: label(s),
        running: s.id === runningId,
        selected: s.id === selectedId,
        final: s.id === last && final ? final : undefined,
        culprit: s.id === culpritId,
        heat: scores?.[String(s.id)],
        cached: cachedIds?.includes(s.id),
        edited: s.id === editedId,
        changed: changedIds?.includes(s.id),
        tags: tags?.(s),
      }
      return { id: String(s.id), type: 'step', position: layout.positions[s.id], data, draggable: false }
    })
    return [...bands, ...stepNodes]
  }, [layout, steps, label, runningId, selectedId, final, culpritId, scores, cachedIds, editedId, changedIds, tags])

  const edges = useMemo<Edge[]>(
    () =>
      steps.flatMap((s) =>
        s.uses
          .filter((u) => u in layout.positions)
          .map((u) => {
            const sameRow = layout.rowOf[u] === layout.rowOf[s.id]
            const hot = selectedId === s.id || selectedId === u
            const impact = impactPath?.includes(u) && impactPath.includes(s.id)
            const style = impact
              ? { stroke: 'var(--bad)', strokeWidth: 2.4 }
              : hot
                ? { stroke: 'var(--recorder)', strokeWidth: 2 }
                : impactPath?.length ? { strokeWidth: 1.2, opacity: 0.35 } : { strokeWidth: 1.4 }
            return {
              id: `e${u}-${s.id}`,
              source: String(u),
              target: String(s.id),
              sourceHandle: sameRow ? 'r' : undefined,
              targetHandle: sameRow ? 'l' : undefined,
              type: sameRow ? 'smoothstep' : 'default',
              style,
            }
          }),
      ),
    [steps, layout, selectedId, impactPath],
  )

  useEffect(() => {
    const t = setTimeout(() => fitView({ padding: 0.04, maxZoom: 1, duration: 250 }), 30)
    return () => clearTimeout(t)
  }, [steps.length, fitView])

  useEffect(() => {
    const refit = () => fitView({ padding: 0.04, maxZoom: 1 })
    window.addEventListener('resize', refit)
    return () => window.removeEventListener('resize', refit)
  }, [fitView])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      onNodeClick={(_, node) => node.type === 'step' && onSelect?.(Number(node.id))}
      nodesConnectable={false}
      elementsSelectable={false}
      fitView
      fitViewOptions={{ padding: 0.04, maxZoom: 1 }}
      minZoom={0.3}
      maxZoom={1.5}
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={24} size={1} color="var(--border)" />
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
  )
}

export function RunGraph(props: RunGraphProps) {
  const layout = useMemo(() => layoutSteps(props.steps), [props.steps])
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = box.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  // Tall enough to show the whole run at the zoom that fits the panel's width (no empty bands on
  // narrow screens); very long runs cap out and zoom out further (or pan / zoom by hand).
  const scale = width ? Math.min(1, (width - 16) / layout.width) : 1
  const height = props.height ?? Math.min(Math.max(layout.height * scale + 24, 220), 1000)
  return (
    <div ref={box} style={{ height }} className="w-full">
      <ReactFlowProvider>
        <Graph {...props} layout={layout} />
      </ReactFlowProvider>
    </div>
  )
}
