"""The pizza ordering agent: system prompt, tool-calling loop, run assembly.

Run one order:      python -m blackbox.agent pair_pizza20_given --seed 0
Run every template: python -m blackbox.agent --all
"""

import argparse
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

from blackbox import config, llm, shop, tools
from blackbox.contract import Run
from blackbox.orders import TEMPLATES, generate
from blackbox.recorder import Recorder
from blackbox.solver import judge

EventFn = Callable[[str, dict], None]
# (step_id, tool name, args, output) -> output; the fault injector plugs in here
StepHook = Callable[[int, str, dict, dict], dict]


def _menu_text() -> str:
    by_cat: dict[str, list[str]] = {}
    for p in shop.MENU.values():
        by_cat.setdefault(p["category"], []).append(p["id"])
    return "; ".join(f"{cat}: {', '.join(ids)}" for cat, ids in by_cat.items())


def _coupons_text() -> str:
    lines = []
    for c in shop.COUPONS.values():
        deal = f"{c['value']}% off (rounded down)" if c["type"] == "pct" else f"Rs {c['value']} off"
        lines.append(f"- {c['code']}: {deal}, minimum order Rs {c['min_order']}, expires {c['expires']}")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You are the ordering agent for a pizza shop in Mumbai. Today is {config.SHOP_DATE}.
Use tools for every step. You may make several tool calls in one turn when they don't depend on each other.

1. Call parse_order with the order exactly as the customer wrote it.
2. For each item call search_menu (with the pizza id) and check_stock.
3. If an item is out of stock, replace it with the pizza of the same category and size whose price is closest to it (tie: the cheaper one). Use search_menu with the category to compare prices, and check_stock the replacement. Don't ask the customer.
4. Call add_to_cart once with all final items. Coupons can only be applied after this.
5. Coupon: call apply_coupon at most once per order. Each call replaces the previous coupon, so never use it to test codes.
   - If the customer gave a code, apply exactly that code. If it comes back invalid, the order has no coupon: don't try any other code.
   - If they gave no code, work out yourself from the rules below which valid coupon gives the biggest discount on the subtotal (tie: PIZZA20), then apply only that one. If none is valid, skip this step.
6. Call check_delivery. If the area is not deliverable, stop and tell the customer; don't place the order.
7. Call calculate_total, then place_order.

Menu ids: {_menu_text()}
Coupons:
{_coupons_text()}"""


def execute_call(
    messages: list[dict],
    rec: Recorder,
    call: dict,
    *,
    request_text: str,
    llm_stats: dict | None,
    on_event: EventFn | None = None,
    step_hook: StepHook | None = None,
) -> dict:
    """Run one tool call from the LLM, append its tool message, record the step. Returns the step."""
    name = call["function"]["name"]
    step_id = len(rec.steps) + 1
    if on_event:
        on_event("step_started", {"id": step_id, "name": name})

    start = time.perf_counter()
    try:
        args: dict[str, Any] = json.loads(call["function"].get("arguments") or "{}")
        output = tools.compute(name, rec.state, args)
    except json.JSONDecodeError:
        args, output = {}, {"error": "arguments were not valid JSON"}
    tool_ms = int((time.perf_counter() - start) * 1000)
    if step_hook:
        output = step_hook(step_id, name, args, output)

    messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(output)})
    step = rec.record(
        name,
        args,
        output,
        step_input={"request_text": request_text} if name == "parse_order" else None,
        llm=llm_stats,
        tool_latency_ms=tool_ms,
        msg_index=len(messages),
    )
    if on_event:
        on_event("step_done", {"step": step})
    return step


def run_loop(
    messages: list[dict],
    rec: Recorder,
    *,
    request_text: str,
    on_event: EventFn | None = None,
    step_hook: StepHook | None = None,
    llm_calls: int = 0,
) -> int:
    """Ask the LLM, run its tool calls, repeat until it stops, places the order, or hits the call cap.

    The LLM stats go on the first step of each batch (the others get null), so the number of LLM
    calls in a run is the number of steps with `llm` set. Returns the running LLM call count.
    """
    while llm_calls < config.MAX_LLM_CALLS:
        message, stats = llm.chat(messages, tools.SCHEMAS)
        llm_calls += 1
        messages.append(message)
        calls = message.get("tool_calls") or []
        if not calls:
            break
        placed = False
        for i, call in enumerate(calls):
            step = execute_call(
                messages, rec, call,
                request_text=request_text,
                llm_stats=stats if i == 0 else None,
                on_event=on_event,
                step_hook=step_hook,
            )
            placed = placed or (step["name"] == "place_order" and step["error"] is None)
        if placed:
            break
    return llm_calls


ORDER_RESULT_KEYS = ("items", "subtotal", "coupon", "discount", "delivery_fee", "total")


def actual_result(steps: list[dict]) -> dict | None:
    """What place_order received, from the last successful place_order step."""
    for step in reversed(steps):
        if step["name"] == "place_order" and step["error"] is None:
            out = step["output"]
            items = [{k: line[k] for k in ("pizza", "size", "qty", "unit_price", "line_total")} for line in out["items"]]
            return {**{k: out[k] for k in ORDER_RESULT_KEYS}, "items": items}
    return None


def run_order(
    spec: dict,
    *,
    run_id: str | None = None,
    source: str = "generated",
    on_event: EventFn | None = None,
    step_hook: StepHook | None = None,
) -> dict:
    """Run the agent on one order from orders.generate (or a live order with the same keys)."""
    run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": spec["request_text"]},
    ]
    rec = Recorder()
    run_loop(messages, rec, request_text=spec["request_text"], on_event=on_event, step_hook=step_hook)

    actual = actual_result(rec.steps)
    run = {
        "run_id": run_id,
        "template_id": spec["template_id"],
        "source": source,
        "parent_run_id": None,
        "replayed_from_step": None,
        "order": spec["order"],
        "request_text": spec["request_text"],
        "expected": spec["expected"],
        "actual": actual,
        "outcome": judge(spec["expected"], actual),
        "fault": None,
        "split": None,
        "messages": messages,
        "steps": rec.steps,
    }
    Run.model_validate(run)
    if on_event:
        on_event("run_done", {k: run[k] for k in ("run_id", "outcome", "actual", "expected")})
    return run


def save_run(run: dict) -> None:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RUNS_DIR / f"{run['run_id']}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")


def run_stats(run: dict) -> dict:
    calls = [s["llm"] for s in run["steps"] if s["llm"]]
    return {
        "llm_calls": len(calls),
        "tokens_in": sum(c["tokens_in"] for c in calls),
        "tokens_out": sum(c["tokens_out"] for c in calls),
        "steps": len(run["steps"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the pizza agent on template orders.")
    parser.add_argument("template", nargs="?", default="pair_pizza20_given", choices=list(TEMPLATES))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--all", action="store_true", help="run every template once with this seed")
    args = parser.parse_args()

    template_ids = list(TEMPLATES) if args.all else [args.template]
    totals = {"llm_calls": 0, "tokens_in": 0, "tokens_out": 0, "success": 0}
    for tid in template_ids:
        spec = generate(tid, args.seed)
        start = time.perf_counter()
        run = run_order(spec, run_id=f"run_p1_{tid}_{args.seed}")
        save_run(run)
        s = run_stats(run)
        for k in ("llm_calls", "tokens_in", "tokens_out"):
            totals[k] += s[k]
        totals["success"] += run["outcome"] == "success"
        exp, act = run["expected"], run["actual"]
        print(
            f"{run['outcome']:8s} {tid:24s} steps={s['steps']:2d} calls={s['llm_calls']} "
            f"tok={s['tokens_in']}/{s['tokens_out']} {time.perf_counter() - start:5.1f}s  "
            f"expected={exp['total'] if exp else None} actual={act['total'] if act else None}",
            flush=True,
        )
    n = len(template_ids)
    print(
        f"\n{totals['success']}/{n} succeeded; per run: {totals['llm_calls'] / n:.1f} calls, "
        f"{totals['tokens_in'] / n:.0f} tokens in, {totals['tokens_out'] / n:.0f} out"
    )


if __name__ == "__main__":
    main()
