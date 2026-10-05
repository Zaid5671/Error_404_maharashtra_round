// Fallbacks for agents without their own UI parts. They only read the generic trace format.

import { useState } from 'react'
import type { Step } from '@/types/contract'
import type { Json, ResultInfo, TaskFormProps } from './types'

export function genericStepLabel(step: Step): string {
  const calls = step.output.calls
  if (step.kind === 'llm' && Array.isArray(calls)) { // an LLM step recorded by the SDK: what it decided
    const tools = [...new Set(calls.map((c) => String((c as { tool?: unknown }).tool)))]
    return tools.length ? `calls ${tools.join(', ')}` : `answers: ${String(step.output.text ?? '').slice(0, 60)}`
  }
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

/** A JSON task box. When the agent offers example tasks (agents connected by URL), pick one to start. */
export function GenericTaskForm({ task, onChange, formData }: TaskFormProps) {
  const [text, setText] = useState(() => JSON.stringify(task, null, 2))
  const [error, setError] = useState<string | null>(null)
  const examples = (Array.isArray(formData?.examples) ? formData.examples : []) as { kind: string; task: Json }[]
  const pick = (i: number) => {
    const t = examples[i]?.task
    if (!t) return
    setText(JSON.stringify(t, null, 2))
    setError(null)
    onChange(t)
  }
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {examples.length > 0 && (
        <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground" htmlFor="task-example">
          Start from an example task
          {/* w-full + min-w-0: long example names must not widen the panel */}
          <select id="task-example" defaultValue="" onChange={(e) => pick(Number(e.target.value))}
            className="h-9 w-full min-w-0 truncate rounded-md border bg-sunk px-2 text-sm text-foreground">
            <option value="" disabled>Choose one of {examples.length} examples…</option>
            {examples.map((e, i) => (
              <option key={i} value={i}>{e.kind} · {String(e.task.request ?? JSON.stringify(e.task)).slice(0, 70)}</option>
            ))}
          </select>
        </label>
      )}
      <label className="grid min-w-0 gap-1 text-xs font-medium text-muted-foreground" htmlFor="task-json">
        Task (JSON)
        <textarea
          id="task-json"
          className="min-h-48 w-full min-w-0 rounded-md border bg-sunk p-2 font-mono text-xs text-foreground"
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
    </div>
  )
}

export function GenericTaskSummary({ task }: { task: Json }) {
  return <pre className="max-h-40 overflow-auto rounded-md border bg-sunk p-2 font-mono text-xs">{JSON.stringify(task, null, 2)}</pre>
}

export function genericResultLine({ outcome, expected, actual }: ResultInfo) {
  if (outcome === 'success') return expected === null ? 'The agent finished. There is no expected result to check it against.' : 'The result matches the expected one.'
  if (actual === null) return 'The agent ended with an error before producing a result.'
  if (expected === null) return 'The run failed.'
  const differing = Object.keys(expected).filter((k) => JSON.stringify(expected[k]) !== JSON.stringify(actual[k]))
  return `The result differs from the expected one in: ${differing.join(', ') || 'its contents'}.`
}
