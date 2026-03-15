"""LangSmith tracing and observability configuration.

This module provides:
- Automatic LangSmith configuration via environment variables
- @traceable decorator for instrumenting functions
- TraceContext for managing trace spans
- Helper functions for feedback and trace URLs
"""

import functools
import os
from collections.abc import Callable
from typing import Any, TypeVar

from langsmith import Client, traceable

from src.utils.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def configure_langsmith() -> bool:
    """Configure LangSmith tracing from settings.

    Sets the required environment variables for LangSmith tracing:
    - LANGSMITH_TRACING
    - LANGSMITH_ENDPOINT
    - LANGSMITH_API_KEY
    - LANGSMITH_PROJECT
    - LANGSMITH_WORKSPACE_ID (for org-scoped keys)

    Returns:
        True if LangSmith is properly configured
    """
    settings = get_settings()

    # Set environment variables for LangSmith (new format)
    if settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = str(settings.langsmith_tracing).lower()
        os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project

        # Set workspace ID for org-scoped keys
        if settings.langsmith_workspace_id:
            os.environ["LANGSMITH_WORKSPACE_ID"] = settings.langsmith_workspace_id

        logger.info(
            f"LangSmith tracing enabled for project: {settings.langsmith_project}"
        )
        return True
    else:
        logger.warning(
            "LANGSMITH_API_KEY not set - LangSmith tracing disabled. "
            "Set LANGSMITH_API_KEY in your environment to enable tracing."
        )
        return False


def is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is enabled.

    Returns:
        True if tracing is enabled and configured
    """
    settings = get_settings()
    return bool(settings.langsmith_api_key and settings.langsmith_tracing)


def get_langsmith_client() -> Client | None:
    """Get a LangSmith client instance.

    Returns:
        LangSmith Client if configured, None otherwise
    """
    if not is_tracing_enabled():
        return None

    try:
        return Client(
            api_url=get_settings().langsmith_endpoint,
            api_key=get_settings().langsmith_api_key,
        )
    except Exception as e:
        logger.error(f"Failed to create LangSmith client: {e}")
        return None


def get_trace_url(run_id: str | None = None) -> str | None:
    """Get the URL to view a trace in LangSmith.

    Args:
        run_id: Optional run ID. If not provided, returns None.

    Returns:
        URL string if tracing is enabled and run_id provided, None otherwise
    """
    if not is_tracing_enabled() or not run_id:
        return None

    settings = get_settings()
    project = settings.langsmith_project

    # Format: https://smith.langchain.com/o/{org}/projects/p/{project}/r/{run_id}
    return f"{settings.langsmith_endpoint}/o/default/projects/p/{project}/r/{run_id}"


def traced(
    name: str | None = None,
    run_type: str = "chain",
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Decorator to trace a function with LangSmith.

    Args:
        name: Name for the trace (defaults to function name)
        run_type: Type of run (chain, llm, tool, etc.)
        tags: Tags to attach to the trace
        metadata: Metadata to attach to the trace

    Returns:
        Decorated function

    Example:
        @traced("analyze_portfolio", run_type="tool")
        async def analyze_portfolio(user_id: str) -> dict:
            ...
    """
    def decorator(func: F) -> F:
        trace_name = name or func.__name__

        @traceable(
            name=trace_name,
            run_type=run_type,
            tags=tags or [],
            metadata=metadata or {},
        )
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        @traceable(
            name=trace_name,
            run_type=run_type,
            tags=tags or [],
            metadata=metadata or {},
        )
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


class TraceContext:
    """Context manager for managing trace spans.

    Example:
        async with TraceContext("portfolio_analysis", tags=["api"]) as ctx:
            ctx.add_metadata({"user_id": "123"})
            result = await analyze()
    """

    def __init__(
        self,
        name: str,
        run_type: str = "chain",
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.name = name
        self.run_type = run_type
        self.tags = list(tags) if tags else []
        self.metadata = dict(metadata) if metadata else {}
        self._run_id: str | None = None

    def add_tags(self, new_tags: list[str]) -> None:
        """Add tags to the trace context."""
        self.tags.extend(new_tags)

    def add_metadata(self, new_metadata: dict[str, Any]) -> None:
        """Add metadata to the trace context."""
        self.metadata.update(new_metadata)

    async def __aenter__(self):
        """Enter the trace context."""
        if is_tracing_enabled():
            self._run_id = f"trace-{self.name}"
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the trace context."""
        return False


def log_feedback(
    run_id: str,
    score: float,
    key: str = "user_rating",
    comment: str | None = None,
) -> bool:
    """Log feedback for a trace run.

    Args:
        run_id: The run ID to log feedback for
        score: Feedback score (0.0 to 1.0)
        key: Key for the feedback
        comment: Optional comment

    Returns:
        True if feedback was logged successfully
    """
    client = get_langsmith_client()
    if not client:
        logger.warning("Cannot log feedback: LangSmith client not configured")
        return False

    try:
        client.create_feedback(
            run_id=run_id,
            key=key,
            score=score,
            comment=comment,
        )
        logger.debug(f"Logged feedback for run {run_id}: {score}")
        return True
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")
        return False


# Re-export traceable for convenience
__all__ = [
    "configure_langsmith",
    "is_tracing_enabled",
    "get_langsmith_client",
    "get_trace_url",
    "traced",
    "TraceContext",
    "log_feedback",
    "traceable",
]


# Initialize tracing on module import
_tracing_configured = configure_langsmith()
