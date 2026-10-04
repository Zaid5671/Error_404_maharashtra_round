"""Kinds of hotel requests the agent gets, and how to make one from a seed."""

from __future__ import annotations

import random

from hotels import CITIES, hotels, rooms_left, rooms_needed, solve

KINDS = ["city_break", "family_stay", "luxury_stay", "long_stay", "sold_out_cheapest"]
MONTHS = {11: "Nov", 12: "Dec"}


def make_task(kind: str, seed: int) -> dict:
    rng = random.Random(f"{kind}:{seed}")
    for _ in range(500):
        city = rng.choice(CITIES)
        month, day = rng.choice([11, 12]), rng.randint(1, 25)
        check_in, said = f"2026-{month:02d}-{day:02d}", f"{day} {MONTHS[month]}"
        guests = {"city_break": rng.randint(1, 2), "family_stay": rng.randint(3, 5), "luxury_stay": 2,
                  "long_stay": rng.randint(1, 2), "sold_out_cheapest": rng.randint(2, 4)}[kind]
        nights = rng.randint(5, 7) if kind == "long_stay" else rng.randint(1, 3)
        task = {"city": city, "check_in": check_in, "nights": nights, "guests": guests}
        if kind == "luxury_stay":
            task["min_rating"] = 4.5
        if solve(task) is None:
            continue
        cheapest = min((h for h in hotels(city) if h["rating"] >= task.get("min_rating", 0)), key=lambda h: h["nightly_rate"])
        full = rooms_left(cheapest["hotel"], check_in) < rooms_needed(guests)
        if (kind == "sold_out_cheapest") != full:
            continue
        who = "just me" if guests == 1 else f"{guests} guests"
        request = {
            "city_break": f"A room in {city} from {said} for {nights} night{'s' if nights > 1 else ''}, {who}",
            "family_stay": f"Family of {guests} visiting {city}: check in {said}, {nights} nights, cheapest option",
            "luxury_stay": f"Somewhere really nice in {city} (4.5 stars or better) for 2 from {said}, {nights} nights",
            "long_stay": f"Long stay in {city}: {nights} nights from {said}, {who}",
            "sold_out_cheapest": f"{who.capitalize()} in {city}, {nights} nights from {said}, as cheap as possible",
        }[kind]
        return {"request": request, **task}
    raise RuntimeError(f"no {kind} task found for seed {seed}")


EXAMPLES = [{"kind": k, "task": make_task(k, s)} for k in KINDS for s in (0, 1)]
