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
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse

from blackbox import store
from blackbox.adapter import AgentAdapter, EventFn, QuotaExhausted
from blackbox.config import REPORTS_DIR
from blackbox.contract import DiagnoseRequest, Diagnosis, FaultInfo, ReplayRequest, Report, Run, RunRequest
from blackbox.diagnose import diagnose, load_model
from blackbox.injector import live_fault
from blackbox.registry import AGENTS, get_agent
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


class Cancelled(Exception):
    """The browser closed the stream; stop the agent."""


# --- helpers -----------------------------------------------------------------------------------


def _check_name(value: str, what: str) -> str:
    if not NAME.match(value):
        raise HTTPException(400, f"invalid {what}: use letters, digits, '_' and '-' only")
    return value


def _adapter(agent: str) -> AgentAdapter:
    _check_name(agent, "agent")
    if agent not in AGENTS:
        raise HTTPException(404, f"unknown agent '{agent}'")
    return get_agent(agent)


def _load(agent: str, run_id: str) -> dict:
    _adapter(agent)
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
def agents() -> dict[str, list[str]]:
    return {"agents": sorted(AGENTS)}


@app.get("/catalog/{agent}")
def catalog(agent: str) -> dict:
    return _adapter(agent).form_data()


@app.get("/faults/{agent}")
def faults(agent: str) -> list[FaultInfo]:
    """The agent's fault catalogue for the fault picker. `seen` says whether the model trained on it."""
    adapter = _adapter(agent)
    try:
        seen = set(load_model(agent)[2]["seen_fault_types"])
    except FileNotFoundError:
        seen = set()
    return [FaultInfo(type=f.type, family=f.family, step_name=f.step_name, seen=f.type in seen, live=f.family == "tool")
            for f in adapter.faults()]


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
    _adapter(agent)
    path = REPORTS_DIR / agent / "report.json"
    if not path.exists():
        raise HTTPException(404, f"no report for '{agent}': run python -m blackbox.evaluate {agent}")
    return Report.model_validate_json(path.read_text(encoding="utf-8"))
