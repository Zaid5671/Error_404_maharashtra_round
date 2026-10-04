"""Jobs started from the app, in a background thread: train then evaluate; or, for an agent
connected by URL, generate labelled runs first, then train and evaluate.

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
from blackbox.generate import generate_from_app
from blackbox.train import train_agent

_jobs: dict[str, dict] = {}
_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def history(agent: str) -> list[dict]:
    path = MODELS_DIR / agent / "history.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


IDLE = {"status": "idle", "kind": None, "log": [], "started": None, "finished": None, "result": None,
        "error": None, "progress": None, "generated": None}


def status(agent: str) -> dict:
    job = _jobs.get(agent) or IDLE
    public = {k: v for k, v in job.items() if k != "stop"}
    return {**public, "log": list(job["log"]), "history": history(agent)}


def _new_job(agent: str, kind: str) -> dict:
    with _lock:
        if _jobs.get(agent, {}).get("status") == "running":
            raise RuntimeError("a job is already running for this agent")
        job = {**IDLE, "status": "running", "kind": kind, "log": [], "started": _now(), "stop": threading.Event()}
        _jobs[agent] = job
    return job


def start(agent: str) -> dict:
    job = _new_job(agent, "train")
    threading.Thread(target=_run, args=(agent, job), daemon=True).start()
    return status(agent)


def start_generate(agent: str, runs_per_kind: int, faults_per_run: int) -> dict:
    job = _new_job(agent, "generate")
    job["progress"] = {"done": 0, "total": 0, "stage": "generate"}
    threading.Thread(target=_run, args=(agent, job), kwargs={"generate": (runs_per_kind, faults_per_run)}, daemon=True).start()
    return status(agent)


def stop(agent: str) -> dict:
    job = _jobs.get(agent)
    if job and job.get("status") == "running" and job.get("stop"):
        job["stop"].set()
    return status(agent)


def _run(agent: str, job: dict, generate: tuple[int, int] | None = None) -> None:
    t0 = time.perf_counter()

    def log(line: str) -> None:
        job["log"].append(f"{time.perf_counter() - t0:5.1f}s  {line}")

    def progress(done: int, total: int) -> None:
        job["progress"] = {"done": done, "total": total, "stage": "generate"}

    try:
        if generate:
            runs_per_kind, faults_per_run = generate
            log(f"generating: {runs_per_kind} runs of each kind of task, {faults_per_run} planted faults per run")
            job["generated"] = generate_from_app(agent, runs_per_kind=runs_per_kind, faults_per_run=faults_per_run,
                                                 log=log, stop=job["stop"], progress=progress)
            index.clear_diagnoses()
            if job["stop"].is_set():
                raise RuntimeError("stopped before training; the runs made so far are kept")
            job["progress"] = {**job["progress"], "stage": "train"}
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
        if job["progress"]:
            job["progress"] = {**job["progress"], "stage": "done"}
        log("done")
    except Exception as e:  # noqa: BLE001 - shown to the user in the job log
        job["status"], job["error"] = "error", str(e)
        log(f"stopped: {e}")
    finally:
        job["finished"] = _now()
        entry = {k: job[k] for k in ("status", "kind", "started", "finished", "result", "error")}
        path = MODELS_DIR / agent / "history.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([entry] + history(agent), indent=2), encoding="utf-8")
