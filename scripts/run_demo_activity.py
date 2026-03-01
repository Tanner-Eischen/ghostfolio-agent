"""Run real chat requests through each model to populate observability data.

Calls the backend /agent/config and /chat so usage is logged and traces appear
in LangSmith. Run with backend at BASE_URL (default http://localhost:8002).

Start the backend first, e.g.:
  uvicorn src.api.routes:app --reload --port 8002

Usage:
  python scripts/run_demo_activity.py [--base-url URL] [--requests-per-model N]
  python scripts/run_demo_activity.py --requests-per-model 3   # 3 chats per model
"""

import argparse
import sys
from pathlib import Path

# Project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

# All allowed agent models; uses real OpenAI API (costs a few cents)
ALLOWED_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-3.5-turbo",
    "gpt-4-turbo",
    "gpt-4",
]

DEMO_MESSAGES = [
    "What is my total portfolio value?",
    "Give a brief risk summary.",
    "List my top holdings.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run demo chat requests per model for observability.")
    parser.add_argument("--base-url", default="http://localhost:8002", help="Backend base URL")
    parser.add_argument("--requests-per-model", type=int, default=2, help="Chat requests per model (default 2)")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    total_ok = 0
    total_err = 0
    for model in ALLOWED_MODELS:
        print(f"\n--- Model: {model} ---")
        try:
            r = httpx.put(f"{base}/agent/config", json={"model": model}, timeout=10.0)
            r.raise_for_status()
        except Exception as e:
            print(f"  Config failed: {e}")
            total_err += 1
            continue
        for i in range(args.requests_per_model):
            msg = DEMO_MESSAGES[i % len(DEMO_MESSAGES)]
            try:
                r = httpx.post(
                    f"{base}/chat",
                    json={"message": msg, "session_id": f"demo-{model}-{i}"},
                    timeout=60.0,
                )
                r.raise_for_status()
                total_ok += 1
                print(f"  [{i+1}] OK: {msg[:40]}...")
            except Exception as e:
                total_err += 1
                print(f"  [{i+1}] Error: {e}")

    print(f"\nDone: {total_ok} requests OK, {total_err} failed.")


if __name__ == "__main__":
    main()
