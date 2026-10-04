"""Training jobs started from the app: train, then evaluate, in a background thread.

One job per agent at a time. The log and result are kept in memory while the server runs; each
finished job is also appended to models/<agent>/history.json.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

from blackbox import index
from blackbox.config import MODELS_DIR
from blackbox.diagnose import load_model
from blackbox.evaluate import write_report
from blackbox.train import train_agent

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def history(agent: str) -> list[dict]:
    path = MODELS_DIR / agent / "history.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def status(agent: str) -> dict:
    job = _jobs.get(agent) or {"status": "idle", "log": [], "started": None, "finished": None, "result": None, "error": None}
    return {**job, "log": list(job["log"]), "history": history(agent)}


def start(agent: str) -> dict:
    with _lock:
        if _jobs.get(agent, {}).get("status") == "running":
            raise RuntimeError("a training job is already running for this agent")
        job = {"status": "running", "log": [], "started": _now(), "finished": None, "result": None, "error": None}
        _jobs[agent] = job
    threading.Thread(target=_run, args=(agent, job), daemon=True).start()
    return status(agent)


def _run(agent: str, job: dict) -> None:
    t0 = time.perf_counter()

    def log(line: str) -> None:
        job["log"].append(f"{time.perf_counter() - t0:5.1f}s  {line}")

    try:
        log("training started")
        meta = train_agent(agent, log)
        load_model.cache_clear()  # the server must diagnose with the new model from now on
        index.clear_diagnoses()
        log("evaluating on the test runs")
        report = write_report(agent, log)
        job["result"] = {"n_train_runs": meta["n_train_runs"], "n_test_runs": report.n_test_runs,
                         "top1": report.overall.top1, "top3": report.overall.top3,
                         "unseen_top1": report.unseen.top1, "unseen_n": report.unseen.n}
        job["status"] = "done"
        log("done")
    except Exception as e:  # noqa: BLE001 - shown to the user in the job log
        job["status"], job["error"] = "error", str(e)
        log(f"stopped: {e}")
    finally:
        job["finished"] = _now()
        entry = {k: job[k] for k in ("status", "started", "finished", "result", "error")}
        path = MODELS_DIR / agent / "history.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([entry] + history(agent), indent=2), encoding="utf-8")
