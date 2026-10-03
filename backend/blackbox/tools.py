"""The agent's tools.

Each tool has compute(state, args) -> output and write(state, output), kept separate so the fault
injector can corrupt an output before it lands in state. reads(args) and writes(args, output) name
the fine-grained state keys a call touches; the recorder turns them into `uses` (graph arrows).
An output with an "error" key writes nothing.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from blackbox import shop

State = dict[str, Any]


class ToolError(Exception):
    pass


def new_state() -> State:
    return {
        "parsed_order": None,
        "menu": {},
        "stock": {},
        "cart": [],
        "subtotal": None,
        "coupon": None,
        "discount": None,
        "deliverable": None,
        "delivery_fee": None,
        "total": None,
        "order_id": None,
    }


@dataclass(frozen=True)
class Tool:
    name: str
    kind: str  # "llm" for parse_order, "tool" otherwise
    description: str
    parameters: dict
    compute: Callable[[State, dict], dict]
    write: Callable[[State, dict], None]
    reads: Callable[[dict], list[str]]
    writes: Callable[[dict, dict], list[str]]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


def _pizza(value: Any) -> str:
    pid = shop.normalize_pizza(str(value))
    if pid is None:
        raise ToolError(f"unknown pizza '{value}'")
    return pid


def _size(value: Any) -> str:
    size = str(value).strip().upper()[:1]
    if size not in shop.SIZES:
        raise ToolError(f"unknown size '{value}', use S, M or L")
    return size


def _items(value: Any) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise ToolError("items must be a non-empty list")
    items = []
    for item in value:
        qty = int(item.get("qty", 0))
        if qty < 1:
            raise ToolError("qty must be at least 1")
        items.append({"pizza": _pizza(item.get("pizza")), "size": _size(item.get("size")), "qty": qty})
    return items


ITEMS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "pizza": {"type": "string", "description": "menu id, e.g. veg_supreme"},
            "size": {"type": "string", "enum": ["S", "M", "L"]},
            "qty": {"type": "integer"},
        },
        "required": ["pizza", "size", "qty"],
    },
}


# --- parse_order (the LLM's first answer; the tool only records it) ---------------


def _parse_compute(state: State, args: dict) -> dict:
    coupon = args.get("coupon")
    return {
        "items": _items(args.get("items")),
        "coupon": str(coupon).strip().upper() if coupon else None,
        "area": str(args.get("area", "")).strip(),
    }


def _parse_write(state: State, out: dict) -> None:
    state["parsed_order"] = out


# --- search_menu ---------------------------------------------------------------------


def _search_compute(state: State, args: dict) -> dict:
    query = str(args.get("query", "")).strip().lower()
    if query in ("veg", "non-veg", "nonveg", "non veg"):
        category = "veg" if query == "veg" else "non-veg"
        found = [p for p in shop.MENU.values() if p["category"] == category]
    else:
        found = [shop.MENU[_pizza(query)]]
    return {"results": [{k: p[k] for k in ("id", "name", "category", "prices")} for p in found]}


def _search_write(state: State, out: dict) -> None:
    for p in out["results"]:
        state["menu"][p["id"]] = dict(p["prices"])


# --- check_stock ---------------------------------------------------------------------


def _stock_compute(state: State, args: dict) -> dict:
    pizza, size = _pizza(args.get("pizza")), _size(args.get("size"))
    return {"pizza": pizza, "size": size, "available": shop.in_stock(pizza, size)}


def _stock_write(state: State, out: dict) -> None:
    state["stock"][f"{out['pizza']}:{out['size']}"] = out["available"]


# --- add_to_cart ---------------------------------------------------------------------


def _cart_compute(state: State, args: dict) -> dict:
    cart = [dict(line) for line in state["cart"]]
    for item in _items(args.get("items")):
        pizza, size = item["pizza"], item["size"]
        if pizza not in state["menu"]:
            raise ToolError(f"price of {pizza} unknown, call search_menu first")
        stock_key = f"{pizza}:{size}"
        if stock_key not in state["stock"]:
            raise ToolError(f"stock of {pizza} {size} unknown, call check_stock first")
        if not state["stock"][stock_key]:
            raise ToolError(f"{pizza} {size} is out of stock")
        price = state["menu"][pizza][size]
        cart.append({**item, "unit_price": price, "line_total": price * item["qty"]})
    return {"cart": cart, "subtotal": sum(line["line_total"] for line in cart)}


def _cart_write(state: State, out: dict) -> None:
    state["cart"] = out["cart"]
    state["subtotal"] = out["subtotal"]


def _cart_reads(args: dict) -> list[str]:
    keys = ["parsed_order", "cart"]
    for item in args.get("items") or []:
        pizza = shop.normalize_pizza(str(item.get("pizza"))) or str(item.get("pizza"))
        size = str(item.get("size", "")).strip().upper()[:1]
        keys += [f"menu:{pizza}", f"stock:{pizza}:{size}"]
    return keys


# --- apply_coupon --------------------------------------------------------------------


def _coupon_compute(state: State, args: dict) -> dict:
    if state["subtotal"] is None:
        raise ToolError("cart is empty, call add_to_cart first")
    return shop.check_coupon(str(args.get("code", "")), state["subtotal"])


def _coupon_write(state: State, out: dict) -> None:
    state["coupon"] = out["code"] if out["valid"] else None
    state["discount"] = out["discount"]


# --- check_delivery ------------------------------------------------------------------


def _delivery_compute(state: State, args: dict) -> dict:
    area = str(args.get("area", ""))
    zone = shop.zone(area)
    if zone is None:
        raise ToolError(f"unknown area '{area}'")
    return {"area": zone["name"], "deliverable": zone["deliverable"], "delivery_fee": zone["fee"]}


def _delivery_write(state: State, out: dict) -> None:
    state["deliverable"] = out["deliverable"]
    state["delivery_fee"] = out["delivery_fee"]


# --- calculate_total -----------------------------------------------------------------


def _total_compute(state: State, args: dict) -> dict:
    if state["subtotal"] is None:
        raise ToolError("cart is empty, call add_to_cart first")
    if state["delivery_fee"] is None:
        raise ToolError("delivery fee unknown, call check_delivery first")
    discount = state["discount"] or 0
    return {
        "subtotal": state["subtotal"],
        "discount": discount,
        "delivery_fee": state["delivery_fee"],
        "total": state["subtotal"] - discount + state["delivery_fee"],
    }


def _total_write(state: State, out: dict) -> None:
    state["total"] = out["total"]


# --- place_order ---------------------------------------------------------------------


def _place_compute(state: State, args: dict) -> dict:
    if not state["deliverable"]:
        raise ToolError("area is not deliverable")
    if state["total"] is None:
        raise ToolError("total unknown, call calculate_total first")
    result = {
        "items": state["cart"],
        "subtotal": state["subtotal"],
        "coupon": state["coupon"],
        "discount": state["discount"] or 0,
        "delivery_fee": state["delivery_fee"],
        "total": state["total"],
    }
    digest = hashlib.sha1(json.dumps(result, sort_keys=True).encode()).hexdigest()[:6].upper()
    return {"order_id": f"ORD-{digest}", "status": "placed", **result}


def _place_write(state: State, out: dict) -> None:
    state["order_id"] = out["order_id"]


def _no_args() -> dict:
    return {"type": "object", "properties": {}}


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "parse_order", "llm",
            "Record the customer's order exactly as they wrote it (before any stock substitution).",
            {
                "type": "object",
                "properties": {
                    "items": ITEMS_SCHEMA,
                    "coupon": {"type": ["string", "null"], "description": "code the customer gave, or null"},
                    "area": {"type": "string"},
                },
                "required": ["items", "coupon", "area"],
            },
            _parse_compute, _parse_write,
            lambda a: [],
            lambda a, o: ["parsed_order"],
        ),
        Tool(
            "search_menu", "tool",
            "Get prices. query is a pizza id, or a category ('veg' or 'non-veg') to list all its pizzas.",
            {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
            _search_compute, _search_write,
            lambda a: ["parsed_order"],
            lambda a, o: [f"menu:{p['id']}" for p in o["results"]],
        ),
        Tool(
            "check_stock", "tool",
            "Check whether a pizza is available in a size.",
            {
                "type": "object",
                "properties": {"pizza": {"type": "string"}, "size": {"type": "string", "enum": ["S", "M", "L"]}},
                "required": ["pizza", "size"],
            },
            _stock_compute, _stock_write,
            lambda a: ["parsed_order"],
            lambda a, o: [f"stock:{o['pizza']}:{o['size']}"],
        ),
        Tool(
            "add_to_cart", "tool",
            "Add the final items (after substitutions) to the cart. Returns the cart and subtotal.",
            {"type": "object", "properties": {"items": ITEMS_SCHEMA}, "required": ["items"]},
            _cart_compute, _cart_write,
            _cart_reads,
            lambda a, o: ["cart", "subtotal"],
        ),
        Tool(
            "apply_coupon", "tool",
            "Apply a coupon code to the current cart. Returns whether it is valid and the discount.",
            {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},
            _coupon_compute, _coupon_write,
            lambda a: ["parsed_order", "subtotal"],
            lambda a, o: ["coupon", "discount"],
        ),
        Tool(
            "check_delivery", "tool",
            "Check whether we deliver to an area and the delivery fee.",
            {"type": "object", "properties": {"area": {"type": "string"}}, "required": ["area"]},
            _delivery_compute, _delivery_write,
            lambda a: ["parsed_order"],
            lambda a, o: ["deliverable", "delivery_fee"],
        ),
        Tool(
            "calculate_total", "tool",
            "Compute the total from the cart, discount and delivery fee.",
            _no_args(),
            _total_compute, _total_write,
            lambda a: ["cart", "subtotal", "discount", "delivery_fee"],
            lambda a, o: ["total"],
        ),
        Tool(
            "place_order", "tool",
            "Place the order. Call only after calculate_total, and never for an area we don't deliver to.",
            _no_args(),
            _place_compute, _place_write,
            lambda a: ["cart", "subtotal", "coupon", "discount", "deliverable", "delivery_fee", "total"],
            lambda a, o: ["order_id"],
        ),
    ]
}

SCHEMAS = [t.schema() for t in TOOLS.values()]


def compute(name: str, state: State, args: dict) -> dict:
    """Run a tool's compute; bad arguments and misuse come back as {"error": ...} for the LLM to see."""
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": f"unknown tool '{name}'"}
    try:
        return tool.compute(state, args)
    except (ToolError, ValueError, TypeError, AttributeError) as e:
        return {"error": str(e)}
