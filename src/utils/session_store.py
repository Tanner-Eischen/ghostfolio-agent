"""Persistent storage for chat session history.

Stores conversation messages and session metadata under data/sessions/
so history survives server restarts. Uses LangChain message serialization
(messages_to_dict / messages_from_dict) for messages.

Structure:
- data/sessions/index.json: list of { session_id, message_count, last_accessed }
- data/sessions/<hash(session_id)>.json: { session_id, last_accessed, messages }
"""

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

from src.utils.logging import get_logger

logger = get_logger(__name__)

SESSIONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"
INDEX_FILE = SESSIONS_DIR / "index.json"


def _session_file_name(session_id: str) -> str:
    """Stable filename for a session (safe for all filesystems)."""
    h = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    return f"{h}.json"


class SessionStore:
    """Thread-safe persistent store for chat sessions."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or SESSIONS_DIR
        self.index_path = self.storage_dir / "index.json"
        self._lock = threading.Lock()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index([])

    def _read_index(self) -> list[dict[str, Any]]:
        try:
            with open(self.index_path, encoding="utf-8") as f:
                data = json.load(f)
                return data.get("entries", [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_index(self, entries: list[dict[str, Any]]) -> None:
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump({"entries": entries}, f, indent=2)

    def get_history(self, session_id: str) -> list[BaseMessage]:
        """Load message history for a session. Returns empty list if not found or on error."""
        path = self.storage_dir / _session_file_name(session_id)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("messages", [])
            if not raw:
                return []
            return list(messages_from_dict(raw))
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            logger.debug(f"Session load {session_id}: {e}")
            return []

    def save_history(
        self,
        session_id: str,
        messages: list[BaseMessage],
        last_accessed: str,
    ) -> None:
        """Persist session messages and update index."""
        path = self.storage_dir / _session_file_name(session_id)
        with self._lock:
            payload = {
                "session_id": session_id,
                "last_accessed": last_accessed,
                "messages": messages_to_dict(messages),
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

            entries = self._read_index()
            by_id = {e["session_id"]: e for e in entries}
            by_id[session_id] = {
                "session_id": session_id,
                "message_count": len(messages),
                "last_accessed": last_accessed,
            }
            new_entries = list(by_id.values())
            new_entries.sort(key=lambda x: x.get("last_accessed") or "", reverse=True)
            self._write_index(new_entries)
        logger.debug(f"Saved session {session_id} ({len(messages)} messages)")

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with message_count and last_accessed, most recent first."""
        with self._lock:
            entries = self._read_index()
        return [
            {
                "session_id": e["session_id"],
                "message_count": e.get("message_count", 0),
                "last_accessed": e.get("last_accessed"),
            }
            for e in entries
        ]

    def delete_session(self, session_id: str) -> bool:
        """Remove a session from disk and index. Returns True if it existed."""
        path = self.storage_dir / _session_file_name(session_id)
        with self._lock:
            entries = self._read_index()
            new_entries = [e for e in entries if e["session_id"] != session_id]
            if len(new_entries) == len(entries):
                return False
            self._write_index(new_entries)
            try:
                path.unlink(missing_ok=True)
            except OSError as err:
                logger.warning(f"Could not delete session file {path}: {err}")
        return True
