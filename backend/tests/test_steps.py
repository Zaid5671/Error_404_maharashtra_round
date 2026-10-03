"""Drives the pizza tools through a scripted run (no LLM) to check the recorder, state and success rule."""

import json

from agents.pizza import tools
from agents.pizza.agent import actual_result, execute_call
from agents.pizza.orders import TEMPLATES, generate
from agents.pizza.solver import judge, solve
from blackbox.recorder import Recorder

ORDER = {
    "items": [{"pizza": "pepperoni", "size": "L", "qty": 2}, {"pizza": "veg_supreme", "size": "M", "qty": 1}],
    "coupon": "PIZZA20",
    "area": "Andheri",
}


def scripted_run(calls: list[tuple[str, dict]], output_hook=None) -> Recorder:
    rec, messages = Recorder(tools.new_state(), output_hook), []
    for i, (name, args) in enumerate(calls):
        call = {"id": f"c{i}", "function": {"name": name, "arguments": json.dumps(args)}}
        execute_call(messages, rec, call, request_text="", llm_stats=None)
    return rec


def happy_path_calls() -> list[tuple[str, dict]]:
    return [
        ("parse_order", ORDER),                                  # 1
        ("search_menu", {"query": "pepperoni"}),                 # 2
        ("search_menu", {"query": "veg_supreme"}),               # 3
        ("check_stock", {"pizza": "pepperoni", "size": "L"}),    # 4
        ("check_stock", {"pizza": "veg_supreme", "size": "M"}),  # 5
        ("add_to_cart", {"items": ORDER["items"]}),              # 6
        ("apply_coupon", {"code": "PIZZA20"}),                   # 7
        ("check_delivery", {"area": "Andheri"}),                 # 8
        ("calculate_total", {}),                                 # 9
        ("place_order", {}),                                     # 10
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
    assert steps[6]["writes"] == ["coupon", "discount"]


def test_happy_path_matches_solver():
    steps = scripted_run(happy_path_calls()).steps
    expected = solve(ORDER)["expected"]
    actual = actual_result(steps)
    assert actual["total"] == expected["total"] == 958
    assert judge(expected, actual) == "success"


def test_output_hook_changes_what_the_agent_sees():
    def halve_discount(step_id, name, args, output):
        return {**output, "value": 10, "discount": 114} if name == "apply_coupon" else output

    steps = scripted_run(happy_path_calls(), output_hook=halve_discount).steps
    actual = actual_result(steps)
    assert steps[6]["output"]["discount"] == 114
    assert actual["total"] == 1147 - 114 + 40
    assert judge(solve(ORDER)["expected"], actual) == "failure"


def test_resume_rebuilds_the_checkpoint():
    full = scripted_run(happy_path_calls()).steps
    rec = Recorder.resume(full[:8])
    assert rec.state == full[7]["state_after"]
    assert rec.last_writer["discount"] == 7
    assert rec.next_id == 9


def test_tool_misuse_is_an_error_not_a_crash():
    steps = scripted_run([("add_to_cart", {"items": ORDER["items"]}), ("place_order", {})]).steps
    assert "search_menu" in steps[0]["error"]
    assert steps[0]["writes"] == []
    assert steps[1]["error"] is not None
    assert actual_result(steps) is None


def test_undeliverable_order_expects_no_order():
    order = {**ORDER, "area": "Vashi"}
    assert solve(order)["expected"] is None
    assert judge(None, None) == "success"


def test_every_template_generates():
    for tid in TEMPLATES:
        for seed in range(10):
            task = generate(tid, seed)
            assert task["request_text"] and task["task"]["items"]
