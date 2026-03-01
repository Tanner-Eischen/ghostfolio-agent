"""Local feedback storage for the eval framework.

Stores user feedback (thumbs up/down) locally in JSON format and provides
integration with the eval system. This bridges the gap between the UI
feedback mechanism and eval scoring.

Storage structure:
    data/feedback/feedback_log.json - Main feedback log

Each feedback entry contains:
- id: Unique feedback ID
- message_id: LangSmith run ID (used to link to evals)
- session_id: Chat session ID
- rating: -1 (thumbs down) or 1 (thumbs up)
- timestamp: When feedback was submitted
- comment: Optional user comment
- eval_case_id: Optional link to eval case
- tool_calls: Tool calls from the response (for context)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import threading

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Storage paths
FEEDBACK_DIR = Path(__file__).parent.parent.parent / "data" / "feedback"
FEEDBACK_LOG_FILE = FEEDBACK_DIR / "feedback_log.json"


@dataclass
class FeedbackEntry:
    """A single feedback entry."""

    id: str
    message_id: str  # LangSmith run ID
    session_id: str
    rating: int  # -1 (down) or 1 (up)
    timestamp: str
    comment: str = ""
    eval_case_id: str | None = None
    tool_calls: list[str] = field(default_factory=list)
    response_preview: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FeedbackEntry":
        return cls(
            id=data.get("id", ""),
            message_id=data.get("message_id", ""),
            session_id=data.get("session_id", ""),
            rating=data.get("rating", 0),
            timestamp=data.get("timestamp", ""),
            comment=data.get("comment", ""),
            eval_case_id=data.get("eval_case_id"),
            tool_calls=data.get("tool_calls", []),
            response_preview=data.get("response_preview", ""),
            metadata=data.get("metadata", {}),
        )


class FeedbackStore:
    """Thread-safe local storage for user feedback."""

    def __init__(self, storage_path: Path | None = None):
        """Initialize the feedback store.

        Args:
            storage_path: Optional custom storage path (for testing)
        """
        self.storage_path = storage_path or FEEDBACK_LOG_FILE
        self._lock = threading.Lock()
        self._ensure_storage_exists()

    def _ensure_storage_exists(self) -> None:
        """Ensure the storage directory and file exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._write_entries([])

    def _read_entries(self) -> list[dict[str, Any]]:
        """Read all entries from storage."""
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("entries", [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _write_entries(self, entries: list[dict[str, Any]]) -> None:
        """Write entries to storage."""
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump({"entries": entries}, f, indent=2)

    def store_feedback(
        self,
        message_id: str,
        session_id: str,
        rating: int,
        comment: str = "",
        tool_calls: list[str] | None = None,
        response_preview: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> FeedbackEntry:
        """Store a feedback entry.

        Args:
            message_id: LangSmith run ID
            session_id: Chat session ID
            rating: -1 (thumbs down) or 1 (thumbs up)
            comment: Optional user comment
            tool_calls: List of tool names used in the response
            response_preview: First 200 chars of the response
            metadata: Additional metadata

        Returns:
            The created FeedbackEntry
        """
        feedback_id = f"fb_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{message_id[:8]}"

        entry = FeedbackEntry(
            id=feedback_id,
            message_id=message_id,
            session_id=session_id,
            rating=rating,
            timestamp=datetime.now(timezone.utc).isoformat(),
            comment=comment,
            tool_calls=tool_calls or [],
            response_preview=response_preview[:200] if response_preview else "",
            metadata=metadata or {},
        )

        with self._lock:
            entries = self._read_entries()
            entries.append(entry.to_dict())
            self._write_entries(entries)

        logger.info(f"Stored feedback {feedback_id}: rating={rating}, message_id={message_id}")
        return entry

    def get_feedback_for_eval(self, eval_case_id: str) -> list[FeedbackEntry]:
        """Get all feedback linked to a specific eval case.

        Args:
            eval_case_id: The eval case ID to filter by

        Returns:
            List of FeedbackEntry objects
        """
        entries = self._read_entries()
        return [
            FeedbackEntry.from_dict(e)
            for e in entries
            if e.get("eval_case_id") == eval_case_id
        ]

    def get_feedback_by_message_id(self, message_id: str) -> FeedbackEntry | None:
        """Get feedback by message ID (LangSmith run ID).

        Args:
            message_id: The LangSmith run ID

        Returns:
            FeedbackEntry or None if not found
        """
        entries = self._read_entries()
        for e in entries:
            if e.get("message_id") == message_id:
                return FeedbackEntry.from_dict(e)
        return None

    def get_feedback_by_session(self, session_id: str) -> list[FeedbackEntry]:
        """Get all feedback for a session.

        Args:
            session_id: The session ID

        Returns:
            List of FeedbackEntry objects
        """
        entries = self._read_entries()
        return [
            FeedbackEntry.from_dict(e)
            for e in entries
            if e.get("session_id") == session_id
        ]

    def link_feedback_to_eval(self, message_id: str, eval_case_id: str) -> bool:
        """Link an existing feedback entry to an eval case.

        Args:
            message_id: The message ID to link
            eval_case_id: The eval case ID to link to

        Returns:
            True if linked successfully, False if not found
        """
        with self._lock:
            entries = self._read_entries()
            found = False
            for e in entries:
                if e.get("message_id") == message_id:
                    e["eval_case_id"] = eval_case_id
                    found = True
                    break
            if found:
                self._write_entries(entries)
                logger.info(f"Linked feedback {message_id} to eval {eval_case_id}")
            return found

    def get_feedback_stats(self) -> dict[str, Any]:
        """Get overall feedback statistics.

        Returns:
            Dict with stats: total, thumbs_up, thumbs_down, by_tool
        """
        entries = self._read_entries()

        total = len(entries)
        thumbs_up = sum(1 for e in entries if e.get("rating", 0) > 0)
        thumbs_down = sum(1 for e in entries if e.get("rating", 0) < 0)

        # Count by tool
        tool_stats: dict[str, dict[str, int]] = {}
        for e in entries:
            for tool in e.get("tool_calls", []):
                if tool not in tool_stats:
                    tool_stats[tool] = {"up": 0, "down": 0}
                if e.get("rating", 0) > 0:
                    tool_stats[tool]["up"] += 1
                elif e.get("rating", 0) < 0:
                    tool_stats[tool]["down"] += 1

        return {
            "total": total,
            "thumbs_up": thumbs_up,
            "thumbs_down": thumbs_down,
            "positive_rate": thumbs_up / total if total > 0 else 0,
            "by_tool": tool_stats,
        }

    def get_recent_feedback(self, limit: int = 100) -> list[FeedbackEntry]:
        """Get recent feedback entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of FeedbackEntry objects, most recent first
        """
        entries = self._read_entries()
        # Sort by timestamp descending
        sorted_entries = sorted(
            entries,
            key=lambda e: e.get("timestamp", ""),
            reverse=True,
        )
        return [FeedbackEntry.from_dict(e) for e in sorted_entries[:limit]]

    def clear_all(self) -> None:
        """Clear all feedback entries (for testing)."""
        with self._lock:
            self._write_entries([])


# Singleton instance
_store_instance: FeedbackStore | None = None


def get_feedback_store() -> FeedbackStore:
    """Get the singleton FeedbackStore instance."""
    global _store_instance
    if _store_instance is None:
        _store_instance = FeedbackStore()
    return _store_instance


__all__ = [
    "FeedbackStore",
    "FeedbackEntry",
    "get_feedback_store",
]
