"""The demo travel agent (examples/travel_agent) with a scripted LLM that follows its rules: the
agent loop, the SDK recording and its check() work, with no API calls."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletion

HERE = Path(__file__).resolve().parents[2] / "examples" / "travel_agent"
sys.path.insert(0, str(HERE))

import blackbox_sdk as bb  # noqa: E402

agent = pytest.importorskip("agent")
tasks = pytest.importorskip("tasks")


def completion(calls=None, text=None):
    return ChatCompletion.model_validate({
        "id": "x", "object": "chat.completion", "created": 0, "model": "fake",
        "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop", "message": {
            "role": "assistant", "content": text,
            "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
                           for i, (n, a) in enumerate(calls or [])] or None}}],
    })


class RuleFollowingLLM:
    """Plays the LLM: reads the task from the request's structured twin and the tool results so far."""

    def __init__(self, task):
        self.task = task
        self.chat = self
        self.completions = self

    def create(self, **kw):
        t = self.task
        results = [json.loads(m["content"]) for m in kw["messages"] if isinstance(m, dict) and m.get("role") == "tool"]
        if not results:
            return completion([("search_flights", {k: t[k] for k in ("origin", "dest", "date", "cabin")})])
        last = results[-1]
        options = sorted(results[0]["flights"], key=lambda f: f["fare"])
        checked = [r for r in results if "seats_left" in r]
        if "flights" in last or (checked and not last.get("enough", True)):
            nxt = options[len(checked)]
            return completion([("check_seats", {"flight": nxt["flight"], "date": t["date"], "cabin": t["cabin"], "passengers": t["passengers"]})])
        if "seats_left" in last:
            fare = next(f["fare"] for f in options if f["flight"] == last["flight"])
            return completion([("price_booking", {"flight": last["flight"], "fare": fare, "passengers": t["passengers"]})])
        if "taxes" in last:
            return completion([("book_flight", {"flight": last["flight"], "date": t["date"], "passengers": t["passengers"],
                                                "cabin": t["cabin"], "total": last["total"]})])
        return completion(text="Booked.")


@pytest.mark.parametrize("kind", tasks.KINDS)
def test_travel_agent_books_the_right_flight(kind, monkeypatch):
    task = tasks.make_task(kind, 3)
    monkeypatch.setattr(agent, "CLIENT", bb.llm(RuleFollowingLLM(task)))
    app = bb.create_app(agent.run_agent, name="travel", examples=tasks.EXAMPLES, make_task=tasks.make_task, check=agent.check)
    with TestClient(app).stream("POST", "/run", json={"task": task}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    done = next(e["data"] for e in events if e["event"] == "run_done")
    assert done["error"] is None and done["check"]["ok"], done
    names = [e["data"]["step"]["name"] for e in events if e["event"] == "step_done"]
    assert names[:2] == ["llm", "search_flights"] and names[-2:] == ["book_flight", "llm"]
    if kind == "tight_seats":
        assert names.count("check_seats") >= 2  # the cheapest flight was too full


def test_info_lists_five_kinds_and_four_tools():
    info = TestClient(bb.create_app(agent.run_agent, name="travel", examples=tasks.EXAMPLES, make_task=tasks.make_task,
                                    check=agent.check)).get("/info").json()
    assert len(info["kinds"]) == 5 and {t["name"] for t in info["tools"] if t["kind"] == "tool"} == set(agent.TOOLS)
