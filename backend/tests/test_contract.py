import json

from blackbox import config
from blackbox.contract import Diagnosis, Run


def load(name):
    return json.loads((config.SAMPLE_DIR / name).read_text(encoding="utf-8"))


def test_sample_run_matches_contract():
    run = Run.model_validate(load("sample_run.json"))
    assert [s.id for s in run.steps] == list(range(1, len(run.steps) + 1))
    for step in run.steps:
        assert all(u < step.id for u in step.uses)
        assert step.msg_index <= len(run.messages)


def test_sample_diagnosis_matches_contract():
    diag = Diagnosis.model_validate(load("sample_diagnosis.json"))
    run = Run.model_validate(load("sample_run.json"))
    assert diag.run_id == run.run_id
    assert diag.culprit == run.fault.step_id
