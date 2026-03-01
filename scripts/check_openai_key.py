"""Confirm OPENAI_API_KEY is in .env and (if possible) that Settings loads it.

Uses the same project-root .env path as src.utils.config so it works from any cwd.
If pydantic fails to import (e.g. version mismatch), at least .env presence is reported.
"""
from pathlib import Path

# Same resolution as config.py: project root = parent of dir containing this script's parent (scripts/)
_project_root = Path(__file__).resolve().parent.parent
_env_path = _project_root / ".env"

if not _env_path.exists():
    print("No .env file at", _env_path)
    exit(1)

key = None
for line in _env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
    line = line.strip()
    if line.startswith("OPENAI_API_KEY="):
        raw = line.split("=", 1)[1].strip()
        key = raw.strip('"').strip("'")
        break

loaded_in_file = bool(key and len(key) > 10)
print("OPENAI_API_KEY in .env:", loaded_in_file)
if loaded_in_file:
    print("  Length:", len(key), "  Prefix:", key[:12] + "...")
else:
    print("  (missing or too short)")

try:
    from src.utils.config import get_settings
    s = get_settings()
    from_config = bool((s.openai_api_key or "").strip())
    print("Loaded via get_settings():", from_config)
    if loaded_in_file and not from_config:
        print("  -> Key is in .env but Settings did not load it. Check pydantic/pydantic-settings versions (need pydantic>=2.10).")
except Exception as e:
    print("Config check skipped:", type(e).__name__, "-", e)
