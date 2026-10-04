"""Agents connected by URL: any agent that runs the Black Box SDK (or speaks its small protocol).

One RemoteAdapter implements the normal AgentAdapter by calling the agent over HTTP, so generation,
fault injection, replay, training, diagnosis and the UI work for it unchanged:
  GET  /info  name, tools, kinds of example tasks
  POST /task  a task of one kind (templates = kinds; train/test is split by kind)
  POST /run   runs the agent and streams its steps; with `cached` + `override` it is a resume
              (steps before k come from the recording, step k gets the edit, the rest run live),
              with `fault` it hides a one-value fault in the run (a live "Surprise me")
Whether a run succeeded: the agent's own check() when it has one; otherwise the result is compared
with a reference (the clean run for generated faults, the same run without the fault for live ones).
"""

from __future__ import annotations

import json
import random
from collections.abc import Callable
from typing import Any

import httpx

from blackbox import generic_faults, store
from blackbox.adapter import EventFn, FaultSpec
from blackbox.contract import Run

TIMEOUT = httpx.Timeout(10.0, read=600.0)


class AgentUnreachable(RuntimeError):
    pass


class AgentProtocolError(RuntimeError):
    pass


def _strip_ids(value: Any) -> Any:
    """A result without ID-like fields (booking_id, orderId): new on every run, so not compared."""
    if isinstance(value, dict):
        return {k: _strip_ids(v) for k, v in value.items() if not (k == "id" or k.endswith("_id") or k.endswith("Id"))}
    if isinstance(value, list):
        return [_strip_ids(v) for v in value]
    return value


class RemoteAdapter:
    plants_live_faults = True  # api.py: hidden faults are planted by the agent's SDK, not an output hook

    def __init__(self, name: str, url: str, client: httpx.Client | None = None) -> None:
        self.name = name
        self.url = url.rstrip("/")
        self._client = client
        self._info: dict | None = None

    # --- talking to the agent ------------------------------------------------------------------

    def _http(self) -> httpx.Client:
        if self._client is None:  # one connection pool per agent, shared by all its runs
            self._client = httpx.Client(base_url=self.url, timeout=TIMEOUT)
        return self._client

    def _call(self, method: str, path: str, **kw) -> Any:
        try:
            r = self._http().request(method, path, **kw)
        except httpx.HTTPError as e:
            raise AgentUnreachable(f"agent '{self.name}' is not reachable at {self.url} ({type(e).__name__})") from e
        if r.status_code >= 400:
            raise AgentProtocolError(f"agent '{self.name}' answered {r.status_code} on {path}: {r.text[:200]}")
        return r.json()

    def info(self, fresh: bool = False) -> dict:
        if self._info is None or fresh:
            self._info = self._call("GET", "/info")
        return self._info

    def _stream(self, body: dict, on_event: EventFn | None, first_live: int = 1) -> tuple[list[dict], dict, dict]:
        """POST /run and collect (steps, tapes, run_done). Events of steps before `first_live` are
        not forwarded: those steps are reused from the recording."""
        steps: list[dict] = []
        tapes: dict[int, Any] = {}
        done: dict | None = None
        try:
            with self._http().stream("POST", "/run", json=body, timeout=TIMEOUT) as r:
                if r.status_code >= 400:
                    r.read()
                    raise AgentProtocolError(f"agent '{self.name}' refused the run ({r.status_code}): {r.text[:200]}")
                for line in r.iter_lines():
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    event, data = msg.get("event"), msg.get("data") or {}
                    if event == "step_started":
                        if on_event and data["id"] >= first_live:
                            on_event("step_started", {"id": data["id"], "name": data["name"]})
                    elif event == "step_done":
                        step = data["step"]
                        steps.append(step)
                        if data.get("tape") is not None:
                            tapes[step["id"]] = data["tape"]
                        if on_event and step["id"] >= first_live:
                            on_event("step_done", {"step": step})
                    elif event == "run_done":
                        done = data
                    elif event == "error":
                        raise AgentProtocolError(f"agent '{self.name}' failed: {data.get('message')}")
        except httpx.HTTPError as e:
            raise AgentUnreachable(f"agent '{self.name}' is not reachable at {self.url} ({type(e).__name__})") from e
        if done is None:
            raise AgentProtocolError(f"agent '{self.name}' ended the run without a result")
        return steps, tapes, done

    # --- AgentAdapter ------------------------------------------------------------------------

    def describe(self) -> dict:
        info = self.info()
        return {"title": info.get("title") or self.name, "description": info.get("description", ""),
                "llm": None, "tools": {t["name"]: t.get("description") for t in info.get("tools", [])}}

    def templates(self) -> list[str]:
        return list(self.info().get("kinds") or [])

    def _request_text(self, task: dict) -> str:
        text = task.get(self.info().get("request_key") or "request")
        return text if isinstance(text, str) else json.dumps(task, ensure_ascii=False)

    def make_task(self, template_id: str, seed: int) -> dict:
        task = self._call("POST", "/task", json={"kind": template_id, "seed": seed})["task"]
        return {"template_id": template_id, "seed": seed, "task": task, "request_text": self._request_text(task), "expected": None}

    def task_from_input(self, task: dict) -> dict:
        if not isinstance(task, dict) or not task:
            raise ValueError("the task must be a non-empty JSON object")
        return {"template_id": "live", "seed": None, "task": task, "request_text": self._request_text(task), "expected": None}

    def form_data(self) -> dict:
        info = self.info()
        return {"examples": info.get("examples", []), "request_key": info.get("request_key", "request")}

    def faults(self) -> list[FaultSpec]:
        """Generic faults on the agent's tools, for the kinds of values their outputs really have."""
        tools = {t["name"]: set(generic_faults.KINDS) for t in self.info().get("tools", []) if t.get("kind") == "tool"}
        observed: dict[str, set[str]] = {}
        for path in store.list_runs(self.name)[:40]:
            for step in json.loads(path.read_text(encoding="utf-8"))["steps"]:
                if step["kind"] == "tool" and step["name"] in tools and isinstance(step["output"], dict):
                    observed.setdefault(step["name"], set()).update(generic_faults.kinds_in(step["output"]))
        return generic_faults.specs({t: observed.get(t, kinds) for t, kinds in tools.items()})

    def judge(self, expected: dict | None, actual: dict | None) -> str:
        if expected is None:
            return "success"  # nothing to compare against
        return "success" if _strip_ids(expected) == _strip_ids(actual) else "failure"

    def run(self, task: dict, *, run_id: str, source: str = "generated", on_event: EventFn | None = None,
            output_hook: Callable | None = None, live_fault: str | None = None) -> dict:
        body: dict = {"task": task["task"]}
        if live_fault:
            tool, kind = live_fault.split(":", 1)
            body["fault"] = {"tool": tool, "kind": kind, "seed": random.randrange(10**9)}
        steps, tapes, done = self._stream(body, on_event)
        run = self._build(task, steps, tapes, done, run_id=run_id, source=source, expected=task["expected"])
        if done.get("fault"):
            f = done["fault"]
            run["fault"] = {"type": live_fault, "family": "tool", "step_id": f["step_id"], "detail": f["detail"]}
            if done.get("check") is None:  # no check(): compare with the same run without the fault
                ref = self.resume(run, f["step_id"], run_id=f"{run_id}__ref", new_output=f["original"])
                run["expected"] = ref["actual"]
                run["outcome"] = "failure" if done.get("error") else self.judge(run["expected"], run["actual"])
        elif source == "generated" and done.get("check") is None and not done.get("error"):
            run["expected"] = run["actual"]  # a clean generated run is the reference for its faulted copies
        Run.model_validate(run)
        if on_event:
            on_event("run_done", {k: run[k] for k in ("run_id", "outcome", "actual", "expected")})
        return run

    def resume(self, run: dict, step_id: int, *, run_id: str, source: str = "replay", new_output: dict | None = None,
               new_args: dict | None = None, on_event: EventFn | None = None, output_hook: Callable | None = None) -> dict:
        tapes = {m["step"]: m["tape"] for m in run.get("messages", []) if m.get("role") == "blackbox_tape"}
        cached = [{"name": s["name"], "output": s["output"], "error": s["error"], "llm": s["llm"], "tape": tapes.get(s["id"])}
                  for s in run["steps"][: step_id - 1]]
        edit = new_output if new_output is not None else new_args
        body: dict = {"task": run["task"], "cached": cached}
        if edit is not None:
            body["override"] = {"step": step_id, "output": edit}
        steps, new_tapes, done = self._stream(body, on_event, first_live=step_id)
        task = {"template_id": run["template_id"], "task": run["task"], "request_text": run["request_text"]}
        new = self._build(task, steps, new_tapes, done, run_id=run_id, source=source, expected=run["expected"],
                          parent_run_id=run["run_id"], replayed_from_step=step_id, split=run.get("split"))
        Run.model_validate(new)
        return new

    def _build(self, task: dict, steps: list[dict], tapes: dict, done: dict, *, run_id: str, source: str,
               expected: dict | None, parent_run_id: str | None = None,
               replayed_from_step: int | None = None, split: str | None = None) -> dict:
        check = done.get("check")
        if check and check.get("expected") is not None:
            expected = check["expected"] if isinstance(check["expected"], dict) else {"_result": check["expected"]}
        actual = done.get("result")
        if done.get("error"):
            outcome = "failure"
        elif check is not None:
            outcome = "success" if check["ok"] else "failure"
        else:
            outcome = self.judge(expected, actual)
        return {
            "run_id": run_id, "agent": self.name, "template_id": task["template_id"], "source": source,
            "parent_run_id": parent_run_id, "replayed_from_step": replayed_from_step,
            "task": task["task"], "request_text": task["request_text"],
            "expected": expected, "actual": actual, "outcome": outcome, "fault": None, "split": split,
            "messages": [{"role": "blackbox_tape", "step": sid, "tape": tape} for sid, tape in sorted(tapes.items())],
            "steps": steps,
        }
