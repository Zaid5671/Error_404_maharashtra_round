"""Fault injection: break one known step of a clean run, so we know the right answer for diagnosis.

The agent supplies its fault catalogue (adapter.faults()); the Black Box decides which fault and
which step, makes the faulted run by resuming the clean run from that step (earlier steps are
reused, not re-run), and records the fault label.
"""

import random

from blackbox.adapter import AgentAdapter, FaultSpec
from blackbox.recorder import OutputHook


def candidates(adapter: AgentAdapter, run: dict, rng: random.Random, family: str) -> list[tuple[FaultSpec, dict, dict]]:
    """Every (fault, step, change) that can apply to this run, for one fault family."""
    found = []
    for spec in adapter.faults():
        if spec.family != family:
            continue
        for step in run["steps"]:
            if step["name"] == spec.step_name:
                change = spec.make(run, step, rng)
                if change is not None:
                    found.append((spec, step, change))
    return found


def inject(
    adapter: AgentAdapter,
    run: dict,
    *,
    run_id: str,
    rng: random.Random,
    family: str = "tool",
    fault_type: str | None = None,
    avoid: set[str] = frozenset(),
    exclude: set[str] = frozenset(),
) -> dict | None:
    """Make one faulted copy of a clean run. Returns None if no fault applies.

    Picks the fault type first (uniformly, skipping `avoid` when possible) so types stay balanced,
    then a step of that type. Types in `exclude` are never used (held-out fault types on train runs).
    """
    options = [o for o in candidates(adapter, run, rng, family) if o[0].type not in exclude]
    if fault_type:
        options = [o for o in options if o[0].type == fault_type]
    if not options:
        return None
    types = sorted({spec.type for spec, _, _ in options})
    preferred = [t for t in types if t not in avoid] or types
    chosen_type = rng.choice(preferred)
    spec, step, change = rng.choice([o for o in options if o[0].type == chosen_type])

    faulted = adapter.resume(
        run, step["id"],
        run_id=run_id,
        source="generated",
        new_output=change.get("output"),
        new_args=change.get("args"),
    )
    faulted["fault"] = {"type": spec.type, "family": spec.family, "step_id": step["id"], "detail": change["detail"]}
    return faulted


def live_fault(
    adapter: AgentAdapter,
    task: dict,
    steps: list[dict],
    rng: random.Random,
    *,
    family: str = "tool",
    other_chance: float = 0.5,
    fault_type: str | None = None,
) -> tuple[OutputHook, dict]:
    """A hidden fault for a live run ("Surprise me"), applied while the run streams.

    Returns (output_hook, fault). `steps` must be kept up to date by the caller (the steps
    finished so far), because fault makers look at earlier steps. One fault type is preferred,
    picked at random; a step where another type applies gets that one with `other_chance`, so a
    fault almost always lands. `fault_type` forces one type (and only that type).
    `fault` is filled in when it lands ({type, family, step_id, detail}).
    """
    specs = [s for s in adapter.faults() if s.family == family and fault_type in (None, s.type)]
    preferred = fault_type or rng.choice(sorted({s.type for s in specs}))
    fault: dict = {}

    def hook(step_id: int, name: str, args: dict, output: dict) -> dict:
        if fault or not isinstance(output, dict) or "error" in output:
            return output
        run = {"steps": steps, "task": task["task"], "request_text": task["request_text"], "expected": task["expected"]}
        step = {"id": step_id, "name": name, "input": args, "output": output, "error": None}
        matching = sorted((s for s in specs if s.step_name == name), key=lambda s: s.type != preferred)
        for spec in matching:
            if spec.type != preferred and rng.random() >= other_chance:
                continue
            change = spec.make(run, step, rng)
            if change and "output" in change:
                fault.update(type=spec.type, family=spec.family, step_id=step_id, detail=change["detail"])
                return change["output"]
        return output

    return hook, fault
