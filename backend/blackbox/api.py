"""FastAPI app: the endpoints in plan.md section 6.

Start it from backend/:  .venv\\Scripts\\python -m uvicorn blackbox.api:app --port 8000

/run and /replay stream SSE events. The agent is ordinary blocking code, so it runs in a worker
thread that pushes events into a queue the response reads. If the browser goes away, the next
event the agent emits raises Cancelled inside it, so it stops spending LLM calls. run_done is held
back until the run is saved, so the run can be fetched as soon as the browser hears it finished.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import threading
import uuid
from collections.abc import Callable

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse

from blackbox import store
from blackbox.adapter import AgentAdapter, EventFn, QuotaExhausted
from blackbox.config import REPORTS_DIR
from blackbox.contract import DiagnoseRequest, Diagnosis, FaultInfo, ReplayRequest, Report, Run, RunRequest
from blackbox.diagnose import diagnose, load_model
from blackbox.injector import live_fault
from blackbox import importer, index, jobs, registry
from blackbox.registry import get_agent
from blackbox.replay import ReplayError, check_edit, new_replay_id, replay

log = logging.getLogger("blackbox.api")
NAME = re.compile(r"^[A-Za-z0-9_-]{1,160}$")  # agent names and run ids; they become file paths
RNG: Callable[[], random.Random] = random.Random  # surprise-mode randomness (tests seed it)

app = FastAPI(title="Black Box")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _warm_caches() -> None:
    threading.Thread(target=index.warm, args=([a["name"] for a in registry.all_agents()],), daemon=True).start()


class Cancelled(Exception):
    """The browser closed the stream; stop the agent."""


# --- helpers -----------------------------------------------------------------------------------


def _check_name(value: str, what: str) -> str:
    if not NAME.match(value):
        raise HTTPException(400, f"invalid {what}: use letters, digits, '_' and '-' only")
    return value


def _known(agent: str) -> str:
    """Any agent, connected or imported."""
    _check_name(agent, "agent")
    if not registry.exists(agent):
        raise HTTPException(404, f"unknown agent '{agent}'")
    return agent


def _adapter(agent: str) -> AgentAdapter:
    """A connected agent's adapter: needed to run, inject faults or replay."""
    _known(agent)
    if not registry.is_connected(agent):
        raise HTTPException(400, f"'{agent}' is an imported agent: it runs outside the app, so it can't be run or replayed here")
    return get_agent(agent)


def _load(agent: str, run_id: str) -> dict:
    _known(agent)
    _check_name(run_id, "run id")
    if not store.run_path(agent, run_id).exists():
        raise HTTPException(404, f"no run '{run_id}' for agent '{agent}'")
    return store.load_run(agent, run_id)


def _stream(work: Callable[[EventFn], dict]) -> EventSourceResponse:
    """Run `work(on_event)` in a thread and stream its events. `work` returns the saved run."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stop = threading.Event()

    def emit(event: str | None, data: dict | None) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, (event, data))

    def on_event(event: str, data: dict) -> None:
        if stop.is_set():
            raise Cancelled
        if event != "run_done":  # sent by the worker once the run is saved
            emit(event, data)

    def worker() -> None:
        try:
            run = work(on_event)
            emit("run_done", {k: run[k] for k in ("run_id", "outcome", "actual", "expected")})
        except Cancelled:
            log.info("stream closed by the client; agent stopped")
        except QuotaExhausted:
            emit("error", {"message": "The LLM provider's daily quota is used up. Try again later or switch provider."})
        except Exception as e:  # noqa: BLE001 - any agent failure becomes an error event
            log.exception("run failed")
            emit("error", {"message": f"The run failed: {type(e).__name__}: {e}"})
        finally:
            emit(None, None)

    async def events():
        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                event, data = await queue.get()
                if event is None:
                    break
                yield {"event": event, "data": json.dumps(data, ensure_ascii=False)}
        finally:
            stop.set()

    return EventSourceResponse(events())


# --- endpoints ---------------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agents")
def agents() -> dict:
    items = registry.all_agents()
    return {"agents": [a["name"] for a in items], "items": items}


class NewAgent(BaseModel):
    name: str
    title: str = ""
    description: str = ""


@app.post("/agents")
def add_agent(body: NewAgent) -> dict:
    try:
        return registry.add_imported(body.name, body.title, body.description)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/agent/{agent}")
def agent_details(agent: str) -> dict:
    """What the Agents page shows: kind, the agent's own description (connected agents), the tools
    seen in its runs, its templates and train/test split, and its trained model."""
    _known(agent)
    connected = registry.is_connected(agent)
    adapter = get_agent(agent) if connected else None
    info = getattr(adapter, "describe", lambda: {})() if adapter else {}
    meta = None
    try:
        meta = load_model(agent)[2]
    except FileNotFoundError:
        pass
    base = next(a for a in registry.all_agents() if a["name"] == agent)
    descriptions = info.get("tools", {})
    tools = [{**t, "description": descriptions.get(t["name"])} for t in index.tool_usage(agent)]
    data = index.dataset(agent, adapter.templates() if adapter else [])
    return {**base, "llm": info.get("llm"), "tools": tools, "templates": data["templates"],
            "model": meta, "can_run": connected, "n_runs": len(index.summaries(agent)), "n_dataset_runs": data["total"]}


@app.get("/runs/{agent}")
def list_runs(agent: str, source: str = "app", outcome: str | None = None, q: str | None = None,
              sort: str = "recent", limit: int = 50, offset: int = 0) -> dict:
    """Saved runs as table rows. source: app (live + replay), all, generated, imported, live, replay."""
    _known(agent)
    if source not in ("app", "all", "generated", "imported", "live", "replay") or sort not in ("recent", "suspicion"):
        raise HTTPException(400, "unknown source or sort")
    return index.list_runs(agent, source=source, outcome=outcome, q=q, sort=sort, limit=min(limit, 200), offset=offset)


@app.get("/overview/{agent}")
def overview(agent: str, scope: str = "app") -> dict:
    return index.overview(_known(agent), "all" if scope == "all" else "app")


@app.get("/replays/{agent}")
def replays(agent: str) -> list[dict]:
    return index.replays(_known(agent))


@app.get("/dataset/{agent}")
def dataset(agent: str) -> dict:
    _known(agent)
    return index.dataset(agent, get_agent(agent).templates() if registry.is_connected(agent) else [])


class ImportBody(BaseModel):
    runs: list = Field(max_length=5000)
    names: list[str] | None = None  # where each run came from (file names), for error messages


@app.post("/import/{agent}")
def import_runs(agent: str, body: ImportBody) -> dict:
    return importer.import_runs(_known(agent), body.runs, body.names)


@app.post("/train/{agent}")
def start_training(agent: str) -> dict:
    try:
        return jobs.start(_known(agent))
    except RuntimeError as e:
        raise HTTPException(409, str(e)) from e


@app.get("/train/{agent}")
def training_status(agent: str) -> dict:
    return jobs.status(_known(agent))


@app.get("/catalog/{agent}")
def catalog(agent: str) -> dict:
    return _adapter(agent).form_data()


@app.get("/faults/{agent}")
def faults(agent: str) -> list[FaultInfo]:
    """The agent's fault catalogue for the fault picker. `seen` says whether the model trained on it."""
    _known(agent)
    try:
        seen = set(load_model(agent)[2]["seen_fault_types"])
    except FileNotFoundError:
        seen = set()
    if registry.is_connected(agent):
        return [FaultInfo(type=f.type, family=f.family, step_name=f.step_name, seen=f.type in seen, live=f.family == "tool")
                for f in get_agent(agent).faults()]
    # an imported agent's faults are the labels found in its runs; none can be hidden live
    found = {(r["fault_type"], r["fault_family"]) for r in index.summaries(agent) if r["fault_type"]}
    return [FaultInfo(type=t, family=fam, step_name="", seen=t in seen, live=False) for t, fam in sorted(found)]


@app.post("/run")
async def run(body: RunRequest) -> EventSourceResponse:
    adapter = _adapter(body.agent)
    try:
        task = adapter.task_from_input(body.task)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    if body.fault_type is not None:
        live = {f.type for f in adapter.faults() if f.family == "tool"}
        if body.fault_mode != "surprise" or body.fault_type not in live:
            raise HTTPException(400, f"'{body.fault_type}' can't be hidden in a live run; choose one of {sorted(live)}")
    run_id = f"live_{uuid.uuid4().hex[:8]}"

    def work(on_event: EventFn) -> dict:
        on_event("run_started", {"run_id": run_id, "agent": body.agent, "task": task["task"],
                                 "request_text": task["request_text"]})
        steps: list[dict] = []
        hook, fault = (live_fault(adapter, task, steps, RNG(), fault_type=body.fault_type)
                       if body.fault_mode == "surprise" else (None, {}))

        def track(event: str, data: dict) -> None:
            if event == "step_done":
                steps.append(data["step"])
            on_event(event, data)

        result = adapter.run(task, run_id=run_id, source="live", on_event=track, output_hook=hook)
        result["fault"] = dict(fault) or None
        store.save_run(result)
        return result

    return _stream(work)


@app.post("/replay")
async def replay_run(body: ReplayRequest) -> EventSourceResponse:
    original = _load(body.agent, body.run_id)
    try:
        check_edit(original, body.step_id, body.new_output)
    except ReplayError as e:
        raise HTTPException(400, str(e)) from e
    new_id = new_replay_id(body.run_id)

    def work(on_event: EventFn) -> dict:
        on_event("run_started", {"run_id": new_id, "agent": body.agent, "task": original["task"],
                                 "request_text": original["request_text"]})
        return replay(body.agent, body.run_id, body.step_id, body.new_output, on_event, new_run_id=new_id)

    return _stream(work)


@app.post("/diagnose")
def diagnose_run(body: DiagnoseRequest) -> Diagnosis:
    run_ = _load(body.agent, body.run_id)
    try:
        return diagnose(body.agent, run_)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/runs/{agent}/{run_id}")
def get_run(agent: str, run_id: str) -> Run:
    return Run.model_validate(_load(agent, run_id))


@app.get("/report/{agent}")
def report(agent: str) -> Report:
    _known(agent)
    path = REPORTS_DIR / agent / "report.json"
    if not path.exists():
        raise HTTPException(404, f"no report for '{agent}': run python -m blackbox.evaluate {agent}")
    return Report.model_validate_json(path.read_text(encoding="utf-8"))
