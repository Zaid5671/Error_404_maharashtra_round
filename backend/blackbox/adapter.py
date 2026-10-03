"""What an agent must provide to plug into the Black Box.

An agent registers one AgentAdapter in blackbox/registry.py. Everything else in the Black Box
(generation, features, training, diagnosis, replay, evaluation, the API) works through it.

During a run the agent must call Recorder.record() once per step (see blackbox/recorder.py).
"""

from collections.abc import Callable
from typing import Protocol

from blackbox.recorder import OutputHook

# (event name, payload) -> None; events are step_started, step_done, step_reused, run_done
EventFn = Callable[[str, dict], None]


class AgentAdapter(Protocol):
    name: str  # stored in Run.agent

    def templates(self) -> list[str]:
        """Ids of the task templates. Train/test splits are made by template."""
        ...

    def make_task(self, template_id: str, seed: int) -> dict:
        """A task from a template: {template_id, seed, task, request_text, expected}."""
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
        new_output: dict,
        *,
        run_id: str,
        on_event: EventFn | None = None,
        output_hook: OutputHook | None = None,
    ) -> dict:
        """Replay: restore the checkpoint before `step_id`, use `new_output` for that step,
        continue the agent from there, and return the new Run."""
        ...

    def judge(self, expected: dict | None, actual: dict | None) -> str:
        """'success' or 'failure' for a result against the expected one."""
        ...
