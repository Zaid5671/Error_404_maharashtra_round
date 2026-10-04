"""The agents the Black Box knows.

Connected agents can run live, inject faults and replay. They plug in one of two ways:
  - built in, with code: an AgentAdapter (name -> "module:attribute" in AGENTS below);
  - by URL, from the app: an agent running the Black Box SDK (stored in connected_agents.json and
    reached through blackbox.remote.RemoteAdapter, so no code changes here).
Imported agents are created from the app and only have traces that were recorded elsewhere and
imported: they can be trained and diagnosed, but not run or replayed.
"""

import importlib
import json
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone

import httpx

from blackbox import config
from blackbox.adapter import AgentAdapter
from blackbox.remote import RemoteAdapter

AGENTS = {
    "pizza": "agents.pizza.adapter:ADAPTER",
}
NAME = re.compile(r"^[a-z][a-z0-9_-]{1,39}$")

# url -> HTTP client for agents connected by URL; tests swap in an in-process client
CLIENT_FACTORY: Callable[[str], httpx.Client] | None = None
_remote: dict[tuple[str, str], RemoteAdapter] = {}
_online: dict[str, tuple[float, bool]] = {}


def get_agent(name: str) -> AgentAdapter:
    """The adapter of a connected agent (built in or by URL). KeyError for imported or unknown agents."""
    if name in AGENTS:
        module, attr = AGENTS[name].split(":")
        return getattr(importlib.import_module(module), attr)
    url = next((a["url"] for a in connected_agents() if a["name"] == name), None)
    if url is None:
        raise KeyError(name)
    key = (name, url)
    if key not in _remote:
        _remote[key] = RemoteAdapter(name, url, CLIENT_FACTORY(url) if CLIENT_FACTORY else None)
    return _remote[key]


def _connected_path():
    return config.RUNS_DIR / "connected_agents.json"


def connected_agents() -> list[dict]:
    path = _connected_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def probe(url: str) -> dict:
    """Ask an agent at this URL who it is (GET /info). Raises ValueError when it can't be reached."""
    url = url.strip().rstrip("/")
    if not re.match(r"^https?://", url):
        raise ValueError("the URL must start with http:// or https://")
    try:
        client = CLIENT_FACTORY(url) if CLIENT_FACTORY else httpx.Client(base_url=url, timeout=3.0)
        r = client.get("/info")
        r.raise_for_status()
        info = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ValueError(f"no Black Box agent answered at {url}: is it running? ({type(e).__name__})") from e
    if not isinstance(info, dict) or "name" not in info or "tools" not in info:
        raise ValueError(f"{url} answered, but not like a Black Box SDK agent (no name/tools in /info)")
    return info


def online(name: str) -> bool:
    """Is a URL-connected agent answering right now? Cached for a few seconds."""
    url = next((a["url"] for a in connected_agents() if a["name"] == name), None)
    if url is None:
        return False
    at, ok = _online.get(url, (0.0, False))
    if time.monotonic() - at > 5:
        try:
            client = CLIENT_FACTORY(url) if CLIENT_FACTORY else httpx.Client(base_url=url, timeout=1.0)
            ok = client.get("/info").status_code == 200
        except httpx.HTTPError:
            ok = False
        _online[url] = (time.monotonic(), ok)
    return ok


def add_connected(name: str, url: str, title: str = "", description: str = "") -> dict:
    """Connect an agent by URL (it must answer /info). Returns the stored entry."""
    _check_new_name(name)
    info = probe(url)
    agent = {"name": name, "url": url.strip().rstrip("/"), "title": title.strip() or info.get("title") or name,
             "description": description.strip() or info.get("description", ""),
             "created": datetime.now(timezone.utc).isoformat()}
    path = _connected_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(connected_agents() + [agent], indent=2), encoding="utf-8")
    return agent


def _check_new_name(name: str) -> None:
    if not NAME.match(name):
        raise ValueError("name must be 2-40 characters: lowercase letters, digits, '_' or '-', starting with a letter")
    if exists(name):
        raise ValueError(f"an agent named '{name}' already exists")


def _imported_path():
    return config.RUNS_DIR / "imported_agents.json"


def imported_agents() -> list[dict]:
    path = _imported_path()
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def all_agents() -> list[dict]:
    connected = []
    for name in AGENTS:
        info = getattr(get_agent(name), "describe", lambda: {})()
        connected.append({"name": name, "kind": "connected", "via": "builtin", "title": info.get("title", name),
                          "description": info.get("description", ""), "created": None})
    remote = [{**a, "kind": "connected", "via": "sdk", "online": online(a["name"])} for a in connected_agents()]
    return connected + remote + [{**a, "kind": "imported"} for a in imported_agents()]


def exists(name: str) -> bool:
    return is_connected(name) or any(a["name"] == name for a in imported_agents())


def is_connected(name: str) -> bool:
    return name in AGENTS or any(a["name"] == name for a in connected_agents())


def add_imported(name: str, title: str, description: str) -> dict:
    _check_new_name(name)
    agent = {"name": name, "title": title.strip() or name, "description": description.strip(),
             "created": datetime.now(timezone.utc).isoformat()}
    path = _imported_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(imported_agents() + [agent], indent=2), encoding="utf-8")
    return agent


def remove(name: str) -> None:
    """Take an agent connected by URL, or an imported agent, out of the app. Its runs, model and
    report stay on disk, so connecting (or creating) it again under the same name brings them back.
    Built-in agents can't be removed."""
    if name in AGENTS:
        raise ValueError(f"'{name}' is built in and can't be removed")
    for path, entries in ((_connected_path(), connected_agents()), (_imported_path(), imported_agents())):
        kept = [a for a in entries if a["name"] != name]
        if len(kept) != len(entries):
            path.write_text(json.dumps(kept, indent=2), encoding="utf-8")
            for key in [k for k in _remote if k[0] == name]:
                del _remote[key]
            return
    raise KeyError(name)

