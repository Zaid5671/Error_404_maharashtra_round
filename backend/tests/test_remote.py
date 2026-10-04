"""An agent connected by URL, end to end: probe, connect, generate data, train, diagnose, a live
run with a hidden fault, and a replay. The agent is the SDK mini agent (fake LLM), served in-process."""

import json
import time

import pytest
from fastapi.testclient import TestClient

from blackbox import api, config, diagnose, evaluate, index, jobs, registry, train
from tests import sdk_agent

URL = "http://minitravel.test"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    for mod in (train, jobs, diagnose):
        monkeypatch.setattr(mod, "MODELS_DIR", tmp_path / "models")
    for mod in (evaluate, index, api):
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path / "reports")
    agent_app = sdk_agent.make_app()
    monkeypatch.setattr(registry, "CLIENT_FACTORY", lambda url: TestClient(agent_app, base_url=url))
    registry._remote.clear()
    registry._online.clear()
    diagnose.load_model.cache_clear()
    index.clear_diagnoses()
    yield TestClient(api.app)
    registry._remote.clear()
    registry._online.clear()
    diagnose.load_model.cache_clear()
    index.clear_diagnoses()


def sse(response) -> list[tuple[str, dict]]:
    events, name = [], None
    for line in response.iter_lines():
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            events.append((name, json.loads(line.split(":", 1)[1])))
    return events


def connect(client):
    r = client.post("/agents/connect", json={"name": "mini", "url": URL})
    assert r.status_code == 200, r.text
    return r.json()


def test_probe_and_connect(client):
    assert client.post("/agents/probe", json={"url": URL}).json()["name"] == "minitravel"
    assert client.post("/agents/probe", json={"url": "ftp://nope"}).status_code == 400
    agent = connect(client)
    assert agent["title"] == "Mini travel agent" and agent["via"] == "sdk"
    items = {a["name"]: a for a in client.get("/agents").json()["items"]}
    assert items["mini"]["kind"] == "connected" and items["mini"]["online"]
    details = client.get("/agent/mini").json()
    assert details["remote"]["online"] and details["remote"]["kinds"] == ["delhi_trip", "family_goa", "goa_trip", "solo_delhi"]
    assert client.post("/agents/connect", json={"name": "mini", "url": URL}).status_code == 400  # name taken


def test_generate_train_diagnose_live_and_replay(client):
    connect(client)
    assert client.post("/generate/mini", json={"runs_per_kind": 4, "faults_per_run": 3}).status_code == 200
    for _ in range(300):
        job = client.get("/train/mini").json()
        if job["status"] != "running":
            break
        time.sleep(0.1)
    assert job["status"] == "done", job["log"]
    assert job["kind"] == "generate" and job["generated"]["failed"] >= 10
    assert job["result"]["top1"] is not None

    # the generic faults are listed, one tool held out as unseen
    faults = client.get("/faults/mini").json()
    assert any(f["type"].startswith("search_flights:") for f in faults)
    assert any(not f["seen"] for f in faults) and any(f["seen"] for f in faults)

    # diagnose a failed test run
    failed = client.get("/runs/mini?source=all&outcome=failure&limit=200").json()["items"]
    target = next(r for r in failed if r["split"] == "test")
    d = client.post("/diagnose", json={"agent": "mini", "run_id": target["run_id"]}).json()
    assert d["culprit"] is not None and d["explanation"]

    # a live run with a hidden fault on the search tool
    task = {"request": "2 people to Goa", "dest": "GOA", "people": 2}
    with client.stream("POST", "/run", json={"agent": "mini", "task": task, "fault_mode": "surprise",
                                             "fault_type": "search_flights:number"}) as r:
        events = sse(r)
    names = [e for e, _ in events]
    assert names[0] == "run_started" and "step_done" in names and names[-1] == "run_done"
    live_id = events[0][1]["run_id"]
    live = client.get(f"/runs/mini/{live_id}").json()
    assert live["fault"]["type"] == "search_flights:number" and live["fault"]["step_id"] == 2

    # replay the faulted step with the true output: steps before it are reused
    clean = client.get("/runs/mini?source=generated&limit=200").json()["items"]
    original = next(r for r in clean if r["outcome"] == "failure" and r["split"] == "train")
    run = client.get(f"/runs/mini/{original['run_id']}").json()
    parent = client.get(f"/runs/mini/{run['parent_run_id']}").json()
    k = run["fault"]["step_id"]
    with client.stream("POST", "/replay", json={"agent": "mini", "run_id": run["run_id"], "step_id": k,
                                                "new_output": parent["steps"][k - 1]["output"]}) as r:
        events = sse(r)
    assert sum(1 for e, _ in events if e == "step_reused") == k - 1
    done = dict(events)["run_done"]
    assert done["outcome"] == "success"


def test_agent_offline_is_reported_plainly(client, monkeypatch):
    connect(client)
    import httpx

    monkeypatch.setattr(registry, "CLIENT_FACTORY", lambda url: httpx.Client(base_url="http://127.0.0.1:9", timeout=0.5))
    registry._remote.clear()
    registry._online.clear()
    assert client.get("/agents").json()["items"][-1]["online"] is False
    r = client.post("/generate/mini", json={})
    assert r.status_code == 503 and "isn't answering" in r.json()["detail"]
    r = client.post("/run", json={"agent": "mini", "task": {"request": "x", "dest": "GOA", "people": 1}, "fault_mode": "none"})
    assert r.status_code == 503 and "not reachable" in r.json()["detail"]  # refused before the run starts
