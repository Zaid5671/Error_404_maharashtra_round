"""Every API route, with the scripted fake LLM (no API calls) and runs saved to a temp folder."""

import json
import random

import pytest
from fastapi.testclient import TestClient

from blackbox import api, config, store
from blackbox.contract import Diagnosis, Report, Run
from blackbox.train import load_runs
from tests.test_replay import BATCHES, ORDER, fake_llm  # noqa: F401 - fake_llm is a fixture


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(api, "RNG", lambda: random.Random(3))
    return TestClient(api.app)


def events(response) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs."""
    out, event = [], None
    for line in response.text.splitlines():
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            out.append((event, json.loads(line.split(":", 1)[1])))
    return out


def live_run(client, fake_llm, fault_mode="none") -> tuple[list[tuple[str, dict]], dict]:
    fake_llm += [list(b) for b in BATCHES]
    r = client.post("/run", json={"agent": "pizza", "task": ORDER, "fault_mode": fault_mode})
    assert r.status_code == 200
    evs = events(r)
    run = client.get(f"/runs/pizza/{evs[0][1]['run_id']}").json()
    return evs, run


def test_agents_catalog_and_report(client):
    assert client.get("/agents").json() == {"agents": ["pizza"]}
    catalog = client.get("/catalog/pizza").json()
    assert {p["id"] for p in catalog["pizzas"]} >= {"margherita", "pepperoni"}
    Report.model_validate(client.get("/report/pizza").json())
    assert client.get("/catalog/flights").status_code == 404


def test_names_that_could_escape_the_runs_folder_are_rejected(client):
    assert client.get("/runs/pizza/..%2F..%2F.env").status_code in (400, 404)
    assert client.get("/runs/pizza/a.b").status_code == 400
    assert client.post("/diagnose", json={"agent": "pizza", "run_id": "../x"}).status_code == 400
    assert client.get("/runs/pizza/missing_run").status_code == 404


def test_invalid_order_is_a_400(client):
    r = client.post("/run", json={"agent": "pizza", "task": {"items": [], "coupon": None, "area": "Bandra"},
                                  "fault_mode": "none"})
    assert r.status_code == 400 and "pizza" in r.json()["detail"]


def test_live_run_streams_and_saves(client, fake_llm):
    evs, run = live_run(client, fake_llm)
    names = [e for e, _ in evs]
    assert names[0] == "run_started" and names[-1] == "run_done"
    assert names.count("step_done") == names.count("step_started") == len(run["steps"]) == 10
    assert evs[-1][1]["outcome"] == "success"
    Run.model_validate(run)
    assert run["source"] == "live" and run["split"] is None and run["fault"] is None
    assert load_runs("pizza") == []  # live runs never reach training


def test_surprise_run_hides_a_fault_and_diagnosis_finds_a_culprit(client, fake_llm):
    evs, run = live_run(client, fake_llm, "surprise")
    assert run["fault"] is not None and run["fault"]["family"] == "tool"
    assert all("fault" not in data for _, data in evs)  # hidden until the user reveals it
    assert run["outcome"] == "failure"
    diag = Diagnosis.model_validate(client.post("/diagnose", json={"agent": "pizza", "run_id": run["run_id"]}).json())
    assert diag.culprit is not None and diag.explanation


def test_replay_streams_reused_steps_and_saves_a_linked_run(client, fake_llm):
    _, original = live_run(client, fake_llm)
    fake_llm += [list(BATCHES[5])]  # after the edited calculate_total the LLM places the order
    total = original["steps"][8]
    assert total["name"] == "calculate_total"
    r = client.post("/replay", json={"agent": "pizza", "run_id": original["run_id"], "step_id": 9,
                                     "new_output": total["output"]})
    evs = events(r)
    assert evs[0][0] == "run_started" and evs[-1][0] == "run_done"
    assert [d["id"] for e, d in evs if e == "step_reused"] == list(range(1, 9))
    new = client.get(f"/runs/pizza/{evs[0][1]['run_id']}").json()
    assert new["parent_run_id"] == original["run_id"] and new["replayed_from_step"] == 9
    assert new["source"] == "replay" and new["outcome"] == "success"


def test_replay_edit_checks(client, fake_llm):
    _, run = live_run(client, fake_llm)
    body = {"agent": "pizza", "run_id": run["run_id"]}
    assert client.post("/replay", json={**body, "step_id": 99, "new_output": {}}).status_code == 400
    bad = client.post("/replay", json={**body, "step_id": 9, "new_output": {"total": 1}})
    assert bad.status_code == 400 and "fields" in bad.json()["detail"]


def test_replay_can_edit_an_llm_step(client, fake_llm):
    _, run = live_run(client, fake_llm)
    fixed = {**run["steps"][0]["output"], "area": "Bandra"}  # the LLM's parsed order, edited
    fake_llm += [list(b) for b in BATCHES[1:]]
    evs = events(client.post("/replay", json={"agent": "pizza", "run_id": run["run_id"], "step_id": 1,
                                              "new_output": fixed}))
    assert evs[-1][0] == "run_done"
    new = store.load_run("pizza", evs[0][1]["run_id"])
    assert new["steps"][0]["output"]["area"] == "Bandra"
