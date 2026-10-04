"""The Black Box SDK on its own: recording, record-and-replay, overrides, live faults, divergence."""

import json

from fastapi.testclient import TestClient

from tests import sdk_agent

TASK = {"request": "2 people to Goa", "dest": "GOA", "people": 2}


def run(client, **body):
    with client.stream("POST", "/run", json={"task": TASK, **body}) as r:
        assert r.status_code == 200
        events = [json.loads(line) for line in r.iter_lines() if line]
    steps = [e["data"]["step"] for e in events if e["event"] == "step_done"]
    tapes = {e["data"]["step"]["id"]: e["data"]["tape"] for e in events if e["event"] == "step_done"}
    done = next(e["data"] for e in events if e["event"] == "run_done")
    return steps, tapes, done


def cached(steps, tapes, upto):
    return [{"name": s["name"], "output": s["output"], "error": s["error"], "llm": s["llm"], "tape": tapes.get(s["id"])}
            for s in steps[: upto - 1]]


def test_info_and_task():
    c = TestClient(sdk_agent.make_app())
    info = c.get("/info").json()
    assert info["name"] == "minitravel" and info["has_check"]
    assert {t["name"] for t in info["tools"]} >= {"llm", "search_flights", "book_flight"}
    assert info["kinds"] == ["delhi_trip", "family_goa", "goa_trip", "solo_delhi"]
    assert c.post("/task", json={"kind": "goa_trip", "seed": 1}).json()["task"]["people"] == 3


def test_records_every_call_as_a_step():
    c = TestClient(sdk_agent.make_app())
    steps, _, done = run(c)
    assert [s["name"] for s in steps] == ["llm", "search_flights", "llm", "book_flight", "llm"]
    assert done["result"] == {"flight": "6E 2", "total": 160} and done["check"]["ok"]
    search, book = steps[1], steps[3]
    assert search["uses"] == [1]  # asked for by the first LLM call
    assert set(book["uses"]) == {2, 3}  # the LLM call that chose it, and the search whose flight it books
    assert steps[2]["uses"] == [2]  # the second LLM call read the search result
    assert steps[0]["llm"]["tokens_in"] == 50 and search["llm"] is None


def test_replay_reuses_earlier_steps_and_applies_the_edit():
    c = TestClient(sdk_agent.make_app())
    steps, tapes, _ = run(c)
    edited = {"flights": [{"flight": "AI 1", "fare": 100, "seats_ok": True}, {"flight": "6E 2", "fare": 120, "seats_ok": True}]}
    before = sdk_agent.CALLS["llm"]
    new, _, done = run(c, cached=cached(steps, tapes, 2), override={"step": 2, "output": edited})
    assert sdk_agent.CALLS["llm"] - before == 2  # steps 3 and 5 only; step 1 came from the recording
    assert new[1]["output"] == edited
    assert done["result"] == {"flight": "AI 1", "total": 200} and not done["check"]["ok"]
    assert not done["diverged"]


def test_live_fault_changes_one_value():
    c = TestClient(sdk_agent.make_app())
    _, _, done = run(c, fault={"tool": "search_flights", "kind": "number", "seed": 3})
    assert done["fault"]["step_id"] == 2 and "fare" in done["fault"]["detail"]
    assert done["fault"]["original"]["flights"][1]["fare"] == 80


def test_divergence_falls_back_to_live():
    c = TestClient(sdk_agent.make_app())
    steps, tapes, _ = run(c)
    bad = cached(steps, tapes, 3)
    bad[1]["name"] = "something_else"
    _, _, done = run(c, cached=bad, override={"step": 3, "output": steps[2]["output"]})
    assert done["diverged"]


def test_llm_decision_fault_changes_one_argument():
    from blackbox.generic_faults import mutate_args, strings_by_field

    llm_out = {"text": "", "calls": [{"id": "c0", "tool": "book_flight", "args": {"flight": "6E 2", "fare": 80, "people": 2}}]}
    strings = strings_by_field([{"flights": [{"flight": "AI 1"}, {"flight": "6E 2"}]}])
    new, detail = mutate_args(llm_out, "text", 1, strings)
    assert new["calls"][0]["args"]["flight"] == "AI 1" and detail.startswith("book_flight(flight)")
    assert llm_out["calls"][0]["args"]["flight"] == "6E 2"  # the original is untouched
    assert mutate_args({"text": "done", "calls": []}, "number", 1, {}) is None


def test_task_values_do_not_link_steps():
    c = TestClient(sdk_agent.make_app())
    steps, _, _ = run(c)
    # book_flight's people=2 comes from the task, not from the search: it links via the flight and fare only
    assert set(steps[3]["reads"]) == {"llm", "search_flights"}
