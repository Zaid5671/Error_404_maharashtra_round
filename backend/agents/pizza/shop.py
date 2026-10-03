"""The mock shop: data files plus the shop rules shared by the tools and the solver."""

import json
from datetime import date
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
SHOP_DATE = date(2026, 10, 3)  # fixed, so coupon expiry never depends on the day we run


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


MENU: dict[str, dict] = {p["id"]: p for p in _load("menu.json")}
OUT_OF_STOCK: set[tuple[str, str]] = {(i["pizza"], i["size"]) for i in _load("stock.json")["out_of_stock"]}
COUPONS: dict[str, dict] = {c["code"]: c for c in _load("coupons.json")}
ZONES: dict[str, dict] = {z["name"].lower(): z for z in _load("zones.json")}
SIZES = ["S", "M", "L"]
SIZE_WORDS = {"S": "small", "M": "medium", "L": "large"}


def normalize_pizza(text: str) -> str | None:
    """Map 'Veg Supreme', 'veg-supreme' or 'veg_supreme' to its menu id."""
    key = text.strip().lower().replace("-", " ").replace("_", " ")
    for pid, pizza in MENU.items():
        if key in (pid.replace("_", " "), pizza["name"].lower()):
            return pid
    return None


def in_stock(pizza: str, size: str) -> bool:
    return (pizza, size) not in OUT_OF_STOCK


def substitute(pizza: str, size: str) -> str:
    """Same category and size, closest price; ties go to the cheaper pizza."""
    target = MENU[pizza]
    options = [
        p for p in MENU.values()
        if p["category"] == target["category"] and p["id"] != pizza and in_stock(p["id"], size)
    ]
    best = min(options, key=lambda p: (abs(p["prices"][size] - target["prices"][size]), p["prices"][size]))
    return best["id"]


def check_coupon(code: str, subtotal: int) -> dict:
    """Validate a coupon against the subtotal and the shop date."""
    coupon = COUPONS.get(code.strip().upper())
    if coupon is None:
        return {"code": code, "valid": False, "reason": "unknown code", "discount": 0}
    out = {"code": coupon["code"], "type": coupon["type"], "value": coupon["value"]}
    if date.fromisoformat(coupon["expires"]) < SHOP_DATE:
        return {**out, "valid": False, "reason": f"expired on {coupon['expires']}", "discount": 0}
    if subtotal < coupon["min_order"]:
        return {**out, "valid": False, "reason": f"minimum order is {coupon['min_order']}", "discount": 0}
    if coupon["type"] == "pct":
        discount = subtotal * coupon["value"] // 100
    else:
        discount = coupon["value"]
    return {**out, "valid": True, "discount": discount}


def best_coupon(subtotal: int) -> str | None:
    """The valid coupon with the biggest discount; ties go to the coupon listed first in coupons.json."""
    best_code, best_discount = None, 0
    for code in COUPONS:
        result = check_coupon(code, subtotal)
        if result["valid"] and result["discount"] > best_discount:
            best_code, best_discount = code, result["discount"]
    return best_code


def zone(area: str) -> dict | None:
    return ZONES.get(area.strip().lower())
