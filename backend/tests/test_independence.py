"""The Black Box must not depend on any agent. Only blackbox/registry.py may name agent modules."""

import re
from pathlib import Path

from blackbox.registry import AGENTS, get_agent

BLACKBOX_DIR = Path(__file__).resolve().parent.parent / "blackbox"


def test_blackbox_does_not_import_agents():
    offenders = [
        p.name
        for p in BLACKBOX_DIR.glob("*.py")
        if p.name != "registry.py" and re.search(r"^\s*(from|import)\s+agents\b", p.read_text(encoding="utf-8"), re.M)
    ]
    assert offenders == []


def test_every_registered_agent_has_the_adapter_methods():
    for name in AGENTS:
        adapter = get_agent(name)
        assert adapter.name == name
        for method in ("templates", "make_task", "faults", "run", "resume", "judge"):
            assert callable(getattr(adapter, method))
        task = adapter.make_task(adapter.templates()[0], 0)
        assert {"template_id", "seed", "task", "request_text", "expected"} <= set(task)
