"""Import traces recorded elsewhere into an agent (usually an imported agent).

Each run must match the trace format (blackbox.contract.Run). It is stored as source "imported";
a run without a split gets one from its template id (blackbox.split.split_by_hash), so test runs
still come from templates the model never trained on. A failed run with a `fault` label is a known
failure the model can learn from and be scored on.
"""

from __future__ import annotations

import re

from pydantic import ValidationError

from blackbox import store
from blackbox.contract import Run
from blackbox.split import split_by_hash

RUN_ID = re.compile(r"^[A-Za-z0-9_-]{1,160}$")


def import_runs(agent: str, runs: list[dict], names: list[str] | None = None) -> dict:
    imported, rejected = [], []
    for i, raw in enumerate(runs):
        where = names[i] if names and i < len(names) else f"run {i + 1}"
        if not isinstance(raw, dict):
            rejected.append({"where": where, "error": "not a JSON object"})
            continue
        run = {**raw, "agent": agent, "source": "imported"}
        run.setdefault("parent_run_id", None)
        run.setdefault("replayed_from_step", None)
        run.setdefault("messages", [])
        if not run.get("split") and isinstance(run.get("template_id"), str):
            run["split"] = split_by_hash(run["template_id"])
        try:
            Run.model_validate(run)
        except ValidationError as e:
            err = e.errors()[0]
            rejected.append({"where": where, "error": f"{'.'.join(map(str, err['loc']))}: {err['msg']}"})
            continue
        if not RUN_ID.match(run["run_id"]):
            rejected.append({"where": where, "error": "run_id may only use letters, digits, '_' and '-'"})
            continue
        if store.run_path(agent, run["run_id"]).exists():
            rejected.append({"where": where, "error": f"a run named '{run['run_id']}' already exists"})
            continue
        store.save_run(run)
        imported.append(run["run_id"])
    return {"imported": len(imported), "run_ids": imported, "rejected": rejected}
