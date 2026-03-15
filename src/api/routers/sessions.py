"""Session endpoints for Ghostfolio Agent API.

Session management and conversation history.
"""


from fastapi import APIRouter, HTTPException

from src.api.models import SessionHistoryResponse, SessionsListResponse, SessionSummary
from src.utils.logging import get_logger
from src.utils.session_store import SessionStore

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
    raw_sessions = store.list_sessions()

    session_summaries = []
    for s in raw_sessions:
        session_id = s["session_id"]
        history = store.get_history(session_id)
        if history:
            last_accessed = s.get("last_accessed") or ""
            session_summaries.append(SessionSummary(
                session_id=session_id,
                message_count=len(history),
                created_at=last_accessed,
                last_activity=last_accessed,
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

    # Calculate session creation time from message metadata
    first_msg = history[0]
    created_at = ""
    if hasattr(first_msg, "additional_kwargs"):
        created_at = first_msg.additional_kwargs.get("timestamp", "")

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
