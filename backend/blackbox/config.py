"""LLM provider, model and paths. Switching provider is a one-line change to PROVIDER."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq" or "ollama" (fallback)

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "model": "openai/gpt-oss-120b",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "api_key": "ollama",
        "model": "llama3.1",
    },
}

LLM_BASE_URL = PROVIDERS[PROVIDER]["base_url"]
LLM_API_KEY = PROVIDERS[PROVIDER]["api_key"]
LLM_MODEL = os.getenv("LLM_MODEL", PROVIDERS[PROVIDER]["model"])
TEMPERATURE = 0

DATA_DIR = BACKEND_DIR / "blackbox" / "data"
RUNS_DIR = BACKEND_DIR / "runs"
MODELS_DIR = BACKEND_DIR / "models"
REPORTS_DIR = BACKEND_DIR / "reports"
SAMPLE_DIR = BACKEND_DIR.parent / "frontend" / "src" / "sample"
