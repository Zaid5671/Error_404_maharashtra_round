"""Fault injection: break one known step of a clean run, so we know the right answer for diagnosis.

The agent supplies its fault catalogue (adapter.faults()); the Black Box decides which fault and
which step, makes the faulted run by resuming the clean run from that step (earlier steps are
reused, not re-run), and records the fault label.
"""

import random

from blackbox.adapter import AgentAdapter, FaultSpec


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
