"""Bridge between user feedback and eval system.

This module provides functions to:
1. Weight eval scores based on user feedback
2. Detect regressions (feedback changed positive to negative)
3. Generate feedback stats per category
4. Link feedback to eval cases for scoring adjustments
"""

from dataclasses import dataclass
from typing import Any

from src.utils.feedback_store import FeedbackEntry, get_feedback_store
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Weight multipliers for feedback
FEEDBACK_WEIGHTS = {
    "positive": 0.1,  # +10% bonus for thumbs up
    "negative": -0.2,  # -20% penalty for thumbs down
}


@dataclass
class FeedbackAdjustedScore:
    """Score adjusted by user feedback."""

    original_score: float
    adjusted_score: float
    feedback_count: int
    positive_count: int
    negative_count: int
    adjustment_reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_score": self.original_score,
            "adjusted_score": self.adjusted_score,
            "feedback_count": self.feedback_count,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "adjustment_reason": self.adjustment_reason,
        }


def get_feedback_for_eval_case(eval_case_id: str) -> list[FeedbackEntry]:
    """Get all feedback linked to an eval case.

    Args:
        eval_case_id: The eval case ID

    Returns:
        List of FeedbackEntry objects
    """
    store = get_feedback_store()
    return store.get_feedback_for_eval(eval_case_id)


def adjust_score_by_feedback(
    base_score: float,
    eval_case_id: str | None = None,
    session_id: str | None = None,
    message_ids: list[str] | None = None,
) -> FeedbackAdjustedScore:
    """Adjust a score based on user feedback.

    The adjustment applies weights based on feedback:
    - Thumbs up: +10% bonus
    - Thumbs down: -20% penalty

    Args:
        base_score: Original score (0.0 to 1.0)
        eval_case_id: Optional eval case ID to filter feedback
        session_id: Optional session ID to filter feedback
        message_ids: Optional list of message IDs to filter feedback

    Returns:
        FeedbackAdjustedScore with adjusted value
    """
    store = get_feedback_store()

    # Collect feedback entries
    feedback_entries: list[FeedbackEntry] = []

    if eval_case_id:
        feedback_entries.extend(store.get_feedback_for_eval(eval_case_id))

    if session_id:
        feedback_entries.extend(store.get_feedback_by_session(session_id))

    if message_ids:
        for mid in message_ids:
            entry = store.get_feedback_by_message_id(mid)
            if entry:
                feedback_entries.append(entry)

    # Deduplicate by ID
    seen_ids = set()
    unique_entries = []
    for entry in feedback_entries:
        if entry.id not in seen_ids:
            seen_ids.add(entry.id)
            unique_entries.append(entry)

    feedback_entries = unique_entries

    if not feedback_entries:
        return FeedbackAdjustedScore(
            original_score=base_score,
            adjusted_score=base_score,
            feedback_count=0,
            positive_count=0,
            negative_count=0,
            adjustment_reason="No feedback available",
        )

    # Count positive and negative feedback
    positive_count = sum(1 for e in feedback_entries if e.rating > 0)
    negative_count = sum(1 for e in feedback_entries if e.rating < 0)
    total_count = len(feedback_entries)

    # Calculate adjustment
    adjustment = 0.0
    if positive_count > 0:
        adjustment += FEEDBACK_WEIGHTS["positive"] * (positive_count / total_count)
    if negative_count > 0:
        adjustment += FEEDBACK_WEIGHTS["negative"] * (negative_count / total_count)

    adjusted_score = max(0.0, min(1.0, base_score + adjustment))

    reason_parts = []
    if positive_count > 0:
        reason_parts.append(f"+{positive_count} positive")
    if negative_count > 0:
        reason_parts.append(f"-{negative_count} negative")
    adjustment_reason = f"Feedback adjustment ({', '.join(reason_parts)})"

    return FeedbackAdjustedScore(
        original_score=base_score,
        adjusted_score=adjusted_score,
        feedback_count=total_count,
        positive_count=positive_count,
        negative_count=negative_count,
        adjustment_reason=adjustment_reason,
    )


def detect_regressions(
    historical_feedback: dict[str, list[FeedbackEntry]],
) -> list[dict[str, Any]]:
    """Detect cases where feedback changed from positive to negative.

    Args:
        historical_feedback: Dict mapping eval_case_id to list of feedback entries

    Returns:
        List of regression reports
    """
    regressions = []

    for eval_case_id, entries in historical_feedback.items():
        # Sort by timestamp
        sorted_entries = sorted(entries, key=lambda e: e.timestamp)

        if len(sorted_entries) < 2:
            continue

        # Look for positive -> negative transitions
        for i in range(1, len(sorted_entries)):
            prev = sorted_entries[i - 1]
            curr = sorted_entries[i]

            if prev.rating > 0 and curr.rating < 0:
                regressions.append({
                    "eval_case_id": eval_case_id,
                    "regression_timestamp": curr.timestamp,
                    "previous_rating": prev.rating,
                    "current_rating": curr.rating,
                    "session_id": curr.session_id,
                    "comment": curr.comment,
                })

    return regressions


def get_feedback_stats_by_category(
    eval_cases: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Get feedback statistics grouped by eval category.

    Args:
        eval_cases: List of eval cases with 'id' and 'category' fields

    Returns:
        Dict mapping category to feedback stats
    """
    store = get_feedback_store()
    stats: dict[str, dict[str, Any]] = {}

    # Group eval cases by category
    by_category: dict[str, list[str]] = {}
    for case in eval_cases:
        cat = case.get("category", "unknown")
        case_id = case.get("id", "")
        if cat not in by_category:
            by_category[cat] = []
        if case_id:
            by_category[cat].append(case_id)

    # Get feedback for each category
    for cat, case_ids in by_category.items():
        positive = 0
        negative = 0
        total_feedback = 0

        for case_id in case_ids:
            entries = store.get_feedback_for_eval(case_id)
            for entry in entries:
                total_feedback += 1
                if entry.rating > 0:
                    positive += 1
                elif entry.rating < 0:
                    negative += 1

        stats[cat] = {
            "total_evals": len(case_ids),
            "total_feedback": total_feedback,
            "positive": positive,
            "negative": negative,
            "positive_rate": positive / total_feedback if total_feedback > 0 else None,
        }

    return stats


def link_session_feedback_to_evals(
    session_id: str,
    eval_case_ids: list[str],
) -> int:
    """Link all feedback from a session to specific eval cases.

    This is useful when running evals that correspond to a chat session.
    Links the session's feedback to the eval cases for scoring.

    Args:
        session_id: The session ID
        eval_case_ids: List of eval case IDs to link to

    Returns:
        Number of feedback entries linked
    """
    store = get_feedback_store()
    entries = store.get_feedback_by_session(session_id)

    linked_count = 0
    for entry in entries:
        # Link to all eval cases (could be smarter about this)
        for eval_case_id in eval_case_ids:
            if store.link_feedback_to_eval(entry.message_id, eval_case_id):
                linked_count += 1

    return linked_count


__all__ = [
    "adjust_score_by_feedback",
    "detect_regressions",
    "get_feedback_stats_by_category",
    "get_feedback_for_eval_case",
    "link_session_feedback_to_evals",
    "FeedbackAdjustedScore",
]
