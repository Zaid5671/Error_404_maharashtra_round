"""The correct result for an order, computed without the LLM, and the success rule."""

from collections import Counter

from agents.pizza import shop


def solve(order: dict) -> dict:
    """Work out what a perfect agent would do. Returns the details plus `expected` (None if not deliverable)."""
    lines: list[dict] = []
    substitutions = []
    for item in order["items"]:
        pizza, size, qty = item["pizza"], item["size"], item["qty"]
        if not shop.in_stock(pizza, size):
            sub = shop.substitute(pizza, size)
            substitutions.append({"from": pizza, "to": sub, "size": size})
            pizza = sub
        price = shop.MENU[pizza]["prices"][size]
        lines.append({"pizza": pizza, "size": size, "qty": qty, "unit_price": price, "line_total": price * qty})
    subtotal = sum(line["line_total"] for line in lines)

    code = order["coupon"] if order["coupon"] else shop.best_coupon(subtotal)
    check = shop.check_coupon(code, subtotal) if code else None
    coupon = check["code"] if check and check["valid"] else None
    discount = check["discount"] if check and check["valid"] else 0

    zone = shop.zone(order["area"])
    deliverable = bool(zone and zone["deliverable"])
    fee = zone["fee"] if deliverable else None

    expected = None
    if deliverable:
        expected = {
            "items": lines,
            "subtotal": subtotal,
            "coupon": coupon,
            "discount": discount,
            "delivery_fee": fee,
            "total": subtotal - discount + fee,
        }
    return {"expected": expected, "subtotal": subtotal, "substitutions": substitutions, "deliverable": deliverable}


def _item_counts(result: dict) -> Counter:
    counts: Counter = Counter()
    for item in result["items"]:
        counts[(item["pizza"], item["size"])] += item["qty"]
    return counts


def judge(expected: dict | None, actual: dict | None) -> str:
    """Success rule from plan.md section 6."""
    if expected is None:
        return "success" if actual is None else "failure"
    if actual is None:
        return "failure"
    same_items = _item_counts(expected) == _item_counts(actual)
    return "success" if same_items and actual["total"] == expected["total"] else "failure"
