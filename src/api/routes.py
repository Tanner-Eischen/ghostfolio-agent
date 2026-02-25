"""FastAPI routes for Ghostfolio Agent API.

This module provides REST API endpoints for the Ghostfolio Agent:
- /health - Health check and dependency status
- /chat - Main chat endpoint with agent
- /feedback - Submit feedback to LangSmith
- /portfolio - Quick portfolio summary
- /sessions - Conversation history management

Task #15: Create FastAPI backend
"""

from contextlib import asynccontextmanager
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent import GhostfolioAgent
from src.utils.config import get_settings
from src.utils.logging import get_logger, setup_logging
from src.utils.tracing import log_feedback, is_tracing_enabled

logger = get_logger(__name__)
settings = get_settings()

# Global agent instance
_agent: GhostfolioAgent | None = None


def get_agent() -> GhostfolioAgent:
    """Get or initialize the agent singleton."""
    global _agent
    if _agent is None:
        logger.info("Initializing GhostfolioAgent...")
        _agent = GhostfolioAgent(
            model="gpt-4o-mini",
            temperature=0.0,
            use_verification=True,
            verification_strict_mode=False,
            enable_tracing=True,
        )
        logger.info("GhostfolioAgent initialized successfully")
    return _agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging()
    logger.info(f"Starting Ghostfolio Agent API in {settings.environment} mode")

    # Pre-initialize agent on startup
    try:
        get_agent()
        logger.info("Agent pre-initialized on startup")
    except Exception as e:
        logger.warning(f"Could not pre-initialize agent: {e}")

    yield

    logger.info("Shutting down Ghostfolio Agent API")


app = FastAPI(
    title="Ghostfolio Agent API",
    description="AI-powered portfolio assistant for Ghostfolio",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware - allow Railway frontends via regex
_cors_kw: dict[str, Any] = {
    "allow_origins": settings.cors_origins_list,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.cors_origin_regex and settings.cors_origin_regex.strip():
    _cors_kw["allow_origin_regex"] = settings.cors_origin_regex
app.add_middleware(CORSMiddleware, **_cors_kw)


# ============================================================================
# Request/Response Models
# ============================================================================


class ChatRequest(BaseModel):
    """Chat request model."""

    message: str = Field(..., min_length=1, max_length=10000, description="User message")
    session_id: str | None = Field(None, description="Session ID for conversation continuity")
    user_id: str | None = Field(None, description="Optional user identifier")


class ChatResponse(BaseModel):
    """Chat response model."""

    response: str = Field(..., description="Agent response text")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    confidence_level: str = Field(..., description="Confidence level label")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tools invoked")
    session_id: str = Field(..., description="Session ID for follow-up queries")
    verification_passed: bool = Field(default=True, description="Whether verification passed")
    requires_escalation: bool = Field(default=False, description="Whether human review recommended")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment (development/staging/production)")
    agent_ready: bool = Field(..., description="Whether agent is initialized")
    dependencies: dict[str, bool] = Field(..., description="External dependency status")


class FeedbackRequest(BaseModel):
    """Feedback submission request."""

    message_id: str = Field(..., description="ID of the message being rated")
    session_id: str = Field(..., description="Session ID for the conversation")
    rating: int = Field(..., ge=-1, le=5, description="Rating (-1=negative, 1=positive, 1-5=stars)")
    comment: str | None = Field(None, max_length=1000, description="Optional feedback comment")


class FeedbackResponse(BaseModel):
    """Feedback submission response."""

    status: str = Field(..., description="Submission status")
    message_id: str = Field(..., description="Message ID that was rated")
    logged: bool = Field(..., description="Whether feedback was logged to LangSmith")


class PortfolioSummaryResponse(BaseModel):
    """Portfolio summary response."""

    total_value: float | None = Field(None, description="Total portfolio value")
    performance_ytd: float | None = Field(None, description="Year-to-date performance %")
    holdings_count: int = Field(0, description="Number of holdings")
    top_holdings: list[dict[str, Any]] = Field(default_factory=list, description="Top holdings")
    diversification_score: float | None = Field(None, description="Diversification score (0-100)")
    risk_level: str | None = Field(None, description="Risk level label")


class SessionHistoryResponse(BaseModel):
    """Session history response."""

    session_id: str = Field(..., description="Session identifier")
    message_count: int = Field(..., description="Number of messages in history")
    messages: list[dict[str, Any]] = Field(default_factory=list, description="Conversation messages")


class ErrorResponse(BaseModel):
    """Error response model."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    detail: str | None = Field(None, description="Additional details")


# ============================================================================
# Health & Status Endpoints
# ============================================================================


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns service status and dependency availability.
    """
    agent_ready = _agent is not None

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.environment,
        agent_ready=agent_ready,
        dependencies={
            "openai": bool(settings.openai_api_key),
            "langsmith": bool(settings.langsmith_api_key),
            "ghostfolio": bool(settings.ghostfolio_access_token),
            "tracing_enabled": is_tracing_enabled(),
        },
    )


@app.get("/", tags=["System"])
async def root() -> dict[str, str]:
    """Root endpoint with API info."""
    return {
        "name": "Ghostfolio Agent API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# ============================================================================
# Chat Endpoints
# ============================================================================


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with the Ghostfolio Agent.

    Send a natural language query about your portfolio and receive
    an AI-powered response with confidence scoring and verification.

    Args:
        request: Chat request with message and optional session ID

    Returns:
        Agent response with confidence, tool calls, and verification status
    """
    try:
        agent = get_agent()

        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Call agent
        result = await agent.chat_with_context(
            message=request.message,
            session_id=session_id,
            user_id=request.user_id,
        )

        return ChatResponse(
            response=result["message"],
            confidence=result["confidence"],
            confidence_level=result["confidence_level"],
            tool_calls=result["tool_calls"],
            session_id=result["session_id"],
            verification_passed=result["verification_passed"],
            requires_escalation=result["requires_escalation"],
            processing_time_ms=result["metadata"].get("processing_time_ms", 0),
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}",
        )


@app.get("/chat/tools", tags=["Chat"])
async def list_tools() -> list[dict[str, str]]:
    """List available agent tools.

    Returns descriptions of all tools the agent can use.
    """
    agent = get_agent()
    return agent.get_tool_descriptions()


# ============================================================================
# Session Management Endpoints
# ============================================================================


@app.get("/sessions/{session_id}", response_model=SessionHistoryResponse, tags=["Sessions"])
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    """Get conversation history for a session.

    Args:
        session_id: Session identifier

    Returns:
        Session history with message count
    """
    agent = get_agent()

    # Access internal history (agent stores this)
    history = agent._conversation_history.get(session_id, [])

    messages = []
    for msg in history:
        role = "user" if msg.__class__.__name__ == "HumanMessage" else "assistant"
        messages.append({
            "role": role,
            "content": msg.content,
        })

    return SessionHistoryResponse(
        session_id=session_id,
        message_count=len(messages),
        messages=messages,
    )


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def clear_session(session_id: str) -> dict[str, Any]:
    """Clear conversation history for a session.

    Args:
        session_id: Session identifier

    Returns:
        Confirmation of deletion
    """
    agent = get_agent()
    cleared = agent.clear_conversation(session_id)

    return {
        "session_id": session_id,
        "cleared": cleared,
        "message": "Session cleared" if cleared else "Session not found",
    }


# ============================================================================
# Feedback Endpoints
# ============================================================================


@app.post("/feedback", response_model=FeedbackResponse, tags=["Feedback"])
async def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Submit feedback for a response.

    Feedback is logged to LangSmith for model improvement.

    Args:
        request: Feedback with message ID, session ID, and rating

    Returns:
        Confirmation of feedback submission
    """
    logged = False

    try:
        if is_tracing_enabled():
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

    return FeedbackResponse(
        status="received",
        message_id=request.message_id,
        logged=logged,
    )


# ============================================================================
# Portfolio Endpoints
# ============================================================================


@app.get("/portfolio", response_model=PortfolioSummaryResponse, tags=["Portfolio"])
async def get_portfolio_summary() -> PortfolioSummaryResponse:
    """Get quick portfolio summary.

    Returns a summary of the user's portfolio including total value,
    performance, top holdings, and risk assessment.

    Returns:
        Portfolio summary with key metrics
    """
    try:
        agent = get_agent()

        # Use portfolio_analysis tool internally
        from src.tools import portfolio_analysis

        result = await portfolio_analysis.ainvoke({
            "timeframe": "YTD",
        })

        # Parse the result
        import json
        if isinstance(result, str):
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                data = {}
        else:
            data = result

        return PortfolioSummaryResponse(
            total_value=data.get("total_value"),
            performance_ytd=data.get("performance", {}).get("ytd"),
            holdings_count=len(data.get("holdings", [])),
            top_holdings=data.get("holdings", [])[:5],
            diversification_score=data.get("diversification_score"),
            risk_level=data.get("risk_level"),
        )

    except Exception as e:
        logger.error(f"Portfolio summary error: {e}")
        # Return empty summary instead of error for better UX
        return PortfolioSummaryResponse(
            total_value=None,
            performance_ytd=None,
            holdings_count=0,
            top_holdings=[],
            diversification_score=None,
            risk_level=None,
        )


@app.get("/portfolio/risk", tags=["Portfolio"])
async def get_risk_assessment() -> dict[str, Any]:
    """Get portfolio risk assessment.

    Returns detailed risk metrics including concentration and diversification.
    """
    try:
        agent = get_agent()

        from src.tools import risk_assessment

        result = await risk_assessment.ainvoke({})

        import json
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {"raw": result}
        return result

    except Exception as e:
        logger.error(f"Risk assessment error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Risk assessment error: {str(e)}",
        )


# ============================================================================
# Utility Endpoints
# ============================================================================


@app.get("/market/{symbol}", tags=["Market"])
async def get_market_data(symbol: str) -> dict[str, Any]:
    """Get current market data for a symbol.

    Args:
        symbol: Stock ticker or crypto symbol

    Returns:
        Current price and market data
    """
    try:
        from src.tools import market_data_lookup

        result = await market_data_lookup.ainvoke({
            "symbols": [symbol.upper()],
        })

        # Handle Pydantic model result
        if hasattr(result, "model_dump"):
            data = result.model_dump()
            # Return first result if available
            if data.get("data") and len(data["data"]) > 0:
                return data["data"][0]
            return data

        # Handle string result
        import json
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if data.get("results"):
                    return data["results"][0]
                return data
            except json.JSONDecodeError:
                return {"raw": result}

        return result

    except Exception as e:
        logger.error(f"Market data error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Market data error: {str(e)}",
        )


# ============================================================================
# Server Entry Point
# ============================================================================


def run_server() -> None:
    """Run the FastAPI server."""
    import uvicorn

    uvicorn.run(
        "src.api.routes:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
    )


if __name__ == "__main__":
    run_server()
