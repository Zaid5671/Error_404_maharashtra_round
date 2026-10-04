// Shapes of the dashboard routes (Runs, Diagnoses, Replays, Overview, Model → Training data,
// Training, Agents). Generic: nothing here is specific to one agent.

import type { Outcome } from './contract'

export type RunSource = 'generated' | 'live' | 'replay' | 'imported'
export type SourceFilter = 'app' | 'all' | RunSource

export interface Suspect {
  step_id: number
  name: string
  score: number
  reason: string | null
}

export interface RunRow {
  run_id: string
  source: RunSource
  template_id: string
  split: 'train' | 'test' | null
  outcome: Outcome
  request_text: string
  n_steps: number
  llm_calls: number
  duration_ms: number
  created: string
  parent_run_id: string | null
  replayed_from_step: number | null
  has_fault: boolean
  suspect: Suspect | null
}

export interface RunPage {
  total: number
  items: RunRow[]
}

export interface DemoRun {
  run_id: string
  fault_type: string
  seen: boolean
  step_id: number
  step_name: string
  request_text: string
}

export interface Overview {
  scope: 'app' | 'all'
  total_runs: number
  failed_runs: number
  failed_share: number
  replays: number
  replays_fixed: number
  replay_success: number | null
  top1: number | null
  unseen_top1: number | null
  model_trained: boolean
  demo_runs: DemoRun[]
}

export interface ReplayRow extends RunRow {
  parent_outcome: Outcome | null
  edited_step: number
  edited_name: string | null
  reused: number
  rerun: number
  llm_calls_saved: number
}

export interface Dataset {
  total: number
  train: number
  test: number
  templates: { train: string[]; test: string[] }
  kinds: { kind: string; train_success: number; train_failure: number; test_success: number; test_failure: number }[]
}

export interface AgentInfo {
  name: string
  kind: 'connected' | 'imported'
  /** connected agents: built into the backend, or connected by URL through the SDK */
  via?: 'builtin' | 'sdk'
  url?: string
  online?: boolean
  title: string
  description: string
  created: string | null
}

/** What an SDK agent says about itself (GET /info, through POST /agents/probe). */
export interface ProbeInfo {
  name: string
  title: string
  description: string
  sdk: string
  tools: { name: string; kind: string; description: string }[]
  kinds: string[]
  examples: { kind: string; task: Record<string, unknown> }[]
  has_check: boolean
}

export interface AgentDetails extends AgentInfo {
  llm: string | null
  tools: { name: string; kind: string; count: number; reads: string[]; writes: string[]; description: string | null }[]
  templates: { train: string[]; test: string[] }
  model: { features: string[]; seen_fault_types: string[]; n_train_runs: number; n_train_cases: number } | null
  can_run: boolean
  n_runs: number
  n_dataset_runs: number
  remote: { url: string; online: boolean; sdk?: string; kinds?: string[]; examples?: number; has_check?: boolean } | null
}

export interface TrainResult {
  n_train_runs: number
  n_test_runs: number
  top1: number
  top3: number
  unseen_top1: number
  unseen_n: number
}

export interface GenerateSummary {
  clean: number
  failed: number
  harmless: number
  clean_failed: number
  /** faulted runs thrown away because the replay broke before reaching the fault */
  broken?: number
  held_out_tool: string | null
}

export interface TrainJob {
  status: 'idle' | 'running' | 'done' | 'error'
  /** train: train + evaluate; generate: generate runs first (agents connected by URL) */
  kind: 'train' | 'generate' | null
  progress: { done: number; total: number; stage: 'generate' | 'train' | 'done' } | null
  generated: GenerateSummary | null
  log: string[]
  started: string | null
  finished: string | null
  result: TrainResult | null
  error: string | null
  history: { status: string; kind?: string; started: string; finished: string; result: TrainResult | null; error: string | null }[]
}

export interface ImportResult {
  imported: number
  run_ids: string[]
  rejected: { where: string; error: string }[]
}
