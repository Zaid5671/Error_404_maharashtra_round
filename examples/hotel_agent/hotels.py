"""Mock hotel data and the booking rule, all deterministic (no network): the "hotel system" the
hotel agent's tools talk to, plus the correct booking for any task (used by check())."""

from __future__ import annotations

import math
import random

CITIES = ["Mumbai", "Delhi", "Bengaluru", "Goa", "Jaipur", "Udaipur", "Kochi"]
NAMES = ["Grand", "Palm", "Lotus", "Harbour", "Heritage", "Sapphire", "Orchid", "Royal", "Sunrise", "Coral"]
KINDS_OF_HOTEL = ["Inn", "Residency", "Resort", "Suites", "Hotel"]
TAX_RATE = 0.12  # on the room charge


def hotels(city: str) -> list[dict]:
    """The hotels in a city with their nightly rate (per room) and rating. Same city -> same hotels."""
    rng = random.Random(city)
    out = []
    for _ in range(4):
        out.append({"hotel": f"{rng.choice(NAMES)} {rng.choice(KINDS_OF_HOTEL)} {city}",
                    "nightly_rate": rng.randrange(1800, 9000, 100), "rating": round(rng.uniform(3.4, 4.9), 1)})
    return out


def rooms_needed(guests: int) -> int:
    return math.ceil(guests / 2)


def rooms_left(hotel: str, check_in: str) -> int:
    return random.Random(f"{hotel}|{check_in}").randint(0, 4)


def total_for(rate: int, nights: int, rooms: int) -> int:
    charge = rate * nights * rooms
    return charge + round(charge * TAX_RATE)


def solve(task: dict) -> dict | None:
    """The right booking: the cheapest hotel rated at least min_rating with enough rooms."""
    need = rooms_needed(task["guests"])
    options = sorted((h for h in hotels(task["city"]) if h["rating"] >= task.get("min_rating", 0)), key=lambda h: h["nightly_rate"])
    for h in options:
        if rooms_left(h["hotel"], task["check_in"]) >= need:
            return {"hotel": h["hotel"], "rooms": need, "nights": task["nights"],
                    "total": total_for(h["nightly_rate"], task["nights"], need)}
    return None
