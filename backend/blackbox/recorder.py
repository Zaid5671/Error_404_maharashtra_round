"""Builds Step records: applies each tool's writes to state, fills `uses`, snapshots state_after."""

import copy

from blackbox.tools import TOOLS, State, new_state


class Recorder:
    def __init__(self) -> None:
        self.state: State = new_state()
        self.steps: list[dict] = []
        self.last_writer: dict[str, int] = {}  # state key -> id of the step that last wrote it

    def record(
        self,
        name: str,
        args: dict,
        output: dict,
        *,
        step_input: dict | None = None,
        llm: dict | None = None,
        tool_latency_ms: int = 0,
        msg_index: int = 0,
    ) -> dict:
        """Record one tool call. `output` is what the tool returned (possibly corrupted by the injector)."""
        step_id = len(self.steps) + 1
        tool = TOOLS.get(name)
        error = output.get("error")

        uses: set[int] = set()
        if tool is not None:
            uses = {self.last_writer[k] for k in tool.reads(args) if k in self.last_writer}
            if error is None:
                tool.write(self.state, output)
                for key in tool.writes(args, output):
                    self.last_writer[key] = step_id

        step = {
            "id": step_id,
            "kind": tool.kind if tool else "tool",
            "name": name,
            "input": step_input if step_input is not None else args,
            "output": output,
            "uses": sorted(uses),
            "llm": llm,
            "tool_latency_ms": tool_latency_ms,
            "error": error,
            "state_after": copy.deepcopy(self.state),
            "msg_index": msg_index,
        }
        self.steps.append(step)
        return step
