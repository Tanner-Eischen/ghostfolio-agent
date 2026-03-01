#!/usr/bin/env python3
"""Start uvicorn using PORT from environment (Railway injects PORT at runtime)."""
import os
import sys

port = int(os.environ.get("PORT", "8000"))
host = "0.0.0.0"
print(f"Starting on {host}:{port}", flush=True)
sys.stdout.flush()
sys.stderr.flush()

import uvicorn
uvicorn.run(
    "src.api.routes:app",
    host=host,
    port=port,
    factory=False,
)
