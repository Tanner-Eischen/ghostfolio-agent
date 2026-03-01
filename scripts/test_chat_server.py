"""Call the chat API (server must be running). Use for quick e2e/server checks.

  python scripts/test_chat_server.py
  python scripts/test_chat_server.py --base-url http://localhost:8002 --message "hey"
  python scripts/test_chat_server.py --message "What's my portfolio value?"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

DEFAULT_BASE = "http://localhost:8002"
MESSAGES = [
    "hey",
    "What's my portfolio value?",
    "What is diversification?",
]


def main():
    p = argparse.ArgumentParser(description="Test chat endpoint via HTTP")
    p.add_argument("--base-url", default=DEFAULT_BASE, help=f"API base URL (default {DEFAULT_BASE})")
    p.add_argument("--message", help="Single message to send (default: run a few canned messages)")
    args = p.parse_args()
    base = args.base_url.rstrip("/")
    url = f"{base}/chat"
    messages = [args.message] if args.message else MESSAGES

    for msg in messages:
        try:
            r = httpx.post(url, json={"message": msg}, timeout=60.0)
            r.raise_for_status()
            data = r.json()
            resp_text = data.get("response", "")[:300]
            print(f"[{r.status_code}] message: {msg!r}")
            print(f"  response: {resp_text}...")
            print()
        except httpx.HTTPStatusError as e:
            print(f"[{e.response.status_code}] message: {msg!r}")
            print(f"  error: {e.response.text[:200]}")
            print()
        except Exception as e:
            print(f"  failed: {e}")
            print()
            sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
