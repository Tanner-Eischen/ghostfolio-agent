"""FastAPI app creation for Ghostfolio Agent API.

This module provides the FastAPI application factory with middleware,
lifespan management, and router assembly.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.dependencies import get_agent
from src.api.routers import (
    agent_router,
    chat_router,
    evals_router,
    feedback_router,
    finances_router,
    market_router,
    portfolio_router,
    sessions_router,
    strategy_router,
    system_router,
    tools_router,
    traces_router,
    verification_router,
)
from src.utils.config import get_settings
from src.utils.logging import get_logger, setup_logging
from src.utils.request_context import (
    REQUEST_GHOSTFOLIO_ACCESS_TOKEN,
    REQUEST_GHOSTFOLIO_API_URL,
)

logger = get_logger(__name__)
settings = get_settings()


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


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application
    """
    app = FastAPI(
        title="Ghostfolio Agent API",
        description="AI-powered portfolio assistant for Ghostfolio",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware - allow Railway frontends via regex
    cors_kw: dict[str, Any] = {
        "allow_origins": settings.cors_origins_list,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.cors_origin_regex and settings.cors_origin_regex.strip():
        cors_kw["allow_origin_regex"] = settings.cors_origin_regex
    app.add_middleware(CORSMiddleware, **cors_kw)

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

    # Include all routers
    app.include_router(system_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)
    app.include_router(feedback_router)
    app.include_router(portfolio_router)
    app.include_router(market_router)
    app.include_router(strategy_router)
    app.include_router(tools_router)
    app.include_router(verification_router)
    app.include_router(traces_router)
    app.include_router(evals_router)
    app.include_router(finances_router)
    app.include_router(agent_router)

    return app


# Create the app instance for uvicorn
app = create_app()


def run_server():
    """Run the server using uvicorn."""
    import uvicorn
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8002,
        reload=settings.environment == "development",
    )


if __name__ == "__main__":
    run_server()
