"""Checkpointed replay: re-run a saved run from one edited step, reusing every step before it."""

import uuid

from blackbox import store
from blackbox.adapter import EventFn
from blackbox.registry import get_agent


class ReplayError(ValueError):
    pass


def replay(agent: str, run_id: str, step_id: int, new_output: dict, on_event: EventFn | None = None) -> dict:
    """Replay `run_id` with `new_output` for tool step `step_id`. Saves and returns the new run.

    Emits step_reused for every earlier step (taken from the checkpoint, not re-run), then the
    agent streams the re-run steps. Replays never inject faults.
    """
    adapter = get_agent(agent)
    original = store.load_run(agent, run_id)
    if not 1 <= step_id <= len(original["steps"]):
        raise ReplayError(f"run {run_id} has no step {step_id}")
    if original["steps"][step_id - 1]["kind"] != "tool":
        raise ReplayError("only tool steps can be edited")

    if on_event:
        for step in original["steps"][: step_id - 1]:
            on_event("step_reused", {"id": step["id"]})
    new_run = adapter.resume(
        original, step_id,
        run_id=f"{run_id}__replay_{uuid.uuid4().hex[:6]}",
        source="replay",
        new_output=new_output,
        on_event=on_event,
    )
    new_run["fault"] = None
    store.save_run(new_run)
    return new_run


def reuse_stats(run: dict) -> dict:
    """For a replayed run: how many steps were reused vs re-run, and LLM calls saved."""
    k = run["replayed_from_step"] or 1
    reused = run["steps"][: k - 1]
    rerun = run["steps"][k - 1:]
    return {
        "reused": len(reused),
        "rerun": len(rerun),
        "llm_calls_saved": sum(1 for s in reused if s["llm"]),
        "llm_calls_made": sum(1 for s in rerun[1:] if s["llm"]),
    }
