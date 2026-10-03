// The Black Box trace format and API shapes (plan.md section 6). Nothing here is specific to one agent.
// `task`, `expected` and `actual` are agent-defined (the pizza agent's shapes are in ./pizza.ts).
// Any change here must also be made in backend/blackbox/contract.py and plan.md section 6.

export type StepKind = 'llm' | 'tool'
export type FaultFamily = 'tool' | 'llm'
export type Outcome = 'success' | 'failure'
type Json = Record<string, unknown>

// --- Run ---------------------------------------------------------------------

export interface StepLLM {
  latency_ms: number
  tokens_in: number
  tokens_out: number
}

export interface Step {
  id: number
  kind: StepKind
  name: string
  input: Json
  output: Json
  reads: string[] // state keys this step read
  writes: string[] // state keys this step wrote (empty when it errored)
  uses: number[] // earlier steps that last wrote the keys in `reads` = graph arrows
  llm: StepLLM | null
  tool_latency_ms: number
  error: string | null
  state_after: Json
  msg_index: number
}

export interface Fault {
  type: string // agent-defined, e.g. "wrong_discount"
  family: FaultFamily
  step_id: number
  detail: string
}

export interface Run {
  run_id: string
  agent: string
  template_id: string
  source: 'generated' | 'live' | 'replay'
  parent_run_id: string | null
  replayed_from_step: number | null
  task: Json
  request_text: string
  expected: Json | null // null: the correct behaviour is to do nothing
  actual: Json | null
  outcome: Outcome
  fault: Fault | null
  split: 'train' | 'test' | null
  messages: Json[]
  steps: Step[]
}

// --- Diagnosis ---------------------------------------------------------------

export interface Reason {
  feature: string
  label: string
  shap: number
}

export interface Diagnosis {
  run_id: string
  scores: Record<string, number> // keys are step ids as strings
  ranking: number[]
  culprit: number | null // null when the run succeeded
  reasons: Reason[]
  explanation: string
  impact_path: number[]
}

// --- Report ------------------------------------------------------------------

export interface Accuracy {
  top1: number
  top3: number
}

export interface SplitAccuracy extends Accuracy {
  n: number
}

export interface Report {
  agent: string
  n_train_runs: number
  n_test_runs: number
  overall: Accuracy
  seen: SplitAccuracy
  unseen: SplitAccuracy
  baselines: { name: string; top1: number }[]
  fault_types: { seen: string[]; unseen: string[] }
}

// --- API request bodies --------------------------------------------------------

export interface RunRequest {
  agent: string
  task: Json
  fault_mode: 'none' | 'surprise'
}

export interface DiagnoseRequest {
  run_id: string
}

export interface ReplayRequest {
  run_id: string
  step_id: number
  new_output: Json
}

// --- SSE events --------------------------------------------------------------

export type RunEvent =
  | { event: 'run_started'; data: { run_id: string; agent: string; task: Json; request_text: string } }
  | { event: 'step_started'; data: { id: number; name: string } }
  | { event: 'step_done'; data: { step: Step } }
  | { event: 'step_reused'; data: { id: number } }
  | { event: 'run_done'; data: { run_id: string; outcome: Outcome; actual: Json | null; expected: Json | null } }
  | { event: 'error'; data: { message: string } }
