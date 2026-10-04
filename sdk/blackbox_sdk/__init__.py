"""Black Box SDK: connect your own agent to the Black Box app.

    import blackbox_sdk as bb

    @bb.tool
    def search_flights(origin, dest, date): ...

    client = bb.llm(OpenAI(...))          # every LLM call is recorded

    bb.serve(run_agent, name="travel", port=8100, examples=[{"kind": "one_way", "task": {...}}])

Then in the app: Agents -> Connect agent -> http://127.0.0.1:8100. The app can now run the agent,
record every step, plant faults, replay from any step, generate training data and diagnose
failures. Tools should return JSON-like values (a dict is best).
"""

from blackbox_sdk.core import llm, tool
from blackbox_sdk.server import VERSION as __version__
from blackbox_sdk.server import create_app, serve

__all__ = ["llm", "tool", "serve", "create_app", "__version__"]
