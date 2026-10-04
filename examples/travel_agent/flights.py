"""Mock flight data and the booking rule, all deterministic (no network): the "airline system" the
travel agent's tools talk to, plus the correct answer for any task (used by check())."""

from __future__ import annotations

import random

CITIES = {"BOM": "Mumbai", "DEL": "Delhi", "BLR": "Bengaluru", "GOI": "Goa", "MAA": "Chennai", "CCU": "Kolkata", "HYD": "Hyderabad"}
AIRLINES = ["AI", "6E", "UK", "SG", "QP"]
TAX_RATE = 0.12  # per passenger, on the fare


def flights(origin: str, dest: str, cabin: str) -> list[dict]:
    """The day's flights on a route, in no particular order. Same route -> same flights."""
    rng = random.Random(f"{origin}-{dest}")
    out = []
    for _ in range(3):
        code = f"{rng.choice(AIRLINES)} {rng.randint(100, 999)}"
        economy = rng.randrange(3000, 9000, 50)
        out.append({"flight": code, "depart": f"{rng.randint(5, 22):02d}:{rng.choice(['00', '15', '30', '45'])}",
                    "fare": economy if cabin == "economy" else int(round(economy * 3.2, -1))})
    return out


def seats_left(flight: str, date: str, cabin: str) -> int:
    return random.Random(f"{flight}|{date}|{cabin}").randint(0, 9)


def taxes(fare: int) -> int:
    return round(fare * TAX_RATE)


def solve(task: dict) -> dict | None:
    """The right booking: the cheapest flight in the cabin with enough seats; None if none has."""
    options = sorted(flights(task["origin"], task["dest"], task["cabin"]), key=lambda f: f["fare"])
    for f in options:
        if seats_left(f["flight"], task["date"], task["cabin"]) >= task["passengers"]:
            return {"flight": f["flight"], "passengers": task["passengers"],
                    "total": (f["fare"] + taxes(f["fare"])) * task["passengers"]}
    return None
