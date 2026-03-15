"""Agent configuration endpoints for Ghostfolio Agent API.

Agent model configuration and management.
"""

from fastapi import APIRouter, HTTPException

from src.api.dependencies import clear_agent
from src.api.models import ALLOWED_AGENT_MODELS, AgentConfigRequest, AgentConfigResponse
from src.utils.config_store import get_agent_config_store
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/agent/config", response_model=AgentConfigResponse, tags=["Agent"])
async def get_agent_config() -> AgentConfigResponse:
    """Get current agent configuration (e.g. selected model). For developers."""
    store = get_agent_config_store()
    model = store.get("model", "gpt-4o-mini")
    return AgentConfigResponse(model=model, allowed_models=ALLOWED_AGENT_MODELS)


@router.put("/agent/config", response_model=AgentConfigResponse, tags=["Agent"])
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
    clear_agent()  # Force reinitialization with new model on next request
    logger.info(f"Agent config updated: model={model}")
    return AgentConfigResponse(model=model, allowed_models=ALLOWED_AGENT_MODELS)
