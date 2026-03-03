"""Session endpoints for Ghostfolio Agent API.

Session management and conversation history.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.api.models import SessionsListResponse, SessionHistoryResponse, SessionSummary
from src.utils.session_store import SessionStore
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


def get_session_store() -> SessionStore:
    """Get the session store instance."""
    return SessionStore()


@router.get("/sessions", response_model=SessionsListResponse, tags=["Sessions"])
async def list_sessions() -> SessionsListResponse:
    """List all conversation sessions.

    Returns a list of all sessions with summary information.

    Returns:
        List of sessions with summaries
    """
    store = get_session_store()
    sessions = store.list_sessions()

    session_summaries = []
    for session_id in sessions:
        history = store.get_history(session_id)
        if history:
            first_msg = history[0] if history else None
            last_msg = history[-1] if history else None

            session_summaries.append(SessionSummary(
                session_id=session_id,
                message_count=len(history),
                created_at=first_msg.get("timestamp", "") if first_msg else "",
                last_activity=last_msg.get("timestamp", "") if last_msg else "",
            ))

    return SessionsListResponse(
        sessions=session_summaries,
        total=len(session_summaries),
    )


@router.get("/sessions/{session_id}", response_model=SessionHistoryResponse, tags=["Sessions"])
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    """Get conversation history for a session.

    Args:
        session_id: Session ID to retrieve

    Returns:
        Session history with all messages
    """
    store = get_session_store()
    history = store.get_history(session_id)

    if not history:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Calculate session creation time
    created_at = history[0].get("timestamp", "") if history else ""

    return SessionHistoryResponse(
        session_id=session_id,
        messages=history,
        created_at=created_at,
    )


@router.delete("/sessions/{session_id}", tags=["Sessions"])
async def clear_session(session_id: str) -> dict[str, str]:
    """Clear a conversation session.

    Args:
        session_id: Session ID to clear

    Returns:
        Confirmation message
    """
    store = get_session_store()
    store.clear_session(session_id)
    logger.info(f"Cleared session: {session_id}")

    return {"status": "cleared", "session_id": session_id}
