"""The pizza agent's fault catalogue (plan.md section 8).

Each maker gets (clean run, step to break, rng) and returns a subtle, realistic change:
{"output": ...} replaces a tool's result, {"args": ...} replaces what the LLM chose.
It returns None when the fault can't apply to this step or couldn't change the order.
Faults stay believable: real-looking prices, sizes and quantities, never zeros or garbage.
"""

import copy
import random

from agents.pizza import shop
from blackbox.adapter import FaultSpec

NEIGHBOUR_SIZE = {"S": ["M"], "M": ["S", "L"], "L": ["M"]}
FEES = sorted({z["fee"] for z in shop.ZONES.values() if z["deliverable"]})


def _ordered_pairs(run: dict) -> set[tuple[str, str]]:
    """(pizza, size) pairs that end up in the order: the final cart, else the parsed order."""
    state = run["steps"][-1]["state_after"] if run["steps"] else {}
    lines = state.get("cart") or (state.get("parsed_order") or {}).get("items") or []
    return {(line["pizza"], line["size"]) for line in lines}


def _state_before(run: dict, step: dict) -> dict:
    return run["steps"][step["id"] - 2]["state_after"] if step["id"] > 1 else {}


def wrong_price(run: dict, step: dict, rng: random.Random) -> dict | None:
    if run["expected"] is None or step["error"]:
        return None
    ordered = _ordered_pairs(run)
    targets = [(i, s) for i, p in enumerate(step["output"]["results"]) for s in shop.SIZES if (p["id"], s) in ordered]
    if not targets:
        return None
    i, size = rng.choice(targets)
    out = copy.deepcopy(step["output"])
    old = out["results"][i]["prices"][size]
    new = old
    while new == old or new < 99:
        new = old + rng.choice([-1, 1]) * rng.choice([30, 40, 50, 60, 70, 80, 100])
    out["results"][i]["prices"][size] = new
    return {"output": out, "detail": f"{out['results'][i]['id']} {size} price {old} -> {new}"}


def stock_lie(run: dict, step: dict, rng: random.Random) -> dict | None:
    out = step["output"]
    if run["expected"] is None or step["error"] or out["available"]:
        return None
    return {"output": {**out, "available": True}, "detail": f"{out['pizza']} {out['size']} reported in stock"}


def wrong_cart_line(run: dict, step: dict, rng: random.Random) -> dict | None:
    if run["expected"] is None or step["error"]:
        return None
    out = copy.deepcopy(step["output"])
    line = rng.choice(out["cart"])
    taken = {(item["pizza"], item["size"]) for item in out["cart"]}
    sizes = [s for s in NEIGHBOUR_SIZE[line["size"]] if shop.in_stock(line["pizza"], s) and (line["pizza"], s) not in taken]
    if sizes and rng.random() < 0.5:
        old = f"size {line['size']}"
        line["size"] = rng.choice(sizes)
        line["unit_price"] = shop.MENU[line["pizza"]]["prices"][line["size"]]
        new = f"size {line['size']}"
    else:
        old = f"qty {line['qty']}"
        line["qty"] = line["qty"] + 1 if line["qty"] == 1 else line["qty"] + rng.choice([-1, 1])
        new = f"qty {line['qty']}"
    line["line_total"] = line["unit_price"] * line["qty"]
    out["subtotal"] = sum(item["line_total"] for item in out["cart"])
    return {"output": out, "detail": f"{line['pizza']} {old} -> {new}"}


def wrong_discount(run: dict, step: dict, rng: random.Random) -> dict | None:
    out = step["output"]
    if run["expected"] is None or step["error"] or "type" not in out:
        return None
    subtotal = _state_before(run, step).get("subtotal") or 0
    coupon = shop.COUPONS[out["code"]]

    def discount(kind: str, value: int) -> int:
        return subtotal * value // 100 if kind == "pct" else value

    if not out["valid"]:  # accept a coupon that should have been rejected
        new = {k: v for k, v in out.items() if k != "reason"}
        new.update(valid=True, discount=discount(coupon["type"], coupon["value"]))
        return {"output": new, "detail": f"{out['code']} accepted although {out['reason']}"}
    if out["type"] == "pct":
        value = rng.choice([v for v in (10, 15, 25, 30) if v != out["value"]])
    else:
        value = rng.choice([v for v in (out["value"] - 50, out["value"] + 50, out["value"] + 100) if v > 0])
    new = {**out, "value": value, "discount": discount(out["type"], value)}
    return {"output": new, "detail": f"{out['code']} value {out['value']} -> {value}"}


def wrong_delivery(run: dict, step: dict, rng: random.Random) -> dict | None:
    out = step["output"]
    if step["error"]:
        return None
    if not out["deliverable"]:
        fee = rng.choice(FEES)
        return {"output": {**out, "deliverable": True, "delivery_fee": fee}, "detail": f"{out['area']} marked deliverable (fee {fee})"}
    if run["expected"] is None:
        return None
    fee = rng.choice([f for f in FEES if f != out["delivery_fee"]])
    return {"output": {**out, "delivery_fee": fee}, "detail": f"{out['area']} fee {out['delivery_fee']} -> {fee}"}


def llm_misread(run: dict, step: dict, rng: random.Random) -> dict | None:
    if run["expected"] is None or step["error"]:
        return None
    args = copy.deepcopy(step["output"])  # parse_order's output is the LLM's parsed order
    item = rng.choice(args["items"])
    taken = {(i["pizza"], i["size"]) for i in args["items"]}
    mode = rng.choice(["size", "qty", "pizza"])
    if mode == "size":
        sizes = [s for s in NEIGHBOUR_SIZE[item["size"]] if (item["pizza"], s) not in taken]
        if sizes:
            old, item["size"] = item["size"], rng.choice(sizes)
            return {"args": args, "detail": f"{item['pizza']} size {old} -> {item['size']}"}
    if mode == "pizza":
        category = shop.MENU[item["pizza"]]["category"]
        options = [p for p in shop.MENU if shop.MENU[p]["category"] == category and (p, item["size"]) not in taken]
        if options:
            old, item["pizza"] = item["pizza"], rng.choice(options)
            return {"args": args, "detail": f"{old} {item['size']} read as {item['pizza']}"}
    old = item["qty"]
    item["qty"] = old + 1 if old == 1 else old + rng.choice([-1, 1])
    return {"args": args, "detail": f"{item['pizza']} qty {old} -> {item['qty']}"}


def llm_wrong_choice(run: dict, step: dict, rng: random.Random) -> dict | None:
    if run["expected"] is None or step["error"]:
        return None
    current = str(step["input"].get("code", "")).upper()
    subtotal = _state_before(run, step).get("subtotal") or 0
    right = shop.check_coupon(current, subtotal)["discount"] if current else 0
    # a different code that is valid but gives another discount: the agent sees "valid" and moves
    # on, as with a real wrong choice (an invalid code just makes it try again and recover)
    options = [
        c for c in shop.COUPONS
        if c != current and shop.check_coupon(c, subtotal)["valid"] and shop.check_coupon(c, subtotal)["discount"] != right
    ]
    if not options:
        return None
    code = rng.choice(options)
    return {"args": {"code": code}, "detail": f"LLM applied {code} instead of {current}"}


FAULTS = [
    FaultSpec("wrong_price", "tool", "search_menu", wrong_price),
    FaultSpec("stock_lie", "tool", "check_stock", stock_lie),
    FaultSpec("wrong_cart_line", "tool", "add_to_cart", wrong_cart_line),
    FaultSpec("wrong_discount", "tool", "apply_coupon", wrong_discount),
    FaultSpec("wrong_delivery", "tool", "check_delivery", wrong_delivery),
    FaultSpec("llm_misread", "llm", "parse_order", llm_misread),
    FaultSpec("llm_wrong_choice", "llm", "apply_coupon", llm_wrong_choice),
]
