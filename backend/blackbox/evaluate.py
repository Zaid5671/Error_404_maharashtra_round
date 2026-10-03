"""Score the trained model on the agent's test runs: python -m blackbox.evaluate pizza

Only failed runs with a known (injected) culprit are scored. "Seen" faults are types the model
trained on; "unseen" are types that never appeared in training. Writes reports/<agent>/report.json.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from blackbox.config import REPORTS_DIR
from blackbox.contract import Report
from blackbox.diagnose import load_model
from blackbox.train import is_case, load_runs, rank_of, score
from blackbox.features import run_features


def accuracy(ranks: list[int]) -> dict:
    n = len(ranks)
    return {"top1": round(sum(k == 1 for k in ranks) / n, 4) if n else 0.0,
            "top3": round(sum(k <= 3 for k in ranks) / n, 4) if n else 0.0}


def evaluate(agent: str) -> Report:
    model, norms, meta = load_model(agent)
    seen_types = set(meta["seen_fault_types"])
    cases = [r for r in load_runs(agent) if r.get("split") == "test" and is_case(r)]
    ranks: dict[str, list[int]] = defaultdict(list)
    for run in cases:
        rows, _ = run_features(run, norms)
        ranks[run["fault"]["type"]].append(rank_of(run, score(model, rows)))

    seen = [k for t, rs in ranks.items() if t in seen_types for k in rs]
    unseen = [k for t, rs in ranks.items() if t not in seen_types for k in rs]
    for t, rs in sorted(ranks.items()):
        a = accuracy(rs)
        print(f"  {t:<18} {'seen' if t in seen_types else 'UNSEEN':<6} n={len(rs):<4} top1={a['top1']:.2f} top3={a['top3']:.2f}")
    return Report(
        agent=agent,
        n_train_runs=meta["n_train_runs"],
        n_test_runs=len(cases),
        overall=accuracy(seen + unseen),
        seen={**accuracy(seen), "n": len(seen)},
        unseen={**accuracy(unseen), "n": len(unseen)},
        fault_types={"seen": sorted(seen_types), "unseen": sorted(t for t in ranks if t not in seen_types)},
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("agent")
    args = ap.parse_args()
    report = evaluate(args.agent)
    out = REPORTS_DIR / args.agent / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    print(f"overall top1={report.overall.top1:.2f} top3={report.overall.top3:.2f} | "
          f"seen top1={report.seen.top1:.2f} (n={report.seen.n}) | unseen top1={report.unseen.top1:.2f} (n={report.unseen.n})")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
