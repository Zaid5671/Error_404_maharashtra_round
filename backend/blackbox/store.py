"""Run files on disk: runs/<agent>/<run_id>.json."""

import json
from pathlib import Path

from blackbox import config


def run_path(agent: str, run_id: str) -> Path:
    return config.RUNS_DIR / agent / f"{run_id}.json"


def save_run(run: dict) -> Path:
    path = run_path(run["agent"], run["run_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_run(agent: str, run_id: str) -> dict:
    return json.loads(run_path(agent, run_id).read_text(encoding="utf-8"))


def list_runs(agent: str) -> list[Path]:
    return sorted((config.RUNS_DIR / agent).glob("*.json"))
