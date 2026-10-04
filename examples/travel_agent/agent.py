"""A flight booking agent built with the Black Box SDK: an LLM that calls four tools.

Run it, then connect it in the Black Box app (Agents -> Connect agent -> http://127.0.0.1:8100):

    backend\\.venv\\Scripts\\python examples\\travel_agent\\agent.py

LLM: TRAVEL_LLM_PROVIDER=groq (default) or gemini, keys from backend/.env (GROQ_API_KEY / GEMINI_API_KEY).
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
sys.path.insert(0, str(ROOT / "sdk"))  # until the SDK is pip-installed (pip install -e sdk)
sys.path.insert(0, str(HERE))

import openai  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

import blackbox_sdk as bb  # noqa: E402
from flights import flights, seats_left, solve, taxes  # noqa: E402
from tasks import EXAMPLES, make_task  # noqa: E402

load_dotenv(ROOT / "backend" / ".env")
PROVIDERS = {
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/", "GEMINI_API_KEY", "gemini-3.5-flash-lite"),
}
PROVIDER = os.getenv("TRAVEL_LLM_PROVIDER", "groq")
BASE_URL, KEY_NAME, MODEL = PROVIDERS[PROVIDER]
MAX_CALLS = 10

SYSTEM = """You are a flight booking agent. Use the tools for every step, one at a time:
1. search_flights for the requested route, date and cabin.
2. Take the cheapest flight and call check_seats for it. If it doesn't have enough seats, check the next cheapest, and so on.
3. Call price_booking for the chosen flight.
4. Call book_flight with the total from price_booking, then reply with one short sentence.
Cities: Mumbai BOM, Delhi DEL, Bengaluru BLR, Goa GOI, Chennai MAA, Kolkata CCU, Hyderabad HYD.
Dates are in 2026; write them as YYYY-MM-DD. Cabin is "economy" unless the traveller asks for business."""


# --- the tools: each call is recorded by the Black Box SDK -----------------------------------------


@bb.tool
def search_flights(origin: str, dest: str, date: str, cabin: str) -> dict:
    """Flights on a route and date, with their fares for the cabin."""
    return {"origin": origin, "dest": dest, "date": date, "cabin": cabin, "flights": flights(origin, dest, cabin)}


@bb.tool
def check_seats(flight: str, date: str, cabin: str, passengers: int) -> dict:
    """How many seats are left on a flight, and whether there are enough."""
    left = seats_left(flight, date, cabin)
    return {"flight": flight, "seats_left": left, "enough": left >= passengers}


@bb.tool
def price_booking(flight: str, fare: int, passengers: int) -> dict:
    """The price of a booking: fare plus taxes, per passenger, times passengers."""
    tax = taxes(fare)
    return {"flight": flight, "fare": fare, "taxes": tax, "passengers": passengers, "total": (fare + tax) * passengers}


@bb.tool
def book_flight(flight: str, date: str, passengers: int, cabin: str, total: int) -> dict:
    """Book the flight at the quoted total."""
    return {"booking_id": f"PNR-{zlib.crc32(f'{flight}|{date}|{passengers}'.encode()) % 10**5:05d}", "status": "confirmed",
            "flight": flight, "passengers": passengers, "total": total}


TOOLS = {f.__name__: f for f in (search_flights, check_seats, price_booking, book_flight)}
SCHEMAS = [
    {"type": "function", "function": {"name": "search_flights", "description": "Flights on a route and date with fares.", "parameters": {
        "type": "object", "required": ["origin", "dest", "date", "cabin"], "properties": {
            "origin": {"type": "string", "description": "city code, e.g. BOM"}, "dest": {"type": "string"},
            "date": {"type": "string", "description": "YYYY-MM-DD"}, "cabin": {"type": "string", "enum": ["economy", "business"]}}}}},
    {"type": "function", "function": {"name": "check_seats", "description": "Seats left on a flight.", "parameters": {
        "type": "object", "required": ["flight", "date", "cabin", "passengers"], "properties": {
            "flight": {"type": "string"}, "date": {"type": "string"}, "cabin": {"type": "string"}, "passengers": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "price_booking", "description": "Total price with taxes.", "parameters": {
        "type": "object", "required": ["flight", "fare", "passengers"], "properties": {
            "flight": {"type": "string"}, "fare": {"type": "integer"}, "passengers": {"type": "integer"}}}}},
    {"type": "function", "function": {"name": "book_flight", "description": "Book the flight at the quoted total.", "parameters": {
        "type": "object", "required": ["flight", "date", "passengers", "cabin", "total"], "properties": {
            "flight": {"type": "string"}, "date": {"type": "string"}, "passengers": {"type": "integer"},
            "cabin": {"type": "string"}, "total": {"type": "integer"}}}}},
]


# --- the LLM: a client that waits and retries on rate limits, recorded by the SDK ------------------


class _Retrying:
    """Retries 429s inside one call, so a rate limit never shows up as a failed step."""

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


CLIENT = bb.llm(_Retrying(openai.OpenAI(base_url=BASE_URL, api_key=os.getenv(KEY_NAME, "missing"))))


def run_agent(task: dict) -> dict | None:
    """Book the flight the request asks for. Returns what was booked (None if nothing was)."""
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
            if call.function.name == "book_flight" and "error" not in out:
                booked = {"flight": out["flight"], "passengers": out["passengers"], "total": out["total"]}
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(out)})
    return booked


def check(task: dict, result: dict | None) -> dict:
    """The agent's own correctness check: did it book the cheapest flight with enough seats, at the right total?"""
    expected = solve(task)
    return {"ok": result == expected, "expected": expected}


if __name__ == "__main__":
    bb.serve(run_agent, name="travel", port=int(os.getenv("TRAVEL_PORT", "8100")), title="Flight booking agent",
             description="Finds flights, checks seats, prices and books the cheapest one that fits.",
             examples=EXAMPLES, make_task=make_task, check=check)
