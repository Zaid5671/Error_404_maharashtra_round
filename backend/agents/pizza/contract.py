"""The pizza agent's own shapes: its task (Order), its result (OrderResult) and its Catalog.

The Black Box stores these as opaque dicts in Run.task / Run.expected / Run.actual.
Mirrored in frontend/src/types/pizza.ts.
"""

from typing import Literal

from blackbox.contract import Model

Size = Literal["S", "M", "L"]
FAULT_TYPES = [
    "wrong_price",
    "stock_lie",
    "wrong_cart_line",
    "wrong_discount",
    "wrong_delivery",
    "llm_misread",
    "llm_wrong_choice",
]


class OrderItem(Model):
    pizza: str
    size: Size
    qty: int


class Order(Model):
    items: list[OrderItem]
    coupon: str | None
    area: str


class ResultItem(OrderItem):
    unit_price: int
    line_total: int


class OrderResult(Model):
    items: list[ResultItem]
    subtotal: int
    coupon: str | None
    discount: int
    delivery_fee: int
    total: int


class CatalogPizza(Model):
    id: str
    name: str
    prices: dict[Size, int]


class CatalogCoupon(Model):
    code: str
    label: str


class CatalogArea(Model):
    name: str
    deliverable: bool


class Catalog(Model):
    pizzas: list[CatalogPizza]
    sizes: list[Size]
    coupons: list[CatalogCoupon]
    areas: list[CatalogArea]
