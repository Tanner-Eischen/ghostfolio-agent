"""Chat endpoints for Ghostfolio Agent API.

Main chat endpoint and related functionality.
"""

import uuid

from fastapi import APIRouter

from src.api.dependencies import add_latency_sample, get_agent, increment_chat_request_count
from src.api.models import ChatRequest, ChatResponse
from src.exceptions import get_friendly_error_message
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with the Ghostfolio Agent.

    Send a natural language query about your portfolio and receive
    an AI-powered response with confidence scoring and verification.
    Always returns 200 with a conversational message (never 400/500 to the client).
    """
    session_id = request.session_id or str(uuid.uuid4())
    try:
        agent = get_agent()
        result = await agent.chat_with_context(
            message=request.message,
            session_id=session_id,
            user_id=request.user_id,
            context=None,
        )

        # Track metrics
        increment_chat_request_count()
        pt_ms = result.get("metadata", {}).get("processing_time_ms")
        if pt_ms is not None:
            add_latency_sample(float(pt_ms))

        invocations = result.get("tool_invocations", [])
        if invocations:
            for inv in invocations:
                logger.info(
                    "chat tool_invocation call=%s output_type=%s",
                    inv.get("call"),
                    type(inv.get("output")).__name__,
                    extra={"tool_invocation": inv},
                )

        return ChatResponse(
            response=result["message"],
            confidence=result["confidence"],
            confidence_level=result["confidence_level"],
            tool_calls=result["tool_calls"],
            tool_outputs=result.get("tool_outputs", []),
            tool_invocations=invocations,
            session_id=result["session_id"],
            verification_passed=result["verification_passed"],
            requires_escalation=result["requires_escalation"],
            processing_time_ms=result["metadata"].get("processing_time_ms", 0),
            run_id=result.get("run_id"),
            trace_url=result.get("trace_url"),
        )

    except Exception as e:
        logger.exception("Chat error: %s", e)
        friendly = get_friendly_error_message(e)
        return ChatResponse(
            response=friendly,
            confidence=0.0,
            confidence_level="VERY_LOW",
            tool_calls=[],
            tool_outputs=[],
            tool_invocations=[],
            session_id=session_id,
            verification_passed=False,
            requires_escalation=True,
            processing_time_ms=0.0,
            run_id=None,
            trace_url=None,
        )


@router.get("/chat/tools", tags=["Chat"])
async def list_tools() -> list[dict[str, str]]:
    """List available agent tools.

    Returns descriptions of all tools the agent can use.
    """
    agent = get_agent()
    return agent.get_tool_descriptions()
