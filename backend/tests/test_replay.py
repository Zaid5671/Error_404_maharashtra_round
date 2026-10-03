"""Resume, replay and fault injection, with a scripted fake LLM (no API calls)."""

import json
import random

import pytest

from agents.pizza import agent, tools
from agents.pizza.adapter import ADAPTER
from agents.pizza.solver import solve
from blackbox import injector
from blackbox.recorder import Recorder

ORDER = {
    "items": [{"pizza": "pepperoni", "size": "L", "qty": 2}, {"pizza": "veg_supreme", "size": "M", "qty": 1}],
    "coupon": "PIZZA20",
    "area": "Andheri",
}
REQUEST = "2 large pepperoni and 1 medium veg supreme, code PIZZA20, deliver to Andheri"
BATCHES = [
    [("parse_order", ORDER)],                                                       # 1
    [("search_menu", {"query": "pepperoni"}), ("search_menu", {"query": "veg_supreme"}),
     ("check_stock", {"pizza": "pepperoni", "size": "L"}),
     ("check_stock", {"pizza": "veg_supreme", "size": "M"})],                       # 2-5
    [("add_to_cart", {"items": ORDER["items"]})],                                   # 6
    [("apply_coupon", {"code": "PIZZA20"}), ("check_delivery", {"area": "Andheri"})],  # 7-8
    [("calculate_total", {})],                                                      # 9
    [("place_order", {})],                                                          # 10
]
STATS = {"latency_ms": 1, "tokens_in": 1, "tokens_out": 1}


def assistant(batch, tag):
    return {
        "role": "assistant",
        "tool_calls": [
            {"id": f"{tag}_{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}
            for i, (n, a) in enumerate(batch)
        ],
    }


@pytest.fixture
def fake_llm(monkeypatch):
    """Answers each LLM call with the next scripted batch."""
    script: list[list] = []

    def chat(messages, schemas):
        if not script:  # out of script: the agent just stops talking
            return {"role": "assistant", "content": "done"}, dict(STATS)
        return assistant(script.pop(0), f"r{len(messages)}"), dict(STATS)

    monkeypatch.setattr(agent.llm, "chat", chat)
    return script


def clean_run() -> dict:
    """The happy path built exactly as the agent loop builds it."""
    rec = Recorder(tools.new_state())
    messages = [{"role": "system", "content": "x"}, {"role": "user", "content": REQUEST}]
    for b, batch in enumerate(BATCHES):
        msg = assistant(batch, f"b{b}")
        messages.append(msg)
        for i, call in enumerate(msg["tool_calls"]):
            agent.execute_call(messages, rec, call, request_text=REQUEST, llm_stats=STATS if i == 0 else None)
    return agent._finish_run(
        rec, messages, run_id="clean", source="generated", template_id="pair_pizza20_given",
        task=ORDER, request_text=REQUEST, expected=solve(ORDER)["expected"], on_event=None, split="test",
    )


def test_clean_run_succeeds():
    assert clean_run()["outcome"] == "success"


def test_resume_mid_batch_reuses_earlier_steps(fake_llm):
    original = clean_run()
    fake_llm += [BATCHES[4], BATCHES[5]]  # the LLM goes on to calculate_total, then place_order
    wrong = {**original["steps"][6]["output"], "value": 10, "discount": 114}
    new = ADAPTER.resume(original, 7, run_id="r1", new_output=wrong)

    assert new["steps"][:6] == original["steps"][:6]
    assert new["steps"][6]["output"]["discount"] == 114
    assert new["steps"][7]["name"] == "check_delivery"  # rest of step 7's batch was re-run
    assert new["steps"][8]["uses"] == [6, 7, 8]
    assert new["actual"]["total"] == 1147 - 114 + 40
    assert new["outcome"] == "failure"
    assert (new["parent_run_id"], new["replayed_from_step"], new["split"]) == ("clean", 7, "test")
    assert fake_llm == []


def test_resume_with_unchanged_output_gives_same_result(fake_llm):
    original = clean_run()
    fake_llm += [BATCHES[4], BATCHES[5]]
    new = ADAPTER.resume(original, 7, run_id="r2", new_output=original["steps"][6]["output"])
    assert new["actual"] == original["actual"]
    assert new["outcome"] == "success"


def test_resume_from_step_one_with_new_args(fake_llm):
    original = clean_run()
    misread = json.loads(json.dumps(ORDER))
    misread["items"][0]["qty"] = 3
    fake_llm += BATCHES[1:]
    new = ADAPTER.resume(original, 1, run_id="r3", new_args=misread)
    assert new["steps"][0]["output"]["items"][0]["qty"] == 3
    assert json.loads(new["messages"][2]["tool_calls"][0]["function"]["arguments"])["items"][0]["qty"] == 3


def test_every_fault_type_applies_to_a_suitable_run():
    run = clean_run()
    found = {spec.type for spec, _, _ in injector.candidates(ADAPTER, run, random.Random(0), "tool")}
    found |= {spec.type for spec, _, _ in injector.candidates(ADAPTER, run, random.Random(0), "llm")}
    # stock_lie needs an out-of-stock item, which this order doesn't have; llm_wrong_choice only
    # applies when the agent picked the coupon itself, and this customer named PIZZA20
    assert found == {"wrong_price", "wrong_cart_line", "wrong_discount", "wrong_delivery", "llm_misread"}
    auto = {**run, "task": {**run["task"], "coupon": None}}
    assert {s.type for s, _, _ in injector.candidates(ADAPTER, auto, random.Random(0), "llm")} == {"llm_misread", "llm_wrong_choice"}


def test_faults_are_subtle_and_change_something():
    run = clean_run()
    for seed in range(30):
        for spec, step, change in injector.candidates(ADAPTER, run, random.Random(seed), "tool"):
            new = change["output"]
            assert new != step["output"], spec.type
            for result in new.get("results", []):
                assert all(p >= 99 for p in result["prices"].values())


def test_inject_labels_the_fault(fake_llm):
    run = clean_run()
    fake_llm += [BATCHES[4], BATCHES[5]] * 3
    faulted = injector.inject(ADAPTER, run, run_id="f1", rng=random.Random(1), fault_type="wrong_discount")
    assert faulted["fault"]["type"] == "wrong_discount"
    assert faulted["fault"]["step_id"] == 7
    assert faulted["outcome"] == "failure"


def test_misread_persists_in_what_the_llm_sees(fake_llm):
    original = clean_run()
    misread = json.loads(json.dumps(ORDER))
    misread["items"][0]["qty"] = 3
    fake_llm += BATCHES[1:]
    new = ADAPTER.resume(original, 1, run_id="r4", new_args=misread)
    user_turn = next(m for m in new["messages"] if m["role"] == "user")["content"]
    assert "pepperoni" in user_turn and user_turn != REQUEST
    assert new["request_text"] == REQUEST  # the run keeps the customer's real words


def test_inject_never_uses_excluded_types(fake_llm):
    run = clean_run()
    fake_llm += [BATCHES[4], BATCHES[5]] * 40
    for seed in range(10):
        faulted = injector.inject(ADAPTER, run, run_id=f"x{seed}", rng=random.Random(seed), exclude={"wrong_delivery"})
        assert faulted["fault"]["type"] != "wrong_delivery"
