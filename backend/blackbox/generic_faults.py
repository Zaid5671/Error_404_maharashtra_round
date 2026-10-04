"""Generic faults for agents connected through the SDK: change one value in a tool's output.

The fault types come from the agent's own tools: "<tool>:number", "<tool>:flag", "<tool>:text".
The value-changing logic is a twin of sdk/blackbox_sdk/mutate.py (keep them in step): the SDK uses
it for hidden faults in live runs, the Black Box for the faulted runs it generates. The Black Box
never imports the SDK, so the code is copied, not shared.
"""

from __future__ import annotations

import copy
import random
from typing import Any

KINDS = ("number", "flag", "text")


def leaves(obj: Any, path: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.extend(leaves(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.extend(leaves(v, f"{path}[{i}]"))
    else:
        out.append((path, obj))
    return out


def _is_id(path: str) -> bool:
    last = path.rsplit(".", 1)[-1].split("[")[0]
    return last == "id" or last.endswith("_id") or last.endswith("Id")


def kind_of(value: Any) -> str | None:
    if isinstance(value, bool):
        return "flag"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str) and value.strip():
        return "text"
    return None


def _set(obj: Any, path: str, value: Any) -> None:
    parts: list[str | int] = []
    for chunk in path.split("."):
        name, *idx = chunk.replace("]", "").split("[")
        if name:
            parts.append(name)
        parts.extend(int(i) for i in idx)
    for p in parts[:-1]:
        obj = obj[p]
    obj[parts[-1]] = value


def _field(path: str) -> str:
    return path.rsplit(".", 1)[-1].split("[")[0]


def _changed(value: Any, kind: str, rng: random.Random, strings: list[str]) -> Any:
    if kind == "flag":
        return not value
    if kind == "number":
        delta = max(1, round(abs(value) * rng.uniform(0.1, 0.3))) if isinstance(value, int) else round(abs(value) * rng.uniform(0.1, 0.3), 2) or 0.5
        new = value + delta * rng.choice([-1, 1])
        return new if value < 0 or new >= 0 else value + delta
    others = sorted({s for s in strings if s.strip().lower() != value.strip().lower()})
    return rng.choice(others) if others else None


def strings_by_field(outputs: list[Any]) -> dict[str, list[str]]:
    """Every string value in these outputs, grouped by field name."""
    out: dict[str, list[str]] = {}
    for o in outputs:
        for p, v in leaves(o):
            if isinstance(v, str) and v.strip():
                out.setdefault(_field(p), []).append(v)
    return out


def mutate(output: dict, kind: str, seed: int, strings: dict[str, list[str]]) -> tuple[dict, str] | None:
    """A copy of `output` with one value of this kind changed, and a sentence saying what changed.
    None when the output has no value of that kind (or no other string to swap in). IDs are left
    alone: a changed ID rarely changes the result."""
    rng = random.Random(seed)
    options = [(p, v) for p, v in leaves(output) if kind_of(v) == kind and not _is_id(p)]
    rng.shuffle(options)
    for path, value in options:
        new = _changed(value, kind, rng, strings.get(_field(path), []))
        if new is None or new == value:
            continue
        changed = copy.deepcopy(output)
        _set(changed, path, new)
        return changed, f"{path} {value} -> {new}"
    return None


# --- fault specs for the injector -----------------------------------------------------------------


def _maker(kind: str):
    def make(run: dict, step: dict, rng: random.Random) -> dict | None:
        if step.get("error") or not isinstance(step.get("output"), dict):
            return None
        strings = strings_by_field([s["output"] for s in run["steps"] if s["kind"] == "tool"])
        change = mutate(step["output"], kind, rng.randrange(10**9), strings)
        return None if change is None else {"output": change[0], "detail": change[1]}

    return make


def specs(tools: dict[str, set[str]]):
    """One FaultSpec per (tool, kind of value its outputs have). `tools` maps a tool to the kinds
    seen in its outputs (all kinds when nothing has been recorded yet)."""
    from blackbox.adapter import FaultSpec

    return [FaultSpec(type=f"{tool}:{kind}", family="tool", step_name=tool, make=_maker(kind))
            for tool in sorted(tools) for kind in KINDS if kind in tools[tool]]


def kinds_in(output) -> set[str]:
    """The kinds of values (number / flag / text) a tool output has, ignoring IDs."""
    return {k for p, v in leaves(output) if (k := kind_of(v)) and not _is_id(p)}
