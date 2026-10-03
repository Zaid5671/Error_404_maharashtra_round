"""Diagnosis pipeline on the two sample runs (no LLM, no generated data needed).

The clean sample, under five template names, stands in for the successful training runs; the
faulted sample is the clean run with PIZZA20 worth 25% instead of 20% at step 8.
"""

import copy
import json

from blackbox import config
from blackbox.contract import Diagnosis
from blackbox.diagnose import diagnose_with, impact_path
from blackbox.features import FEATURES, fit_norms, run_features
from blackbox.train import fit, rank_of, score


def load(name):
    return json.loads((config.SAMPLE_DIR / name).read_text(encoding="utf-8"))


def clean_copies(n=5):
    clean = load("pizza_clean.json")
    return [{**copy.deepcopy(clean), "template_id": f"t{i}"} for i in range(n)]


def test_the_injected_step_is_the_first_anomaly():
    faulted = load("pizza_faulted.json")
    rows, notes = run_features(faulted, fit_norms(clean_copies()))
    culprit = [s["id"] for s in faulted["steps"]].index(faulted["fault"]["step_id"])
    assert rows[culprit]["first_anomaly"] == 1
    assert rows[culprit]["surprise"] >= 1
    assert any("20" in text for _, text in notes[culprit])
    assert set(rows[0]) == set(FEATURES)


def test_clean_run_has_no_anomalies_against_itself():
    clean = clean_copies()
    rows, _ = run_features(clean[0], fit_norms(clean))
    assert not any(r["anomalous"] for r in rows)


def test_diagnose_returns_a_valid_diagnosis():
    clean, faulted = clean_copies(), load("pizza_faulted.json")
    norms = fit_norms(clean)
    model = fit([(r, run_features(r, norms)[0]) for r in clean * 4 + [faulted] * 20])

    diag = Diagnosis.model_validate(diagnose_with(model, norms, faulted).model_dump())
    culprit = faulted["fault"]["step_id"]
    assert diag.culprit == culprit and diag.ranking[0] == culprit
    assert rank_of(faulted, score(model, run_features(faulted, norms)[0])) == 1
    assert set(diag.scores) == {str(s["id"]) for s in faulted["steps"]}
    assert diag.reasons and all(r.shap > 0 for r in diag.reasons)
    assert diag.impact_path[0] == culprit and diag.impact_path[-1] == faulted["steps"][-1]["id"]
    assert f"step {culprit}" in diag.explanation.lower()

    ok = diagnose_with(model, norms, clean[0])
    assert ok.culprit is None and ok.reasons == [] and ok.impact_path == []


def test_impact_path_follows_uses_to_the_last_step():
    steps = [{"id": 1, "uses": []}, {"id": 2, "uses": [1]}, {"id": 3, "uses": []}, {"id": 4, "uses": [2, 3]}]
    assert impact_path(steps, 1) == [1, 2, 4]
    assert impact_path(steps, 3) == [3, 4]
