"""LLM provider and model for the agents. Switching provider is a one-line change to PROVIDER."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

PROVIDER = os.getenv("LLM_PROVIDER", "gemini")  # "gemini", "groq" (demo backup) or "ollama"

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "api_key": os.getenv("GROQ_API_KEY", ""),
        "model": "openai/gpt-oss-120b",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model": "gemini-3.5-flash-lite",
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
REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "medium")  # "none", "low", "medium", "high"
REQUESTS_PER_MINUTE = int(os.getenv("LLM_RPM", "14"))  # free tier: 15 per model; paid tier is much higher
MAX_LLM_CALLS = 12  # per run; a run that hits this ends without finishing its task
