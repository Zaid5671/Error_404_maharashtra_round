"""Diagnose one run: score every step, pick the culprit, explain why, trace the impact.

    from blackbox.diagnose import diagnose
    diagnose("pizza", run)  # -> Diagnosis

Reasons are the culprit's largest positive SHAP contributions (XGBoost pred_contribs). An anomaly
feature is labelled with the concrete fact that fired it ("delivery_fee = 60, but with
area=Andheri it was always 40"); other features get a short readable label.
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import xgboost as xgb

from blackbox.config import MODELS_DIR
from blackbox.contract import Diagnosis, Reason
from blackbox.features import FEATURES, LABELS, descendants, run_features

N_REASONS = 3


@lru_cache(maxsize=None)
def load_model(agent: str) -> tuple[xgb.Booster, dict, dict]:
    folder = MODELS_DIR / agent
    if not (folder / "model.json").exists():
        raise FileNotFoundError(f"no trained model for agent '{agent}': run python -m blackbox.train {agent}")
    model = xgb.Booster()
    model.load_model(folder / "model.json")
    norms = json.loads((folder / "feature_stats.json").read_text(encoding="utf-8"))
    meta = json.loads((folder / "meta.json").read_text(encoding="utf-8"))
    return model, norms, meta


def impact_path(steps: list[dict], culprit: int) -> list[int]:
    """The culprit and every later step its output reached on the way to the last step."""
    down = descendants(steps)
    last = steps[-1]["id"]
    reach_last = {s["id"] for s in steps if s["id"] == last or last in down[s["id"]]}
    return [culprit] + sorted(d for d in down[culprit] if d in reach_last)


def _label(feature: str, row: dict, notes: list[tuple[str, str]], n_down: int) -> str:
    facts = [text for f, text in notes if f == feature]
    if facts:
        return facts[0]
    if feature == "downstream_anomalies":
        return f"{int(row[feature])} later steps that depend on it also look abnormal"
    if feature == "n_downstream":
        return f"{n_down} later steps depend on its output"
    if feature == "anomalies_before" and row[feature] == 0:
        return "No step before it looked abnormal"
    if feature == "anomalous_ancestor" and row[feature] == 0:
        return "Nothing it depends on looked abnormal"
    return LABELS[feature]


def _name(step: dict) -> str:
    return f"step {step['id']} ({step['name']})"


def diagnose(agent: str, run: dict) -> Diagnosis:
    model, norms, _ = load_model(agent)
    return diagnose_with(model, norms, run)


def diagnose_with(model: xgb.Booster, norms: dict, run: dict) -> Diagnosis:
    steps = run["steps"]
    rows, notes = run_features(run, norms)
    X = xgb.DMatrix(np.array([[r[f] for f in FEATURES] for r in rows], dtype=float), feature_names=FEATURES)
    scores = model.predict(X).tolist()
    order = sorted(range(len(steps)), key=lambda i: -scores[i])
    result = {
        "run_id": run["run_id"],
        "scores": {str(s["id"]): round(p, 4) for s, p in zip(steps, scores)},
        "ranking": [steps[i]["id"] for i in order],
    }
    if run["outcome"] != "failure" or not steps:
        return Diagnosis(**result, culprit=None, reasons=[], impact_path=[],
                         explanation="The run succeeded, so there is no failure to explain.")

    top = order[0]
    culprit = steps[top]
    contribs = model.predict(X, pred_contribs=True)[top][:-1]  # last column is the bias
    n_down = len(descendants(steps)[culprit["id"]])
    reasons = [
        Reason(feature=f, label=_label(f, rows[top], notes[top], n_down), shap=round(float(c), 4))
        for c, f in sorted(zip(contribs, FEATURES), reverse=True)[:N_REASONS] if c > 0
    ]
    path = impact_path(steps, culprit["id"])
    fact = next((text for _, text in notes[top]), None)
    explanation = f"{_name(culprit).capitalize()} most likely caused the failure"
    explanation += f": {fact}." if fact else f" ({reasons[0].label.lower()})." if reasons else "."
    if len(path) > 1:
        by_id = {s["id"]: s for s in steps}
        later = [_name(by_id[i]) for i in path[1:]]
        reach = (" and ".join(later) if len(later) <= 2
                 else f"{len(later)} later steps, up to {later[-1]}")
        explanation += f" Its output flowed into {reach}, so the final result was wrong."
    return Diagnosis(**result, culprit=culprit["id"], reasons=reasons, explanation=explanation, impact_path=path)
