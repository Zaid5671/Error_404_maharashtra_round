"""Black Box paths. Nothing here depends on a particular agent."""

from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = BACKEND_DIR / "runs"  # runs/<agent>/<run_id>.json
MODELS_DIR = BACKEND_DIR / "models"
REPORTS_DIR = BACKEND_DIR / "reports"
SAMPLE_DIR = BACKEND_DIR.parent / "frontend" / "src" / "sample"
