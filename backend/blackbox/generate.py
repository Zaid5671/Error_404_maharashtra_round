"""Batch generation of labelled runs for one agent. Resumable: existing run files are skipped.

Work is done in groups, one per (seed, template): a clean run, then its faulted copies made by
resuming the clean run from the fault step. Groups go seed by seed across all templates, so
stopping at any point leaves a balanced dataset.

  python -m blackbox.generate --agent pizza            # full run (leave it running)
  python -m blackbox.generate --agent pizza --status   # counts only, no LLM calls
"""

from __future__ import annotations

import argparse
import json
import random
import threading
import time
from collections import Counter
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from blackbox import config, injector, store
from blackbox.adapter import AgentAdapter, QuotaExhausted
from blackbox.registry import get_agent
from blackbox.split import split_of

_log_lock = threading.Lock()
_stop = threading.Event()


def log(agent: str, message: str) -> None:
    line = f"{datetime.now():%H:%M:%S} {message}"
    with _log_lock:
        print(line, flush=True)
        path = config.RUNS_DIR / agent / "generate.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def _load_or_none(agent: str, run_id: str) -> dict | None:
    path = store.run_path(agent, run_id)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _describe(run: dict) -> str:
    fault = run["fault"]
    label = f"{fault['type']}@{fault['step_id']}" if fault else "clean"
    calls = sum(1 for s in run["steps"] if s["llm"])
    return f"{run['outcome']:7s} {label:24s} {run['run_id']}  steps={len(run['steps'])} llm_calls={calls}"


def run_group(adapter: AgentAdapter, template_id: str, seed: int, args: argparse.Namespace, test_index: int | None) -> None:
    """One clean run plus its faulted copies."""
    agent, templates = adapter.name, adapter.templates()
    split = split_of(template_id, templates)
    clean_id = f"{template_id}__s{seed}"

    clean = _load_or_none(agent, clean_id)
    if clean is None:
        clean = adapter.run(adapter.make_task(template_id, seed), run_id=clean_id, source="generated")
        clean["split"] = split
        store.save_run(clean)
        log(agent, _describe(clean))
    if clean["outcome"] != "success":
        return  # the agent erred on its own: kept for the demo, not used to make labelled faults

    # run ids never name the fault: the app shows them next to "Reveal hidden fault"
    jobs: list[tuple[str, str, str | None]] = [(f"{clean_id}__tool{j}", "tool", None) for j in range(args.tool_faults)]
    if split == "test" and test_index is not None:  # LLM faults are unseen types: test runs only
        if test_index < args.misread:
            jobs.append((f"{clean_id}__llm0", "llm", "llm_misread"))
        if test_index < args.choice:
            jobs.append((f"{clean_id}__llm1", "llm", "llm_wrong_choice"))
        if test_index < args.substitute:
            jobs.append((f"{clean_id}__llm2", "llm", "llm_wrong_substitute"))

    used: set[str] = set()
    for run_id, family, fault_type in jobs:
        if _stop.is_set():
            return
        existing = _load_or_none(agent, run_id)
        if existing is not None:
            if existing.get("fault"):
                used.add(existing["fault"]["type"])
            continue
        faulted = injector.inject(
            adapter, clean, run_id=run_id, rng=random.Random(run_id),
            family=family, fault_type=fault_type, avoid=used,
            exclude=set(args.holdout) if split == "train" else set(),
        )
        if faulted is None:
            continue
        used.add(faulted["fault"]["type"])
        store.save_run(faulted)
        log(agent, _describe(faulted) + f"  [{faulted['fault']['detail']}]")


def status(agent: str) -> str:
    counts: Counter = Counter()
    for path in store.list_runs(agent):
        run = json.loads(path.read_text(encoding="utf-8"))
        kind = run["fault"]["type"] if run["fault"] else "clean"
        counts[(run["split"], kind, run["outcome"])] += 1
    lines = [f"{'split':6s} {'kind':18s} {'success':>7s} {'failure':>7s}"]
    for split, kind in sorted({(s, k) for s, k, _ in counts}, key=lambda x: (str(x[0]), x[1])):
        lines.append(f"{str(split):6s} {kind:18s} {counts[(split, kind, 'success')]:7d} {counts[(split, kind, 'failure')]:7d}")
    lines.append(f"total runs: {sum(counts.values())}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate labelled runs for one agent.")
    parser.add_argument("--agent", default="pizza")
    parser.add_argument("--seeds", type=int, default=14, help="clean runs per template")
    parser.add_argument("--tool-faults", type=int, default=2, help="faulted copies per clean run (seen fault types)")
    parser.add_argument("--misread", type=int, default=40, help="llm_misread runs (test only, unseen)")
    parser.add_argument("--choice", type=int, default=0, help="llm_wrong_choice runs (test only, unseen)")
    parser.add_argument("--substitute", type=int, default=0, help="llm_wrong_substitute runs (test only, unseen; only where a substitution happened)")
    parser.add_argument(
        "--holdout", type=lambda v: [t for t in v.split(",") if t], default=[],
        help="comma-separated tool fault types never used on train runs (unseen types for testing)",
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--max-groups", type=int, default=None, help="stop after this many groups (for a quick check)")
    parser.add_argument("--status", action="store_true", help="print counts and exit")
    args = parser.parse_args()

    if args.status:
        print(status(args.agent))
        return

    adapter = get_agent(args.agent)
    templates = adapter.templates()
    groups = [(t, seed) for seed in range(args.seeds) for t in templates]
    test_order = [g for g in groups if split_of(g[0], templates) == "test"]
    if args.max_groups:
        groups = groups[: args.max_groups]

    log(args.agent, f"start: {len(groups)} groups, {args.workers} workers")
    start = time.time()

    def work(group: tuple[str, int]) -> None:
        if _stop.is_set():
            return
        template_id, seed = group
        test_index = test_order.index(group) if group in test_order else None
        try:
            run_group(adapter, template_id, seed, args, test_index)
        except QuotaExhausted as e:
            if not _stop.is_set():
                _stop.set()
                log(args.agent, f"DAILY CAP HIT, stopping. Run the same command later to resume.\n{str(e)[:600]}")
        except Exception as e:  # one bad run must not stop the batch
            log(args.agent, f"ERROR in {template_id} seed {seed}: {type(e).__name__}: {e}")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, groups))

    log(args.agent, f"{'stopped' if _stop.is_set() else 'done'} after {(time.time() - start) / 60:.1f} min\n{status(args.agent)}")


# --- generation started from the app (agents connected by URL) ------------------------------------


def generate_from_app(
    agent: str,
    *,
    runs_per_kind: int,
    faults_per_run: int,
    log: Callable[[str], None],
    stop: threading.Event,
    progress: Callable[[int, int], None],
    workers: int = 2,
) -> dict:
    """Make labelled runs for an agent: each kind of example task `runs_per_kind` times (clean
    runs), then `faults_per_run` faulted copies of each clean run (one value changed in one tool's
    output, the rest re-run from there). Train/test is split by kind. One tool's faults are kept
    out of training entirely, so the report can show accuracy on a fault type the model never saw.
    Resumable: runs already on disk are skipped."""
    adapter = get_agent(agent)
    kinds = adapter.templates()
    if len(kinds) < 2:
        raise ValueError("the agent needs at least 2 kinds of example tasks, so some can be kept for testing (4 or more is better)")
    specs = adapter.faults()
    tools = sorted({s.step_name for s in specs})
    if not tools:
        raise ValueError("the agent has no tools wrapped with @bb.tool, so there is nothing to plant faults in")
    held_out = random.Random(agent).choice(tools) if len(tools) > 1 else None
    exclude = {s.type for s in specs if s.step_name == held_out}
    test_kinds = sorted(k for k in kinds if split_of(k, kinds) == "test")
    log(f"{len(kinds)} kinds of task: test on {', '.join(test_kinds)}; train on the rest")
    if held_out:
        log(f"faults on {held_out} are kept for testing only (an unseen fault type)")

    groups = [(kind, seed) for seed in range(runs_per_kind) for kind in kinds]
    total, done, lock = len(groups) * (1 + faults_per_run), [0], threading.Lock()
    counts: Counter = Counter()

    def tick(n: int = 1) -> None:
        with lock:
            done[0] += n
            progress(done[0], total)

    def group(g: tuple[str, int]) -> None:
        kind, seed = g
        if stop.is_set():
            return
        split = split_of(kind, kinds)
        clean_id = f"{kind}__s{seed}"
        clean = _load_or_none(agent, clean_id)
        if clean is None:
            clean = adapter.run(adapter.make_task(kind, seed), run_id=clean_id, source="generated")
            clean["split"] = split
            store.save_run(clean)
            log(f"{'✓' if clean['outcome'] == 'success' else '✗'} clean    {clean_id}  {len(clean['steps'])} steps")
        tick()
        counts["clean"] += 1
        if clean["outcome"] != "success":  # the agent got it wrong by itself: no reference to break
            counts["clean_failed"] += 1
            tick(faults_per_run)
            return
        used: set[str] = set()
        for j in range(faults_per_run):
            if stop.is_set():
                return
            run_id = f"{clean_id}__f{j}"
            faulted = _load_or_none(agent, run_id)
            if faulted is None:
                faulted = injector.inject(adapter, clean, run_id=run_id, rng=random.Random(run_id), avoid=used,
                                          exclude=exclude if split == "train" else set())
                if faulted is not None:
                    store.save_run(faulted)
                    f = faulted["fault"]
                    verdict = "✗ failed" if faulted["outcome"] == "failure" else "✓ fault didn't matter"
                    log(f"fault    {run_id}  {f['type']} at step {f['step_id']} ({f['detail']}) → {verdict}")
            if faulted is not None:
                used.add(faulted["fault"]["type"])
                counts["failed" if faulted["outcome"] == "failure" else "harmless"] += 1
            tick()

    def safe(g: tuple[str, int]) -> None:
        try:
            group(g)
        except Exception as e:  # noqa: BLE001 - one bad run must not stop the batch, but a dead agent does
            log(f"error in {g[0]} #{g[1]}: {type(e).__name__}: {e}")
            if "not reachable" in str(e):
                stop.set()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(safe, groups))
    summary = {"clean": counts["clean"], "failed": counts["failed"], "harmless": counts["harmless"],
               "clean_failed": counts["clean_failed"], "held_out_tool": held_out}
    log(f"{'stopped' if stop.is_set() else 'generated'}: {summary['clean']} clean runs, {summary['failed']} failures "
        f"with a known culprit, {summary['harmless']} faults that didn't change the result")
    return summary


if __name__ == "__main__":
    main()
