"""Feedback endpoints for Ghostfolio Agent API.

Feedback submission and management.
"""

from fastapi import APIRouter

from src.api.models import FeedbackRequest, FeedbackResponse
from src.utils.logging import get_logger
from src.utils.tracing import log_feedback

router = APIRouter()
logger = get_logger(__name__)


@router.post("/feedback", response_model=FeedbackResponse, tags=["Feedback"])
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Submit feedback on a response.

    Sends feedback to LangSmith and stores it locally for evaluation.

    Args:
        request: Feedback request with message_id, rating, and optional comment

    Returns:
        Feedback submission status
    """
    logged = False
    stored_locally = False

    # Try to log to LangSmith
    try:
        if request.message_id:
            # Convert rating to score
            if request.rating == -1:
                score = 0.0
            elif request.rating == 1:
                score = 1.0
            else:
                score = request.rating / 5.0

            # Log to LangSmith
            log_feedback(
                run_id=request.message_id,
                key="user_rating",
                score=score,
                comment=request.comment,
            )
            logged = True
            logger.info(f"Feedback logged: message={request.message_id}, rating={request.rating}")

    except Exception as e:
        logger.warning(f"Could not log feedback to LangSmith: {e}")

    # Store feedback locally for eval integration
    try:
        from src.utils.feedback_store import get_feedback_store

        store = get_feedback_store()
        store.store_feedback(
            message_id=request.message_id,
            session_id=request.session_id,
            rating=request.rating,
            comment=request.comment or "",
        )
        stored_locally = True
        logger.info(f"Feedback stored locally: message={request.message_id}")

    except Exception as e:
        logger.warning(f"Could not store feedback locally: {e}")

    return FeedbackResponse(
        status="received",
        message_id=request.message_id,
        logged=logged or stored_locally,
    )
