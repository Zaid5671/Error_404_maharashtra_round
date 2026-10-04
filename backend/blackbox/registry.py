"""The agents the Black Box knows.

Connected agents plug in with code: an AgentAdapter (name -> "module:attribute" below). They can run
live, inject faults and replay. Imported agents are created from the app and only have traces that
were recorded elsewhere and imported: they can be trained and diagnosed, but not run or replayed.
"""

import importlib
import json
import re
from datetime import datetime, timezone

from blackbox import config
from blackbox.adapter import AgentAdapter

AGENTS = {
    "pizza": "agents.pizza.adapter:ADAPTER",
}
NAME = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")


def get_agent(name: str) -> AgentAdapter:
    """The adapter of a connected agent. KeyError for imported or unknown agents."""
    module, attr = AGENTS[name].split(":")
    return getattr(importlib.import_module(module), attr)


def _imported_path():
    return config.RUNS_DIR / "imported_agents.json"


def imported_agents() -> list[dict]:
    path = _imported_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def all_agents() -> list[dict]:
    connected = []
    for name in AGENTS:
        info = getattr(get_agent(name), "describe", lambda: {})()
        connected.append({"name": name, "kind": "connected", "title": info.get("title", name),
                          "description": info.get("description", ""), "created": None})
    return connected + [{**a, "kind": "imported"} for a in imported_agents()]


def exists(name: str) -> bool:
    return name in AGENTS or any(a["name"] == name for a in imported_agents())


def is_connected(name: str) -> bool:
    return name in AGENTS


def add_imported(name: str, title: str, description: str) -> dict:
    if not NAME.match(name):
        raise ValueError("name must be 2-40 characters: lowercase letters, digits, '_' or '-', starting with a letter")
    if exists(name):
        raise ValueError(f"an agent named '{name}' already exists")
    agent = {"name": name, "title": title.strip() or name, "description": description.strip(),
             "created": datetime.now(timezone.utc).isoformat()}
    path = _imported_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(imported_agents() + [agent], indent=2), encoding="utf-8")
    return agent
