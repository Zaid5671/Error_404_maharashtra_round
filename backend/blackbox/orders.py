"""Order templates -> {template_id, seed, order, request_text, expected}.

A template fixes the scenario (coupon given or not, forced out-of-stock items, area, subtotal band).
The seed picks the concrete items and the wording, so (template_id, seed) is always the same order.
"""

import random
from dataclasses import dataclass, field

from blackbox import shop
from blackbox.solver import solve

DELIVERABLE = [z["name"] for z in shop.ZONES.values() if z["deliverable"]]
UNDELIVERABLE = [z["name"] for z in shop.ZONES.values() if not z["deliverable"]]
IN_STOCK = [(p, s) for p in shop.MENU for s in shop.SIZES if shop.in_stock(p, s)]


@dataclass(frozen=True)
class Template:
    id: str
    n_items: tuple[int, int]  # random in-stock items, on top of `forced`
    coupon: str | None  # code the customer gives; None means they give none
    subtotal: tuple[int, int] = (0, 10**6)  # accepted subtotal band (after substitution), inclusive
    forced: list[tuple[str, str]] = field(default_factory=list)  # (pizza, size) always included
    areas: list[str] = field(default_factory=lambda: DELIVERABLE)
    max_qty: int = 2


TEMPLATES: dict[str, Template] = {
    t.id: t
    for t in [
        # coupon chosen by the agent (customer gives none)
        Template("single_no_coupon", (1, 1), None, (0, 299), max_qty=1),
        Template("small_auto_welcome", (1, 2), None, (300, 499)),
        Template("pair_auto_pizza20", (2, 2), None, (500, 1199)),
        Template("family_auto_big300", (2, 3), None, (1200, 1499)),
        Template("party_auto_pizza20", (3, 4), None, (1500, 3000), max_qty=3),
        # coupon given by the customer
        Template("pair_pizza20_given", (2, 2), "PIZZA20", (500, 1199)),
        Template("family_big300_given", (2, 3), "BIG300", (1200, 2000)),
        Template("small_welcome_given", (1, 2), "WELCOME50", (300, 499)),
        Template("welcome_given_not_best", (2, 3), "WELCOME50", (600, 1500)),
        Template("expired_code", (2, 3), "DIWALI30", (600, 1500)),
        Template("below_min_code", (1, 2), "BIG300", (300, 1100)),
        Template("unknown_code", (1, 2), "FREEPIZZA", (300, 1200)),
        # out-of-stock items the agent must substitute
        Template("sub_paneer_auto", (0, 1), None, forced=[("paneer_tikka", "L")]),
        Template("sub_chicken_pizza20", (1, 2), "PIZZA20", (500, 1500), forced=[("chicken_tikka", "M")]),
        Template("sub_margherita", (1, 1), None, forced=[("margherita", "S")]),
        Template("sub_two_items", (0, 1), None, forced=[("paneer_tikka", "L"), ("chicken_tikka", "M")]),
        # areas we don't deliver to
        Template("undeliverable", (1, 2), None, areas=UNDELIVERABLE),
        Template("undeliverable_coupon", (2, 2), "PIZZA20", areas=UNDELIVERABLE),
    ]
}


# --- wording -------------------------------------------------------------------

QTY_WORDS = {1: ["1", "one", "a"], 2: ["2", "two"], 3: ["3", "three"]}
OPENERS = ["", "I'd like ", "Can I get ", "Please send ", "Order: ", "Hi, I want "]
COUPON_PHRASES = [", code {c}", ". Use coupon {c}", " with promo code {c}", " (apply {c})"]
AREA_PHRASES = [", deliver to {a}", ". I'm in {a}", ", delivery to {a}", ". Address is in {a}"]


def _item_text(rng: random.Random, item: dict) -> str:
    qty = rng.choice(QTY_WORDS[item["qty"]])
    name = shop.MENU[item["pizza"]]["name"].lower()
    noun = rng.choice(["", " pizza"])
    if noun and item["qty"] > 1:
        noun += "s"
    return f"{qty} {shop.SIZE_WORDS[item['size']]} {name}{noun}"


def request_text(rng: random.Random, order: dict) -> str:
    parts = [_item_text(rng, item) for item in order["items"]]
    items = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    text = rng.choice(OPENERS) + items
    if order["coupon"]:
        text += rng.choice(COUPON_PHRASES).format(c=order["coupon"])
    text += rng.choice(AREA_PHRASES).format(a=order["area"])
    return text


# --- generation ------------------------------------------------------------------


def _sample_order(rng: random.Random, t: Template) -> dict:
    pairs = list(t.forced)
    # keep lines unique after substitution, so expected and actual compare cleanly
    taken = set(pairs) | {(shop.substitute(p, s), s) for p, s in t.forced}
    for _ in range(rng.randint(*t.n_items)):
        options = [pair for pair in IN_STOCK if pair not in taken]
        pair = rng.choice(options)
        pairs.append(pair)
        taken.add(pair)
    rng.shuffle(pairs)
    items = [{"pizza": p, "size": s, "qty": rng.randint(1, t.max_qty)} for p, s in pairs]
    return {"items": items, "coupon": t.coupon, "area": rng.choice(t.areas)}


def generate(template_id: str, seed: int) -> dict:
    t = TEMPLATES[template_id]
    rng = random.Random(f"{template_id}:{seed}")
    for _ in range(500):
        order = _sample_order(rng, t)
        solved = solve(order)
        if t.subtotal[0] <= solved["subtotal"] <= t.subtotal[1]:
            return {
                "template_id": template_id,
                "seed": seed,
                "order": order,
                "request_text": request_text(rng, order),
                "expected": solved["expected"],
            }
    raise ValueError(f"template {template_id} could not hit its subtotal band")
