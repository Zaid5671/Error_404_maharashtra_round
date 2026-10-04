"""Read-only views over an agent's saved runs, for the dashboard pages (Runs, Diagnoses, Replays,
Overview, Model → Training data, Agent). Generic: only the trace format is read.

Run files are parsed once and cached by modification time, and each failed run is diagnosed at
most once, so listing hundreds of runs stays fast after the first request.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from blackbox import store
from blackbox.config import REPORTS_DIR
from blackbox.diagnose import diagnose, load_model
from blackbox.features import LABELS
from blackbox.split import split_of

_summaries: dict[Path, tuple[float, dict]] = {}
_suspects: dict[tuple[str, str, float], dict | None] = {}

APP_SOURCES = {"live", "replay"}  # runs made in the app, as opposed to the generated dataset


def clear_diagnoses() -> None:
    """Forget cached diagnoses (after the model is retrained)."""
    _suspects.clear()


def summary(agent: str, path: Path) -> dict:
    """One row per run: what a table needs, without the steps or messages."""
    mtime = path.stat().st_mtime
    hit = _summaries.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    run = json.loads(path.read_text(encoding="utf-8"))
    steps = run["steps"]
    row = {
        "run_id": run["run_id"],
        "source": run["source"],
        "template_id": run["template_id"],
        "split": run.get("split"),
        "outcome": run["outcome"],
        "request_text": run["request_text"],
        "n_steps": len(steps),
        "llm_calls": sum(1 for s in steps if s["llm"]),
        "duration_ms": sum((s["llm"] or {}).get("latency_ms", 0) + s["tool_latency_ms"] for s in steps),
        "created": datetime.fromtimestamp(mtime, timezone.utc).isoformat(),
        "parent_run_id": run.get("parent_run_id"),
        "replayed_from_step": run.get("replayed_from_step"),
        "has_fault": run.get("fault") is not None,
        "fault_type": (run.get("fault") or {}).get("type"),
        "fault_family": (run.get("fault") or {}).get("family"),
        "fault_step": (run.get("fault") or {}).get("step_id"),
    }
    _summaries[path] = (mtime, row)
    return row


def summaries(agent: str) -> list[dict]:
    return [summary(agent, p) for p in store.list_runs(agent)]


def _brief_reason(reasons: list) -> str | None:
    """The strongest reason that states a fact from the run, else the strongest reason."""
    facts = [r.label for r in reasons if r.label != LABELS.get(r.feature)]
    return facts[0] if facts else reasons[0].label if reasons else None


def suspect(agent: str, row: dict) -> dict | None:
    """The diagnosis of a failed run in brief: suspected step, its score and the top reason."""
    if row["outcome"] != "failure":
        return None
    path = store.run_path(agent, row["run_id"])
    key = (agent, row["run_id"], path.stat().st_mtime)
    if key not in _suspects:
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
            d = diagnose(agent, run)
            step = next(s for s in run["steps"] if s["id"] == d.culprit)
            _suspects[key] = {"step_id": d.culprit, "name": step["name"], "score": d.scores[str(d.culprit)],
                              "reason": _brief_reason(d.reasons)}
        except (FileNotFoundError, StopIteration):
            _suspects[key] = None
    return _suspects[key]


def _matches(row: dict, source: str, outcome: str | None, q: str | None) -> bool:
    if source == "app" and row["source"] not in APP_SOURCES:
        return False
    if source not in ("app", "all") and row["source"] != source:
        return False
    if outcome and row["outcome"] != outcome:
        return False
    if q:
        hay = " ".join(str(row[k] or "") for k in ("run_id", "template_id", "request_text", "source")).lower()
        if not all(word in hay for word in q.lower().split()):
            return False
    return True


def list_runs(agent: str, *, source: str = "app", outcome: str | None = None, q: str | None = None,
              sort: str = "recent", limit: int = 50, offset: int = 0) -> dict:
    rows = [r for r in summaries(agent) if _matches(r, source, outcome, q)]
    if sort == "suspicion":
        for r in rows:
            r["suspect"] = suspect(agent, r)
        rows.sort(key=lambda r: -(r["suspect"] or {}).get("score", 0))
    else:
        rows.sort(key=lambda r: r["created"], reverse=True)
    page = rows[offset: offset + limit]
    for r in page:
        r["suspect"] = suspect(agent, r)
    return {"total": len(rows), "items": page}


def replays(agent: str) -> list[dict]:
    """Every replay with what it changed and whether it fixed its original run."""
    rows = {r["run_id"]: r for r in summaries(agent)}
    out = []
    for r in rows.values():
        if r["source"] != "replay":
            continue
        parent = rows.get(r["parent_run_id"] or "")
        run = json.loads(store.run_path(agent, r["run_id"]).read_text(encoding="utf-8"))
        k = r["replayed_from_step"] or 1
        out.append({
            **r,
            "parent_outcome": parent["outcome"] if parent else None,
            "edited_step": k,
            "edited_name": run["steps"][k - 1]["name"] if len(run["steps"]) >= k else None,
            "reused": k - 1,
            "rerun": len(run["steps"]) - k + 1,
            "llm_calls_saved": sum(1 for s in run["steps"][: k - 1] if s["llm"]),
        })
    out.sort(key=lambda r: r["created"], reverse=True)
    return out


def overview(agent: str, scope: str = "app") -> dict:
    rows = [r for r in summaries(agent) if scope == "all" or r["source"] in APP_SOURCES]
    failed = [r for r in rows if r["outcome"] == "failure"]
    reps = [r for r in replays(agent) if r["parent_outcome"] == "failure"]
    fixed = [r for r in reps if r["outcome"] == "success"]
    try:
        meta = load_model(agent)[2]
    except FileNotFoundError:
        meta = None
    report_path = REPORTS_DIR / agent / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    return {
        "scope": scope,
        "total_runs": len(rows),
        "failed_runs": len(failed),
        "failed_share": len(failed) / len(rows) if rows else 0.0,
        "replays": len(reps),
        "replays_fixed": len(fixed),
        "replay_success": len(fixed) / len(reps) if reps else None,
        "top1": report["overall"]["top1"] if report else None,
        "unseen_top1": report["unseen"]["top1"] if report else None,
        "model_trained": meta is not None,
        "demo_runs": demo_runs(agent),
    }


def demo_runs(agent: str, per_type: int = 1) -> list[dict]:
    """Prepared failed runs for the demo: one test run per fault type, unseen types first, picked
    among the runs the model diagnoses correctly so the demo shows the real behaviour on a good case."""
    try:
        seen = set(load_model(agent)[2]["seen_fault_types"])
    except FileNotFoundError:
        return []
    picked: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(summaries(agent), key=lambda r: r["run_id"]):
        t = r["fault_type"]
        if r["source"] not in ("generated", "imported") or r["split"] != "test" or r["outcome"] != "failure" or not t:
            continue
        if len(picked[t]) >= per_type:
            continue
        s = suspect(agent, r)
        if s and s["step_id"] == r["fault_step"]:
            picked[t].append({"run_id": r["run_id"], "fault_type": t, "seen": t in seen, "step_id": s["step_id"],
                              "step_name": s["name"], "request_text": r["request_text"]})
    return sorted((x for xs in picked.values() for x in xs), key=lambda x: (x["seen"], x["fault_type"]))


def dataset(agent: str, templates: list[str]) -> dict:
    """The generated runs the model learned from and was tested on."""
    rows = [r for r in summaries(agent) if r["source"] in ("generated", "imported")]
    kinds: Counter = Counter()
    by_type: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        kind = "clean" if not r["has_fault"] else r["fault_type"]
        kinds[(r["split"], kind, r["outcome"])] += 1
        by_type[kind][f"{r['split']}_{r['outcome']}"] += 1
    split_templates: dict[str, list[str]] = {"train": [], "test": []}
    seen_split = {r["template_id"]: r["split"] for r in rows if r["split"]}
    for t in sorted(set(templates) | set(seen_split)):
        split_templates[seen_split.get(t) or split_of(t, templates)].append(t)
    return {
        "total": len(rows),
        "train": sum(1 for r in rows if r["split"] == "train"),
        "test": sum(1 for r in rows if r["split"] == "test"),
        "templates": split_templates,
        "kinds": [{"kind": k, **{f"{s}_{o}": c[f"{s}_{o}"] for s in ("train", "test") for o in ("success", "failure")}}
                  for k, c in sorted(by_type.items(), key=lambda kv: (kv[0] != "clean", kv[0]))],
    }


def tool_usage(agent: str) -> list[dict]:
    """What each step type does, learned from the runs: kind, how often, which state keys it reads
    and writes (keys like menu:pepperoni are folded to menu:*)."""
    fold = lambda k: re.sub(r":.*", ":*", k)  # noqa: E731
    info: dict[str, dict] = {}
    for p in store.list_runs(agent)[:300]:
        run = json.loads(p.read_text(encoding="utf-8"))
        for s in run["steps"]:
            t = info.setdefault(s["name"], {"name": s["name"], "kind": s["kind"], "count": 0, "reads": set(), "writes": set()})
            t["count"] += 1
            t["reads"] |= {fold(k) for k in s["reads"]}
            t["writes"] |= {fold(k) for k in s["writes"]}
    return [{**t, "reads": sorted(t["reads"]), "writes": sorted(t["writes"])} for t in info.values()]


def warm(agents: list[str]) -> None:
    """Diagnose every failed run once (in the background at server start), so lists sorted by
    suspicion open instantly."""
    for agent in agents:
        try:
            for row in summaries(agent):
                suspect(agent, row)
        except Exception:  # noqa: BLE001 - warming is best effort; requests compute on demand
            pass
