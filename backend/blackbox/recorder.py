"""The Black Box recorder. Agent-independent: any agent calls record() once per step.

The agent owns its state (a JSON-serialisable dict) and passes it in. For each step it reports
the state keys the step read and wrote; the recorder turns those into `uses` (graph arrows) by
remembering which step last wrote each key, and snapshots the state after every step.

The Black Box can set `output_hook` to see (and change) a step's output before the agent applies
it to its state. The fault injector plugs in there.
"""

import copy
from collections.abc import Callable

# (step_id, step name, args, output) -> output
OutputHook = Callable[[int, str, dict, dict], dict]


class Recorder:
    def __init__(self, state: dict, output_hook: OutputHook | None = None) -> None:
        self.state = state
        self.output_hook = output_hook
        self.steps: list[dict] = []
        self.last_writer: dict[str, int] = {}  # state key -> id of the step that last wrote it

    @classmethod
    def resume(cls, steps: list[dict], output_hook: OutputHook | None = None) -> "Recorder":
        """Rebuild a recorder at the checkpoint after `steps` (for replay). Needs at least one step."""
        rec = cls(copy.deepcopy(steps[-1]["state_after"]), output_hook)
        rec.steps = [copy.deepcopy(s) for s in steps]
        for step in rec.steps:
            for key in step["writes"]:
                rec.last_writer[key] = step["id"]
        return rec

    @property
    def next_id(self) -> int:
        return len(self.steps) + 1

    def record(
        self,
        *,
        name: str,
        kind: str,
        args: dict,
        output: dict,
        reads: list[str],
        writes: Callable[[dict], list[str]],
        apply: Callable[[dict], None],
        step_input: dict | None = None,
        llm: dict | None = None,
        tool_latency_ms: int = 0,
        msg_index: int = 0,
    ) -> dict:
        """Record one step and return it. Use the returned step["output"]: the hook may have changed it.

        writes(output) names the state keys the step wrote; apply(output) writes them into the
        agent's state. Neither is called when the output has an "error" key.
        """
        step_id = self.next_id
        if self.output_hook:
            output = self.output_hook(step_id, name, args, output)
        error = output.get("error")

        uses = sorted({self.last_writer[k] for k in reads if k in self.last_writer})
        written: list[str] = []
        if error is None:
            apply(output)
            written = writes(output)
            for key in written:
                self.last_writer[key] = step_id

        step = {
            "id": step_id,
            "kind": kind,
            "name": name,
            "input": step_input if step_input is not None else args,
            "output": output,
            "reads": reads,
            "writes": written,
            "uses": uses,
            "llm": llm,
            "tool_latency_ms": tool_latency_ms,
            "error": error,
            "state_after": copy.deepcopy(self.state),
            "msg_index": msg_index,
        }
        self.steps.append(step)
        return step
