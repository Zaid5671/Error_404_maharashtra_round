"""What an agent must provide to plug into the Black Box.

An agent registers one AgentAdapter in blackbox/registry.py. Everything else in the Black Box
(generation, fault injection, features, training, diagnosis, replay, evaluation, the API) works
through it.

During a run the agent must call Recorder.record() once per step (see blackbox/recorder.py).
"""

import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

from blackbox.recorder import OutputHook

# (event name, payload) -> None; events are step_started, step_done, step_reused, run_done
EventFn = Callable[[str, dict], None]

# (clean run, step to break, rng) -> {"output": ..., "detail": ...} to replace the step's output,
# or {"args": ..., "detail": ...} to replace the arguments the LLM chose for it,
# or None when this fault can't apply to (or can't matter for) this step.
FaultMaker = Callable[[dict, dict, random.Random], dict | None]


@dataclass(frozen=True)
class FaultSpec:
    """One realistic way to break a step. Agent-specific; the Black Box decides when to use it."""

    type: str  # e.g. "wrong_discount"
    family: Literal["tool", "llm"]  # tool = a tool returned a wrong result; llm = the LLM chose wrongly
    step_name: str  # which kind of step it breaks
    make: FaultMaker


class AgentAdapter(Protocol):
    name: str  # stored in Run.agent

    def templates(self) -> list[str]:
        """Ids of the task templates. Train/test splits are made by template."""
        ...

    def make_task(self, template_id: str, seed: int) -> dict:
        """A task from a template: {template_id, seed, task, request_text, expected}."""
        ...

    def faults(self) -> list[FaultSpec]:
        """The agent's fault catalogue."""
        ...

    def run(
        self,
        task: dict,
        *,
        run_id: str,
        source: str = "generated",
        on_event: EventFn | None = None,
        output_hook: OutputHook | None = None,
    ) -> dict:
        """Run the agent on a task and return a Run (blackbox.contract.Run as a dict)."""
        ...

    def resume(
        self,
        run: dict,
        step_id: int,
        *,
        run_id: str,
        source: str = "replay",
        new_output: dict | None = None,
        new_args: dict | None = None,
        on_event: EventFn | None = None,
        output_hook: OutputHook | None = None,
    ) -> dict:
        """Continue `run` from the checkpoint before `step_id`.

        Steps before `step_id` are reused, not re-run. Step `step_id` gets `new_output` (or is re-run
        with `new_args` replacing the arguments the LLM chose); then the agent carries on. Returns the
        new Run with parent_run_id and replayed_from_step set.
        """
        ...

    def judge(self, expected: dict | None, actual: dict | None) -> str:
        """'success' or 'failure' for a result against the expected one."""
        ...


class QuotaExhausted(Exception):
    """An agent's LLM provider hit its daily cap. Generation stops cleanly and can resume later."""
