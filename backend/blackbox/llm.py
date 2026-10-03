"""The one place that calls the LLM: request pacing, 429 handling, and timing/token stats."""

import re
import threading
import time

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from blackbox import config


class QuotaExhausted(Exception):
    """The provider's daily request cap was hit; generation should stop and resume later."""


_client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY, max_retries=0)
_lock = threading.Lock()
_next_slot = 0.0  # shared across threads, so parallel workers respect one per-minute limit


def _wait_for_slot() -> None:
    global _next_slot
    with _lock:
        now = time.monotonic()
        wait = _next_slot - now
        _next_slot = max(now, _next_slot) + 60 / config.REQUESTS_PER_MINUTE
    if wait > 0:
        time.sleep(wait)


def _retry_delay(text: str) -> float:
    match = re.search(r"retry in ([\d.]+)s", text)
    return float(match.group(1)) + 1 if match else 15.0


def chat(messages: list[dict], tools: list[dict]) -> tuple[dict, dict]:
    """One LLM call. Returns (assistant message as a dict, {latency_ms, tokens_in, tokens_out})."""
    for attempt in range(6):
        _wait_for_slot()
        start = time.perf_counter()
        try:
            resp = _client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=messages,
                tools=tools,
                temperature=config.TEMPERATURE,
                reasoning_effort=config.REASONING_EFFORT,
            )
        except RateLimitError as e:
            text = e.response.text
            if "PerDay" in text:
                raise QuotaExhausted(text) from e
            time.sleep(_retry_delay(text))
            continue
        except (APIConnectionError, APIStatusError) as e:
            if isinstance(e, APIStatusError) and e.status_code < 500:
                raise
            time.sleep(2 ** attempt)
            continue
        latency_ms = int((time.perf_counter() - start) * 1000)
        # exclude_none keeps provider extras (Gemini's thought signatures) that must be sent back
        message = resp.choices[0].message.model_dump(exclude_none=True)
        usage = resp.usage
        stats = {
            "latency_ms": latency_ms,
            "tokens_in": usage.prompt_tokens if usage else 0,
            "tokens_out": usage.completion_tokens if usage else 0,
        }
        return message, stats
    raise RuntimeError("LLM call failed after 6 attempts")
