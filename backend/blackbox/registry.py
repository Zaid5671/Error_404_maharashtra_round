"""The agents plugged into the Black Box. Add a new agent here: name -> "module:attribute"."""

import importlib

from blackbox.adapter import AgentAdapter

AGENTS = {
    "pizza": "agents.pizza.adapter:ADAPTER",
}


def get_agent(name: str) -> AgentAdapter:
    module, attr = AGENTS[name].split(":")
    return getattr(importlib.import_module(module), attr)
