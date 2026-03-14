"""Portfolio endpoints for Ghostfolio Agent API.

Portfolio summary and risk assessment.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from src.api.dependencies import get_agent
from src.api.models import PortfolioSummaryResponse
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/portfolio", response_model=PortfolioSummaryResponse, tags=["Portfolio"])
async def get_portfolio_summary() -> PortfolioSummaryResponse:
    """Get quick portfolio summary.

    Returns a summary of the user's portfolio including total value,
    performance, top holdings, and risk assessment.

    Returns:
        Portfolio summary with key metrics
    """
    try:
        get_agent()  # Ensure agent is initialized

        # Use portfolio_analysis tool internally
        from src.tools import portfolio_analysis

        result = await portfolio_analysis.ainvoke({
            "timeframe": "YTD",
        })

        # Parse the result
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


@router.get("/portfolio/risk", tags=["Portfolio"])
async def get_risk_assessment() -> dict[str, Any]:
    """Get portfolio risk assessment.

    Returns detailed risk metrics including concentration and diversification.
    """
    try:
        get_agent()  # Ensure agent is initialized

        from src.tools import risk_assessment

        result = await risk_assessment.ainvoke({})

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
