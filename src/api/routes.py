"""FastAPI routes for Ghostfolio Agent API.

This module provides REST API endpoints for the Ghostfolio Agent:
- /health - Health check and dependency status
- /chat - Main chat endpoint with agent
- /feedback - Submit feedback to LangSmith
- /portfolio - Quick portfolio summary
- /sessions - Conversation history management

Task #15: Create FastAPI backend
"""

import ast
import json
import re
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.agent import GhostfolioAgent
from src.tools.registry import list_tools as list_registered_tools, get_tool_schema
from src.utils.config import get_settings
from src.utils.config_store import (
    get_verification_config_store,
    get_strategy_config_store,
)
from src.utils.langsmith_client import get_recent_runs, get_run_details
from src.utils.logging import get_logger, setup_logging
from src.utils.tracing import log_feedback, is_tracing_enabled
from src.utils.usage_tracker import get_usage_stats, get_cost_projections
from src.repo.manager import (
    ensure_git_on_path,
    get_repo_manager,
    RepoConnectionRequest,
    RepoConnection,
    RepoConnectionResponse,
)

# Import eval runner API wrapper
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from evals.runner_api import (
    list_eval_cases as get_real_eval_cases,
    get_latest_results,
    format_results_for_api,
    run_evals_async,
)

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
    ensure_git_on_path()  # So repo connect (clone) can find git when not in shell PATH
    logger.info(f"Starting Ghostfolio Agent API in {settings.environment} mode")

    # Pre-initialize agent on startup
    try:
        get_agent()
        logger.info("Agent pre-initialized on startup")
    except Exception as e:
        logger.warning(f"Could not pre-initialize agent: {e}")

    # Ensure Git is available for repo connect (clone)
    try:
        manager = get_repo_manager()
        git_ok, git_error = await manager._check_git_available()
        if not git_ok:
            logger.warning(
                "Git is not available at startup: %s. Repo connect (clone) will fail until Git is installed and in PATH.",
                git_error,
            )
        else:
            logger.info("Git is available for repository cloning")
    except Exception as e:
        logger.warning("Could not check Git at startup: %s", e)

    # Production: auto-connect to REPO_URL if set and no connections exist
    repo_url = (settings.repo_url or "").strip()
    if repo_url and repo_url.startswith("http"):
        try:
            manager = get_repo_manager()
            if len(manager.list_connections()) == 0:
                req = RepoConnectionRequest(
                    source=repo_url,
                    branch=(settings.repo_branch or "main").strip() or None,
                )
                resp = await manager.connect(req)
                if resp.success and resp.connection:
                    logger.info("Auto-connected to production repo: %s", resp.connection.name)
                else:
                    logger.warning("Auto-connect to REPO_URL failed: %s", getattr(resp, "error", "unknown"))
        except Exception as e:
            logger.warning("Auto-connect to REPO_URL failed: %s", e)

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
    repo_id: str | None = Field(None, description="Optional repo context for tool execution")


class ChatResponse(BaseModel):
    """Chat response model."""

    response: str = Field(..., description="Agent response text")
    confidence: float = Field(..., ge=0, le=100, description="Confidence score (0-100)")
    confidence_level: str = Field(..., description="Confidence level label")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="Tools invoked")
    tool_outputs: list[Any] = Field(default_factory=list, description="Tool execution results")
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

    # Include Git availability (required for repo connect / clone)
    git_available = False
    try:
        manager = get_repo_manager()
        git_available, _ = await manager._check_git_available()
    except Exception:
        pass

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
            "git": git_available,
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
        request: Chat request with message, optional session ID, and optional repo context

    Returns:
        Agent response with confidence, tool calls, and verification status
    """
    try:
        agent = get_agent()

        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Build context with repo_id if provided
        context = {}
        if request.repo_id:
            context["repo_id"] = request.repo_id

        # Call agent
        result = await agent.chat_with_context(
            message=request.message,
            session_id=session_id,
            user_id=request.user_id,
            context=context if context else None,
        )

        return ChatResponse(
            response=result["message"],
            confidence=result["confidence"],
            confidence_level=result["confidence_level"],
            tool_calls=result["tool_calls"],
            tool_outputs=result.get("tool_outputs", []),
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
# Repo Endpoints (Page 1 - Dashboard)
# ============================================================================


class RepoInfoResponse(BaseModel):
    """Repository information response."""

    name: str = Field(..., description="Repository name")
    version: str = Field(..., description="Current version")
    status: str = Field(..., description="Repository status")
    endpoints: int = Field(..., description="Number of detected endpoints")
    services: int = Field(..., description="Number of detected services")
    tool_hooks: int = Field(..., description="Number of tool hooks")


class DependencyNode(BaseModel):
    """A node in the dependency graph."""

    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Display name")
    type: str = Field(..., description="Node type: agent, service, database, api")
    icon: str = Field(..., description="Material icon name")
    color: str = Field(..., description="Color theme: primary, indigo, emerald, slate")
    file_count: int = Field(default=0, description="Number of source files in this module")
    line_count: int = Field(default=0, description="Total lines of code")
    external_deps: list[str] = Field(default_factory=list, description="External npm/pip packages used")
    has_circular: bool = Field(default=False, description="Whether this module is in a circular dependency")


class DependencyEdge(BaseModel):
    """An edge in the dependency graph."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    label: str | None = Field(default=None, description="Optional edge label")
    weight: int = Field(default=1, description="Number of import statements between modules")
    import_types: list[str] = Field(default_factory=list, description="Types of imports (e.g. services, types)")


class DependenciesResponse(BaseModel):
    """Dependencies graph response."""

    nodes: list[DependencyNode] = Field(..., description="Graph nodes")
    edges: list[DependencyEdge] = Field(..., description="Graph edges")


class ConnectionsListResponse(BaseModel):
    """Response for listing connections."""
    connections: list[RepoConnection] = Field(default_factory=list, description="Active connections")


# ============================================================================
# Repo Connection Endpoints
# ============================================================================


@app.post("/repo/connect", response_model=RepoConnectionResponse, tags=["Repo"])
async def connect_repo(request: RepoConnectionRequest) -> RepoConnectionResponse:
    """Connect to a target repository for analysis.

    Accepts a git URL or local path to a repository. For git URLs, clones
    the repository. For local paths, validates and registers the path.

    Args:
        request: Connection request with source (URL or path), optional branch, optional name

    Returns:
        RepoConnectionResponse with connection details or error
    """
    try:
        manager = get_repo_manager()
        out = await manager.connect(request)
        # Ensure UI always gets a message when success is False
        if not out.success and not (out.error and out.error.strip()):
            logger.warning("Repo connect returned success=False with no error message; source=%s", request.source)
            out = RepoConnectionResponse(
                success=False,
                error="Connection failed. Try a public Git URL (e.g. https://github.com/ghostfolio/ghostfolio.git). If that also fails, ensure Git is installed where the backend runs and check server logs."
            )
        return out
    except Exception as e:
        # Always return 200 with success=False and a message so the UI can show it
        logger.exception("Repo connect failed: %s (type=%s)", e, type(e).__name__)
        msg = str(e).strip()
        if not msg:
            msg = (
                "Connection failed. Try a public Git URL (e.g. https://github.com/ghostfolio/ghostfolio.git). "
                "Ensure Git is installed where the backend runs and check server logs for details."
            )
        elif len(msg) > 500:
            msg = msg[:500] + "..."
        return RepoConnectionResponse(success=False, error=msg)


@app.get("/repo/connections", response_model=ConnectionsListResponse, tags=["Repo"])
async def list_connections() -> ConnectionsListResponse:
    """List all active repository connections.

    Returns:
        List of connected repositories with their metadata
    """
    manager = get_repo_manager()
    connections = manager.list_connections()
    return ConnectionsListResponse(connections=connections)


def _repo_not_found(repo_id: str) -> HTTPException:
    """Consistent 404 for missing or stale repository connections."""
    return HTTPException(status_code=404, detail=f"Repository connection '{repo_id}' not found")


@app.delete("/repo/{repo_id}", tags=["Repo"])
async def disconnect_repo(repo_id: str) -> dict[str, bool]:
    """Disconnect and cleanup a repository connection.

    For cloned repos: removes the cloned directory
    For local repos: just removes the connection

    Args:
        repo_id: The connection ID to disconnect

    Returns:
        {"success": true} if disconnected, 404 if not found
    """
    manager = get_repo_manager()
    if manager.disconnect(repo_id):
        return {"success": True}
    raise _repo_not_found(repo_id)


# ============================================================================
# Repo Analysis Endpoints
# ============================================================================


@app.get("/repo", response_model=RepoInfoResponse, tags=["Repo"])
async def get_repo_info() -> RepoInfoResponse:
    """Get repository information and analysis.

    Returns metadata about the connected codebase including
    detected endpoints, services, and tool integration points.
    Reads from environment variables or git commands.
    """
    import subprocess
    from pathlib import Path

    # Try to get repo info from environment variables first
    repo_name = settings.repo_name
    repo_branch = settings.repo_branch
    if not repo_name and settings.repo_url:
        # Derive owner/repo from URL (e.g. https://github.com/Tanner-Eischen/ghostfolio -> Tanner-Eischen/ghostfolio)
        url = (settings.repo_url or "").strip().rstrip("/").replace(".git", "")
        parts = [p for p in url.split("/") if p]
        if len(parts) >= 2:
            repo_name = f"{parts[-2]}/{parts[-1]}"

    # Fallback to git commands if not set
    if not repo_name or not repo_branch:
        try:
            # Get repo root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent.parent,
                timeout=5,
            )
            if result.returncode == 0:
                repo_root = Path(result.stdout.strip())

                # Get remote URL to extract repo name
                remote_result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    capture_output=True,
                    text=True,
                    cwd=repo_root,
                    timeout=5,
                )
                if remote_result.returncode == 0:
                    remote_url = remote_result.stdout.strip()
                    # Extract name from URLs like:
                    # https://github.com/user/repo.git -> user/repo
                    # git@github.com:user/repo.git -> user/repo
                    if remote_url:
                        remote_url = remote_url.replace(".git", "")
                        if "/" in remote_url:
                            parts = remote_url.split("/")
                            if len(parts) >= 2:
                                if not repo_name:
                                    repo_name = f"{parts[-2]}/{parts[-1]}"

                # Get current branch
                branch_result = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=repo_root,
                    timeout=5,
                )
                if branch_result.returncode == 0 and not repo_branch:
                    repo_branch = branch_result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug(f"Could not get git info: {e}")

    # Default values if still not set
    if not repo_name:
        repo_name = "ghostfolio-agent"
    if not repo_branch:
        repo_branch = "main"

    # Compute real values from code analysis
    endpoints = _count_fastapi_endpoints()
    modules = _detect_modules()
    tool_hooks = _count_tool_hooks()
    version = _get_version()

    return RepoInfoResponse(
        name=repo_name,
        version=version,
        status="indexed",
        endpoints=endpoints,
        services=len(modules),
        tool_hooks=tool_hooks,
    )


@app.get("/repo/dependencies", response_model=DependenciesResponse, tags=["Repo"])
async def get_repo_dependencies() -> DependenciesResponse:
    """Get repository dependency graph.

    Returns a graph structure with nodes (services, databases, etc.)
    and edges (relationships between them).

    This analyzes the codebase structure and imports to build
    a dependency graph for the mapper visualization.
    """
    nodes, edges = _analyze_repo_dependencies()
    return DependenciesResponse(nodes=nodes, edges=edges)


@app.get("/repo/{repo_id}", response_model=RepoInfoResponse, tags=["Repo"])
async def get_connected_repo_info(repo_id: str) -> RepoInfoResponse:
    """Get analysis for a connected repository.

    Args:
        repo_id: The connection ID returned from /repo/connect

    Returns:
        RepoInfoResponse with analysis of the connected repository
    """
    manager = get_repo_manager()
    repo_path = manager.get_repo_path(repo_id)
    connection = manager.get_connection(repo_id)

    if not repo_path or not connection:
        raise _repo_not_found(repo_id)

    # Analyze the connected repository
    modules = _detect_modules(target_path=repo_path)
    endpoints = _count_endpoints_in_path(repo_path)
    version = _get_version(target_path=repo_path)

    return RepoInfoResponse(
        name=connection.name,
        version=version,
        status="connected",
        endpoints=endpoints,
        services=len(modules),
        tool_hooks=0,  # Tool hooks are specific to this agent, not target repos
    )


# ============================================================================
# Code Analysis Helpers (Real Data)
# ============================================================================


def _analyze_python_imports(file_path: Path, target_path: Path | None = None, known_modules: list[str] | None = None) -> set[str]:
    """Extract internal module imports from a Python file using AST.

    Args:
        file_path: Path to Python file
        target_path: Root path of the target repository (for determining package name)
        known_modules: List of known module names to match imports against

    Returns:
        Set of module names imported from the target package
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (SyntaxError, FileNotFoundError, UnicodeDecodeError):
        return set()

    imports = set()

    # If we have known modules, use them to match imports
    if known_modules:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    # Check if import matches any known module
                    for mod in known_modules:
                        if alias.name == mod or alias.name.startswith(f"{mod}."):
                            imports.add(mod)
                            break
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # Check if from-import matches any known module
                    for mod in known_modules:
                        if node.module == mod or node.module.startswith(f"{mod}."):
                            imports.add(mod)
                            break
        return imports

    # Fallback: Determine the package prefix to look for
    package_prefix = "src."  # Default for ghostfolio-agent
    if target_path:
        # Try to detect the package name from the target path
        package_name = target_path.name
        if (target_path / package_name / "__init__.py").exists():
            package_prefix = f"{package_name}."
        elif (target_path / "src" / "__init__.py").exists():
            package_prefix = "src."
        else:
            # Look for any Python package in the target
            for item in target_path.iterdir():
                if item.is_dir() and (item / "__init__.py").exists() and not item.name.startswith("_"):
                    package_prefix = f"{item.name}."
                    break

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(package_prefix):
                    # Extract module name (e.g., "src.agent" -> "agent")
                    parts = alias.name.split(".")
                    if len(parts) >= 2:
                        imports.add(parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(package_prefix):
                # Extract module name
                parts = node.module.split(".")
                if len(parts) >= 2:
                    imports.add(parts[1])
    return imports


def _load_ts_path_aliases(repo_root: Path) -> dict[str, str]:
    """Load path aliases from tsconfig.base.json or tsconfig.json.

    Converts compilerOptions.paths like \"@ghostfolio/common/*\" -> [\"libs/common/src/lib/*\"]
    into alias -> module mapping: \"@ghostfolio/common\" -> \"libs/common\".
    """
    result: dict[str, str] = {}
    for tsconfig_name in ["tsconfig.base.json", "tsconfig.json"]:
        tsconfig_path = repo_root / tsconfig_name
        if not tsconfig_path.exists():
            continue
        try:
            config = json.loads(tsconfig_path.read_text(encoding="utf-8", errors="replace"))
            paths = config.get("compilerOptions", {}).get("paths", {}) or {}
            for alias_pattern, targets in paths.items():
                if not isinstance(targets, list) or not targets:
                    continue
                # "@ghostfolio/common/*" -> "@ghostfolio/common"
                alias = alias_pattern.rstrip("/*")
                if alias.startswith("@"):
                    # First target: "libs/common/src/lib/*" -> "libs/common"
                    target = targets[0]
                    if isinstance(target, str) and "*" in target:
                        module_part = target.split("*")[0].rstrip("/").replace("\\", "/")
                        # "libs/common/src/lib" -> take first two segments as "libs/common"
                        parts = module_part.split("/")
                        if len(parts) >= 2:
                            result[alias] = f"{parts[0]}/{parts[1]}"
                        elif len(parts) == 1:
                            result[alias] = parts[0]
                    elif isinstance(target, str):
                        result[alias] = target.split("/")[0]
            if result:
                break
        except (json.JSONDecodeError, OSError):
            continue
    return result


def _analyze_ts_imports(
    file_path: Path, repo_root: Path, modules: list[str], path_aliases: dict[str, str] | None = None
) -> set[str]:
    """Extract internal module imports from a TypeScript/JavaScript file via regex.

    Matches: import X from '@scope/name', from \"@scope/name\", from '../libs/name',
    require('@scope/name'). Uses tsconfig path aliases when available (e.g. @ghostfolio/common).
    """
    if path_aliases is None:
        path_aliases = _load_ts_path_aliases(repo_root)
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, UnicodeDecodeError):
        return set()
    # Build stem -> module mapping (e.g. "api" -> "apps/api", "domain" -> "libs/domain")
    stem_to_modules: dict[str, list[str]] = defaultdict(list)
    for mod in modules:
        stem = mod.split("/")[-1].split("\\")[-1]
        stem_to_modules[stem].append(mod)
    # Alias -> module from tsconfig (e.g. "@ghostfolio/common" -> "libs/common")
    alias_to_module: dict[str, str] = {}
    for alias, resolved in path_aliases.items():
        if resolved in modules:
            alias_to_module[alias] = resolved
    imports: set[str] = set()
    # from '@scope/name' or from \"@scope/name\" or from '../path/name'
    for m in re.finditer(
        r"""(?:from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
        content,
    ):
        path = (m.group(1) or m.group(2) or "").strip()
        if not path:
            continue
        # Resolve path aliases: @ghostfolio/common/foo -> libs/common
        path_normalized = path.replace("\\", "/")
        for alias, mod in alias_to_module.items():
            if path_normalized == alias or path_normalized.startswith(alias + "/"):
                imports.add(mod)
                break
        else:
            # Fallback: last segment as stem (../libs/domain -> domain)
            stem = path_normalized.split("/")[-1].split("@")[-1]
            if stem in stem_to_modules:
                for mod in stem_to_modules[stem]:
                    imports.add(mod)
    return imports


def _extract_external_deps_python(content: str, known_modules: list[str]) -> set[str]:
    """Extract top-level external package names from Python source (e.g. fastapi, pydantic)."""
    external: set[str] = set()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return external
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top and not any(top == m.split("/")[0].split("\\")[0] for m in known_modules):
                    external.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top and not any(top == m.split("/")[0].split("\\")[0] for m in known_modules):
                    external.add(top)
    return external


def _extract_external_deps_ts(content: str, path_aliases: dict[str, str], modules: list[str]) -> set[str]:
    """Extract external npm package names from TypeScript/JS source."""
    external: set[str] = set()
    alias_prefixes = {a for a in path_aliases}
    for m in re.finditer(
        r"""(?:from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
        content,
    ):
        path = (m.group(1) or m.group(2) or "").strip().replace("\\", "/")
        if not path or path.startswith("."):
            continue
        if any(path == a or path.startswith(a + "/") for a in alias_prefixes):
            continue
        # First segment is package name (e.g. @angular/core -> @angular/core, lodash -> lodash)
        if path.startswith("@"):
            parts = path.split("/")
            if len(parts) >= 2:
                external.add(f"{parts[0]}/{parts[1]}")
            elif len(parts) == 1:
                external.add(parts[0])
        else:
            external.add(path.split("/")[0])
    return external


def _count_fastapi_endpoints() -> int:
    """Count registered FastAPI endpoints.

    Returns:
        Number of unique route endpoints (counting each route once, not per method)
    """
    count = 0
    for route in app.routes:
        # Count routes that have methods (actual endpoints, not mounts)
        if hasattr(route, "methods") and route.methods:
            # Count each unique path as one endpoint
            count += 1
    return count


def _count_tool_hooks() -> int:
    """Count registered tool functions.

    Returns:
        Number of tools in the registry
    """
    try:
        from src.tools.registry import get_tool_count
        return get_tool_count()
    except Exception:
        return 0


def _count_endpoints_in_path(target_path: Path) -> int:
    """Count API endpoints in a target repository.

    Detects FastAPI/Flask (Python), NestJS decorators, and Express (TypeScript/JavaScript).
    """
    count = 0
    py_patterns = [
        r"@app\.(get|post|put|delete|patch)\s*\(",
        r"@router\.(get|post|put|delete|patch)\s*\(",
        r"@app\.route\s*\(",
        r"@blueprint\.(get|post|put|delete|patch)\s*\(",
        r"@api\.resource\s*\(",
    ]
    ts_patterns = [
        r"@(Get|Post|Put|Delete|Patch)\s*\(",
        r"@(Get|Post|Put|Delete|Patch)\s*\(\s*\)",
        r"\.(get|post|put|delete|patch)\s*\(",
        r"app\.(get|post|put|delete|patch)\s*\(",
        r"router\.(get|post|put|delete|patch)\s*\(",
    ]
    for py_file in target_path.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            for pattern in py_patterns:
                count += len(re.findall(pattern, content, re.IGNORECASE))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    for ts_file in target_path.rglob("*.ts"):
        if ".spec." in ts_file.name or ".test." in ts_file.name:
            continue
        try:
            content = ts_file.read_text(encoding="utf-8", errors="replace")
            for pattern in ts_patterns:
                count += len(re.findall(pattern, content, re.IGNORECASE))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    for js_file in target_path.rglob("*.js"):
        if ".spec." in js_file.name or ".test." in js_file.name:
            continue
        try:
            content = js_file.read_text(encoding="utf-8", errors="replace")
            for pattern in ts_patterns:
                count += len(re.findall(pattern, content, re.IGNORECASE))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return count


def _detect_modules(target_path: Path | None = None) -> list[str]:
    """Detect actual modules in src/ or target directory.

    Args:
        target_path: Optional path to target repository. If None, uses ghostfolio-agent's src/

    Returns:
        List of module directory names
    """
    if target_path:
        # Look for Python and TypeScript modules in target
        modules = []

        # Check for common TypeScript/Node project structures (Nx, etc.)
        for struct in ["apps", "libs", "src"]:
            struct_path = target_path / struct
            if struct_path.exists() and struct_path.is_dir():
                for item in struct_path.iterdir():
                    if item.is_dir() and not item.name.startswith(("_", ".")):
                        modules.append(f"{struct}/{item.name}")

        # Prisma (schema/migrations) as a first-class module
        if (target_path / "prisma").is_dir():
            modules.append("prisma")

        # Root-level dirs that contain code (e.g. tools); skip expanded structs and non-code dirs
        skip_root = {"node_modules", "dist", "build", "test", "tests", "docker", "data", ".git", ".config", ".husky", ".vscode", "apps", "libs", "src"}
        for item in target_path.iterdir():
            if not item.is_dir() or item.name.startswith(("_", ".")) or item.name == "__pycache__":
                continue
            if item.name in skip_root or item.name == "prisma":
                continue
            has_code = (
                (item / "__init__.py").exists()
                or any(item.rglob("*.py"))
                or any(item.rglob("*.ts"))
                or any(item.rglob("*.tsx"))
                or any(item.rglob("*.js"))
                or (item / "schema.prisma").exists()
            )
            if has_code and not any(m == item.name or m.endswith(f"/{item.name}") for m in modules):
                modules.append(item.name)

        return sorted(modules) if modules else ["(root)"]
    else:
        # Default behavior for ghostfolio-agent
        src_dir = Path(__file__).parent.parent
        modules = []
        if src_dir.exists():
            for item in src_dir.iterdir():
                if item.is_dir() and not item.name.startswith("_") and item.name != "__pycache__":
                    modules.append(item.name)
        return sorted(modules)


def _get_version(target_path: Path | None = None) -> str:
    """Get version from pyproject.toml, __init__.py, or git.

    Args:
        target_path: Optional path to target repository. If None, uses ghostfolio-agent's root

    Returns:
        Version string
    """
    import re
    import subprocess

    repo_root = target_path or Path(__file__).parent.parent.parent

    # Try pyproject.toml first
    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text(encoding="utf-8")
            for line in content.split("\n"):
                if line.startswith("version ="):
                    # Skip dynamic version specs like: version = { source = "file", ... }
                    if "{" in line:
                        # Try to extract path from dynamic version spec
                        match = re.search(r'path\s*=\s*["\']([^"\']+)["\']', line)
                        if match:
                            init_path = repo_root / match.group(1)
                            if init_path.exists():
                                init_content = init_path.read_text(encoding="utf-8")
                                # Look for __version__ = "x.y.z"
                                version_match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', init_content)
                                if version_match:
                                    version = version_match.group(1)
                                    return f"v{version}" if not version.startswith("v") else version
                        continue

                    version = line.split("=")[1].strip().strip('"').strip("'")
                    if version and not version.startswith("{"):
                        return f"v{version}" if not version.startswith("v") else version
        except Exception:
            pass

    # Try to find version in __init__.py files
    for init_file in repo_root.rglob("__init__.py"):
        try:
            content = init_file.read_text(encoding="utf-8")
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                version = match.group(1)
                return f"v{version}" if not version.startswith("v") else version
        except Exception:
            continue

    # Try git describe
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return "v0.1.0"


def _analyze_module_dependencies(target_path: Path, module_name: str) -> tuple[list[DependencyNode], list[DependencyEdge]]:
    """Analyze submodules within a specific module for drill-down view.

    Args:
        target_path: Root path of the repository
        module_name: Name of the module to drill down into (e.g., "fastapi")

    Returns:
        Tuple of (nodes, edges) for the module's internal structure
    """
    nodes: list[DependencyNode] = []
    edges: list[DependencyEdge] = []

    module_path = target_path / module_name
    if not module_path.exists() or not module_path.is_dir():
        return nodes, edges

    # Find all Python files and submodules
    submodules: dict[str, Path] = {}

    # Add Python files as submodules
    for py_file in module_path.glob("*.py"):
        if py_file.name != "__init__.py":
            name = py_file.stem
            submodules[name] = py_file

    # Add subdirectories as submodules
    for item in module_path.iterdir():
        if item.is_dir() and not item.name.startswith("_") and item.name != "__pycache__":
            if (item / "__init__.py").exists() or any(item.rglob("*.py")):
                submodules[item.name] = item

    # Analyze imports between submodules
    submodule_imports: dict[str, set[str]] = defaultdict(set)
    for sub_name, sub_path in submodules.items():
        if sub_path.is_file():
            imports = _analyze_submodule_imports(sub_path, module_name, list(submodules.keys()))
            submodule_imports[sub_name].update(imports)
        else:
            # For directories, analyze all Python files
            for py_file in sub_path.rglob("*.py"):
                imports = _analyze_submodule_imports(py_file, module_name, list(submodules.keys()))
                submodule_imports[sub_name].update(imports)

    # Build nodes
    for sub_name in sorted(submodules.keys()):
        # Determine type based on name patterns
        if "test" in sub_name.lower():
            node_type, icon, color = "service", "science", "emerald"
        elif "route" in sub_name.lower() or "api" in sub_name.lower():
            node_type, icon, color = "api", "api", "slate"
        elif "util" in sub_name.lower() or "helper" in sub_name.lower():
            node_type, icon, color = "service", "build", "indigo"
        elif "security" in sub_name.lower() or "auth" in sub_name.lower():
            node_type, icon, color = "service", "lock", "emerald"
        elif "openapi" in sub_name.lower() or "doc" in sub_name.lower():
            node_type, icon, color = "service", "description", "indigo"
        else:
            node_type, icon, color = "service", "extension", "indigo"

        nodes.append(DependencyNode(
            id=f"submodule-{sub_name}",
            name=sub_name.replace("_", " ").title(),
            type=node_type,
            icon=icon,
            color=color,
        ))

    # Build edges
    for sub_name, imports in submodule_imports.items():
        for imported in imports:
            if imported in submodules and imported != sub_name:
                edges.append(DependencyEdge(
                    source=f"submodule-{sub_name}",
                    target=f"submodule-{imported}",
                ))

    return nodes, edges


def _analyze_submodule_imports(file_path: Path, module_name: str, known_submodules: list[str]) -> set[str]:
    """Extract submodule imports from a Python file.

    Args:
        file_path: Path to Python file
        module_name: Parent module name (e.g., "fastapi")
        known_submodules: List of known submodule names

    Returns:
        Set of submodule names imported
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (SyntaxError, FileNotFoundError, UnicodeDecodeError):
        return set()

    imports = set()
    module_prefix = f"{module_name}."

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(module_prefix):
                    # Extract submodule name (e.g., "fastapi.routing" -> "routing")
                    parts = alias.name.split(".")
                    if len(parts) >= 2 and parts[1] in known_submodules:
                        imports.add(parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                if node.module.startswith(module_prefix):
                    parts = node.module.split(".")
                    if len(parts) >= 2 and parts[1] in known_submodules:
                        imports.add(parts[1])
                elif node.module == module_name:
                    # from fastapi import X - check level
                    if node.level == 0:
                        # Relative import check for sibling modules
                        pass

    return imports


def _find_nodes_in_cycles(edges: list[DependencyEdge]) -> set[str]:
    """Find all node IDs that participate in at least one cycle (Tarjan's SCC).

    Returns:
        Set of node ids that are in a strongly connected component of size > 1.
    """
    if not edges:
        return set()
    # Build adjacency list
    adj: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        adj[e.source].append(e.target)
    all_nodes = set(adj) | {e.target for e in edges}
    index_counter = [0]
    stack: list[str] = []
    lowlink: dict[str, int] = {}
    index: dict[str, int] = {}
    on_stack: dict[str, bool] = defaultdict(bool)
    sccs: list[set[str]] = []

    def strongconnect(v: str) -> None:
        index[v] = index_counter[0]
        lowlink[v] = index_counter[0]
        index_counter[0] += 1
        stack.append(v)
        on_stack[v] = True
        for w in adj.get(v, []):
            if w not in index:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack[w]:
                lowlink[v] = min(lowlink[v], index[w])
        if lowlink[v] == index[v]:
            scc: set[str] = set()
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.add(w)
                if w == v:
                    break
            sccs.append(scc)

    for node in all_nodes:
        if node not in index:
            strongconnect(node)

    in_cycle: set[str] = set()
    for scc in sccs:
        if len(scc) > 1:
            in_cycle |= scc
    return in_cycle


def _analyze_repo_dependencies(target_path: Path | None = None) -> tuple[list[DependencyNode], list[DependencyEdge]]:
    """Analyze the repository structure and build dependency graph from actual imports.

    Scans the src/ or target directory for modules, parses Python files using AST
    to extract import statements, and builds a real dependency graph.

    Args:
        target_path: Optional path to target repository. If None, uses ghostfolio-agent's src/
    """
    if target_path:
        repo_root = target_path
        src_dir = target_path
    else:
        repo_root = Path(__file__).parent.parent.parent
        src_dir = repo_root / "src"

    nodes: list[DependencyNode] = []
    edges: list[DependencyEdge] = []

    # Detect actual modules
    modules = _detect_modules(target_path=target_path)
    path_aliases = _load_ts_path_aliases(repo_root) if target_path else {}

    # Analyze imports and collect per-module stats and edge weights
    module_imports: dict[str, set[str]] = defaultdict(set)
    module_file_count: dict[str, int] = defaultdict(int)
    module_line_count: dict[str, int] = defaultdict(int)
    module_external_deps: dict[str, set[str]] = defaultdict(set)
    edge_weights: dict[tuple[str, str], int] = defaultdict(int)

    for module in modules:
        module_dir = src_dir / module
        if not module_dir.exists():
            continue
        for py_file in module_dir.rglob("*.py"):
            module_file_count[module] += 1
            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
                module_line_count[module] += len(content.splitlines())
                imports = _analyze_python_imports(py_file, target_path=target_path, known_modules=modules)
                module_imports[module].update(imports)
                for imp in imports:
                    edge_weights[(module, imp)] += 1
                module_external_deps[module].update(_extract_external_deps_python(content, modules))
            except (FileNotFoundError, UnicodeDecodeError):
                pass
        if target_path:
            for ts_file in module_dir.rglob("*.ts"):
                if ".spec." in ts_file.name or ".test." in ts_file.name:
                    continue
                module_file_count[module] += 1
                try:
                    content = ts_file.read_text(encoding="utf-8", errors="replace")
                    module_line_count[module] += len(content.splitlines())
                    imports = _analyze_ts_imports(ts_file, repo_root, modules, path_aliases)
                    module_imports[module].update(imports)
                    for imp in imports:
                        edge_weights[(module, imp)] += 1
                    module_external_deps[module].update(
                        _extract_external_deps_ts(content, path_aliases, modules)
                    )
                except (FileNotFoundError, UnicodeDecodeError):
                    pass
            for tsx_file in module_dir.rglob("*.tsx"):
                if ".spec." in tsx_file.name or ".test." in tsx_file.name:
                    continue
                module_file_count[module] += 1
                try:
                    content = tsx_file.read_text(encoding="utf-8", errors="replace")
                    module_line_count[module] += len(content.splitlines())
                    imports = _analyze_ts_imports(tsx_file, repo_root, modules, path_aliases)
                    module_imports[module].update(imports)
                    for imp in imports:
                        edge_weights[(module, imp)] += 1
                    module_external_deps[module].update(
                        _extract_external_deps_ts(content, path_aliases, modules)
                    )
                except (FileNotFoundError, UnicodeDecodeError):
                    pass
            for js_file in module_dir.rglob("*.js"):
                if ".spec." in js_file.name or ".test." in js_file.name:
                    continue
                module_file_count[module] += 1
                try:
                    content = js_file.read_text(encoding="utf-8", errors="replace")
                    module_line_count[module] += len(content.splitlines())
                    imports = _analyze_ts_imports(js_file, repo_root, modules, path_aliases)
                    module_imports[module].update(imports)
                    for imp in imports:
                        edge_weights[(module, imp)] += 1
                    module_external_deps[module].update(
                        _extract_external_deps_ts(content, path_aliases, modules)
                    )
                except (FileNotFoundError, UnicodeDecodeError):
                    pass

    # Module display configuration
    module_config = {
        "agent": {"name": "Agent Core", "type": "agent", "icon": "smart_toy", "color": "primary"},
        "api": {"name": "API Routes", "type": "api", "icon": "api", "color": "slate"},
        "tools": {"name": "Tool Registry", "type": "service", "icon": "build", "color": "indigo"},
        "verification": {"name": "Verification Layer", "type": "service", "icon": "verified", "color": "indigo"},
        "utils": {"name": "Utilities", "type": "service", "icon": "settings", "color": "indigo"},
        "repo": {"name": "Repository Manager", "type": "service", "icon": "folder", "color": "indigo"},
    }

    # Add Agent Core as central node (only for ghostfolio-agent, not target repos)
    if not target_path:
        nodes.append(DependencyNode(
            id="agent-core",
            name="Agent Core",
            type="agent",
            icon="smart_toy",
            color="primary",
        ))

        # Add database node (external dependency)
        nodes.append(DependencyNode(
            id="database",
            name="Database",
            type="database",
            icon="database",
            color="emerald",
        ))

    def _mid(m: str) -> str:
        return f"module-{m.replace('/', '-').replace(chr(92), '-')}"

    # Add nodes for detected modules (has_circular set later after cycle detection)
    for module in modules:
        config = module_config.get(module, {
            "name": module.split("/")[-1].split("\\")[-1].replace("_", " ").title(),
            "type": "service",
            "icon": "extension",
            "color": "indigo"
        })
        nodes.append(DependencyNode(
            id=_mid(module),
            name=config["name"],
            type=config["type"],
            icon=config["icon"],
            color=config["color"],
            file_count=module_file_count.get(module, 0),
            line_count=module_line_count.get(module, 0),
            external_deps=sorted(module_external_deps.get(module, set())),
            has_circular=False,
        ))

    # Build edges from actual import analysis (with weight = number of files importing)
    for module, imports in module_imports.items():
        for imported in imports:
            if imported in modules and imported != module:
                weight = edge_weights.get((module, imported), 1)
                edges.append(DependencyEdge(
                    source=_mid(module),
                    target=_mid(imported),
                    weight=weight,
                    import_types=[],
                ))

    # Add agent core connections (only for ghostfolio-agent)
    if not target_path:
        # Add agent core connections (API routes to agent)
        if "api" in modules:
            edges.append(DependencyEdge(source="module-api", target="agent-core", label="routes"))

        # Agent core uses tools
        if "tools" in modules:
            edges.append(DependencyEdge(source="agent-core", target="module-tools", label="invokes", weight=1, import_types=[]))

        # Agent core uses verification
        if "verification" in modules:
            edges.append(DependencyEdge(source="agent-core", target="module-verification", label="verifies", weight=1, import_types=[]))

    # Mark nodes that participate in circular dependencies
    cycle_node_ids = _find_nodes_in_cycles(edges)
    for i, node in enumerate(nodes):
        if node.id in cycle_node_ids:
            nodes[i] = node.model_copy(update={"has_circular": True})

    return nodes, edges


@app.get("/repo/{repo_id}/dependencies", response_model=DependenciesResponse, tags=["Repo"])
async def get_connected_repo_dependencies(repo_id: str) -> DependenciesResponse:
    """Get dependency graph for a connected repository.

    Args:
        repo_id: The connection ID returned from /repo/connect

    Returns:
        DependenciesResponse with nodes and edges for the target repository
    """
    manager = get_repo_manager()
    repo_path = manager.get_repo_path(repo_id)

    if not repo_path:
        raise _repo_not_found(repo_id)

    nodes, edges = _analyze_repo_dependencies(target_path=repo_path)
    return DependenciesResponse(nodes=nodes, edges=edges)


@app.get("/repo/{repo_id}/dependencies/{module_name}", response_model=DependenciesResponse, tags=["Repo"])
async def get_module_dependencies(repo_id: str, module_name: str) -> DependenciesResponse:
    """Get dependency graph for a specific module (drill-down view).

    Analyzes submodules/files within a module and their internal dependencies.
    Use this to drill down into a module node from the top-level graph.

    Args:
        repo_id: The connection ID returned from /repo/connect
        module_name: The module to analyze (e.g., "fastapi", "tests")

    Returns:
        DependenciesResponse with nodes and edges for the module's internal structure
    """
    manager = get_repo_manager()
    repo_path = manager.get_repo_path(repo_id)

    if not repo_path:
        raise _repo_not_found(repo_id)

    if ".." in module_name or "/" in module_name or "\\" in module_name:
        raise HTTPException(status_code=400, detail="Invalid module name")

    nodes, edges = _analyze_module_dependencies(repo_path, module_name)
    return DependenciesResponse(nodes=nodes, edges=edges)


# ============================================================================
# File Explorer & Code Preview Endpoints
# ============================================================================


class FileNode(BaseModel):
    """A file or directory node in the file tree."""

    name: str = Field(..., description="File or directory name")
    path: str = Field(..., description="Relative path from repo root")
    type: str = Field(..., description="file or directory")
    children: list["FileNode"] | None = Field(default=None, description="Child nodes for directories")


class FileTreeResponse(BaseModel):
    """File tree response."""

    root: FileNode = Field(..., description="Root node of the file tree")


class InjectionPoint(BaseModel):
    """A detected injection point in the code."""

    file_path: str = Field(..., description="Path to the file")
    line_number: int = Field(..., description="Starting line number")
    code_snippet: list[str] = Field(..., description="Lines of code")
    route_type: str = Field(..., description="HTTP method (get, post, etc.)")
    route_path: str = Field(..., description="Route path")


class InjectionPointsResponse(BaseModel):
    """Detected injection points response."""

    points: list[InjectionPoint] = Field(..., description="List of injection points")
    total: int = Field(..., description="Total count")


class CodebaseInsight(BaseModel):
    """AI-generated codebase insight."""

    summary: str = Field(..., description="Brief summary of the codebase")
    entry_points: list[str] = Field(..., description="Suggested entry points for agent integration")
    architecture: str = Field(..., description="Architecture pattern detected")
    recommendations: list[str] = Field(..., description="Integration recommendations")


@app.get("/repo/{repo_id}/files", response_model=FileTreeResponse, tags=["Repo"])
async def get_repo_files(repo_id: str, max_depth: int = 3) -> FileTreeResponse:
    """Get file tree for a connected repository.

    Args:
        repo_id: The connection ID
        max_depth: Maximum depth to traverse (default 3)

    Returns:
        FileTreeResponse with nested file/directory structure
    """
    manager = get_repo_manager()
    repo_path = manager.get_repo_path(repo_id)

    if not repo_path:
        raise _repo_not_found(repo_id)

    def build_tree(path: Path, depth: int = 0) -> FileNode:
        name = path.name
        rel_path = str(path.relative_to(repo_path))

        if path.is_file():
            return FileNode(name=name, path=rel_path, type="file")

        children = None
        if depth < max_depth:
            children = []
            # Skip hidden directories and common non-essential dirs
            skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", ".idea", ".vscode", "dist", "build"}
            try:
                for item in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    if item.name.startswith(".") or item.name in skip_dirs:
                        continue
                    if item.is_file() and not item.suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".yaml", ".yml", ".md", ".toml"}:
                        continue
                    children.append(build_tree(item, depth + 1))
            except PermissionError:
                pass

        return FileNode(name=name, path=rel_path, type="directory", children=children)

    root = build_tree(repo_path)
    return FileTreeResponse(root=root)


@app.get("/repo/{repo_id}/injection-points", response_model=InjectionPointsResponse, tags=["Repo"])
async def get_injection_points(repo_id: str, limit: int = 10) -> InjectionPointsResponse:
    """Get detected injection points (API routes) for agent integration.

    Scans for FastAPI, Flask, and similar route decorators.

    Args:
        repo_id: The connection ID
        limit: Maximum number of points to return

    Returns:
        InjectionPointsResponse with detected route handlers
    """
    manager = get_repo_manager()
    repo_path = manager.get_repo_path(repo_id)

    if not repo_path:
        raise _repo_not_found(repo_id)

    points = []
    py_patterns = [
        (r"@app\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", "fastapi"),
        (r"@router\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", "fastapi"),
        (r"@app\.route\s*\(\s*['\"]([^'\"]+)['\"]", "flask"),
    ]
    ts_patterns = [
        (r"@(Get|Post|Put|Delete|Patch)\s*\(\s*['\"`]?([^'\"`)]*)['\"`]?\s*\)", "nestjs"),
        (r"\.(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"`]+)['\"`]", "express"),
        (r"app\.(get|post|put|delete|patch)\s*\(\s*['\"`]([^'\"`]+)['\"`]", "express"),
    ]

    def add_point(rel_path: str, line_number: int, lines: list[str], route_type: str, route_path: str, i: int) -> None:
        start = max(0, i - 2)
        end = min(len(lines), i + 8)
        points.append(InjectionPoint(
            file_path=rel_path,
            line_number=line_number,
            code_snippet=lines[start:end],
            route_type=route_type.upper(),
            route_path=route_path or "/",
        ))

    for py_file in repo_path.rglob("*.py"):
        if len(points) >= limit:
            break
        try:
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            rel_path = str(py_file.relative_to(repo_path))
            for i, line in enumerate(lines):
                for pattern, _ in py_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        route_type = match.group(1).upper()
                        route_path = match.group(2) if match.lastindex >= 2 else "/"
                        add_point(rel_path, i + 1, lines, route_type, route_path, i)
                        if len(points) >= limit:
                            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue

    for ts_file in repo_path.rglob("*.ts"):
        if len(points) >= limit:
            break
        if ".spec." in ts_file.name or ".test." in ts_file.name:
            continue
        try:
            content = ts_file.read_text(encoding="utf-8", errors="replace")
            lines = content.split("\n")
            rel_path = str(ts_file.relative_to(repo_path))
            for i, line in enumerate(lines):
                for pattern, _ in ts_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        route_type = (match.group(1) or "GET").upper()
                        route_path = match.group(2) if match.lastindex >= 2 and match.group(2) else "/"
                        add_point(rel_path, i + 1, lines, route_type, route_path, i)
                        if len(points) >= limit:
                            break
        except (UnicodeDecodeError, FileNotFoundError):
            continue

    return InjectionPointsResponse(points=points, total=len(points))


@app.get("/repo/{repo_id}/insights", response_model=CodebaseInsight, tags=["Repo"])
async def get_codebase_insights(repo_id: str) -> CodebaseInsight:
    """Get AI-generated codebase insights and integration recommendations.

    Analyzes the repository structure and provides suggestions for
    where and how to integrate an AI agent.

    Args:
        repo_id: The connection ID

    Returns:
        CodebaseInsight with analysis and recommendations
    """
    manager = get_repo_manager()
    repo_path = manager.get_repo_path(repo_id)

    if not repo_path:
        raise _repo_not_found(repo_id)

    connection = manager.get_connection(repo_id)
    repo_name = connection.name if connection else "Unknown"

    # Analyze structure
    modules = _detect_modules(target_path=repo_path)
    endpoints = _count_endpoints_in_path(repo_path)

    # Detect framework from package.json (Node/TypeScript repos)
    has_nx = False
    has_angular = False
    has_nest = False
    pkg_path = repo_path / "package.json"
    if pkg_path.exists():
        try:
            import json
            pkg = json.loads(pkg_path.read_text(encoding="utf-8", errors="replace"))
            deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
            has_nx = "nx" in deps or (pkg.get("name") == "ghostfolio")
            has_angular = any("angular" in k.lower() for k in deps)
            has_nest = any("nestjs" in k.lower() or "nest-" in k.lower() for k in deps)
        except Exception:
            pass

    # Detect framework/architecture (Python)
    has_fastapi = (repo_path / "fastapi").is_dir() or any(
        "fastapi" in f.read_text(encoding="utf-8", errors="ignore").lower()
        for f in repo_path.rglob("*.py")
        if f.stat().st_size < 100000
    ) if repo_path.exists() else False

    # Generate insights based on analysis
    if has_nx or has_angular:
        architecture = "Nx Monorepo (Angular + Node)"
        if has_nest:
            architecture = "Nx Monorepo (Angular + NestJS API)"
        entry_points = [m for m in modules if "api" in m.lower() or "server" in m.lower()][:5] or modules[:5] or ["(root)"]
        summary = f"Nx/TypeScript repo with {len(modules)} apps/libs, {endpoints} detected endpoints. Frontend (Angular) and API (NestJS/Node) structure."
        recommendations = [
            "Integrate agent via API app: add a new NestJS module or controller for agent endpoints",
            "Use Nx libs for shared agent client or types",
            "Consider server-side agent in apps/api and client calls from Angular apps/client",
        ]
    elif has_fastapi or "fastapi" in repo_name.lower():
        architecture = "FastAPI Async Web Framework"
        entry_points = ["fastapi/applications.py", "fastapi/routing.py"]
        summary = f"FastAPI is a modern async web framework with {endpoints} detected routes and {len(modules)} modules."
        recommendations = [
            "Inject agent at FastAPI application startup via lifespan context",
            "Add middleware for request/response interception",
            "Use dependency injection for agent service integration",
        ]
    else:
        architecture = "Python Package" if any(repo_path.rglob("*.py")) else ("Node/TypeScript" if any(repo_path.rglob("*.ts")) else "Unknown")
        entry_points = modules[:5] if modules else ["(root)"]
        summary = f"Repository with {len(modules)} modules and {endpoints} detected endpoints."
        recommendations = [
            "Analyze entry points for agent integration opportunities",
            "Review module dependencies for optimal injection points",
            "Consider adding agent service as a separate module",
        ]

    return CodebaseInsight(
        summary=summary,
        entry_points=entry_points,
        architecture=architecture,
        recommendations=recommendations,
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
    repo_id: str | None = Field(default=None, description="Optional repo ID for context")


class ToolExecuteResponse(BaseModel):
    """Response from tool execution."""

    tool_name: str = Field(..., description="Name of the executed tool")
    success: bool = Field(..., description="Whether execution succeeded")
    result: Any = Field(..., description="Tool execution result")
    execution_time_ms: float = Field(..., description="Execution time in milliseconds")
    repo_context: str | None = Field(default=None, description="Repository context if provided")


@app.post("/tools/{tool_name}/execute", response_model=ToolExecuteResponse, tags=["Tools"])
async def execute_tool(tool_name: str, request: ToolExecuteRequest) -> ToolExecuteResponse:
    """Execute a tool with optional repository context.

    This endpoint allows executing registered tools with data from
    the connected repository (Page 1 analysis).

    Args:
        tool_name: Name of the tool to execute
        request: Execution request with parameters and optional repo context

    Returns:
        ToolExecuteResponse with the result
    """
    import time

    tool = get_tool_schema(tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")

    # Get repo context if provided
    repo_context = None
    if request.repo_id:
        manager = get_repo_manager()
        connection = manager.get_connection(request.repo_id)
        if connection:
            repo_context = connection.name

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
            repo_context=repo_context,
        )

    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        logger.error(f"Tool execution failed: {e}")

        return ToolExecuteResponse(
            tool_name=tool_name,
            success=False,
            result={"error": str(e)},
            execution_time_ms=round(execution_time, 2),
            repo_context=repo_context,
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


# ============================================================================
# Repo-Based Tool Suggestion Endpoints (Page 2 - Tool Library)
# ============================================================================


class ToolSuggestionParameter(BaseModel):
    """A parameter for a suggested tool."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(..., description="Parameter type (string, number, array, object)")
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether the parameter is required")


class ToolSuggestion(BaseModel):
    """A suggested tool based on repository analysis."""

    id: str = Field(..., description="Unique suggestion ID")
    name: str = Field(..., description="Suggested tool name")
    description: str = Field(..., description="What this tool would do")
    source_type: str = Field(..., description="How this was detected: endpoint, pattern, dependency")
    source_file: str | None = Field(default=None, description="File where this was detected")
    source_line: int | None = Field(default=None, description="Line number if applicable")
    parameters: list[ToolSuggestionParameter] = Field(default_factory=list, description="Suggested parameters")
    priority: str = Field(default="medium", description="Suggestion priority: high, medium, low")
    reasoning: str = Field(..., description="Why this tool is suggested")


class ToolSuggestionsResponse(BaseModel):
    """Response for tool suggestions based on repo analysis."""

    repo_id: str = Field(..., description="Repository ID")
    repo_name: str = Field(..., description="Repository name")
    suggestions: list[ToolSuggestion] = Field(default_factory=list, description="Tool suggestions")
    total_suggestions: int = Field(..., description="Total number of suggestions")
    analysis_summary: str = Field(..., description="Summary of the analysis")


class GeneratedToolResponse(BaseModel):
    """Response for a generated tool."""

    id: str = Field(..., description="Generated tool ID")
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters")
    generated_code: str = Field(..., description="Generated Python code for the tool")
    status: str = Field(default="generated", description="Tool status")
    source_suggestion_id: str = Field(..., description="ID of the suggestion this was generated from")


@app.get("/repo/{repo_id}/tool-suggestions", response_model=ToolSuggestionsResponse, tags=["Tools"])
async def get_tool_suggestions(repo_id: str) -> ToolSuggestionsResponse:
    """Get tool suggestions based on repository analysis.

    Analyzes the connected repository's injection points, dependencies,
    and insights to suggest tools that could be created for agent integration.

    This connects Page 1 (Dashboard analysis) to Page 2 (Tool Library).

    Args:
        repo_id: The connection ID from Page 1

    Returns:
        ToolSuggestionsResponse with suggested tools based on repo analysis
    """
    manager = get_repo_manager()
    repo_path = manager.get_repo_path(repo_id)
    connection = manager.get_connection(repo_id)

    if not repo_path or not connection:
        raise _repo_not_found(repo_id)

    suggestions: list[ToolSuggestion] = []

    # 1. Get injection points and convert to tool suggestions
    injection_points_data = await get_injection_points(repo_id, limit=50)

    for point in injection_points_data.points:
        # Determine priority based on route type
        priority = "high" if point.route_type in ["POST", "PUT"] else "medium"

        # Extract parameters from route path
        params: list[ToolSuggestionParameter] = []
        import re
        path_params = re.findall(r'\{(\w+)\}', point.route_path)
        for param in path_params:
            params.append(ToolSuggestionParameter(
                name=param,
                type="string",
                description=f"Path parameter: {param}",
                required=True,
            ))

        # Generate tool name from route
        tool_name = point.route_path.replace("/", "_").replace("{", "").replace("}", "").strip("_")
        if not tool_name:
            tool_name = f"{point.route_type.lower()}_endpoint"

        suggestions.append(ToolSuggestion(
            id=f"inj-{hash(point.file_path + str(point.line_number)) % 100000}",
            name=f"{tool_name}_tool",
            description=f"Tool to interact with {point.route_type} {point.route_path} endpoint",
            source_type="endpoint",
            source_file=point.file_path,
            source_line=point.line_number,
            parameters=params,
            priority=priority,
            reasoning=f"Detected {point.route_type} route at {point.route_path} - agent could use this to interact with the API",
        ))

    # 2. Get insights and add pattern-based suggestions
    insights_data = await get_codebase_insights(repo_id)

    # Add suggestions based on architecture
    arch_lower = insights_data.architecture.lower()
    if "fastapi" in arch_lower:
        suggestions.append(ToolSuggestion(
            id="arch-fastapi",
            name="api_request_tool",
            description="Generic tool to make authenticated requests to FastAPI endpoints",
            source_type="pattern",
            source_file=None,
            source_line=None,
            parameters=[
                ToolSuggestionParameter(name="endpoint", type="string", description="API endpoint path", required=True),
                ToolSuggestionParameter(name="method", type="string", description="HTTP method", required=True),
                ToolSuggestionParameter(name="data", type="object", description="Request body", required=False),
            ],
            priority="high",
            reasoning="FastAPI architecture detected - a generic API request tool would enable agent interaction with all endpoints",
        ))

    if "async" in arch_lower or "web framework" in arch_lower:
        suggestions.append(ToolSuggestion(
            id="arch-async",
            name="async_operation_tool",
            description="Tool to execute async operations and background tasks",
            source_type="pattern",
            source_file=None,
            source_line=None,
            parameters=[
                ToolSuggestionParameter(name="operation", type="string", description="Operation to execute", required=True),
                ToolSuggestionParameter(name="timeout", type="number", description="Timeout in seconds", required=False),
            ],
            priority="medium",
            reasoning="Async framework detected - agent may need to handle async operations",
        ))

    # 3. Add suggestions from recommendations
    for i, rec in enumerate(insights_data.recommendations[:3]):
        suggestions.append(ToolSuggestion(
            id=f"rec-{i}",
            name=f"integration_tool_{i}",
            description=rec,
            source_type="recommendation",
            source_file=None,
            source_line=None,
            parameters=[],
            priority="low",
            reasoning=f"Based on codebase analysis recommendation",
        ))

    # 4. Get dependencies and suggest tools for key modules
    deps_data = await get_connected_repo_dependencies(repo_id)

    # Find API/service modules and suggest tools
    for node in deps_data.nodes:
        if node.type == "api" or "api" in node.name.lower() or "route" in node.name.lower():
            suggestions.append(ToolSuggestion(
                id=f"dep-{node.id}",
                name=f"{node.name.lower().replace(' ', '_')}_tool",
                description=f"Tool to interact with {node.name} module",
                source_type="dependency",
                source_file=None,
                source_line=None,
                parameters=[
                    ToolSuggestionParameter(name="action", type="string", description="Action to perform", required=True),
                ],
                priority="medium",
                reasoning=f"Key {node.type} module detected in dependency graph - agent integration point",
            ))

    # Deduplicate by name and limit results
    seen_names = set()
    unique_suggestions = []
    for s in suggestions:
        if s.name not in seen_names:
            seen_names.add(s.name)
            unique_suggestions.append(s)

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    unique_suggestions.sort(key=lambda x: priority_order.get(x.priority, 3))

    # Limit to top 20 suggestions
    unique_suggestions = unique_suggestions[:20]

    analysis_summary = f"Analyzed {connection.name}: {len(injection_points_data.points)} endpoints, {len(deps_data.nodes)} modules, {len(insights_data.recommendations)} recommendations"

    return ToolSuggestionsResponse(
        repo_id=repo_id,
        repo_name=connection.name,
        suggestions=unique_suggestions,
        total_suggestions=len(unique_suggestions),
        analysis_summary=analysis_summary,
    )


class GenerateToolRequest(BaseModel):
    """Request to generate a tool from a suggestion."""

    suggestion_id: str = Field(..., description="ID of the tool suggestion to generate")
    custom_name: str | None = Field(default=None, description="Optional custom name for the tool")
    custom_description: str | None = Field(default=None, description="Optional custom description")


@app.post("/repo/{repo_id}/generate-tool", response_model=GeneratedToolResponse, tags=["Tools"])
async def generate_tool_from_suggestion(repo_id: str, request: GenerateToolRequest) -> GeneratedToolResponse:
    """Generate a tool from a suggestion.

    Takes a tool suggestion ID and generates the Python code for that tool.
    The tool is not registered but returned as code for review.

    Args:
        repo_id: The repository connection ID
        request: The generation request with suggestion ID

    Returns:
        GeneratedToolResponse with the generated tool code
    """
    # Get suggestions to find the requested one
    suggestions_data = await get_tool_suggestions(repo_id)

    suggestion = None
    for s in suggestions_data.suggestions:
        if s.id == request.suggestion_id:
            suggestion = s
            break

    if not suggestion:
        raise HTTPException(status_code=404, detail=f"Suggestion {request.suggestion_id} not found")

    # Generate tool code
    tool_name = request.custom_name or suggestion.name
    tool_description = request.custom_description or suggestion.description

    # Build parameters schema
    params_schema = []
    for p in suggestion.parameters:
        params_schema.append(f'        "{p.name}": {{"type": "{p.type}", "description": "{p.description}"}}')

    params_code = ",\n".join(params_schema) if params_schema else "        # No parameters"

    # Generate the tool code
    generated_code = f'''"""Generated tool: {tool_name}

{tool_description}

Source: {suggestion.source_type} detected in {suggestion.source_file or 'repository'}
Generated: {datetime.utcnow().isoformat()}
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Any


class {tool_name.title().replace("_", "")}Input(BaseModel):
    """Input schema for {tool_name}."""

    # TODO: Add input fields based on detected parameters
    pass


@tool
async def {tool_name}(**kwargs: Any) -> dict[str, Any]:
    """{tool_description}

    Args:
        **kwargs: Tool parameters

    Returns:
        Result dictionary with response data
    """
    # TODO: Implement tool logic
    # Source: {suggestion.source_file or 'repository analysis'}
    # Reasoning: {suggestion.reasoning}

    return {{
        "status": "not_implemented",
        "message": "Tool generated from repository analysis - implementation required",
        "source": "{suggestion.source_type}",
    }}


__all__ = ["{tool_name}"]
'''

    return GeneratedToolResponse(
        id=f"gen-{hash(tool_name) % 100000}",
        name=tool_name,
        description=tool_description,
        parameters={p.name: {"type": p.type, "required": p.required} for p in suggestion.parameters},
        generated_code=generated_code,
        status="generated",
        source_suggestion_id=suggestion.id,
    )


# ============================================================================
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

    return TraceDetailResponse(
        id=run["id"],
        timestamp=run["timestamp"] or "",
        duration_ms=run["duration_ms"],
        tokens_used=run["tokens_used"],
        status=run["status"],
        tool_calls=run.get("tool_calls", []),
        steps=run.get("steps", []),
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
async def run_evals_endpoint() -> dict[str, str]:
    """Run all evaluations.

    Triggers evaluation run for all test cases.
    This runs asynchronously and returns a run_id.
    """
    try:
        run_id = await run_evals_async()
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


class UsageStatsResponse(BaseModel):
    """Usage stats response model."""

    total_cost: float = Field(..., description="Total cost in USD")
    total_tokens: int = Field(..., description="Total tokens used")
    requests_count: int = Field(..., description="Total requests count")
    avg_cost_per_request: float = Field(..., description="Average cost per request")


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
    return UsageStatsResponse(
        total_cost=stats["total_cost"],
        total_tokens=stats["total_tokens"],
        requests_count=stats["requests_count"],
        avg_cost_per_request=stats["avg_cost_per_request"],
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
