"""OpenRouter smoke test via LLM-Trust-Breaking's own client. 3 calls. Setup check, not results."""
import sys
import time

REPO = r"<repo>\LLM-Trust-Breaking"
sys.path.insert(0, REPO)
from dotenv import dotenv_values
from src.llm.client_factory import create_llm_clients

model = sys.argv[1]
key = dotenv_values(REPO + r"\.env").get("OPENROUTER_API_KEY")
llm, _par = create_llm_clients(model=model, openrouter_api_key=key, openai_api_key=None, temperature=0.0)

calls = ok = 0


def run(label, fn):
    global calls, ok
    calls += 1
    t = time.time()
    try:
        out = fn()
        ok += 1
        print(f"call {calls} [{label}] ok {time.time()-t:.1f}s -> {str(out).strip()[:110]!r}")
    except Exception as e:
        print(f"call {calls} [{label}] FAILED {type(e).__name__}: {str(e)[:300]}")
    time.sleep(4)  # free tier: 20 req/min


run("simple", lambda: llm.call_simple("You are terse.", "Reply with exactly the word: pong", max_tokens=200))
run("simple", lambda: llm.call_simple("You are terse.", "Name two colours, comma separated, nothing else.", max_tokens=200))
schema = {
    "name": "choice",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {"action": {"type": "string", "enum": ["cooperate", "defect"]}},
        "required": ["action"],
        "additionalProperties": False,
    },
}
run("json_schema", lambda: llm.call_with_json_schema("You are an agent.", "Choose an action.", schema, max_tokens=200))
print(f"model={model} calls={calls} ok={ok}")
