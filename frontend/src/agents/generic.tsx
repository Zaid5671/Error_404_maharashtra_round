// Fallbacks for agents without their own UI parts. They only read the generic trace format.

import { useState } from 'react'
import type { Step } from '@/types/contract'
import type { Json, ResultInfo, TaskFormProps } from './types'

export function genericStepLabel(step: Step): string {
  const bits: string[] = []
  for (const [key, value] of Object.entries(step.output)) {
    if (bits.length >= 3) break
    if (Array.isArray(value)) bits.push(`${value.length} ${key}`)
    else if (value !== null && typeof value !== 'object') {
      bits.push(`${key} ${typeof value === 'boolean' ? (value ? 'yes' : 'no') : String(value)}`)
    }
  }
  return bits.join(' · ')
}

export function GenericTaskForm({ task, onChange }: TaskFormProps) {
  const [text, setText] = useState(() => JSON.stringify(task, null, 2))
  const [error, setError] = useState<string | null>(null)
  return (
    <label className="grid gap-1 text-xs font-medium text-muted-foreground" htmlFor="task-json">
      Task (JSON)
      <textarea
        id="task-json"
        className="min-h-48 rounded-md border bg-sunk p-2 font-mono text-xs text-foreground"
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          try {
            onChange(JSON.parse(e.target.value) as Json)
            setError(null)
          } catch {
            setError('Not valid JSON yet')
          }
        }}
      />
      {error && <span className="text-bad">{error}</span>}
    </label>
  )
}

export function GenericTaskSummary({ task }: { task: Json }) {
  return <pre className="max-h-40 overflow-auto rounded-md border bg-sunk p-2 font-mono text-xs">{JSON.stringify(task, null, 2)}</pre>
}

export function genericResultLine({ outcome, expected, actual }: ResultInfo) {
  if (outcome === 'success') return 'The result matches the expected one.'
  if (actual === null) return 'The agent finished without producing a result.'
  if (expected === null) return 'The agent acted, but the correct behaviour was to do nothing.'
  const differing = Object.keys(expected).filter((k) => JSON.stringify(expected[k]) !== JSON.stringify(actual[k]))
  return `The result differs from the expected one in: ${differing.join(', ') || 'its contents'}.`
}
