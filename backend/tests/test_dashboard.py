"""Dashboard routes and the imported-agent flow: create an agent, import traces, train, diagnose.
Runs, models and reports all go to temp folders; no LLM calls."""

import copy
import json
import time

import pytest
from fastapi.testclient import TestClient

from blackbox import api, config, diagnose, evaluate, index, jobs, train
from blackbox.contract import Diagnosis
from tests.test_api import live_run
from tests.test_replay import fake_llm  # noqa: F401 - fixture


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    for mod in (train, jobs, diagnose):
        monkeypatch.setattr(mod, "MODELS_DIR", tmp_path / "models")
    for mod in (evaluate, index, api):
        monkeypatch.setattr(mod, "REPORTS_DIR", tmp_path / "reports")
    diagnose.load_model.cache_clear()
    index.clear_diagnoses()
    yield TestClient(api.app)
    diagnose.load_model.cache_clear()
    index.clear_diagnoses()


def sample(name):
    return json.loads((config.SAMPLE_DIR / name).read_text(encoding="utf-8"))


def traces(n_train=30, n_test=4):
    """Copies of the clean and faulted sample runs, as if logged by another team's agent."""
    clean, faulted = sample("pizza_clean.json"), sample("pizza_faulted.json")
    out = []
    for i in range(n_train + n_test):
        split = "train" if i < n_train else "test"
        for kind, run in (("ok", clean), ("bad", faulted)):
            r = copy.deepcopy(run)
            r.update(run_id=f"{kind}_{i}", template_id=f"t{i % 6}", split=split)
            out.append(r)
    return out


def test_imported_agent_import_train_and_diagnose(client):
    assert client.post("/agents", json={"name": "Bad Name"}).status_code == 400
    assert client.post("/agents", json={"name": "support", "title": "Support bot"}).status_code == 200
    assert client.post("/agents", json={"name": "support"}).status_code == 400  # already exists
    assert {a["name"]: a["kind"] for a in client.get("/agents").json()["items"]} == {"pizza": "connected", "support": "imported"}

    runs = traces()
    bad = {"run_id": "x"}  # not a trace
    res = client.post("/import/support", json={"runs": runs + [bad], "names": [f"f{i}.json" for i in range(len(runs) + 1)]}).json()
    assert res["imported"] == len(runs) and len(res["rejected"]) == 1 and res["rejected"][0]["where"] == f"f{len(runs)}.json"
    again = client.post("/import/support", json={"runs": runs[:1]}).json()
    assert again["imported"] == 0 and "already exists" in again["rejected"][0]["error"]

    data = client.get("/dataset/support").json()
    assert data["total"] == len(runs) and data["train"] == 60 and data["test"] == 8

    # an imported agent can't run or replay, but everything else works
    assert client.get("/catalog/support").status_code == 400
    assert client.post("/run", json={"agent": "support", "task": {}, "fault_mode": "none"}).status_code == 400

    client.post("/train/support")
    for _ in range(100):
        status = client.get("/train/support").json()
        if status["status"] != "running":
            break
        time.sleep(0.1)
    assert status["status"] == "done", status["log"]
    assert status["result"]["n_test_runs"] == 4 and status["history"][0]["status"] == "done"

    d = Diagnosis.model_validate(client.post("/diagnose", json={"agent": "support", "run_id": "bad_31"}).json())
    assert d.culprit == 8  # the faulted sample's broken step
    details = client.get("/agent/support").json()
    assert details["kind"] == "imported" and details["model"]["n_train_runs"] == 60 and not details["can_run"]
    assert {t["name"] for t in details["tools"]} >= {"apply_coupon", "place_order"}


def test_training_needs_enough_data(client):
    client.post("/agents", json={"name": "tiny"})
    client.post("/import/tiny", json={"runs": traces(n_train=2, n_test=0)})
    client.post("/train/tiny")
    for _ in range(50):
        status = client.get("/train/tiny").json()
        if status["status"] != "running":
            break
        time.sleep(0.1)
    assert status["status"] == "error" and "at least" in status["error"]


def test_runs_list_overview_and_replays(client, fake_llm):
    _, run = live_run(client, fake_llm, "surprise", "wrong_delivery")
    rows = client.get("/runs/pizza").json()
    assert rows["total"] == 1 and rows["items"][0]["run_id"] == run["run_id"]
    assert client.get("/runs/pizza", params={"outcome": "success"}).json()["total"] == 0
    assert client.get("/runs/pizza", params={"q": "nothing-like-this"}).json()["total"] == 0
    assert client.get("/runs/pizza", params={"source": "bogus"}).status_code == 400
    ov = client.get("/overview/pizza").json()
    assert ov["total_runs"] == 1 and ov["failed_runs"] == 1 and ov["replays"] == 0
    assert client.get("/replays/pizza").json() == []
