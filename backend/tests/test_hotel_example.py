"""The demo hotel agent (examples/hotel_agent) with a scripted LLM that follows its rules, no API calls.
Its files are loaded fresh (the travel agent also has agent.py / tasks.py)."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openai.types.chat import ChatCompletion

import blackbox_sdk as bb

HERE = Path(__file__).resolve().parents[2] / "examples" / "hotel_agent"


@pytest.fixture(scope="module")
def hotel():
    saved = {k: sys.modules.pop(k) for k in ("agent", "tasks", "hotels") if k in sys.modules}
    sys.path.insert(0, str(HERE))
    try:
        import agent
        import tasks
        yield agent, tasks
    finally:
        sys.path.remove(str(HERE))
        for k in ("agent", "tasks", "hotels"):
            sys.modules.pop(k, None)
        sys.modules.update(saved)


def completion(calls=None, text=None):
    return ChatCompletion.model_validate({
        "id": "x", "object": "chat.completion", "created": 0, "model": "fake",
        "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop", "message": {
            "role": "assistant", "content": text,
            "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
                           for i, (n, a) in enumerate(calls or [])] or None}}],
    })


class RuleFollowingLLM:
    def __init__(self, task):
        self.task = task
        self.chat = self
        self.completions = self

    def create(self, **kw):
        t = self.task
        results = [json.loads(m["content"]) for m in kw["messages"] if isinstance(m, dict) and m.get("role") == "tool"]
        if not results:
            return completion([("search_hotels", {"city": t["city"]})])
        last = results[-1]
        options = sorted((h for h in results[0]["hotels"] if h["rating"] >= t.get("min_rating", 0)), key=lambda h: h["nightly_rate"])
        checked = [r for r in results if "rooms_left" in r]
        if "hotels" in last or (checked and not last.get("enough", True)):
            return completion([("check_rooms", {"hotel": options[len(checked)]["hotel"], "check_in": t["check_in"], "guests": t["guests"]})])
        if "rooms_left" in last:
            rate = next(h["nightly_rate"] for h in options if h["hotel"] == last["hotel"])
            return completion([("price_stay", {"hotel": last["hotel"], "nightly_rate": rate, "nights": t["nights"], "rooms": last["rooms_needed"]})])
        if "nightly_rate" in last:
            return completion([("book_room", {"hotel": last["hotel"], "check_in": t["check_in"], "nights": t["nights"],
                                              "rooms": last["rooms"], "total": last["total"]})])
        return completion(text="Booked.")


@pytest.mark.parametrize("kind", ["city_break", "family_stay", "luxury_stay", "long_stay", "sold_out_cheapest"])
def test_hotel_agent_books_the_right_stay(kind, hotel, monkeypatch):
    agent, tasks = hotel
    task = tasks.make_task(kind, 2)
    monkeypatch.setattr(agent, "CLIENT", bb.llm(RuleFollowingLLM(task)))
    app = bb.create_app(agent.run_agent, name="hotels", examples=tasks.EXAMPLES, make_task=tasks.make_task, check=agent.check)
    with TestClient(app).stream("POST", "/run", json={"task": task}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    done = next(e["data"] for e in events if e["event"] == "run_done")
    assert done["error"] is None and done["check"]["ok"], done
    names = [e["data"]["step"]["name"] for e in events if e["event"] == "step_done"]
    assert names[:2] == ["llm", "search_hotels"] and names[-2:] == ["book_room", "llm"]
    if kind == "sold_out_cheapest":
        assert names.count("check_rooms") >= 2


def test_hotel_info(hotel):
    agent, tasks = hotel
    info = TestClient(bb.create_app(agent.run_agent, name="hotels", examples=tasks.EXAMPLES, make_task=tasks.make_task,
                                    check=agent.check, llm="groq · test")).get("/info").json()
    assert len(info["kinds"]) == 5 and info["llm"] == "groq · test"
    assert set(agent.TOOLS) <= {t["name"] for t in info["tools"]}
