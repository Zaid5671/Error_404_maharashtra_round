"""The data contract (plan.md section 6) as pydantic models.

Any change here must also be made in frontend/src/types/contract.ts and plan.md section 6.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

Size = Literal["S", "M", "L"]
StepKind = Literal["llm", "tool"]
FaultFamily = Literal["tool", "llm"]
FaultType = Literal[
    "wrong_price",
    "stock_lie",
    "wrong_cart_line",
    "wrong_discount",
    "wrong_delivery",
    "llm_misread",
    "llm_wrong_choice",
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Run ---------------------------------------------------------------------


class OrderItem(Model):
    pizza: str
    size: Size
    qty: int


class Order(Model):
    items: list[OrderItem]
    coupon: str | None
    area: str


class ResultItem(OrderItem):
    unit_price: int
    line_total: int


class OrderResult(Model):
    items: list[ResultItem]
    subtotal: int
    coupon: str | None
    discount: int
    delivery_fee: int
    total: int


class StepLLM(Model):
    latency_ms: int
    tokens_in: int
    tokens_out: int


class Step(Model):
    id: int
    kind: StepKind
    name: str
    input: dict[str, Any]
    output: dict[str, Any]
    uses: list[int]
    llm: StepLLM | None
    tool_latency_ms: int
    error: str | None
    state_after: dict[str, Any]
    msg_index: int


class Fault(Model):
    type: FaultType
    family: FaultFamily
    step_id: int
    detail: str


class Run(Model):
    run_id: str
    template_id: str
    source: Literal["generated", "live", "replay"]
    parent_run_id: str | None
    replayed_from_step: int | None
    order: Order
    request_text: str
    expected: OrderResult
    actual: OrderResult | None
    outcome: Literal["success", "failure"]
    fault: Fault | None
    split: Literal["train", "test"] | None
    messages: list[dict[str, Any]]
    steps: list[Step]


# --- Diagnosis ---------------------------------------------------------------


class Reason(Model):
    feature: str
    label: str
    shap: float


class Diagnosis(Model):
    run_id: str
    scores: dict[str, float]  # keys are step ids as strings
    ranking: list[int]
    culprit: int | None  # None when the run succeeded
    reasons: list[Reason]
    explanation: str
    impact_path: list[int]


# --- Report ------------------------------------------------------------------


class Accuracy(Model):
    top1: float
    top3: float


class SplitAccuracy(Accuracy):
    n: int


class Baseline(Model):
    name: str
    top1: float


class FaultTypes(Model):
    seen: list[FaultType]
    unseen: list[FaultType]


class Report(Model):
    n_train_runs: int
    n_test_runs: int
    overall: Accuracy
    seen: SplitAccuracy
    unseen: SplitAccuracy
    baselines: list[Baseline]
    fault_types: FaultTypes


# --- Catalog -----------------------------------------------------------------


class CatalogPizza(Model):
    id: str
    name: str
    prices: dict[Size, int]


class CatalogCoupon(Model):
    code: str
    label: str


class CatalogArea(Model):
    name: str
    deliverable: bool


class Catalog(Model):
    pizzas: list[CatalogPizza]
    sizes: list[Size]
    coupons: list[CatalogCoupon]
    areas: list[CatalogArea]


# --- API request bodies --------------------------------------------------------


class RunRequest(Model):
    order: Order
    fault_mode: Literal["none", "surprise"]


class DiagnoseRequest(Model):
    run_id: str


class ReplayRequest(Model):
    run_id: str
    step_id: int
    new_output: dict[str, Any]


# --- SSE event payloads ------------------------------------------------------


class StepStartedEvent(Model):
    id: int
    name: str


class StepDoneEvent(Model):
    step: Step


class StepReusedEvent(Model):
    id: int


class RunDoneEvent(Model):
    run_id: str
    outcome: Literal["success", "failure"]
    actual: OrderResult | None
    expected: OrderResult


class ErrorEvent(Model):
    message: str
