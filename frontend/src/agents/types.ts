// What an agent provides to the frontend: the mirror of the backend's AgentAdapter.
// Only TaskForm and defaultTask are required; everything else falls back to agents/generic.tsx.

import type { ComponentType, ReactNode } from 'react'
import type { Outcome, Step } from '@/types/contract'

export type Json = Record<string, unknown>

export interface TaskFormProps {
  task: Json
  onChange: (task: Json) => void
  /** What GET /catalog/{agent} returned (e.g. the pizza menu), or null while it loads. */
  formData: Json | null
}

export interface ResultInfo {
  outcome: Outcome
  expected: Json | null
  actual: Json | null
}

export interface AgentPlugin {
  name: string // registry name, same as Run.agent
  title: string // shown in the task panel header
  defaultTask: Json
  TaskForm: ComponentType<TaskFormProps>
  /** One-glance summary of a task, shown once a run starts. */
  TaskSummary?: ComponentType<{ task: Json }>
  /** Short readable label for a step's result, or null to use the generic one. */
  stepLabel?: (step: Step) => string | null
  /** The banner sentence for a finished run. */
  resultLine?: (result: ResultInfo) => ReactNode
}

/** A plugin with every optional part filled in (by the registry). */
export type ResolvedPlugin = Required<Omit<AgentPlugin, 'stepLabel'>> & { stepLabel: (step: Step) => string }
