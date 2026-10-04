"""Recording, record-and-replay and live faults for one agent run.

Every call to a wrapped tool or LLM client inside a run becomes one step in the Black Box trace
format. A run can be given:
  - cached:   the recorded steps 1..k-1 of an earlier run. Those calls return their saved outputs
              instantly (no LLM or tool call), so the agent rebuilds its own state by itself.
  - override: {"step": k, "output": {...}}. Call k returns this output instead of running.
  - fault:    {"tool": name, "kind": "number" | "flag" | "text", "seed": n}. The first live call of
              that tool whose output has a value of that kind gets one value changed (a hidden fault).
After step k everything runs live. If the agent makes a different call than the recording at some
step, the cache is dropped from there on and the run is marked "diverged".
"""

from __future__ import annotations

import contextvars
import functools
import inspect
import json
import time
from collections.abc import Callable
from typing import Any

from blackbox_sdk.mutate import mutate, strings_by_field

TOOLS: dict[str, dict] = {}  # name -> {"name", "kind", "description"}, filled by @tool
_current: contextvars.ContextVar[Session | None] = contextvars.ContextVar("blackbox_session", default=None)

WRAP = "_result"  # key used when a tool returns something that isn't a dict


def jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def encode(value: Any) -> dict:
    value = jsonable(value)
    return value if isinstance(value, dict) else {WRAP: value}


def decode(output: dict) -> Any:
    return output[WRAP] if set(output) == {WRAP} else output


def _scalars(obj: Any) -> set:
    """Values worth matching between steps: strings of 2+ chars and numbers other than 0 and 1."""
    out: set = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= _scalars(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= _scalars(v)
    elif isinstance(obj, str) and len(obj.strip()) >= 2:
        out.add(obj.strip().lower())
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool) and obj not in (0, 1):
        out.add(float(obj))
    return out


class Session:
    def __init__(
        self,
        emit: Callable[[str, dict], None],
        cached: list[dict] | None = None,
        override: dict | None = None,
        fault: dict | None = None,
    ) -> None:
        self.emit = emit
        self.cached = cached or []
        self.override = override
        self.fault = dict(fault) if fault else None
        self.fault_applied: dict | None = None
        self.diverged = False
        self.steps: list[dict] = []
        self.tapes: dict[int, Any] = {}  # step id -> raw LLM response, so a replay can rebuild it exactly
        self.state: dict[str, Any] = {}  # step name -> its latest output
        self.last_writer: dict[str, int] = {}
        self.tools_since_llm: list[str] = []
        self.turn = 0

    # --- the one place a call becomes a step ---------------------------------------------------

    def step(self, kind: str, name: str, step_input: dict, live: Callable[[], Any],
             to_output: Callable[[Any], dict] = encode, from_output: Callable[[dict], Any] = decode,
             tape: Callable[[Any], Any] | None = None, from_tape: Callable[[Any], Any] | None = None) -> Any:
        step_id = len(self.steps) + 1
        self.emit("step_started", {"id": step_id, "name": name})
        saved = self.cached[step_id - 1] if step_id <= len(self.cached) and not self.diverged else None
        if saved is not None and saved.get("name") != name:
            self.diverged, saved = True, None
        forced = self.override if self.override and self.override.get("step") == step_id else None

        error: str | None = None
        llm_stats: dict | None = None
        raw: Any = None
        started = time.perf_counter()
        if forced is not None:
            output = forced["output"]
            value = from_output(output)
        elif saved is not None:
            output, error, raw = saved["output"], saved.get("error"), saved.get("tape")
            value = from_tape(raw) if raw is not None and from_tape else from_output(output)
            llm_stats = saved.get("llm")
        else:
            try:
                value = live()
                output = to_output(value)
                raw = tape(value) if tape else None
            except Exception as e:  # the agent sees its own exception after we record it
                error, output, value = f"{type(e).__name__}: {e}", {"error": f"{type(e).__name__}: {e}"}, e
            if kind == "llm" and error is None:
                usage = getattr(value, "usage", None)
                llm_stats = {
                    "latency_ms": int((time.perf_counter() - started) * 1000),
                    "tokens_in": int(getattr(usage, "prompt_tokens", 0) or 0),
                    "tokens_out": int(getattr(usage, "completion_tokens", 0) or 0),
                }
            if kind == "tool" and error is None and self.fault and not self.fault_applied and self.fault["tool"] == name:
                strings = strings_by_field([s["output"] for s in self.steps if s["kind"] == "tool"] + [output])
                change = mutate(output, self.fault["kind"], self.fault.get("seed", 0), strings)
                if change:
                    output, detail = change
                    self.fault_applied = {"step_id": step_id, "detail": detail, "original": encode(value)}
                    value = from_output(output)
        latency = int((time.perf_counter() - started) * 1000)

        reads, uses = self._links(kind, step_input)
        writes = [] if error else [name]
        if not error:
            self.state[name] = output
            self.last_writer[name] = step_id
        step = {
            "id": step_id, "kind": kind, "name": name,
            "input": jsonable(step_input), "output": output,
            "reads": reads, "writes": writes, "uses": uses,
            "llm": llm_stats if kind == "llm" else None,
            "tool_latency_ms": 0 if kind == "llm" else latency,
            "error": error,
            "state_after": jsonable(self.state),
            "msg_index": 0,
        }
        self.steps.append(step)
        if raw is not None:
            self.tapes[step_id] = raw
        if kind == "llm":
            self.turn += 1
            self.tools_since_llm = []
        else:
            self.tools_since_llm.append(name)
        self.emit("step_done", {"step": step, "tape": raw})
        if error:
            if isinstance(value, Exception):
                raise value
            raise RuntimeError(error)
        return value

    def _links(self, kind: str, step_input: dict) -> tuple[list[str], list[int]]:
        """Which earlier steps this one used. An LLM call reads the tool results that came back
        since the previous LLM call; a tool call reads the LLM call that asked for it, plus any
        earlier tool whose output contains one of its input values."""
        if kind == "llm":
            reads = list(dict.fromkeys(self.tools_since_llm)) or (["llm"] if "llm" in self.last_writer else [])
        else:
            wanted = _scalars(step_input)
            reads = ["llm"] if "llm" in self.last_writer else []
            for name, output in self.state.items():
                if name != "llm" and wanted & _scalars(output):
                    reads.append(name)
        uses = sorted({self.last_writer[k] for k in reads if k in self.last_writer})
        return reads, uses



# --- wrappers the agent's author uses -------------------------------------------------------------


def tool(fn: Callable | None = None, *, name: str | None = None, description: str | None = None):
    """Decorator: record every call of this tool as a step. Use as @tool or @tool(name=...)."""

    def wrap(f: Callable) -> Callable:
        tool_name = name or f.__name__
        doc = description or (inspect.getdoc(f) or "").split("\n")[0]
        TOOLS[tool_name] = {"name": tool_name, "kind": "tool", "description": doc}
        sig = inspect.signature(f)

        @functools.wraps(f)
        def inner(*args, **kwargs):
            session = _current.get()
            if session is None:
                return f(*args, **kwargs)
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            step_input = {k: v for k, v in bound.arguments.items() if k not in ("self", "cls")}
            return session.step("tool", tool_name, step_input, lambda: f(*args, **kwargs))

        return inner

    return wrap(fn) if fn is not None else wrap


def _llm_output(resp: Any) -> dict:
    msg = resp.choices[0].message
    calls = []
    for tc in msg.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {"_raw": tc.function.arguments}
        calls.append({"id": tc.id, "tool": tc.function.name, "args": args})
    return {"text": msg.content or "", "calls": calls}


def _llm_from_output(output: dict, model: str) -> Any:
    from openai.types.chat import ChatCompletion

    calls = output.get("calls") or []
    return ChatCompletion.model_validate({
        "id": "blackbox-replay", "object": "chat.completion", "created": 0, "model": model,
        "choices": [{
            "index": 0, "finish_reason": "tool_calls" if calls else "stop",
            "message": {
                "role": "assistant", "content": output.get("text") or None,
                "tool_calls": [
                    {"id": c.get("id") or f"call_{i}", "type": "function",
                     "function": {"name": c["tool"], "arguments": json.dumps(c.get("args", {}))}}
                    for i, c in enumerate(calls)
                ] or None,
            },
        }],
    })


def _llm_from_tape(raw: Any) -> Any:
    from openai.types.chat import ChatCompletion

    return ChatCompletion.model_validate(raw)


class _Completions:
    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, **kwargs: Any) -> Any:
        session = _current.get()
        if session is None:
            return self._client.chat.completions.create(**kwargs)
        model = kwargs.get("model", "")
        return session.step(
            "llm", "llm", {"turn": session.turn + 1},
            live=lambda: self._client.chat.completions.create(**kwargs),
            to_output=_llm_output,
            from_output=lambda out: _llm_from_output(out, model),
            tape=lambda resp: resp.model_dump(mode="json"),
            from_tape=_llm_from_tape,
        )


class _Chat:
    def __init__(self, client: Any) -> None:
        self.completions = _Completions(client)


class llm:  # noqa: N801 - used like a function: client = bb.llm(OpenAI(...))
    """Wrap an OpenAI-compatible client: every chat.completions.create call is recorded as a step."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.chat = _Chat(client)
        TOOLS.setdefault("llm", {"name": "llm", "kind": "llm", "description": "The LLM decides what to do next"})

    def __getattr__(self, attr: str) -> Any:
        return getattr(self._client, attr)


def run_session(agent_fn: Callable[[dict], Any], task: dict, session: Session) -> Any:
    """Run the agent on a task with this session recording (and replaying) its calls."""
    token = _current.set(session)
    try:
        return agent_fn(task)
    finally:
        _current.reset(token)
