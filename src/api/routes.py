"""FastAPI routes for Ghostfolio Agent API.

This module provides REST API endpoints for the Ghostfolio Agent:
- /health - Health check and dependency status
- /chat - Main chat endpoint with agent
- /feedback - Submit feedback to LangSmith
- /portfolio - Quick portfolio summary
- /sessions - Conversation history management

Task #15: Create FastAPI backend
"""

# Import eval runner API wrapper
import sys
import uuid
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent import GhostfolioAgent
from src.agent.core import reload_agent_tools
from src.exceptions import get_friendly_error_message
from src.tools.code_validator import sanitize_tool_name, validate_generated_tool
from src.tools.registry import (
    get_tool_schema,
    register_generated_tool,
    unregister_generated_tool,
)
from src.tools.registry import (
    list_tools as list_registered_tools,
)
from src.utils.config import get_settings
from src.utils.config_store import (
    get_agent_config_store,
    get_strategy_config_store,
    get_verification_config_store,
)
from src.utils.langsmith_client import get_recent_runs, get_run_details
from src.utils.logging import get_logger, setup_logging
from src.utils.request_context import (
    REQUEST_GHOSTFOLIO_ACCESS_TOKEN,
    REQUEST_GHOSTFOLIO_API_URL,
)
from src.utils.tracing import is_tracing_enabled, log_feedback
from src.utils.usage_tracker import (
    MODEL_PRICING,
    calculate_cost,
    get_cost_by_run_id,
    get_cost_projections,
    get_usage_stats,
    seed_demo_usage,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from evals.runner_api import (
    format_results_for_api,
    get_latest_results,
    run_evals_async,
)
from evals.runner_api import (
    list_eval_cases as get_real_eval_cases,
)

logger = get_logger(__name__)
settings = get_settings()

# Global agent instance
_agent: GhostfolioAgent | None = None

# Performance metrics (in-memory, reset on restart)
_chat_request_count: int = 0
_latency_samples: deque = deque(maxlen=100)


def clear_agent() -> None:
    """Clear the agent singleton so next get_agent() reinitializes (e.g. after model change)."""
    global _agent
    _agent = None


def get_agent() -> GhostfolioAgent:
    """Get or initialize the agent singleton. Uses model from agent config store."""
    global _agent
    store = get_agent_config_store()
    model = store.get("model", "gpt-4o-mini")
    if _agent is None or getattr(_agent.llm, "model_name", getattr(_agent.llm, "model", None)) != model:
        if _agent is not None:
            logger.info("Reinitializing agent with model=%s", model)
        _agent = None
        logger.info("Initializing GhostfolioAgent with model=%s...", model)
        _agent = GhostfolioAgent(
            model=model,
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
    logger.info("Starting Ghostfolio Agent API in %s mode", settings.environment)

    # Pre-initialize agent on startup
    try:
        get_agent()
        logger.info("Agent pre-initialized on startup")
    except Exception as e:
        logger.warning("Could not pre-initialize agent: %s", e)

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

# Per-request Ghostfolio token and optional API URL (stateless)
GHOSTFOLIO_TOKEN_HEADER = "X-Ghostfolio-Access-Token"
GHOSTFOLIO_API_URL_HEADER = "X-Ghostfolio-Api-Url"


@app.middleware("http")
async def set_request_ghostfolio_token(request: Any, call_next: Any):
    """Set request-scoped Ghostfolio token and optional API URL from headers."""
    token = request.headers.get(GHOSTFOLIO_TOKEN_HEADER)
    if token and isinstance(token, str):
        token = token.strip() or None
    api_url = request.headers.get(GHOSTFOLIO_API_URL_HEADER)
    if api_url and isinstance(api_url, str):
        api_url = api_url.strip() or None
    old_token = None
    old_url = None
    if token:
        old_token = REQUEST_GHOSTFOLIO_ACCESS_TOKEN.set(token)
    if api_url:
        old_url = REQUEST_GHOSTFOLIO_API_URL.set(api_url)
    try:
        response = await call_next(request)
        return response
    finally:
        if token:
            try:
                REQUEST_GHOSTFOLIO_ACCESS_TOKEN.reset(old_token)
            except LookupError:
                pass
        if api_url:
            try:
                REQUEST_GHOSTFOLIO_API_URL.reset(old_url)
            except LookupError:
                pass


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
    tool_outputs: list[Any] = Field(default_factory=list, description="Tool execution results")
    tool_invocations: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured list of { call: { tool, input }, output } for each tool invocation",
    )
    session_id: str = Field(..., description="Session ID for follow-up queries")
    verification_passed: bool = Field(default=True, description="Whether verification passed")
    requires_escalation: bool = Field(default=False, description="Whether human review recommended")
    processing_time_ms: float = Field(..., description="Processing time in milliseconds")
    run_id: str | None = Field(None, description="LangSmith run ID for feedback and trace link")
    trace_url: str | None = Field(None, description="URL to view trace in LangSmith")


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


class SessionSummary(BaseModel):
    """Summary of one session for listing."""

    session_id: str = Field(..., description="Session identifier")
    message_count: int = Field(..., description="Number of messages")
    last_accessed: str | None = Field(None, description="ISO timestamp of last access")


class SessionsListResponse(BaseModel):
    """List of sessions (past conversations)."""

    sessions: list[SessionSummary] = Field(default_factory=list, description="Sessions, most recent first")


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
        "metrics": "/metrics",
    }


@app.get("/metrics", tags=["System"])
async def get_metrics() -> dict[str, Any]:
    """Performance metrics (in-memory, reset on restart).

    Returns chat request count and latency stats from the last N requests.
    Use for lightweight performance monitoring without external infra.
    """
    global _chat_request_count, _latency_samples
    samples = list(_latency_samples)
    out = {
        "chat_request_count": _chat_request_count,
        "latency_sample_count": len(samples),
    }
    if samples:
        sorted_ms = sorted(samples)
        n = len(sorted_ms)
        idx_p50 = min(int(n * 0.5), n - 1) if n else 0
        idx_p95 = min(int(n * 0.95), n - 1) if n else 0
        out["latency_p50_ms"] = round(sorted_ms[idx_p50], 2)
        out["latency_p95_ms"] = round(sorted_ms[idx_p95], 2)
        out["latency_avg_ms"] = round(sum(samples) / n, 2)
    else:
        out["latency_p50_ms"] = None
        out["latency_p95_ms"] = None
        out["latency_avg_ms"] = None
    return out


# ============================================================================
# Chat Endpoints
# ============================================================================


def _chat_fallback_message(exc: Exception) -> str:
    """Turn an exception into a short, conversational message for the user (no HTTP/tech jargon)."""
    # Use centralized error message formatting
    return get_friendly_error_message(exc)


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
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

        global _chat_request_count, _latency_samples
        _chat_request_count += 1
        pt_ms = result.get("metadata", {}).get("processing_time_ms")
        if pt_ms is not None:
            _latency_samples.append(float(pt_ms))

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
        friendly = _chat_fallback_message(e)
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


@app.get("/chat/tools", tags=["Chat"])
async def list_tools() -> list[dict[str, str]]:
    """List available agent tools.

    Returns descriptions of all tools the agent can use.
    """
    agent = get_agent()
    return agent.get_tool_descriptions()


# Allowed LLM models for agent (OpenAI models supported by ChatOpenAI)
ALLOWED_AGENT_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]


class AgentConfigResponse(BaseModel):
    """Agent configuration response."""

    model: str = Field(..., description="Current LLM model id (e.g. gpt-4o-mini)")
    allowed_models: list[str] = Field(
        default_factory=lambda: ALLOWED_AGENT_MODELS.copy(),
        description="Model ids that can be selected",
    )


class AgentConfigRequest(BaseModel):
    """Agent configuration update request."""

    model: str = Field(..., description="LLM model id to use")


@app.get("/agent/config", response_model=AgentConfigResponse, tags=["Agent"])
async def get_agent_config() -> AgentConfigResponse:
    """Get current agent configuration (e.g. selected model). For developers."""
    store = get_agent_config_store()
    model = store.get("model", "gpt-4o-mini")
    return AgentConfigResponse(model=model, allowed_models=ALLOWED_AGENT_MODELS)


@app.put("/agent/config", response_model=AgentConfigResponse, tags=["Agent"])
async def put_agent_config(request: AgentConfigRequest) -> AgentConfigResponse:
    """Update agent configuration (e.g. switch model). Agent is reinitialized on next chat. For developers."""
    model = request.model.strip().lower().replace("_", "-")
    if model not in ALLOWED_AGENT_MODELS:
        raise HTTPException(
            status_code=400,
            detail=f"Model must be one of: {', '.join(ALLOWED_AGENT_MODELS)}",
        )
    store = get_agent_config_store()
    store.set("model", model)
    clear_agent()
    logger.info("Agent config updated: model=%s", model)
    return AgentConfigResponse(model=model, allowed_models=ALLOWED_AGENT_MODELS)


# ============================================================================
# Session Management Endpoints
# ============================================================================


@app.get("/sessions", response_model=SessionsListResponse, tags=["Sessions"])
async def list_sessions() -> SessionsListResponse:
    """List all conversation sessions (past conversations).

    Returns sessions with message count and last accessed time, most recent first.
    """
    agent = get_agent()
    raw = agent.list_sessions()
    sessions = [
        SessionSummary(
            session_id=s["session_id"],
            message_count=s["message_count"],
            last_accessed=s.get("last_accessed"),
        )
        for s in raw
    ]
    return SessionsListResponse(sessions=sessions)


@app.get("/sessions/{session_id}", response_model=SessionHistoryResponse, tags=["Sessions"])
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    """Get conversation history for a session.

    Args:
        session_id: Session identifier

    Returns:
        Session history with message count
    """
    agent = get_agent()
    history = agent.get_session_history(session_id)

    messages = []
    for msg in history:
        name = msg.__class__.__name__
        if name == "HumanMessage":
            role = "user"
        elif name == "AIMessage":
            role = "assistant"
        else:
            # Skip ToolMessage for display (keep thread user/assistant only)
            continue
        content = getattr(msg, "content", "") or ""
        if isinstance(content, list):
            content = str(content)
        messages.append({"role": role, "content": content})

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

    Feedback is logged to LangSmith for model improvement and stored locally
    for eval integration.

    Args:
        request: Feedback with message ID, session ID, and rating

    Returns:
        Confirmation of feedback submission
    """
    logged = False
    stored_locally = False

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
        get_agent()  # Ensure agent is initialized

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
        get_agent()  # Ensure agent is initialized

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
# Strategy Endpoints (Page 2 - Strategy)
# ============================================================================


class StrategyConfigResponse(BaseModel):
    """Strategy configuration response."""

    framework: str = Field(default="LangGraph", description="Selected framework")
    model: str = Field(default="GPT-4o (OpenAI)", description="Selected model")
    temperature: float = Field(default=0.0, description="Model temperature")
    json_mode: bool = Field(default=True, description="JSON mode enabled")
    stream_responses: bool = Field(default=False, description="Stream responses")
    contribution_path: str = Field(default="langchain", description="Contribution path")


class StrategyRecommendationResponse(BaseModel):
    """Strategy recommendation response."""

    framework: str = Field(..., description="Framework name")
    reason: str = Field(..., description="Recommendation reason")
    recommended: bool = Field(..., description="Is recommended")


@app.get("/strategy", response_model=StrategyConfigResponse, tags=["Strategy"])
async def get_strategy_config() -> StrategyConfigResponse:
    """Get current strategy configuration.

    Returns the active agent configuration including framework,
    model, and processing settings.
    """
    store = get_strategy_config_store()
    return StrategyConfigResponse(
        framework=store.get("framework", "LangGraph"),
        model=store.get("model", "GPT-4o (OpenAI)"),
        temperature=store.get("temperature", 0.0),
        json_mode=store.get("json_mode", True),
        stream_responses=store.get("stream_responses", False),
        contribution_path=store.get("contribution_path", "langchain"),
    )


@app.post("/strategy", response_model=StrategyConfigResponse, tags=["Strategy"])
async def save_strategy_config(config: StrategyConfigResponse) -> StrategyConfigResponse:
    """Save strategy configuration.

    Updates the active agent configuration and persists it.
    """
    store = get_strategy_config_store()
    store.update(config.model_dump())
    logger.info(f"Strategy config updated: {config.model_dump()}")
    return config


@app.get("/strategy/recommendations", response_model=list[StrategyRecommendationResponse], tags=["Strategy"])
async def get_strategy_recommendations() -> list[StrategyRecommendationResponse]:
    """Get strategy recommendations based on repo analysis.

    Returns framework recommendations tailored to the connected codebase.
    """
    return [
        StrategyRecommendationResponse(
            framework="LangGraph",
            reason="Best fit for stateful cyclic workflows with complex tool orchestration",
            recommended=True,
        ),
        StrategyRecommendationResponse(
            framework="LangChain",
            reason="Simpler linear chains if you don't need state management",
            recommended=False,
        ),
        StrategyRecommendationResponse(
            framework="CrewAI",
            reason="Consider for multi-agent collaboration scenarios",
            recommended=False,
        ),
    ]


# ============================================================================
# Tools Endpoints (Page 3 - Tool Library)
# ============================================================================


class ToolResponse(BaseModel):
    """Tool response model."""

    id: str = Field(..., description="Tool ID")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    status: str = Field(default="active", description="Tool status")


class ToolCreateRequest(BaseModel):
    """Tool creation request."""

    name: str = Field(..., min_length=1, description="Tool name")
    description: str = Field(..., min_length=1, description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class ToolRegistrationRequest(BaseModel):
    """Request to register a generated tool."""

    name: str = Field(..., min_length=1, description="Tool name")
    description: str = Field(..., min_length=1, description="Tool description")
    generated_code: str = Field(..., min_length=1, description="Python source code with @tool decorator")
    source_suggestion_id: str | None = Field(default=None, description="ID of the suggestion that generated this tool")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Parameter schema")


class ToolRegistrationResponse(BaseModel):
    """Response from tool registration."""

    success: bool = Field(..., description="Whether registration succeeded")
    message: str = Field(..., description="Status message")
    tool_name: str | None = Field(default=None, description="Registered tool name")
    tool_id: str | None = Field(default=None, description="Tool ID (same as name)")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")
    agent_reloaded: bool = Field(default=False, description="Whether the agent was reloaded")


@app.get("/tools", response_model=list[ToolResponse], tags=["Tools"])
async def list_tools_registry() -> list[ToolResponse]:
    """List all registered tools.

    Returns all tools discovered from the src/tools/ directory.
    """
    tools = list_registered_tools()
    return [
        ToolResponse(
            id=tool["id"],
            name=tool["name"],
            description=tool["description"],
            parameters=tool["parameters"],
            status=tool.get("status", "active"),
        )
        for tool in tools
    ]


class ToolDetailResponse(BaseModel):
    """Detailed tool response model."""

    id: str = Field(..., description="Tool ID")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    status: str = Field(default="active", description="Tool status")
    args_schema: dict[str, Any] | None = Field(default=None, description="Full JSON schema")
    execution_count: int = Field(default=0, description="Number of times executed")


@app.get("/tools/{tool_name}", response_model=ToolDetailResponse, tags=["Tools"])
async def get_tool_detail(tool_name: str) -> ToolDetailResponse:
    """Get detailed information about a specific tool.

    Args:
        tool_name: Name of the tool to retrieve

    Returns:
        ToolDetailResponse with full tool information
    """
    schema = get_tool_schema(tool_name)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    return ToolDetailResponse(
        id=tool_name,
        name=schema["name"],
        description=schema["description"],
        parameters=schema["parameters"],
        status="active",
        args_schema=schema.get("args_schema"),
        execution_count=0,  # TODO: Track execution counts
    )


class ToolExecuteRequest(BaseModel):
    """Request to execute a tool."""

    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")


class ToolExecuteResponse(BaseModel):
    """Response from tool execution."""

    tool_name: str = Field(..., description="Name of the executed tool")
    success: bool = Field(..., description="Whether execution succeeded")
    result: Any = Field(..., description="Tool execution result")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")


@app.post("/tools/{tool_name}/execute", response_model=ToolExecuteResponse, tags=["Tools"])
async def execute_tool(tool_name: str, request: ToolExecuteRequest) -> ToolExecuteResponse:
    """Execute a tool with the given parameters.

    Args:
        tool_name: Name of the tool to execute
        request: Execution request with parameters

    Returns:
        ToolExecuteResponse with the result
    """
    import time

    tool = get_tool_schema(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    start_time = time.time()

    try:
        # Execute the tool
        # For now, we use the agent's tools which are async
        from src.tools import ALL_TOOLS

        target_tool = None
        for t in ALL_TOOLS:
            if t.name == tool_name:
                target_tool = t
                break

        if not target_tool:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found in registry")

        # Execute with provided parameters
        result = await target_tool.ainvoke(request.parameters)

        execution_time = (time.time() - start_time) * 1000

        # Handle Pydantic model results
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="json")

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=True,
            result=result,
            execution_time_ms=round(execution_time, 2),
        )

    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Tool execution failed: {e}")

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            result={"error": str(e)},
            execution_time_ms=round(execution_time, 2),
        )


@app.post("/tools", response_model=ToolResponse, tags=["Tools"])
async def create_tool(request: ToolCreateRequest) -> ToolResponse:
    """Create a new tool (placeholder for future dynamic tool creation).

    Note: In the current implementation, tools are discovered from
    src/tools/ and cannot be created at runtime. This endpoint
    is provided for API compatibility.
    """
    import uuid

    # For now, just return the tool info but don't actually register it
    # Tools must be added to src/tools/ and ALL_TOOLS
    logger.warning(f"Tool creation requested but not implemented: {request.name}")
    return ToolResponse(
        id=str(uuid.uuid4()),
        name=request.name,
        description=request.description,
        parameters=request.parameters,
        status="inactive",  # Mark as inactive since it's not actually registered
    )


@app.post("/tools/register", response_model=ToolRegistrationResponse, tags=["Tools"])
async def register_tool(request: ToolRegistrationRequest) -> ToolRegistrationResponse:
    """Register a generated tool and make it available to the agent.

    This endpoint:
    1. Validates the generated code for safety
    2. Persists the tool to disk
    3. Loads the tool dynamically
    4. Reloads the agent to make the tool available

    Args:
        request: Tool registration request with name, description, and code

    Returns:
        ToolRegistrationResponse with success status and any warnings
    """
    logger.info(f"Registering generated tool: {request.name}")

    # Validate the code first
    validation = validate_generated_tool(request.generated_code)

    if not validation.valid:
        error_msg = "; ".join(validation.errors)
        logger.warning(f"Tool validation failed: {error_msg}")
        return ToolRegistrationResponse(
            success=False,
            message=f"Validation failed: {error_msg}",
            tool_name=None,
            warnings=validation.warnings,
        )

    # Sanitize the tool name
    safe_name = sanitize_tool_name(request.name)

    # Register the tool
    success, message = register_generated_tool(
        name=safe_name,
        description=request.description,
        generated_code=request.generated_code,
        source_suggestion_id=request.source_suggestion_id,
        parameters=request.parameters,
    )

    if not success:
        logger.warning(f"Tool registration failed: {message}")
        return ToolRegistrationResponse(
            success=False,
            message=message,
            tool_name=None,
            warnings=validation.warnings,
        )

    # Reload the agent to make the tool available
    reloaded = reload_agent_tools()
    if not reloaded:
        logger.warning("Tool registered but agent reload failed")
        # Tool is still registered, just needs manual reload later

    logger.info(f"Tool '{safe_name}' registered successfully, agent reloaded: {reloaded}")

    return ToolRegistrationResponse(
        success=True,
        message=f"Tool '{safe_name}' registered successfully",
        tool_name=safe_name,
        tool_id=safe_name,
        warnings=validation.warnings,
        agent_reloaded=reloaded,
    )


@app.delete("/tools/generated/{tool_name}", response_model=dict, tags=["Tools"])
async def delete_generated_tool(tool_name: str) -> dict:
    """Unregister a generated tool.

    Args:
        tool_name: Name of the generated tool to delete

    Returns:
        Dict with success status
    """
    logger.info(f"Unregistering generated tool: {tool_name}")

    success, message = unregister_generated_tool(tool_name)

    if success:
        # Reload the agent
        reload_agent_tools()

    return {
        "success": success,
        "message": message,
    }

# Verification Endpoints (Page 4 - Verification)
# ============================================================================


class VerificationConfigResponse(BaseModel):
    """Verification configuration response."""

    fact_checking: bool = Field(default=True, description="Enable fact checking")
    hallucination_detection: bool = Field(default=True, description="Enable hallucination detection")
    confidence_scoring: bool = Field(default=True, description="Enable confidence scoring")
    hitl_enabled: bool = Field(default=False, description="Enable human-in-the-loop")
    confidence_threshold: int = Field(default=70, ge=0, le=100, description="Confidence threshold for HITL")


@app.get("/verification/config", response_model=VerificationConfigResponse, tags=["Verification"])
async def get_verification_config() -> VerificationConfigResponse:
    """Get verification configuration.

    Returns current verification layer settings.
    """
    store = get_verification_config_store()
    return VerificationConfigResponse(
        fact_checking=store.get("fact_checking", True),
        hallucination_detection=store.get("hallucination_detection", True),
        confidence_scoring=store.get("confidence_scoring", True),
        hitl_enabled=store.get("hitl_enabled", False),
        confidence_threshold=store.get("confidence_threshold", 70),
    )


@app.put("/verification/config", response_model=VerificationConfigResponse, tags=["Verification"])
async def update_verification_config(config: VerificationConfigResponse) -> VerificationConfigResponse:
    """Update verification configuration.

    Updates verification layer settings and persists them.
    """
    store = get_verification_config_store()
    store.update(config.model_dump())
    logger.info(f"Verification config updated: {config.model_dump()}")
    return config


# ============================================================================
# Traces Endpoints (Page 5 - Observability)
# ============================================================================


class TraceResponse(BaseModel):
    """Trace response model."""

    id: str = Field(..., description="Trace ID")
    timestamp: str = Field(..., description="Timestamp")
    duration_ms: int = Field(..., description="Duration in milliseconds")
    tokens_used: int = Field(..., description="Total tokens used")
    status: str = Field(..., description="Trace status")
    tool_calls: list[str] = Field(default_factory=list, description="Tool calls made")


class TraceDetailResponse(TraceResponse):
    """Trace detail response model."""

    steps: list[dict[str, Any]] = Field(default_factory=list, description="Execution steps")
    cost_usd: float | None = Field(None, description="Recorded cost for this run when linked via run_id")


@app.get("/traces", response_model=list[TraceResponse], tags=["Traces"])
async def list_traces(limit: int = Query(default=20, ge=1, le=100)) -> list[TraceResponse]:
    """List all traces.

    Returns recent agent execution traces from LangSmith.
    """
    # Get real traces from LangSmith
    runs = get_recent_runs(limit=limit)

    if not runs:
        # Return empty list if no traces available
        return []

    return [
        TraceResponse(
            id=run["id"],
            timestamp=run["timestamp"] or "",
            duration_ms=run["duration_ms"],
            tokens_used=run["tokens_used"],
            status=run["status"],
            tool_calls=run.get("tool_calls", []),
        )
        for run in runs
    ]


@app.get("/traces/{trace_id}", response_model=TraceDetailResponse, tags=["Traces"])
async def get_trace_detail(trace_id: str) -> TraceDetailResponse:
    """Get trace detail.

    Returns detailed information about a specific trace from LangSmith.
    """
    run = get_run_details(trace_id)

    if not run:
        raise HTTPException(status_code=404, detail="Trace not found")

    cost_usd = get_cost_by_run_id(trace_id)

    return TraceDetailResponse(
        id=run["id"],
        timestamp=run["timestamp"] or "",
        duration_ms=run["duration_ms"],
        tokens_used=run["tokens_used"],
        status=run["status"],
        tool_calls=run.get("tool_calls", []),
        steps=run.get("steps", []),
        cost_usd=cost_usd,
    )


# ============================================================================
# Evals Endpoints (Page 6 - Evaluations)
# ============================================================================


class EvalCaseResponse(BaseModel):
    """Eval case response model."""

    id: str = Field(..., description="Case ID")
    name: str = Field(..., description="Case name")
    description: str = Field(..., description="Case description")
    category: str = Field(..., description="Case category")


class EvalResultResponse(BaseModel):
    """Eval result response model."""

    case_id: str = Field(..., description="Case ID")
    passed: bool = Field(..., description="Whether the case passed")
    score: float = Field(..., description="Score (0-1)")
    duration_ms: int = Field(..., description="Duration in milliseconds")
    error: str | None = Field(default=None, description="Error message if failed")


class EvalSummaryResponse(BaseModel):
    """Eval summary response model."""

    total_cases: int = Field(..., description="Total cases")
    passed: int = Field(..., description="Passed cases")
    failed: int = Field(..., description="Failed cases")
    pass_rate: float = Field(..., description="Pass rate percentage")
    avg_latency_ms: int = Field(..., description="Average latency")
    hallucination_rate: float = Field(..., description="Hallucination rate percentage")


class EvalResultsResponse(BaseModel):
    """Eval results response model."""

    summary: EvalSummaryResponse = Field(..., description="Summary")
    results: list[EvalResultResponse] = Field(..., description="Individual results")


class EvalRunRequest(BaseModel):
    """Request model for running evals with optional config."""

    config: dict[str, Any] | None = Field(
        default=None,
        description="Optional eval configuration (fact_checking, hitl_enabled, etc.)",
    )


@app.get("/evals/cases", response_model=list[EvalCaseResponse], tags=["Evals"])
async def list_eval_cases() -> list[EvalCaseResponse]:
    """List all evaluation cases.

    Returns all available test cases from the eval framework.
    """
    cases = get_real_eval_cases()
    return [
        EvalCaseResponse(
            id=case["id"],
            name=case.get("name", case["id"]),
            description=case.get("description", ""),
            category=case.get("category", "unknown"),
        )
        for case in cases
    ]


@app.post("/evals/run", tags=["Evals"])
async def run_evals_endpoint(request: EvalRunRequest | None = None) -> dict[str, str]:
    """Run all evaluations.

    Triggers evaluation run for all test cases.
    This runs asynchronously and returns a run_id.

    Optionally accepts a config object to override verification settings for this run:
    - fact_checking: bool
    - hallucination_detection: bool
    - confidence_scoring: bool
    - hitl_enabled: bool
    - confidence_threshold: int (0-100)
    - strict_mode: bool
    """
    try:
        config = request.config if request else None
        if config:
            logger.info(f"Running evals with custom config: {config}")
        run_id = await run_evals_async(config)
        logger.info(f"Evaluation run triggered: {run_id}")
        return {"run_id": run_id, "status": "started"}
    except Exception as e:
        logger.error(f"Failed to run evals: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run evaluations: {str(e)}")


@app.get("/evals/results", response_model=EvalResultsResponse, tags=["Evals"])
async def get_eval_results() -> EvalResultsResponse:
    """Get evaluation results.

    Returns latest evaluation results and summary from the eval framework.
    """
    raw_results = get_latest_results()
    formatted = format_results_for_api(raw_results)

    summary = formatted["summary"]
    return EvalResultsResponse(
        summary=EvalSummaryResponse(
            total_cases=summary["total_cases"],
            passed=summary["passed"],
            failed=summary["failed"],
            pass_rate=summary["pass_rate"],
            avg_latency_ms=summary["avg_latency_ms"],
            hallucination_rate=summary["hallucination_rate"],
        ),
        results=[
            EvalResultResponse(
                case_id=r["case_id"],
                passed=r["passed"],
                score=r["score"],
                duration_ms=r["duration_ms"],
                error=r.get("error"),
            )
            for r in formatted["results"]
        ],
    )


# ============================================================================
# Finances Endpoints (Page 7 - Finances)
# ============================================================================


class UsageByModel(BaseModel):
    """Per-model usage stats."""

    requests: int = Field(..., description="Request count for this model")
    tokens: int = Field(..., description="Total tokens for this model")
    cost: float = Field(..., description="Total cost in USD for this model")


class UsageStatsResponse(BaseModel):
    """Usage stats response model."""

    total_cost: float = Field(..., description="Total cost in USD")
    total_tokens: int = Field(..., description="Total tokens used")
    requests_count: int = Field(..., description="Total requests count")
    avg_cost_per_request: float = Field(..., description="Average cost per request")
    by_model: dict[str, UsageByModel] = Field(
        default_factory=dict,
        description="Breakdown by model (requests, tokens, cost)",
    )


class CostProjectionsResponse(BaseModel):
    """Cost projections response model."""

    daily_cost: float = Field(..., description="Daily cost projection")
    monthly_cost: float = Field(..., description="Monthly cost projection")
    projected_annual: float = Field(..., description="Annual cost projection")
    cost_breakdown: dict[str, int] = Field(..., description="Cost breakdown by token type")


@app.get("/finances/usage", response_model=UsageStatsResponse, tags=["Finances"])
async def get_usage_stats_endpoint() -> UsageStatsResponse:
    """Get usage statistics.

    Returns current usage and cost data from the usage tracker.
    """
    stats = get_usage_stats()
    by_model = {
        model: UsageByModel(requests=data["requests"], tokens=data["tokens"], cost=data["cost"])
        for model, data in stats.get("by_model", {}).items()
    }
    return UsageStatsResponse(
        total_cost=stats["total_cost"],
        total_tokens=stats["total_tokens"],
        requests_count=stats["requests_count"],
        avg_cost_per_request=stats["avg_cost_per_request"],
        by_model=by_model,
    )


@app.get("/finances/projections", response_model=CostProjectionsResponse, tags=["Finances"])
async def get_cost_projections_endpoint(queries_per_day: int = Query(default=100, ge=1, le=10000)) -> CostProjectionsResponse:
    """Get cost projections.

    Returns projected costs based on expected query volume.
    """
    projections = get_cost_projections(queries_per_day)
    return CostProjectionsResponse(
        daily_cost=projections["daily_cost"],
        monthly_cost=projections["monthly_cost"],
        projected_annual=projections["projected_annual"],
        cost_breakdown=projections["cost_breakdown"],
    )


class ModelPricingEntry(BaseModel):
    """Pricing for one model (USD per 1M tokens)."""

    input_per_1m: float = Field(..., description="Input price per 1M tokens")
    output_per_1m: float = Field(..., description="Output price per 1M tokens")


class ModelPricingResponse(BaseModel):
    """Model pricing for cost comparison."""

    models: dict[str, ModelPricingEntry] = Field(..., description="Model id -> pricing")


@app.get("/finances/model-pricing", response_model=ModelPricingResponse, tags=["Finances"])
async def get_model_pricing() -> ModelPricingResponse:
    """Get pricing per model (USD per 1M tokens). For cost comparison UI."""
    models = {
        mid: ModelPricingEntry(input_per_1m=p["input"], output_per_1m=p["output"])
        for mid, p in MODEL_PRICING.items()
    }
    return ModelPricingResponse(models=models)


class CostComparisonEntry(BaseModel):
    """Cost comparison row for one model."""

    model_id: str = Field(..., description="Model id")
    label: str = Field(..., description="Display label")
    input_per_1m: float = Field(..., description="Input $/1M tokens")
    output_per_1m: float = Field(..., description="Output $/1M tokens")
    cost_per_query: float = Field(..., description="Est. cost per query at default token mix")
    monthly_cost: float = Field(..., description="Est. monthly cost at given queries/day")


class CostComparisonResponse(BaseModel):
    """Cost comparison across models."""

    queries_per_day: int = Field(..., description="Queries per day used for projection")
    avg_tokens_per_query: int = Field(..., description="Avg tokens per query assumption")
    input_ratio_pct: int = Field(..., description="Input token ratio (0-100)")
    models: list[CostComparisonEntry] = Field(..., description="Per-model comparison")


def _model_display_label(model_id: str) -> str:
    """Human-readable label for model id."""
    labels = {
        "gpt-4o-mini": "GPT-4o Mini",
        "gpt-4o": "GPT-4o",
        "gpt-4-turbo": "GPT-4 Turbo",
        "gpt-4": "GPT-4",
        "gpt-3.5-turbo": "GPT-3.5 Turbo",
        "claude-3-opus": "Claude 3 Opus",
        "claude-3-sonnet": "Claude 3 Sonnet",
        "claude-3-haiku": "Claude 3 Haiku",
    }
    return labels.get(model_id, model_id)


class SeedDemoUsageResponse(BaseModel):
    """Response after seeding demo usage."""

    entries_added: int = Field(..., description="Number of usage log entries added")
    models: int = Field(..., description="Number of models that received entries")


@app.post("/finances/seed-demo-usage", response_model=SeedDemoUsageResponse, tags=["Finances"])
async def post_seed_demo_usage(
    entries_per_model: int = Query(default=12, ge=1, le=50),
    days_back: int = Query(default=3, ge=1, le=30),
) -> SeedDemoUsageResponse:
    """Seed the usage log with synthetic entries for all models. For demo/observability only."""
    total = seed_demo_usage(entries_per_model=entries_per_model, days_back=days_back)
    return SeedDemoUsageResponse(
        entries_added=total,
        models=len(MODEL_PRICING),
    )


@app.get("/finances/cost-comparison", response_model=CostComparisonResponse, tags=["Finances"])
async def get_cost_comparison(
    queries_per_day: int = Query(default=100, ge=1, le=100000),
    avg_tokens_per_query: int = Query(default=500, ge=100, le=10000),
    input_ratio_pct: int = Query(default=60, ge=0, le=100),
) -> CostComparisonResponse:
    """Get cost comparison across models for given query volume. For Observability page."""
    input_ratio = input_ratio_pct / 100.0
    input_tokens = int(avg_tokens_per_query * input_ratio)
    output_tokens = avg_tokens_per_query - input_tokens
    entries: list[CostComparisonEntry] = []
    for model_id, pricing in MODEL_PRICING.items():
        cost_per_query = calculate_cost(input_tokens, output_tokens, model_id)
        daily_cost = cost_per_query * queries_per_day
        monthly_cost = daily_cost * 30
        entries.append(
            CostComparisonEntry(
                model_id=model_id,
                label=_model_display_label(model_id),
                input_per_1m=pricing["input"],
                output_per_1m=pricing["output"],
                cost_per_query=round(cost_per_query, 6),
                monthly_cost=round(monthly_cost, 2),
            )
        )
    # Sort by monthly cost ascending
    entries.sort(key=lambda e: e.monthly_cost)
    return CostComparisonResponse(
        queries_per_day=queries_per_day,
        avg_tokens_per_query=avg_tokens_per_query,
        input_ratio_pct=input_ratio_pct,
        models=entries,
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
