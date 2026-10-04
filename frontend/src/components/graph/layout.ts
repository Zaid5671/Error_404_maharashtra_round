// Turn-aware layout. Rows follow the data flow (a step sits one row below the deepest step it
// uses), but a step never sits above its own LLM turn, so every turn is one contiguous band.
// A step with LLM stats starts a turn; the steps after it in the same response share it.

import type { Step } from '@/types/contract'

export const NODE_W = 156
export const NODE_H = 116
const GAP_X = 14
const GAP_Y = 40
const BAND_LABEL = 24
const PAD = 16

export interface Band {
  index: number // 0-based turn number
  stepIds: number[]
  y: number
  height: number
}

export interface GraphLayout {
  positions: Record<number, { x: number; y: number }>
  rowOf: Record<number, number>
  bands: Band[]
  width: number
  height: number
}

export function llmTurns(steps: Step[]): Step[][] {
  const turns: Step[][] = []
  for (const step of steps) {
    if (step.llm || turns.length === 0) turns.push([])
    turns[turns.length - 1].push(step)
  }
  return turns
}

export function layoutSteps(steps: Step[]): GraphLayout {
  const turns = llmTurns(steps)
  const rowOf: Record<number, number> = {}
  const firstRow: number[] = []
  const lastRow: number[] = []

  turns.forEach((turn, k) => {
    firstRow[k] = k === 0 ? 0 : lastRow[k - 1] + 1
    lastRow[k] = firstRow[k]
    for (const step of turn) {
      const known = step.uses.filter((u) => u in rowOf)
      const depRow = known.length ? 1 + Math.max(...known.map((u) => rowOf[u])) : 0
      rowOf[step.id] = Math.max(depRow, firstRow[k])
      lastRow[k] = Math.max(lastRow[k], rowOf[step.id])
    }
  })

  const nRows = steps.length ? lastRow[lastRow.length - 1] + 1 : 0
  const rows: number[][] = Array.from({ length: nRows }, () => [])
  steps.forEach((s) => rows[rowOf[s.id]].push(s.id))

  const widest = Math.max(1, ...rows.map((r) => r.length))
  const width = Math.max(widest * (NODE_W + GAP_X) - GAP_X + PAD * 2, 250) // room for the turn label
  const rowY: number[] = []
  let y = PAD
  for (let r = 0; r < nRows; r++) {
    if (firstRow.includes(r)) y += BAND_LABEL
    rowY[r] = y
    y += NODE_H + GAP_Y
  }

  const positions: GraphLayout['positions'] = {}
  rows.forEach((ids, r) => {
    const rowWidth = ids.length * (NODE_W + GAP_X) - GAP_X
    const x0 = (width - rowWidth) / 2
    ids.forEach((id, i) => (positions[id] = { x: x0 + i * (NODE_W + GAP_X), y: rowY[r] }))
  })

  const bands = turns.map((turn, k) => {
    const top = rowY[firstRow[k]] - BAND_LABEL - 6
    return { index: k, stepIds: turn.map((s) => s.id), y: top, height: rowY[lastRow[k]] + NODE_H + 10 - top }
  })
  return { positions, rowOf, bands, width, height: y - GAP_Y + PAD }
}
