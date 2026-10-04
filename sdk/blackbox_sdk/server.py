"""The agent's side of the connection: a small HTTP server the Black Box app talks to.

  GET  /info  -> who the agent is: name, title, its tools, its kinds of example tasks
  POST /task  -> {"kind", "seed"} -> {"task"}: a task to run (for generating training data)
  POST /run   -> {"task", "cached"?, "override"?, "fault"?} -> the run, streamed as JSON lines:
                 step_started, step_done, then run_done {result, check, diverged, fault} (or error)
"""

from __future__ import annotations

import json
import queue
import threading
import traceback
from collections.abc import Callable
from typing import Any

from blackbox_sdk.core import TOOLS, Session, encode, jsonable, run_session

VERSION = "0.1"


def _example_list(examples: list) -> list[dict]:
    out = []
    for e in examples:
        if isinstance(e, dict) and "task" in e and isinstance(e["task"], dict):
            out.append({"kind": str(e.get("kind") or "example"), "task": e["task"]})
        elif isinstance(e, dict):
            out.append({"kind": "example", "task": e})
    return out


def _checked(check: Callable | None, task: dict, result: Any) -> dict | None:
    """The author's check: True/False, or {"ok": bool, "expected": ...}."""
    if check is None:
        return None
    verdict = check(task, result)
    if isinstance(verdict, dict):
        return {"ok": bool(verdict.get("ok")), "expected": jsonable(verdict.get("expected"))}
    return {"ok": bool(verdict), "expected": None}


def create_app(
    agent: Callable[[dict], Any],
    *,
    name: str,
    title: str | None = None,
    description: str = "",
    examples: list | None = None,
    make_task: Callable[[str, int], dict] | None = None,
    check: Callable[[dict, Any], Any] | None = None,
    request_key: str = "request",
    llm: str | None = None,
):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import StreamingResponse

    example_list = _example_list(examples or [])
    kinds = sorted({e["kind"] for e in example_list})
    app = FastAPI(title=f"{name} (Black Box SDK)")

    @app.get("/info")
    def info() -> dict:
        return {
            "name": name, "title": title or name, "description": description,
            "sdk": f"blackbox-sdk {VERSION}", "request_key": request_key,
            "tools": sorted(TOOLS.values(), key=lambda t: (t["kind"] != "llm", t["name"])),
            "kinds": kinds, "examples": example_list, "has_check": check is not None, "llm": llm,
        }

    @app.post("/task")
    def task(body: dict) -> dict:
        kind, seed = str(body.get("kind", "")), int(body.get("seed", 0))
        if make_task is not None:
            return {"task": jsonable(make_task(kind, seed))}
        matching = [e["task"] for e in example_list if e["kind"] == kind]
        if not matching:
            raise HTTPException(404, f"no example tasks of kind '{kind}'")
        return {"task": matching[seed % len(matching)]}

    @app.post("/run")
    def run(body: dict) -> StreamingResponse:
        if not isinstance(body.get("task"), dict):
            raise HTTPException(400, "body.task must be an object")
        lines: queue.Queue = queue.Queue()
        stop = threading.Event()

        def emit(event: str, data: dict) -> None:
            if stop.is_set():
                raise RuntimeError("the Black Box closed the connection")
            lines.put(json.dumps({"event": event, "data": data}, default=str))

        def work() -> None:
            session = Session(emit, body.get("cached"), body.get("override"), body.get("fault"), body["task"])
            try:
                try:
                    result, error = run_session(agent, body["task"], session), None
                except Exception as e:  # noqa: BLE001 - the run still counts: it ended in an error
                    result, error = None, f"{type(e).__name__}: {e}"
                    traceback.print_exc()
                emit("run_done", {
                    "result": None if result is None else encode(result),
                    "error": error,
                    "check": None if error else _checked(check, body["task"], result),
                    "diverged": session.diverged,
                    "fault": session.fault_applied,
                })
            except Exception as e:  # noqa: BLE001
                lines.put(json.dumps({"event": "error", "data": {"message": f"{type(e).__name__}: {e}"}}))
            finally:
                lines.put(None)

        def stream():
            threading.Thread(target=work, daemon=True).start()
            try:
                while (line := lines.get()) is not None:
                    yield line + "\n"
            finally:
                stop.set()

        return StreamingResponse(stream(), media_type="application/x-ndjson")

    return app


def serve(agent: Callable[[dict], Any], *, name: str, port: int = 8100, host: str = "127.0.0.1", **kwargs: Any) -> None:
    """Start the agent's Black Box server, then connect it in the app (Agents -> Connect agent)."""
    import uvicorn

    print(f"Black Box SDK: agent '{name}' is ready. In the app: Agents -> Connect agent -> http://{host}:{port}")
    uvicorn.run(create_app(agent, name=name, **kwargs), host=host, port=port, log_level="warning")
