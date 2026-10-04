"""A tiny flight agent built with the Black Box SDK and a scripted fake LLM (no API calls).

Used by the SDK tests and the remote-agent tests. The fake LLM searches, books the cheapest
flight for the requested number of people, then answers.
"""

import json

from openai.types.chat import ChatCompletion

import blackbox_sdk as bb

CALLS = {"llm": 0}  # how many real (non-replayed) LLM calls were made


def _completion(text: str | None = None, calls: list[tuple[str, dict]] | None = None) -> ChatCompletion:
    return ChatCompletion.model_validate({
        "id": "fake", "object": "chat.completion", "created": 0, "model": "fake",
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
        "choices": [{"index": 0, "finish_reason": "tool_calls" if calls else "stop", "message": {
            "role": "assistant", "content": text,
            "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
                           for i, (n, a) in enumerate(calls or [])] or None,
        }}],
    })


class FakeChat:
    def __init__(self) -> None:
        self.completions = self

    def create(self, **kw):
        CALLS["llm"] += 1
        msgs = kw["messages"]
        tool_msgs = [json.loads(m["content"]) for m in msgs if isinstance(m, dict) and m.get("role") == "tool"]
        task = json.loads(msgs[0]["content"])
        if not tool_msgs:
            return _completion(calls=[("search_flights", {"dest": task["dest"]})])
        if len(tool_msgs) == 1:
            best = min(tool_msgs[0]["flights"], key=lambda f: f["fare"])
            return _completion(calls=[("book_flight", {"flight": best["flight"], "fare": best["fare"], "people": task["people"]})])
        return _completion(text=f"Booked {tool_msgs[-1]['flight']}")


class FakeClient:
    chat = FakeChat()


CLIENT = bb.llm(FakeClient())  # created once, like a real agent's client


FARES = {"GOA": [("AI 1", 100), ("6E 2", 80)], "DEL": [("UK 3", 60), ("AI 4", 90)]}


@bb.tool
def search_flights(dest: str) -> dict:
    """Flights to a city with their fares."""
    return {"flights": [{"flight": f, "fare": fare, "seats_ok": True} for f, fare in FARES[dest]]}


@bb.tool
def book_flight(flight: str, fare: int, people: int) -> dict:
    """Book a flight."""
    return {"booking_id": f"PNR-{flight}", "flight": flight, "total": fare * people}


TOOLS = {"search_flights": search_flights, "book_flight": book_flight}


def run_agent(task: dict) -> dict:
    client = CLIENT
    messages: list = [{"role": "user", "content": json.dumps(task)}]
    for _ in range(6):
        msg = client.chat.completions.create(model="fake", messages=messages).choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            break
        for call in msg.tool_calls:
            out = TOOLS[call.function.name](**json.loads(call.function.arguments))
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(out)})
    return {"flight": out["flight"], "total": out["total"]}


def check(task: dict, result: dict) -> dict:
    flight, fare = min(FARES[task["dest"]], key=lambda f: f[1])
    expected = {"flight": flight, "total": fare * task["people"]}
    return {"ok": result == expected, "expected": expected}


EXAMPLES = [
    {"kind": "goa_trip", "task": {"request": "2 people to Goa", "dest": "GOA", "people": 2}},
    {"kind": "goa_trip", "task": {"request": "3 people to Goa", "dest": "GOA", "people": 3}},
    {"kind": "delhi_trip", "task": {"request": "1 person to Delhi", "dest": "DEL", "people": 1}},
    {"kind": "delhi_trip", "task": {"request": "4 people to Delhi", "dest": "DEL", "people": 4}},
    {"kind": "family_goa", "task": {"request": "5 people to Goa", "dest": "GOA", "people": 5}},
    {"kind": "solo_delhi", "task": {"request": "just me to Delhi", "dest": "DEL", "people": 1}},
]


def make_app():
    return bb.create_app(run_agent, name="minitravel", title="Mini travel agent", description="Books the cheapest flight",
                         examples=EXAMPLES, check=check)
