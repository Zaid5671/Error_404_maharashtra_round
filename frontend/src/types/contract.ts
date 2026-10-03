// The data contract (plan.md section 6).
// Any change here must also be made in backend/blackbox/contract.py and plan.md section 6.

export type Size = 'S' | 'M' | 'L'
export type StepKind = 'llm' | 'tool'
export type FaultFamily = 'tool' | 'llm'
export type FaultType =
  | 'wrong_price'
  | 'stock_lie'
  | 'wrong_cart_line'
  | 'wrong_discount'
  | 'wrong_delivery'
  | 'llm_misread'
  | 'llm_wrong_choice'
export type Outcome = 'success' | 'failure'

// --- Run ---------------------------------------------------------------------

export interface OrderItem {
  pizza: string
  size: Size
  qty: number
}

export interface Order {
  items: OrderItem[]
  coupon: string | null
  area: string
}

export interface ResultItem extends OrderItem {
  unit_price: number
  line_total: number
}

export interface OrderResult {
  items: ResultItem[]
  subtotal: number
  coupon: string | null
  discount: number
  delivery_fee: number
  total: number
}

export interface StepLLM {
  latency_ms: number
  tokens_in: number
  tokens_out: number
}

export interface Step {
  id: number
  kind: StepKind
  name: string
  input: Record<string, unknown>
  output: Record<string, unknown>
  uses: number[]
  llm: StepLLM | null
  tool_latency_ms: number
  error: string | null
  state_after: Record<string, unknown>
  msg_index: number
}

export interface Fault {
  type: FaultType
  family: FaultFamily
  step_id: number
  detail: string
}

export interface Run {
  run_id: string
  template_id: string
  source: 'generated' | 'live' | 'replay'
  parent_run_id: string | null
  replayed_from_step: number | null
  order: Order
  request_text: string
  expected: OrderResult
  actual: OrderResult | null
  outcome: Outcome
  fault: Fault | null
  split: 'train' | 'test' | null
  messages: Record<string, unknown>[]
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
  n_train_runs: number
  n_test_runs: number
  overall: Accuracy
  seen: SplitAccuracy
  unseen: SplitAccuracy
  baselines: { name: string; top1: number }[]
  fault_types: { seen: FaultType[]; unseen: FaultType[] }
}

// --- Catalog -----------------------------------------------------------------

export interface Catalog {
  pizzas: { id: string; name: string; prices: Partial<Record<Size, number>> }[]
  sizes: Size[]
  coupons: { code: string; label: string }[]
  areas: { name: string; deliverable: boolean }[]
}

// --- API request bodies --------------------------------------------------------

export interface RunRequest {
  order: Order
  fault_mode: 'none' | 'surprise'
}

export interface DiagnoseRequest {
  run_id: string
}

export interface ReplayRequest {
  run_id: string
  step_id: number
  new_output: Record<string, unknown>
}

// --- SSE events --------------------------------------------------------------

export type RunEvent =
  | { event: 'step_started'; data: { id: number; name: string } }
  | { event: 'step_done'; data: { step: Step } }
  | { event: 'step_reused'; data: { id: number } }
  | { event: 'run_done'; data: { run_id: string; outcome: Outcome; actual: OrderResult | null; expected: OrderResult } }
  | { event: 'error'; data: { message: string } }
