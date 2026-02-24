"""FastAPI routes for Ghostfolio Agent API."""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.utils.config import get_settings
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    setup_logging()
    logger.info(f"Starting Ghostfolio Agent API in {settings.environment} mode")
    yield
    logger.info("Shutting down Ghostfolio Agent API")


app = FastAPI(
    title="Ghostfolio Agent API",
    description="AI-powered portfolio assistant for Ghostfolio",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class ChatRequest(BaseModel):
    """Chat request model."""

    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """Chat response model."""

    response: str
    confidence: float
    tool_calls: list[dict[str, Any]]
    session_id: str


class HealthResponse(BaseModel):
    """Health check response model."""

    status: str
    version: str
    environment: str
    dependencies: dict[str, bool]


class FeedbackRequest(BaseModel):
    """Feedback submission request."""

    message_id: str
    rating: int  # 1-5 or -1 for negative, +1 for positive
    comment: str | None = None


# Routes
@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        environment=settings.environment,
        dependencies={
            "anthropic": bool(settings.anthropic_api_key),
            "langsmith": bool(settings.langchain_api_key),
            "ghostfolio": bool(settings.ghostfolio_access_token),
        },
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with the Ghostfolio Agent.

    Args:
        request: Chat request with message and optional session ID

    Returns:
        Agent response with confidence and tool calls
    """
    # TODO: Implement actual chat logic (Task #15)
    raise HTTPException(
        status_code=501,
        detail="Chat endpoint not implemented. Complete Task #15.",
    )


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest) -> dict[str, str]:
    """Submit feedback for a response.

    Args:
        request: Feedback with message ID and rating

    Returns:
        Confirmation message
    """
    # TODO: Implement feedback submission to LangSmith (Task #15)
    return {"status": "received", "message_id": request.message_id}


@app.get("/portfolio")
async def get_portfolio_summary() -> dict[str, Any]:
    """Get quick portfolio summary.

    Returns:
        Portfolio summary with total value and top holdings
    """
    # TODO: Implement portfolio summary endpoint (Task #15)
    raise HTTPException(
        status_code=501,
        detail="Portfolio endpoint not implemented. Complete Task #15.",
    )


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
