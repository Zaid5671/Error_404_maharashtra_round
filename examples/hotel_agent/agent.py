"""A hotel booking agent: an LLM that searches hotels, checks rooms, prices the stay and books it.

This agent stands for one a team already had. To connect it to the Black Box they added only the
lines marked "# Black Box SDK". Remove those lines and it is an ordinary agent again.

Run it, then connect it in the Black Box app (Agents -> Add agent -> http://127.0.0.1:8101):

    backend\\.venv\\Scripts\\python examples\\hotel_agent\\agent.py

LLM: HOTEL_LLM_PROVIDER=groq (default) or gemini, keys from backend/.env (GROQ_API_KEY / GEMINI_API_KEY).
"""

from __future__ import annotations

import json
import os
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "sdk"))  # Black Box SDK (until it is pip-installed: pip install -e sdk)
sys.path.insert(0, str(HERE))

import openai  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

import blackbox_sdk as bb  # noqa: E402  # Black Box SDK
from hotels import hotels, rooms_left, rooms_needed, solve, total_for  # noqa: E402
from tasks import EXAMPLES, make_task  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")
PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "gemini-3.5-flash-lite"),
}
PROVIDER = os.getenv("HOTEL_LLM_PROVIDER", "groq")
BASE_URL, KEY_NAME, MODEL = PROVIDERS[PROVIDER]
MAX_CALLS = 10

SYSTEM = """You are a hotel booking agent. Use the tools for every step, one at a time:
1. search_hotels for the city. If the guest asks for a minimum rating, ignore hotels rated below it.
2. Take the cheapest remaining hotel and call check_rooms for it. If it doesn't have enough rooms, check the next cheapest, and so on.
3. Call price_stay for the chosen hotel.
4. Call book_room with the total from price_stay, then reply with one short sentence.
Dates are in 2026; write them as YYYY-MM-DD. Two guests share one room."""


# --- the agent's tools ----------------------------------------------------------------------------


@bb.tool  # Black Box SDK
def search_hotels(city: str) -> dict:
    """Hotels in a city with their nightly rate per room and their rating."""
    return {"city": city, "hotels": hotels(city)}


@bb.tool  # Black Box SDK
def check_rooms(hotel: str, check_in: str, guests: int) -> dict:
    """Rooms left at a hotel on a date, and whether there are enough for the guests."""
    left, need = rooms_left(hotel, check_in), rooms_needed(guests)
    return {"hotel": hotel, "rooms_left": left, "rooms_needed": need, "enough": left >= need}


@bb.tool  # Black Box SDK
def price_stay(hotel: str, nightly_rate: int, nights: int, rooms: int) -> dict:
    """The price of a stay: rate x nights x rooms, plus taxes."""
    return {"hotel": hotel, "nightly_rate": nightly_rate, "nights": nights, "rooms": rooms,
            "total": total_for(nightly_rate, nights, rooms)}


@bb.tool  # Black Box SDK
def book_room(hotel: str, check_in: str, nights: int, rooms: int, total: int) -> dict:
    """Book the rooms at the quoted total."""
    ref = zlib.crc32(f"{hotel}|{check_in}|{nights}|{rooms}".encode()) % 10**5
    return {"booking_id": f"HB-{ref:05d}", "status": "confirmed", "hotel": hotel, "rooms": rooms, "nights": nights, "total": total}


TOOLS = {f.__name__: f for f in (search_hotels, check_rooms, price_stay, book_room)}


def _schema(name: str, description: str, props: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": description, "parameters": {
        "type": "object", "required": list(props), "properties": props}}}


SCHEMAS = [
    _schema("search_hotels", "Hotels in a city with nightly rate and rating.", {"city": {"type": "string"}}),
    _schema("check_rooms", "Rooms left at a hotel.", {"hotel": {"type": "string"}, "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                                                      "guests": {"type": "integer"}}),
    _schema("price_stay", "Total price of a stay with taxes.", {"hotel": {"type": "string"}, "nightly_rate": {"type": "integer"},
                                                               "nights": {"type": "integer"}, "rooms": {"type": "integer"}}),
    _schema("book_room", "Book rooms at the quoted total.", {"hotel": {"type": "string"}, "check_in": {"type": "string"},
                                                            "nights": {"type": "integer"}, "rooms": {"type": "integer"}, "total": {"type": "integer"}}),
]


# --- the LLM client (retries rate limits inside one call) -----------------------------------------


class _Retrying:
    def __init__(self, client: openai.OpenAI) -> None:
        self._client = client
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        for attempt in range(8):
            try:
                return self._client.chat.completions.create(**kwargs)
            except openai.RateLimitError as e:
                wait = float(getattr(e, "response", None) and e.response.headers.get("retry-after") or 0) or 5 * (attempt + 1)
                time.sleep(min(wait, 60))
        return self._client.chat.completions.create(**kwargs)


CLIENT = bb.llm(_Retrying(openai.OpenAI(base_url=BASE_URL, api_key=os.getenv(KEY_NAME, "missing"))))  # Black Box SDK: bb.llm(...)


def run_agent(task: dict) -> dict | None:
    """Book the stay the request asks for. Returns what was booked (None if nothing was)."""
    messages: list = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": task["request"]}]
    booked = None
    extra = {"reasoning_effort": "low"} if PROVIDER == "groq" else {}
    for _ in range(MAX_CALLS):
        msg = CLIENT.chat.completions.create(model=MODEL, messages=messages, tools=SCHEMAS, temperature=0, **extra).choices[0].message
        messages.append(msg)
        if not msg.tool_calls:
            break
        for call in msg.tool_calls:
            try:
                out = TOOLS[call.function.name](**json.loads(call.function.arguments or "{}"))
            except (KeyError, TypeError, json.JSONDecodeError) as e:
                out = {"error": f"bad tool call: {e}"}
            if call.function.name == "book_room" and "error" not in out:
                booked = {"hotel": out["hotel"], "rooms": out["rooms"], "nights": out["nights"], "total": out["total"]}
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(out)})
    return booked


def check(task: dict, result: dict | None) -> dict:
    """Did it book the cheapest suitable hotel with enough rooms, at the right total?"""
    expected = solve(task)
    return {"ok": result == expected, "expected": expected}


if __name__ == "__main__":
    bb.serve(run_agent, name="hotels", port=int(os.getenv("HOTEL_PORT", "8101")),  # Black Box SDK
             title="Hotel booking agent", description="Finds hotels, checks rooms, prices the stay and books the cheapest one that fits.",
             examples=EXAMPLES, make_task=make_task, check=check, llm=f"{PROVIDER} · {MODEL}")
