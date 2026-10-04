"""Plugs the pizza agent into the Black Box (implements blackbox.adapter.AgentAdapter)."""

import random

from pydantic import ValidationError

from agents.pizza import agent, faults, orders, shop, solver
from agents.pizza.contract import Catalog, Order
from blackbox.adapter import EventFn, FaultSpec
from blackbox.recorder import OutputHook


class PizzaAdapter:
    name = agent.AGENT_NAME

    def templates(self) -> list[str]:
        return list(orders.TEMPLATES)

    def make_task(self, template_id: str, seed: int) -> dict:
        return orders.generate(template_id, seed)

    def faults(self) -> list[FaultSpec]:
        return faults.FAULTS

    def task_from_input(self, task: dict) -> dict:
        try:
            order = Order.model_validate(task).model_dump()
        except ValidationError as e:
            raise ValueError(f"invalid order: {e.errors()[0]['msg']}") from e
        if not order["items"]:
            raise ValueError("invalid order: add at least one pizza")
        for item in order["items"]:
            if item["pizza"] not in shop.MENU:
                raise ValueError(f"invalid order: unknown pizza '{item['pizza']}'")
            if not 1 <= item["qty"] <= 9:
                raise ValueError("invalid order: quantity must be 1-9")
        return {
            "template_id": "live",
            "seed": None,
            "task": order,
            "request_text": orders.request_text(random.Random(), order),
            "expected": solver.solve(order)["expected"],
        }

    def describe(self) -> dict:
        """Optional hook: what the Agents page shows about this agent."""
        from agents import config
        from agents.pizza import tools

        return {
            "title": "Pizza ordering agent",
            "description": "Takes a customer's order in plain words, checks the menu, stock, coupons and delivery "
                           "area with tools, and places the order.",
            "llm": f"{config.PROVIDER} · {config.LLM_MODEL} · reasoning {config.REASONING_EFFORT}",
            "tools": {t.name: t.description for t in tools.TOOLS.values()},
        }

    def form_data(self) -> dict:
        return Catalog(
            pizzas=[{"id": p["id"], "name": p["name"], "prices": p["prices"]} for p in shop.MENU.values()],
            sizes=shop.SIZES,
            coupons=[{"code": c["code"], "label": c["label"]} for c in shop.COUPONS.values()],
            areas=[{"name": z["name"], "deliverable": z["deliverable"]} for z in shop.ZONES.values()],
        ).model_dump()

    def run(
        self,
        task: dict,
        *,
        run_id: str,
        source: str = "generated",
        on_event: EventFn | None = None,
        output_hook: OutputHook | None = None,
    ) -> dict:
        return agent.run_order(task, run_id=run_id, source=source, on_event=on_event, output_hook=output_hook)

    def resume(
        self,
        run: dict,
        step_id: int,
        *,
        run_id: str,
        source: str = "replay",
        new_output: dict | None = None,
        new_args: dict | None = None,
        on_event: EventFn | None = None,
        output_hook: OutputHook | None = None,
    ) -> dict:
        return agent.resume_run(
            run, step_id,
            run_id=run_id, source=source, new_output=new_output, new_args=new_args,
            on_event=on_event, output_hook=output_hook,
        )

    def judge(self, expected: dict | None, actual: dict | None) -> str:
        return solver.judge(expected, actual)


ADAPTER = PizzaAdapter()
