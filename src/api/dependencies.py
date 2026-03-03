"""Shared dependencies for Ghostfolio Agent API.

This module provides dependency injection functions and shared state
for the API endpoints.
"""

from collections import deque
from typing import Any

from src.agent import GhostfolioAgent
from src.utils.config_store import get_agent_config_store
from src.utils.logging import get_logger

logger = get_logger(__name__)

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


def get_chat_request_count() -> int:
    """Get the total chat request count."""
    return _chat_request_count


def increment_chat_request_count() -> int:
    """Increment and return the chat request count."""
    global _chat_request_count
    _chat_request_count += 1
    return _chat_request_count


def add_latency_sample(latency_ms: float) -> None:
    """Add a latency sample for metrics."""
    _latency_samples.append(latency_ms)


def get_latency_samples() -> list[float]:
    """Get latency samples as a list."""
    return list(_latency_samples)


def get_latency_stats() -> dict[str, Any]:
    """Calculate latency statistics from samples."""
    if not _latency_samples:
        return {
            "p50_ms": None,
            "p95_ms": None,
            "avg_ms": None,
        }

    samples = sorted(_latency_samples)
    n = len(samples)

    # Calculate percentiles
    p50_idx = int(n * 0.50)
    p95_idx = int(n * 0.95)

    return {
        "p50_ms": round(samples[p50_idx], 2) if p50_idx < n else None,
        "p95_ms": round(samples[p95_idx], 2) if p95_idx < n else None,
        "avg_ms": round(sum(samples) / n, 2),
    }
