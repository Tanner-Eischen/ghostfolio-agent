"""System endpoints for Ghostfolio Agent API.

Health check, metrics, and root endpoints.
"""

from datetime import datetime

from fastapi import APIRouter

from src.api.dependencies import get_chat_request_count, get_latency_stats
from src.api.models import HealthResponse
from src.utils.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check() -> HealthResponse:
    """Health check endpoint.

    Returns the current health status of the API and its dependencies.

    Returns:
        Health status with dependency information
    """
    _ = get_latency_stats()  # Available for future use

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.environment,
        timestamp=datetime.utcnow().isoformat(),
        dependencies={
            "ghostfolio_api": "unknown",  # Would need actual check
            "openai_api": "configured" if settings.openai_api_key else "not_configured",
        },
    )


@router.get("/", tags=["System"])
async def root() -> dict[str, str]:
    """Root endpoint with API information.

    Returns basic API information and useful links.

    Returns:
        API information and links
    """
    return {
        "name": "Ghostfolio Agent API",
        "version": "0.1.0",
        "description": "AI-powered portfolio assistant for Ghostfolio",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/metrics", tags=["System"])
async def get_metrics() -> dict:
    """Get performance metrics.

    Returns performance metrics including latency statistics.

    Returns:
        Performance metrics
    """
    latency_stats = get_latency_stats()

    return {
        "chat_requests_total": get_chat_request_count(),
        "latency_p50_ms": latency_stats["p50_ms"],
        "latency_p95_ms": latency_stats["p95_ms"],
        "latency_avg_ms": latency_stats["avg_ms"],
    }
