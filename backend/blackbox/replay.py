"""Checkpointed replay: re-run a saved run from one edited step, reusing every step before it."""

import uuid

from blackbox import store
from blackbox.adapter import EventFn
from blackbox.registry import get_agent


class ReplayError(ValueError):
    pass


def new_replay_id(run_id: str) -> str:
    return f"{run_id}__replay_{uuid.uuid4().hex[:6]}"


def check_edit(original: dict, step_id: int, new_output: dict) -> dict:
    """The step being edited. Raises ReplayError when the edit can't be replayed."""
    if not 1 <= step_id <= len(original["steps"]):
        raise ReplayError(f"run {original['run_id']} has no step {step_id}")
    step = original["steps"][step_id - 1]
    if not isinstance(new_output, dict):
        raise ReplayError("the edited output must be an object")
    old = step["output"] if isinstance(step["output"], dict) else {}
    if set(new_output) != set(old):
        missing, extra = sorted(set(old) - set(new_output)), sorted(set(new_output) - set(old))
        raise ReplayError(f"the edit must keep the step's fields (missing {missing}, unexpected {extra})")
    return step


def replay(
    agent: str,
    run_id: str,
    step_id: int,
    new_output: dict,
    on_event: EventFn | None = None,
    *,
    new_run_id: str | None = None,
) -> dict:
    """Replay `run_id` with `new_output` for step `step_id`. Saves and returns the new run.

    Emits step_reused for every earlier step (taken from the checkpoint, not re-run), then the
    agent streams the re-run steps. For a tool step the edit replaces the tool's output; for an LLM
    step it replaces the values the LLM chose (its tool-call arguments), so a misread can be fixed.
    Replays never inject faults.
    """
    adapter = get_agent(agent)
    original = store.load_run(agent, run_id)
    step = check_edit(original, step_id, new_output)

    if on_event:
        for earlier in original["steps"][: step_id - 1]:
            on_event("step_reused", {"id": earlier["id"]})
    edit = {"new_args": new_output} if step["kind"] == "llm" else {"new_output": new_output}
    new_run = adapter.resume(
        original, step_id,
        run_id=new_run_id or new_replay_id(run_id),
        source="replay",
        on_event=on_event,
        **edit,
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
