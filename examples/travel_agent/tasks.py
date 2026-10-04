"""Kinds of booking requests and how to make one from a seed (for the Black Box's generated data)."""

from __future__ import annotations

import random

from flights import CITIES, flights, seats_left, solve

KINDS = ["solo_economy", "family_economy", "business_trip", "tight_seats", "weekend_pair"]
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
MONTHS = {11: "Nov", 12: "Dec"}


def _date(rng: random.Random) -> tuple[str, str]:
    month, day = rng.choice([11, 12]), rng.randint(1, 28)
    return f"2026-{month:02d}-{day:02d}", f"{day} {MONTHS[month]}"


def _people(n: int, rng: random.Random) -> str:
    if n == 1:
        return rng.choice(["just me", "1 adult", "one person"])
    return rng.choice([f"{n} adults", f"{WORDS[n]} people", f"{n} passengers"])


def make_task(kind: str, seed: int) -> dict:
    rng = random.Random(f"{kind}:{seed}")
    for _ in range(500):
        origin, dest = rng.sample(sorted(CITIES), 2)
        date, said = _date(rng)
        cabin = "business" if kind == "business_trip" else "economy"
        n = {"solo_economy": 1, "family_economy": rng.randint(3, 5), "business_trip": rng.randint(1, 2),
             "tight_seats": rng.randint(2, 4), "weekend_pair": 2}[kind]
        task = {"origin": origin, "dest": dest, "date": date, "passengers": n, "cabin": cabin}
        if solve(task) is None:
            continue
        cheapest = min(flights(origin, dest, cabin), key=lambda f: f["fare"])
        tight = seats_left(cheapest["flight"], date, cabin) < n
        if (kind == "tight_seats") != tight:  # tight_seats: the cheapest flight is too full; others: it isn't
            continue
        o, d = CITIES[origin], CITIES[dest]
        phrasing = {
            "solo_economy": f"{rng.choice(['Book', 'I need', 'Get me'])} a one-way economy flight from {o} to {d} on {said}, {_people(n, rng)}",
            "family_economy": f"Family trip: {_people(n, rng)} flying {o} to {d} on {said}, economy please",
            "business_trip": f"Business class from {o} to {d} on {said} for {_people(n, rng)}",
            "tight_seats": f"{_people(n, rng).capitalize()}, {o} to {d}, {said}, cheapest economy seats you can find",
            "weekend_pair": f"Weekend getaway for two: {o} to {d} on {said}, economy",
        }[kind]
        return {"request": phrasing, **task}
    raise RuntimeError(f"no {kind} task found for seed {seed}")


EXAMPLES = [{"kind": k, "task": make_task(k, s)} for k in KINDS for s in (0, 1)]
