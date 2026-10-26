"""Smoke test: 3 tiny calls through Colosseum's GeminiClient. Setup check only, not results."""
import os
import sys
import time

# Honest test of the real path: do NOT preload the key; GeminiClient's own load_dotenv decides.
from llm_server.clients.gemini_client import GeminiClient

model = sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-flash"
try:
    client = GeminiClient()
except Exception as e:
    print("CLIENT INIT FAILED:", type(e).__name__, str(e)[:200])
    sys.exit(1)
print("client init ok; key found via client's own load_dotenv:", bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")))

usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
calls = ok = 0
prompts = [
    "Reply with exactly the word: pong",
    "In one short sentence, what is a blackboard in multi-agent systems?",
    "Name two colours, comma separated, nothing else.",
]
for p in prompts:
    calls += 1
    t = time.time()
    try:
        resp, text = client.generate_response(
            input=client.init_context("You are terse.", p),
            params={"model": model, "max_tokens": 200, "temperature": 0.0},
        )
        usage = client.get_usage(resp, usage)
        ok += 1
        print(f"call {calls} ok {time.time()-t:.1f}s -> {text.strip()[:100]!r}")
    except Exception as e:
        print(f"call {calls} FAILED {type(e).__name__}: {str(e)[:300]}")
    time.sleep(7)  # stay well under free-tier per-minute limits

print(f"model={model} calls={calls} ok={ok} usage={usage}")
