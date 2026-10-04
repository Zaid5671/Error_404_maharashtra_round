"""The Black Box trace format and API shapes (plan.md section 6). Nothing here is specific to one agent.

`task`, `expected` and `actual` are opaque to the Black Box: each agent defines their shape
(the pizza agent's are in agents/pizza/contract.py).

Any change here must also be made in frontend/src/types/contract.ts and plan.md section 6.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

StepKind = Literal["llm", "tool"]
FaultFamily = Literal["tool", "llm"]
Outcome = Literal["success", "failure"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Run ---------------------------------------------------------------------


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
    reads: list[str]  # state keys this step read
    writes: list[str]  # state keys this step wrote (empty when it errored)
    uses: list[int]  # earlier steps that last wrote the keys in `reads` = graph arrows
    llm: StepLLM | None
    tool_latency_ms: int
    error: str | None
    state_after: dict[str, Any]
    msg_index: int


class Fault(Model):
    type: str  # agent-defined, e.g. "wrong_discount"
    family: FaultFamily
    step_id: int
    detail: str


class Run(Model):
    run_id: str
    agent: str  # which agent produced this run, e.g. "pizza"
    template_id: str
    source: Literal["generated", "live", "replay"]
    parent_run_id: str | None
    replayed_from_step: int | None
    task: dict[str, Any]  # the agent's structured input
    request_text: str
    expected: dict[str, Any] | None  # agent-defined correct result; None = correct behaviour is to do nothing
    actual: dict[str, Any] | None
    outcome: Outcome
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


class FaultTypes(Model):
    seen: list[str]
    unseen: list[str]


class TypeAccuracy(Accuracy):
    type: str
    seen: bool  # trained on this fault type
    n: int


class Report(Model):
    agent: str
    n_train_runs: int
    n_test_runs: int
    overall: Accuracy
    seen: SplitAccuracy
    unseen: SplitAccuracy
    fault_types: FaultTypes
    by_type: list[TypeAccuracy]


# --- API request bodies --------------------------------------------------------


class RunRequest(Model):
    agent: str
    task: dict[str, Any]
    fault_mode: Literal["none", "surprise"]
    fault_type: str | None = None  # with "surprise": hide this fault from the agent's catalogue


class FaultInfo(Model):
    type: str
    family: FaultFamily
    step_name: str
    seen: bool  # the trained model saw this fault type in training
    live: bool  # can be hidden in a live run (tool faults)


class DiagnoseRequest(Model):
    agent: str
    run_id: str


class ReplayRequest(Model):
    agent: str
    run_id: str
    step_id: int
    new_output: dict[str, Any]


# --- SSE event payloads ------------------------------------------------------


class RunStartedEvent(Model):
    run_id: str
    agent: str
    task: dict[str, Any]
    request_text: str


class StepStartedEvent(Model):
    id: int
    name: str


class StepDoneEvent(Model):
    step: Step


class StepReusedEvent(Model):
    id: int


class RunDoneEvent(Model):
    run_id: str
    outcome: Outcome
    actual: dict[str, Any] | None
    expected: dict[str, Any] | None


class ErrorEvent(Model):
    message: str
