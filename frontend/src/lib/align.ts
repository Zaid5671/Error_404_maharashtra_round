// Line up two runs by what their steps did, like a text diff, not by step number. After a fix
// the agent may skip a detour or reorder calls, so step #9 in one run can be step #6 in the other.
//
// A weighted longest-common-subsequence pairs steps in order: same tool, input and output scores
// 3, same tool and input 2, same tool 1. Steps left over that share a tool name are then paired
// as "moved" (the agent called them in a different order). Whatever remains exists in one run only.

import type { Step } from '@/types/contract'

export interface FieldChange {
  field: string
  before: string
  after: string
}

export type PairKind = 'same' | 'changed' | 'moved' | 'onlyA' | 'onlyB'

export interface Pair {
  a: Step | null
  b: Step | null
  kind: PairKind
  changes: FieldChange[]
}

/** Every scalar in a value, by path: {cart: [{qty: 2}]} -> {"cart[0].qty": 2}. */
export function flatten(value: unknown, path = '', out: Record<string, unknown> = {}) {
  if (Array.isArray(value)) value.forEach((v, i) => flatten(v, `${path}[${i}]`, out))
  else if (value !== null && typeof value === 'object') Object.entries(value).forEach(([k, v]) => flatten(v, path ? `${path}.${k}` : k, out))
  else out[path] = value
  return out
}

const show = (v: unknown) => (v === undefined ? '—' : JSON.stringify(v))
const same = (x: unknown, y: unknown) => JSON.stringify(x) === JSON.stringify(y)

export function fieldChanges(a: Step, b: Step): FieldChange[] {
  const out: FieldChange[] = []
  for (const part of ['input', 'output'] as const) {
    const fa = flatten(a[part]), fb = flatten(b[part])
    for (const key of new Set([...Object.keys(fa), ...Object.keys(fb)])) {
      if (!same(fa[key], fb[key])) out.push({ field: `${part === 'input' ? 'in.' : ''}${key}`, before: show(fa[key]), after: show(fb[key]) })
    }
  }
  return out
}

function score(a: Step, b: Step): number {
  if (a.name !== b.name) return 0
  if (!same(a.input, b.input)) return 1
  return same(a.output, b.output) ? 3 : 2
}

export function alignRuns(as: Step[], bs: Step[]): Pair[] {
  const n = as.length, m = bs.length
  const dp = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0))
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      const s = score(as[i], bs[j])
      dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1], s ? s + dp[i + 1][j + 1] : 0)
    }
  }
  const pairs: Pair[] = []
  let i = 0, j = 0
  while (i < n || j < m) {
    const s = i < n && j < m ? score(as[i], bs[j]) : 0
    if (s && dp[i][j] === s + dp[i + 1][j + 1]) {
      const changes = fieldChanges(as[i], bs[j])
      pairs.push({ a: as[i], b: bs[j], kind: changes.length ? 'changed' : 'same', changes })
      i++; j++
    } else if (j >= m || (i < n && dp[i + 1][j] >= dp[i][j + 1])) {
      pairs.push({ a: as[i++], b: null, kind: 'onlyA', changes: [] })
    } else {
      pairs.push({ a: null, b: bs[j++], kind: 'onlyB', changes: [] })
    }
  }
  // the same tool called at a different point: pair it as moved, kept where it was in run A
  for (const p of pairs) {
    if (p.kind !== 'onlyA') continue
    const q = pairs.find((x) => x.kind === 'onlyB' && x.b!.name === p.a!.name)
    if (!q) continue
    p.b = q.b
    p.kind = 'moved'
    p.changes = fieldChanges(p.a!, p.b!)
    pairs.splice(pairs.indexOf(q), 1)
  }
  return pairs
}
