"""Verification endpoints for Ghostfolio Agent API.

Verification configuration and management.
"""

from fastapi import APIRouter

from src.api.models import VerificationConfigResponse
from src.utils.config_store import get_verification_config_store
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/verification/config", response_model=VerificationConfigResponse, tags=["Verification"])
async def get_verification_config() -> VerificationConfigResponse:
    """Get current verification configuration.

    Returns settings for fact-checking, hallucination detection, and confidence scoring.
    """
    store = get_verification_config_store()
    return VerificationConfigResponse(
        fact_checking=store.get("fact_checking", True),
        hallucination_detection=store.get("hallucination_detection", True),
        confidence_scoring=store.get("confidence_scoring", True),
        hitl_enabled=store.get("hitl_enabled", False),
        confidence_threshold=store.get("confidence_threshold", 70),
        strict_mode=store.get("strict_mode", False),
    )


@router.put("/verification/config", response_model=VerificationConfigResponse, tags=["Verification"])
async def update_verification_config(config: VerificationConfigResponse) -> VerificationConfigResponse:
    """Update verification configuration.

    Updates settings for fact-checking, hallucination detection, and confidence scoring.
    """
    store = get_verification_config_store()
    store.update(config.model_dump())
    logger.info(f"Verification config updated: {config.model_dump()}")
    return config
