"""Drives the tools through a scripted run (no LLM) to check uses, state and the success rule."""

import json

from blackbox.agent import actual_result, execute_call
from blackbox.orders import TEMPLATES, generate
from blackbox.recorder import Recorder
from blackbox.solver import judge, solve

ORDER = {
    "items": [{"pizza": "pepperoni", "size": "L", "qty": 2}, {"pizza": "veg_supreme", "size": "M", "qty": 1}],
    "coupon": "PIZZA20",
    "area": "Andheri",
}


def scripted_run(calls: list[tuple[str, dict]]) -> Recorder:
    rec, messages = Recorder(), []
    for i, (name, args) in enumerate(calls):
        call = {"id": f"c{i}", "function": {"name": name, "arguments": json.dumps(args)}}
        execute_call(messages, rec, call, request_text="", llm_stats=None)
    return rec


def happy_path_calls() -> list[tuple[str, dict]]:
    return [
        ("parse_order", ORDER),                               # 1
        ("search_menu", {"query": "pepperoni"}),              # 2
        ("search_menu", {"query": "veg_supreme"}),            # 3
        ("check_stock", {"pizza": "pepperoni", "size": "L"}), # 4
        ("check_stock", {"pizza": "veg_supreme", "size": "M"}),  # 5
        ("add_to_cart", {"items": ORDER["items"]}),           # 6
        ("apply_coupon", {"code": "PIZZA20"}),                # 7
        ("check_delivery", {"area": "Andheri"}),              # 8
        ("calculate_total", {}),                              # 9
        ("place_order", {}),                                  # 10
    ]


def test_uses_follow_the_data():
    steps = scripted_run(happy_path_calls()).steps
    uses = {s["id"]: s["uses"] for s in steps}
    assert uses[1] == []
    assert uses[2] == [1]
    assert uses[6] == [1, 2, 3, 4, 5]
    assert uses[7] == [1, 6]
    assert uses[9] == [6, 7, 8]
    assert uses[10] == [6, 7, 8, 9]
    assert all(s["error"] is None for s in steps)


def test_happy_path_matches_solver():
    steps = scripted_run(happy_path_calls()).steps
    expected = solve(ORDER)["expected"]
    actual = actual_result(steps)
    assert actual["total"] == expected["total"] == 958
    assert judge(expected, actual) == "success"


def test_tool_misuse_is_an_error_not_a_crash():
    steps = scripted_run([("add_to_cart", {"items": ORDER["items"]}), ("place_order", {})]).steps
    assert "search_menu" in steps[0]["error"]
    assert steps[1]["error"] is not None
    assert actual_result(steps) is None


def test_undeliverable_order_expects_no_order():
    order = {**ORDER, "area": "Vashi"}
    assert solve(order)["expected"] is None
    assert judge(None, None) == "success"


def test_every_template_generates():
    for tid in TEMPLATES:
        for seed in range(10):
            spec = generate(tid, seed)
            assert spec["request_text"]
