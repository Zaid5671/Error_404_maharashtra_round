"""Train the diagnosis model for one agent: python -m blackbox.train pizza [--cv]

Rows are steps; label 1 = the step where the fault was injected. Training uses the agent's
`split == "train"` runs: failed faulted runs give the culprit and innocent steps, clean runs give
more innocent steps. Fault types that never appear in training stay unseen for the evaluation.

Features of a training run come from norms fitted WITHOUT that run's template (out of fold), so
the model learns from the same kind of imperfect memory it will have on new tasks.
--cv: leave one training fault type out at a time and report how well the left-out type is found.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import numpy as np
import xgboost as xgb

from blackbox.config import MODELS_DIR
from blackbox.features import FEATURES, fit_norms, run_features
from blackbox.store import list_runs

# Common sense the model must obey, for any agent: more evidence never lowers suspicion, and an
# abnormal step earlier in the chain only lowers it (this step is then more likely a symptom).
# Without these, the model learns WHERE culprits sat in training (e.g. "the first step is never
# guilty") instead of WHAT looked wrong, and misses faults in places it never saw one.
MONOTONE = {
    "surprise": 1, "range_violation": 1, "link_mismatch": 1, "request_mismatch": 1, "error": 1,
    "anomalous": 1, "first_anomaly": 1, "downstream_anomalies": 1, "n_downstream": 1,
    "anomalies_before": -1, "anomalous_ancestor": -1, "position": -1,
}
PARAMS = {"objective": "binary:logistic", "max_depth": 4, "eta": 0.1, "subsample": 0.9,
          "min_child_weight": 2, "eval_metric": "logloss", "seed": 0,
          "monotone_constraints": "(" + ",".join(str(MONOTONE.get(f, 0)) for f in FEATURES) + ")"}
ROUNDS = 200


def load_runs(agent: str) -> list[dict]:
    """The generator's runs only. Live runs and replays live in the same folder, and a replay of a
    training run even keeps its split, so they must never reach training or evaluation."""
    runs = (json.loads(p.read_text(encoding="utf-8")) for p in list_runs(agent))
    return [r for r in runs if r["source"] == "generated"]


def is_case(run: dict) -> bool:
    """A failure with a known culprit: what the model is trained and scored on."""
    return run["outcome"] == "failure" and run.get("fault") is not None


def is_clean(run: dict) -> bool:
    return run["outcome"] == "success" and run.get("fault") is None


def out_of_fold(runs: list[dict]) -> list[tuple[dict, list[dict]]]:
    """Feature rows for each run, using norms fitted on the other templates' clean runs."""
    by_template = defaultdict(list)
    for r in runs:
        by_template[r["template_id"]].append(r)
    out = []
    for template, group in by_template.items():
        norms = fit_norms([r for r in runs if r["template_id"] != template])
        out += [(r, run_features(r, norms)[0]) for r in group]
    return out


def matrix(featured: list[tuple[dict, list[dict]]]) -> tuple[np.ndarray, np.ndarray]:
    X, y = [], []
    for run, rows in featured:
        culprit = run["fault"]["step_id"] if is_case(run) else None
        for step, row in zip(run["steps"], rows):
            X.append([row[f] for f in FEATURES])
            y.append(int(step["id"] == culprit))
    return np.array(X, dtype=float), np.array(y)


def fit(featured: list[tuple[dict, list[dict]]]) -> xgb.Booster:
    X, y = matrix(featured)
    return xgb.train(PARAMS, xgb.DMatrix(X, label=y, feature_names=FEATURES), ROUNDS)


def score(model: xgb.Booster, rows: list[dict]) -> list[float]:
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype=float)
    return model.predict(xgb.DMatrix(X, feature_names=FEATURES)).tolist()


def rank_of(run: dict, scores: list[float]) -> int:
    """1-based rank of the true culprit (ties count against the model)."""
    ids = [s["id"] for s in run["steps"]]
    mine = scores[ids.index(run["fault"]["step_id"])]
    return 1 + sum(s >= mine for i, s in zip(ids, scores) if i != run["fault"]["step_id"])


def usable(runs: list[dict]) -> list[dict]:
    return [r for r in runs if is_case(r) or is_clean(r)]


def cross_validate(train: list[dict]) -> None:
    featured = out_of_fold(usable(train))
    types = sorted({r["fault"]["type"] for r, _ in featured if is_case(r)})
    for t in types:
        fold = [(r, x) for r, x in featured if not (is_case(r) and r["fault"]["type"] == t)]
        model = fit(fold)
        ranks = [rank_of(r, score(model, x)) for r, x in featured if is_case(r) and r["fault"]["type"] == t]
        print(f"  left out {t:<18} n={len(ranks):<4} top1={np.mean([k == 1 for k in ranks]):.2f} "
              f"top3={np.mean([k <= 3 for k in ranks]):.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("agent")
    ap.add_argument("--cv", action="store_true", help="leave-one-fault-type-out check on training runs")
    args = ap.parse_args()

    train = usable([r for r in load_runs(args.agent) if r.get("split") == "train"])
    if args.cv:
        cross_validate(train)
        return
    model = fit(out_of_fold(train))
    out = MODELS_DIR / args.agent
    out.mkdir(parents=True, exist_ok=True)
    model.save_model(out / "model.json")
    (out / "feature_stats.json").write_text(json.dumps(fit_norms(train)), encoding="utf-8")
    seen = sorted({r["fault"]["type"] for r in train if is_case(r)})
    meta = {"features": FEATURES, "seen_fault_types": seen, "n_train_runs": len(train),
            "n_train_cases": sum(map(is_case, train))}
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"trained {args.agent}: {meta['n_train_runs']} runs ({meta['n_train_cases']} failures), seen faults {seen}")


if __name__ == "__main__":
    main()
