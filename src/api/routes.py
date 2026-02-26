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
from collections import defaultdict
from contextlib import asynccontextmanager
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


class DependencyEdge(BaseModel):
    """An edge in the dependency graph."""

    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    label: str | None = Field(default=None, description="Optional edge label")


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
    manager = get_repo_manager()
    return await manager.connect(request)


@app.get("/repo/connections", response_model=ConnectionsListResponse, tags=["Repo"])
async def list_connections() -> ConnectionsListResponse:
    """List all active repository connections.

    Returns:
        List of connected repositories with their metadata
    """
    manager = get_repo_manager()
    connections = manager.list_connections()
    return ConnectionsListResponse(connections=connections)


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
    raise HTTPException(status_code=404, detail=f"Connection {repo_id} not found")


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

    if not repo_path:
        raise HTTPException(status_code=404, detail=f"Repository connection {repo_id} not found")

    connection = manager.get_connection(repo_id)
    if not connection:
        raise HTTPException(status_code=404, detail=f"Repository connection {repo_id} not found")

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

    Detects FastAPI routes (@app.get, @router.post), Flask routes (@app.route),
    and similar patterns.

    Args:
        target_path: Path to the target repository

    Returns:
        Number of detected API endpoints
    """
    count = 0

    # Patterns to look for in Python files
    route_patterns = [
        r"@app\.(get|post|put|delete|patch)\s*\(",
        r"@router\.(get|post|put|delete|patch)\s*\(",
        r"@app\.route\s*\(",
        r"@blueprint\.(get|post|put|delete|patch)\s*\(",
        r"@api\.resource\s*\(",
    ]

    import re

    for py_file in target_path.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
            for pattern in route_patterns:
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
        # Look for Python package directories in target
        modules = []
        for item in target_path.iterdir():
            if item.is_dir() and not item.name.startswith(("_", ".")) and item.name != "pycache__":
                # Check if it's a Python package or a module directory
                if (item / "__init__.py").exists() or any(item.rglob("*.py")):
                    modules.append(item.name)
        return sorted(modules)
    else:
        # Default behavior for ghostfolio-agent
        src_dir = Path(__file__).parent.parent
        modules = []
        if src_dir.exists():
            for item in src_dir.iterdir():
                if item.is_dir() and not item.name.startswith("_") and not item.name == "pycache":
                    modules.append(item.name)
        return sorted(modules)


def _get_version(target_path: Path | None = None) -> str:
    """Get version from pyproject.toml or git.

    Args:
        target_path: Optional path to target repository. If None, uses ghostfolio-agent's root

    Returns:
        Version string
    """
    import subprocess

    repo_root = target_path or Path(__file__).parent.parent.parent

    # Try pyproject.toml first
    pyproject_path = repo_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text(encoding="utf-8")
            # Simple regex-free parsing for version
            for line in content.split("\n"):
                if line.startswith("version ="):
                    version = line.split("=")[1].strip().strip('"').strip("'")
                    if version:
                        return f"v{version}" if not version.startswith("v") else version
        except Exception:
            pass

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
        if item.is_dir() and not item.name.startswith("_") and item.name != "pycache__":
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

    # Analyze imports for each module
    module_imports: dict[str, set[str]] = defaultdict(set)
    for module in modules:
        module_dir = src_dir / module
        if module_dir.exists():
            for py_file in module_dir.rglob("*.py"):
                imports = _analyze_python_imports(py_file, target_path=target_path, known_modules=modules)
                module_imports[module].update(imports)

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

    # Add nodes for detected modules
    for module in modules:
        config = module_config.get(module, {
            "name": module.replace("_", " ").title(),
            "type": "service",
            "icon": "extension",
            "color": "indigo"
        })
        nodes.append(DependencyNode(
            id=f"module-{module}",
            name=config["name"],
            type=config["type"],
            icon=config["icon"],
            color=config["color"],
        ))

    # Build edges from actual import analysis
    for module, imports in module_imports.items():
        for imported in imports:
            # Only create edges for modules that exist
            if imported in modules and imported != module:
                edges.append(DependencyEdge(
                    source=f"module-{module}",
                    target=f"module-{imported}",
                ))

    # Add agent core connections (only for ghostfolio-agent)
    if not target_path:
        # Add agent core connections (API routes to agent)
        if "api" in modules:
            edges.append(DependencyEdge(source="module-api", target="agent-core", label="routes"))

        # Agent core uses tools
        if "tools" in modules:
            edges.append(DependencyEdge(source="agent-core", target="module-tools", label="invokes"))

        # Agent core uses verification
        if "verification" in modules:
            edges.append(DependencyEdge(source="agent-core", target="module-verification", label="verifies"))

    return nodes, edges


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
        raise HTTPException(status_code=404, detail=f"Repository connection {repo_id} not found")

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
        raise HTTPException(status_code=404, detail=f"Repository connection {repo_id} not found")

    nodes, edges = _analyze_module_dependencies(repo_path, module_name)
    return DependenciesResponse(nodes=nodes, edges=edges)


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
            tool_calls=run.get("metadata", {}).get("tool_names", []),
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
        return {"run_id": "", "status": "error", "error": str(e)}


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
