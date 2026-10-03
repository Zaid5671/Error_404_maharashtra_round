"""Step -> feature row. Generic: only the trace is used (step names, input/output values,
reads/writes/uses, request_text), never rules of a particular agent.

"Normal" is learned from successful runs (`fit_norms`) as four kinds of memory:
  - values:   for a step name, an output field and its context (the step's string inputs and the
              strings next to the field), which values were seen. A deterministic context that
              now gives a new value is a surprise (a menu price, a delivery fee, a stock answer).
  - ranges:   for an output field value in a context, the range of the numbers the step had
              available (its numeric inputs and the numbers it read). A value outside that range
              is a violation (a coupon accepted on an order smaller than ever seen before).
  - volatile: fields that change on every run (ids, free text); never used as context.
  - hints:    request words that predict an output value (the word "small" -> size S). A step
              whose output lacks a value the request points to is a request mismatch.
Two checks need no memory: link mismatch (an output record disagrees with every matching
record in the step's input, the steps it uses and the state it read) and the step error.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

Scalar = str | int | float | bool
HINT = 0.9  # a request word is a hint when it predicts a value at least this often ...
HINT_LIFT = 0.3  # ... and that much more often than without the word ...
HINT_TEMPLATES = 3  # ... across this many task templates (one template's quirks are not a rule)
MIN_SEEN = 5  # a context counts as "always X" after this many runs

# --- flattening --------------------------------------------------------------------------------


def _is_scalar(v: Any) -> bool:
    return isinstance(v, (str, int, float, bool)) and v is not None


def leaves(obj: Any, path: str = "", ctx: tuple = ()) -> list[tuple[str, Scalar, tuple]]:
    """(path pattern, value, context strings) for every scalar in obj. List indices become []."""
    out = []
    if isinstance(obj, dict):
        local = tuple((f"{path}.{k}".lstrip("."), v) for k, v in obj.items() if isinstance(v, (str, bool)))
        for k, v in obj.items():
            p = f"{path}.{k}".lstrip(".")
            if _is_scalar(v):
                out.append((p, v, ctx + tuple(c for c in local if c[0] != p)))
            else:
                out.extend(leaves(v, p, ctx + local))
    elif isinstance(obj, list):
        for v in obj:
            if _is_scalar(v):
                out.append((f"{path}[]", v, ctx))
            else:
                out.extend(leaves(v, f"{path}[]", ctx))
    return out


def records(obj: Any) -> list[dict[str, Scalar]]:
    """Every dict inside obj, reduced to its scalar fields."""
    out = []
    if isinstance(obj, dict):
        rec = {k: v for k, v in obj.items() if _is_scalar(v)}
        if rec:
            out.append(rec)
        for v in obj.values():
            out.extend(records(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(records(v))
    return out


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _key(v: Scalar) -> str:
    return json.dumps(v)


def read_state(step: dict, before: dict) -> dict[str, Any]:
    """The values of the keys this step read, from the state before it. `a:b:c` -> state[a][b:c]."""
    out = {}
    for k in step["reads"]:
        if k in before:
            out[k] = before[k]
        elif ":" in k:
            head, rest = k.split(":", 1)
            if isinstance(before.get(head), dict) and rest in before[head]:
                out[k] = before[head][rest]
    return out


def _numbers(step: dict, state: dict) -> dict[str, float]:
    """Numbers the step had available: its numeric inputs and the numbers it read."""
    nums = {f"in.{p}": float(v) for p, v, _ in leaves(step["input"])
            if isinstance(v, (int, float)) and not isinstance(v, bool) and "[]" not in p}
    nums.update({f"read.{k}": float(v) for k, v in state.items()
                 if isinstance(v, (int, float)) and not isinstance(v, bool)})
    return nums


# --- what a step looks like, independent of norms ----------------------------------------------


class StepView:
    """The parts of a step the features need, computed once."""

    def __init__(self, run: dict, i: int):
        step = run["steps"][i]
        before = run["steps"][i - 1]["state_after"] if i else {}
        self.step = step
        self.name = step["name"]
        self.state = read_state(step, before)
        self.inputs = [(p, v) for p, v, _ in leaves(step["input"]) if isinstance(v, (str, bool))]
        self.out = leaves(step["output"]) if isinstance(step["output"], (dict, list)) else []
        self.numbers = _numbers(step, self.state)
        self.values_by_path: dict[str, set[str]] = defaultdict(set)
        for p, v, _ in self.out:
            if not isinstance(v, float):
                self.values_by_path[p].add(_key(v))

    def context(self, ctx: tuple, volatile: set) -> str:
        items = [(f"in.{p}", v) for p, v in self.inputs] + [(f"out.{p}", v) for p, v in ctx]
        return _key(sorted((p, v) for p, v in items if (self.name, p.split(".", 1)[1]) not in volatile))


# --- norms (fit on successful training runs) ---------------------------------------------------


def fit_norms(runs: list[dict]) -> dict:
    clean = [r for r in runs if r["outcome"] == "success" and not r.get("fault")]
    distinct: dict[tuple, set] = defaultdict(set)
    count: Counter = Counter()
    views = [(r, [StepView(r, i) for i in range(len(r["steps"]))]) for r in clean]
    for _, vs in views:
        for v in vs:
            for p, val, _ in v.out:
                distinct[(v.name, p)].add(_key(val))
                count[(v.name, p)] += 1
            for p, val in v.inputs:
                distinct[(v.name, p)].add(_key(val))
                count[(v.name, p)] += 1
    volatile = {k for k, s in distinct.items() if len(s) > 20 and len(s) > 0.5 * count[k]}

    values: dict[str, Counter] = defaultdict(Counter)
    ranges: dict[str, dict[str, list[float]]] = defaultdict(dict)
    path_seen: Counter = Counter()
    word_seen: Counter = Counter()
    word_value: Counter = Counter()
    word_templates: dict[tuple, set] = defaultdict(set)
    value_seen: Counter = Counter()
    for run, vs in views:
        words = tokens(run["request_text"])
        for v in vs:
            for p, val, ctx in v.out:
                if (v.name, p) in volatile:
                    continue
                c = v.context(ctx, volatile)
                values[f"{v.name}|{p}|{c}"][_key(val)] += 1
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    rk = f"{v.name}|{p}|{c}|{_key(val)}"
                    for n, x in v.numbers.items():
                        lo, hi, k = ranges[rk].get(n, [x, x, 0])
                        ranges[rk][n] = [min(lo, x), max(hi, x), k + 1]
            for p, vals in v.values_by_path.items():
                if (v.name, p) in volatile:
                    continue
                path_seen[(v.name, p)] += 1
                for val in vals:
                    value_seen[(v.name, p, val)] += 1
                for w in words:
                    word_seen[(v.name, p, w)] += 1
                    for val in vals:
                        word_value[(v.name, p, w, val)] += 1
                        word_templates[(v.name, p, w, val)].add(run["template_id"])

    hints: dict[str, list[str]] = defaultdict(list)
    for (name, p, w, val), n in word_value.items():
        n_w = word_seen[(name, p, w)]
        always = value_seen[(name, p, val)] / path_seen[(name, p)]
        if (n_w >= MIN_SEEN and n / n_w >= HINT and n / n_w - always >= HINT_LIFT
                and len(word_templates[(name, p, w, val)]) >= HINT_TEMPLATES):
            hints[f"{name}|{p}|{w}"].append(val)

    return {
        "volatile": sorted(f"{a}|{b}" for a, b in volatile),
        "values": {k: dict(c) for k, c in values.items()},
        "ranges": ranges,
        "hints": hints,
        "n_runs": len(clean),
    }


# --- per-step checks ---------------------------------------------------------------------------


def _fmt(v: str) -> str:
    return v.strip('"')


def _ctx_text(ctx_key: str) -> str:
    seen, pairs = set(), []
    for p, v in json.loads(ctx_key):  # one mention per value: query=x and id=x say the same thing
        if v not in seen:
            seen.add(v)
            pairs.append(f"{p.split('.')[-1]}={v}")
    return ", ".join(pairs[:3]) or "no inputs"


def check_step(v: StepView, norms: dict, words: set[str], sources: list[dict]) -> tuple[dict, list[tuple[str, str]]]:
    """Anomaly measures for one step plus readable evidence for each one that fired."""
    volatile = {tuple(x.split("|", 1)) for x in norms["volatile"]}
    values, ranges, hints = norms["values"], norms["ranges"], norms["hints"]
    surprise, violation, unknown, range_note = 0, 0.0, 0, ""
    evidence: list[tuple[str, str]] = []  # (feature, readable fact)

    for p, val, ctx in v.out:
        if (v.name, p) in volatile:
            continue
        c = v.context(ctx, volatile)
        seen = values.get(f"{v.name}|{p}|{c}")
        if not seen:
            unknown += 1
            continue
        total = sum(seen.values())
        mode, n_mode = max(seen.items(), key=lambda kv: kv[1])
        if _key(val) not in seen and total >= MIN_SEEN and n_mode / total >= 0.9:
            surprise += 1
            evidence.append(("surprise", f"{p.split('.')[-1]} = {val}, but with {_ctx_text(c)} it was always {_fmt(mode)}"))
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            for n, (lo, hi, k) in ranges.get(f"{v.name}|{p}|{c}|{_key(val)}", {}).items():
                x = v.numbers.get(n)
                if x is None or k < 3:
                    continue
                gap = (lo - x) / max(abs(lo), 1) if x < lo else (x - hi) / max(abs(hi), 1) if x > hi else 0.0
                if gap > violation:
                    violation = gap
                    side = f"below the lowest seen ({lo:g})" if x < lo else f"above the highest seen ({hi:g})"
                    range_note = f"{p.split('.')[-1]} = {val} with {n.split('.', 1)[1]} {x:g}, {side}"
    if range_note:
        evidence.append(("range_violation", range_note))

    links = 0
    for rec in records(v.step["output"]):
        best, agree = 0, False
        for src in sources:
            shared = [k for k in rec if k in src and not isinstance(rec[k], float)]
            if not shared:
                continue
            ok = all(rec[k] == src[k] for k in shared)
            if len(shared) > best:
                best, agree = len(shared), ok
            elif len(shared) == best:
                agree = agree or ok
        if best and not agree:
            links += 1
            evidence.append(("link_mismatch", "output " + ", ".join(f"{k}={rec[k]}" for k in list(rec)[:3])
                             + " doesn't match its input or the steps it used"))

    request = 0
    for p, vals in v.values_by_path.items():
        for w in words:
            for want in hints.get(f"{v.name}|{p}|{w}", []):
                if want not in vals:
                    request += 1
                    evidence.append(("request_mismatch", f"the request says '{w}', but {p.split('.')[-1]} has no {_fmt(want)}"))

    error = int(v.step.get("error") is not None)
    if error:
        evidence.append(("error", f"error: {v.step['error']}"))
    return {"surprise": surprise, "range_violation": round(violation, 4), "link_mismatch": links,
            "request_mismatch": request, "unknown_context": unknown, "error": error}, evidence


def descendants(steps: list[dict]) -> dict[int, set[int]]:
    """For each step, every later step that depends on it directly or indirectly."""
    down: dict[int, set[int]] = {s["id"]: set() for s in steps}
    for s in reversed(steps):
        for u in s["uses"]:
            if u in down:
                down[u] |= {s["id"]} | down[s["id"]]
    return down


ANOMALY = ("surprise", "range_violation", "link_mismatch", "request_mismatch", "error")

FEATURES = [
    "surprise", "range_violation", "link_mismatch", "request_mismatch", "error", "unknown_context",
    "anomalous", "first_anomaly", "anomalies_before", "anomalous_ancestor", "downstream_anomalies",
    "n_downstream", "position", "is_last",
]

LABELS = {
    "surprise": "Output differs from what this step always returned for the same input",
    "range_violation": "Output given for a value outside the range seen in successful runs",
    "link_mismatch": "Output doesn't match the step's own input or the steps it used",
    "request_mismatch": "Output doesn't match the words in the request",
    "error": "The step reported an error",
    "unknown_context": "Inputs never seen in successful runs",
    "anomalous": "The step looks abnormal",
    "first_anomaly": "First abnormal step in the run",
    "anomalies_before": "Abnormal steps before it",
    "anomalous_ancestor": "A step it depends on already looked abnormal",
    "downstream_anomalies": "Later steps that depend on it look abnormal",
    "n_downstream": "Number of later steps that depend on it",
    "n_uses": "Number of earlier steps it uses",
    "position": "Position in the run",
    "is_last": "Last step of the run",
    "is_llm": "Step is an LLM decision",
}


def run_features(run: dict, norms: dict) -> tuple[list[dict[str, float]], list[list[tuple[str, str]]]]:
    """One feature row and one evidence list per step, in step order."""
    steps = run["steps"]
    words = tokens(run["request_text"])
    by_id = {s["id"]: s for s in steps}
    down = descendants(steps)
    rows, notes = [], []
    for i, s in enumerate(steps):
        v = StepView(run, i)
        sources = records(s["input"]) + [r for u in s["uses"] if u in by_id for r in records(by_id[u]["output"])]
        flat = {k: x for k, x in v.state.items() if _is_scalar(x)}
        sources += ([flat] if flat else []) + records({k: x for k, x in v.state.items() if not _is_scalar(x)})
        checks, ev = check_step(v, norms, words, sources)
        rows.append(checks)
        notes.append(ev)

    anomalous = [any(r[k] > 0 for k in ANOMALY) for r in rows]
    ancestors: dict[int, set[int]] = {s["id"]: set() for s in steps}
    for s in steps:
        for u in s["uses"]:
            if u in ancestors:
                ancestors[s["id"]] |= {u} | ancestors[u]
    idx = {s["id"]: i for i, s in enumerate(steps)}
    first = anomalous.index(True) if any(anomalous) else -1
    n = len(steps)
    for i, (s, r) in enumerate(zip(steps, rows)):
        r["anomalous"] = int(anomalous[i])
        r["first_anomaly"] = int(i == first)
        r["anomalies_before"] = sum(anomalous[:i])
        r["anomalous_ancestor"] = int(any(anomalous[idx[a]] for a in ancestors[s["id"]]))
        r["downstream_anomalies"] = sum(anomalous[idx[d]] for d in down[s["id"]])
        r["n_downstream"] = len(down[s["id"]]) / n
        r["n_uses"] = len(s["uses"])
        r["position"] = i / max(n - 1, 1)
        r["is_last"] = int(i == n - 1)
        r["is_llm"] = int(s["kind"] == "llm")
    return [{k: float(r[k]) for k in FEATURES} for r in rows], notes
