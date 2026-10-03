"""P0 check: the API key works, one tool call succeeds, and the rate limits are printed.

Run with: python -m blackbox.check_llm
"""

import json
import time

from openai import OpenAI

from blackbox import config

TOOLS = [{
    "type": "function",
    "function": {
        "name": "parse_order",
        "description": "Record the customer's parsed pizza order.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {"type": "array", "items": {"type": "object", "properties": {
                    "pizza": {"type": "string"},
                    "size": {"type": "string", "enum": ["S", "M", "L"]},
                    "qty": {"type": "integer"}},
                    "required": ["pizza", "size", "qty"]}},
                "coupon": {"type": ["string", "null"]},
                "area": {"type": "string"},
            },
            "required": ["items", "coupon", "area"],
        },
    },
}]


def main() -> None:
    if not config.LLM_API_KEY:
        raise SystemExit(f"No API key for provider {config.PROVIDER}: set it in backend/.env")
    client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
    start = time.perf_counter()
    raw = client.chat.completions.with_raw_response.create(
        model=config.LLM_MODEL,
        temperature=config.TEMPERATURE,
        messages=[
            {"role": "system", "content": "You are a pizza ordering agent. Parse the order with parse_order. Pizza ids are snake_case."},
            {"role": "user", "content": "2 large pepperoni and 1 medium veg supreme, code PIZZA20, deliver to Kothrud"},
        ],
        tools=TOOLS,
        tool_choice={"type": "function", "function": {"name": "parse_order"}},
    )
    elapsed = (time.perf_counter() - start) * 1000
    resp = raw.parse()
    call = resp.choices[0].message.tool_calls[0]
    print(f"provider={config.PROVIDER} model={config.LLM_MODEL} latency={elapsed:.0f}ms")
    print(f"tokens in={resp.usage.prompt_tokens} out={resp.usage.completion_tokens}")
    print(f"tool call: {call.function.name}{json.dumps(json.loads(call.function.arguments))}")
    print("rate limits:")
    for key, value in raw.headers.items():
        if key.lower().startswith("x-ratelimit"):
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
