"""Plugs the pizza agent into the Black Box (implements blackbox.adapter.AgentAdapter)."""

from agents.pizza import agent, orders, solver
from blackbox.adapter import EventFn
from blackbox.recorder import OutputHook


class PizzaAdapter:
    name = agent.AGENT_NAME

    def templates(self) -> list[str]:
        return list(orders.TEMPLATES)

    def make_task(self, template_id: str, seed: int) -> dict:
        return orders.generate(template_id, seed)

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
        new_output: dict,
        *,
        run_id: str,
        on_event: EventFn | None = None,
        output_hook: OutputHook | None = None,
    ) -> dict:
        raise NotImplementedError("replay is built in P2")

    def judge(self, expected: dict | None, actual: dict | None) -> str:
        return solver.judge(expected, actual)


ADAPTER = PizzaAdapter()
