"""Finances endpoints for Ghostfolio Agent API.

Usage statistics and cost projections.
"""


from fastapi import APIRouter

from src.api.models import (
    ALLOWED_AGENT_MODELS,
    CostComparisonEntry,
    CostComparisonResponse,
    CostProjectionsResponse,
    ModelPricingEntry,
    ModelPricingResponse,
    SeedDemoUsageResponse,
    UsageByModel,
    UsageStatsResponse,
)
from src.utils.config_store import get_agent_config_store
from src.utils.logging import get_logger
from src.utils.usage_tracker import (
    MODEL_PRICING,
    get_cost_projections,
    get_usage_stats,
    seed_demo_usage,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get("/finances/usage", response_model=UsageStatsResponse, tags=["Finances"])
async def get_usage() -> UsageStatsResponse:
    """Get usage statistics.

    Returns token usage and cost statistics for the current period.
    """
    stats = get_usage_stats()

    by_model = [
        UsageByModel(
            model=m.get("model", "unknown"),
            input_tokens=m.get("input_tokens", 0),
            output_tokens=m.get("output_tokens", 0),
            total_tokens=m.get("total_tokens", 0),
            cost_usd=m.get("cost_usd", 0.0),
        )
        for m in stats.get("by_model", [])
    ]

    return UsageStatsResponse(
        total_requests=stats.get("total_requests", 0),
        total_tokens=stats.get("total_tokens", 0),
        total_cost_usd=stats.get("total_cost_usd", 0.0),
        by_model=by_model,
        period_start=stats.get("period_start"),
        period_end=stats.get("period_end"),
    )


@router.get("/finances/projections", response_model=CostProjectionsResponse, tags=["Finances"])
async def get_projections() -> CostProjectionsResponse:
    """Get cost projections.

    Returns projected costs based on current usage patterns.
    """
    projections = get_cost_projections()

    return CostProjectionsResponse(
        daily_cost_usd=projections.get("daily_cost_usd", 0.0),
        monthly_cost_usd=projections.get("monthly_cost_usd", 0.0),
        yearly_cost_usd=projections.get("yearly_cost_usd", 0.0),
        requests_per_day=projections.get("requests_per_day", 0),
    )


@router.get("/finances/model-pricing", response_model=ModelPricingResponse, tags=["Finances"])
async def get_model_pricing() -> ModelPricingResponse:
    """Get model pricing information.

    Returns pricing for all available models.
    """
    models = []
    for model_id, pricing in MODEL_PRICING.items():
        models.append(ModelPricingEntry(
            model=model_id,
            input_cost_per_1k=pricing.get("input", 0.0),
            output_cost_per_1k=pricing.get("output", 0.0),
        ))

    return ModelPricingResponse(models=models)


@router.get("/finances/cost-comparison", response_model=CostComparisonResponse, tags=["Finances"])
async def get_cost_comparison() -> CostComparisonResponse:
    """Compare costs across different models.

    Returns cost comparison for all available models based on current usage.
    """
    store = get_agent_config_store()
    current_model = store.get("model", "gpt-4o-mini")

    # Get current usage stats
    stats = get_usage_stats()
    current_monthly_cost = stats.get("total_cost_usd", 0.0)

    # Calculate comparisons
    comparisons = []
    for model_id in ALLOWED_AGENT_MODELS:
        pricing = MODEL_PRICING.get(model_id, {"input": 0.0, "output": 0.0})

        # Estimate monthly cost based on current usage
        # This is a simplified calculation
        estimated_monthly = current_monthly_cost  # Would need actual token counts

        comparisons.append(CostComparisonEntry(
            model=model_id,
            estimated_monthly_cost_usd=estimated_monthly,
            input_cost_per_1k=pricing.get("input", 0.0),
            output_cost_per_1k=pricing.get("output", 0.0),
            notes="Current model" if model_id == current_model else None,
        ))

    return CostComparisonResponse(
        current_model=current_model,
        current_monthly_cost_usd=current_monthly_cost,
        comparisons=comparisons,
    )


@router.post("/finances/seed-demo-usage", response_model=SeedDemoUsageResponse, tags=["Finances"])
async def seed_demo_usage_endpoint() -> SeedDemoUsageResponse:
    """Seed demo usage data for testing.

    Populates the usage tracker with sample data for demonstration.
    """
    records = seed_demo_usage()
    logger.info(f"Seeded {records} demo usage records")

    return SeedDemoUsageResponse(
        status="success",
        records_created=records,
    )
