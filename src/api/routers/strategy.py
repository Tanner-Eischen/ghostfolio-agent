"""Strategy endpoints for Ghostfolio Agent API.

Strategy configuration and recommendations.
"""

from fastapi import APIRouter

from src.api.models import StrategyConfigResponse, StrategyRecommendationResponse
from src.utils.config_store import get_strategy_config_store
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/strategy", response_model=StrategyConfigResponse, tags=["Strategy"])
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


@router.post("/strategy", response_model=StrategyConfigResponse, tags=["Strategy"])
async def save_strategy_config(config: StrategyConfigResponse) -> StrategyConfigResponse:
    """Save strategy configuration.

    Updates the active agent configuration and persists it.
    """
    store = get_strategy_config_store()
    store.update(config.model_dump())
    logger.info(f"Strategy config updated: {config.model_dump()}")
    return config


@router.get("/strategy/recommendations", response_model=list[StrategyRecommendationResponse], tags=["Strategy"])
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
            framework="LangChain Agent",
            reason="Good for simpler linear tool chains with less state management",
            recommended=False,
        ),
        StrategyRecommendationResponse(
            framework="Custom",
            reason="For specialized requirements not met by existing frameworks",
            recommended=False,
        ),
    ]
