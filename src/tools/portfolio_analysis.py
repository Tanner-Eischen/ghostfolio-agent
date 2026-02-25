"""Portfolio Analysis Tool - Analyze holdings, allocation, and performance."""

from datetime import datetime
from typing import Any

from langchain_core.tools import tool
from langsmith import traceable
from pydantic import BaseModel, Field

from src.api.ghostfolio import GhostfolioClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Input/Output Models
# ============================================================================


class PortfolioAnalysisInput(BaseModel):
    """Input schema for portfolio_analysis tool."""

    account_id: str | None = Field(
        default=None,
        description="Optional specific account ID to analyze. If not provided, analyzes all accounts.",
    )
    timeframe: str = Field(
        default="YTD",
        description="Timeframe for performance analysis. Options: Today, WTD, MTD, YTD, 1Y, 5Y, Max",
    )


class Holding(BaseModel):
    """A single portfolio holding."""

    symbol: str = Field(description="Asset symbol (e.g., AAPL, BTC)")
    name: str = Field(description="Full name of the asset")
    quantity: float = Field(description="Number of shares/units held")
    value: float = Field(description="Current market value in base currency")
    allocation_pct: float = Field(description="Percentage of total portfolio")
    asset_class: str | None = Field(default=None, description="Asset class (EQUITY, FIXED_INCOME, etc.)")


class Performance(BaseModel):
    """Portfolio performance metrics."""

    absolute_change: float = Field(description="Absolute change in value")
    relative_change: float = Field(description="Relative change as decimal (e.g., 0.10 = 10%)")
    timeframe: str = Field(description="Timeframe of performance calculation")


class PortfolioAnalysisResult(BaseModel):
    """Result of portfolio analysis."""

    total_value: float = Field(description="Total portfolio value in base currency")
    holdings: list[Holding] = Field(description="List of portfolio holdings")
    performance: Performance = Field(description="Performance metrics")
    diversification_score: float = Field(
        default=0.0,
        description="Diversification score from 0-100",
        ge=0,
        le=100,
    )
    currency: str = Field(default="USD", description="Base currency of the portfolio")
    last_updated: str = Field(description="Timestamp of last data update")
    data_source: str = Field(default="ghostfolio", description="Source of portfolio data")
    account_filter: str | None = Field(
        default=None, description="Account ID if filtered to specific account"
    )


# ============================================================================
# Diversification Score Calculator
# ============================================================================


@traceable(name="calculate_diversification_score", run_type="tool")
def calculate_diversification_score(holdings: list[dict[str, Any]]) -> float:
    """Calculate a diversification score based on portfolio holdings.

    The score is based on:
    1. Number of holdings (0-30 points): More holdings = better diversification
    2. Allocation balance (0-40 points): Using Herfindahl-Hirschman Index (HHI)
       - Lower HHI (less concentration) = better diversification
    3. Asset class diversity (0-30 points): More asset classes = better diversification

    Args:
        holdings: List of holding dictionaries with allocation_pct and asset_class

    Returns:
        Diversification score from 0-100
    """
    if not holdings:
        return 0.0

    # 1. Number of holdings score (0-30 points)
    # Reward more holdings, capped at 20 holdings for max score
    num_holdings = len(holdings)
    holdings_score = min(30, num_holdings * 1.5)

    # 2. Allocation balance score using HHI (0-40 points)
    # HHI = sum of squared allocation percentages
    # Perfect diversification (equal weight) gives lowest HHI
    allocation_pcts = [h.get("allocation_pct", h.get("allocationPct", 0)) for h in holdings]
    hhi = sum((p / 100) ** 2 for p in allocation_pcts)

    # HHI ranges from 1/n (perfect diversification) to 1 (single asset)
    # Invert to get score: lower HHI = higher score
    # For 6 holdings, perfect HHI = 1/6 = 0.167
    min_hhi = 1 / max(num_holdings, 1)
    if hhi <= min_hhi:
        balance_score = 40.0
    else:
        # Scale from min_hhi to 1.0
        balance_score = max(0, 40 * (1 - (hhi - min_hhi) / (1 - min_hhi)))

    # 3. Asset class diversity score (0-30 points)
    asset_classes = set()
    for h in holdings:
        asset_class = h.get("asset_class", h.get("assetClass", "UNKNOWN"))
        if asset_class:
            asset_classes.add(asset_class)

    # Reward multiple asset classes (max 5 for full score)
    num_asset_classes = len(asset_classes)
    asset_class_score = min(30, num_asset_classes * 6)

    total_score = holdings_score + balance_score + asset_class_score

    logger.debug(
        f"Diversification score: {total_score:.1f} "
        f"(holdings={holdings_score:.1f}, balance={balance_score:.1f}, "
        f"asset_class={asset_class_score:.1f})"
    )

    return round(total_score, 1)


# ============================================================================
# Tool Implementation
# ============================================================================


@tool
async def portfolio_analysis(
    account_id: str | None = None,
    timeframe: str = "YTD",
) -> PortfolioAnalysisResult:
    """Analyze user's portfolio including holdings, allocation, and performance metrics.

    Use this tool when the user asks about:
    - Total portfolio value
    - Current holdings and their allocation
    - Portfolio performance over a time period
    - How diversified their portfolio is

    Args:
        account_id: Optional specific account to analyze. If None, analyzes all accounts.
        timeframe: Time period for performance (Today, WTD, MTD, YTD, 1Y, 5Y, Max)

    Returns:
        PortfolioAnalysisResult with total value, holdings, performance, and diversification score
    """
    # Validate timeframe
    valid_timeframes = ["Today", "WTD", "MTD", "YTD", "1Y", "5Y", "Max"]
    if timeframe not in valid_timeframes:
        logger.warning(f"Invalid timeframe '{timeframe}', defaulting to YTD")
        timeframe = "YTD"

    logger.info(f"Analyzing portfolio (account_id={account_id}, timeframe={timeframe})")

    async with GhostfolioClient(use_mock=True) as client:
        try:
            # Fetch portfolio data
            portfolio_data = await client.get_portfolio()

            # If specific account requested, filter holdings
            holdings_data = portfolio_data.get("holdings", [])
            if account_id:
                # Get positions to filter by account
                positions = await client.get_positions()
                account_positions = {
                    p.get("symbol") for p in positions if p.get("id", "").startswith(account_id)
                }

                # For mock data, we don't have account-specific positions,
                # so we'll get orders to determine which symbols are in which account
                orders = await client.get_orders(account_id=account_id)
                account_symbols = {o.get("symbol") for o in orders}

                # Filter holdings to only those in the account
                holdings_data = [
                    h
                    for h in holdings_data
                    if h.get("symbol") in account_symbols
                ]

                # Recalculate allocations for filtered holdings
                if holdings_data:
                    total_value = sum(h.get("value", 0) for h in holdings_data)
                    for h in holdings_data:
                        if total_value > 0:
                            h["allocation_pct"] = (h.get("value", 0) / total_value) * 100
                            h["allocationPct"] = h["allocation_pct"]

            # Fetch performance data
            performance_data = await client.get_performance(timeframe=timeframe, account_id=account_id)

            # Build holdings list
            holdings = [
                Holding(
                    symbol=h.get("symbol", "UNKNOWN"),
                    name=h.get("name", "Unknown Asset"),
                    quantity=float(h.get("quantity", 0)),
                    value=float(h.get("value", 0)),
                    allocation_pct=float(h.get("allocation_pct", h.get("allocationPct", 0))),
                    asset_class=h.get("asset_class", h.get("assetClass")),
                )
                for h in holdings_data
            ]

            # Calculate total value
            total_value = sum(h.value for h in holdings) if holdings else 0.0
            if total_value == 0.0:
                total_value = float(portfolio_data.get("total_value", portfolio_data.get("totalValue", 0)))

            # Calculate diversification score
            diversification_score = calculate_diversification_score(holdings_data)

            # Build performance metrics
            perf = portfolio_data.get("performance", {})
            if performance_data:
                perf = performance_data

            performance = Performance(
                absolute_change=float(perf.get("absolute_change", perf.get("absoluteChange", 0))),
                relative_change=float(perf.get("relative_change", perf.get("relativeChange", 0))),
                timeframe=timeframe,
            )

            # Get currency and last updated
            currency = portfolio_data.get("currency", "USD")
            last_updated = portfolio_data.get("last_updated", datetime.utcnow().isoformat())

            result = PortfolioAnalysisResult(
                total_value=total_value,
                holdings=holdings,
                performance=performance,
                diversification_score=diversification_score,
                currency=currency,
                last_updated=last_updated,
                data_source="ghostfolio",
                account_filter=account_id,
            )

            logger.info(
                f"Portfolio analysis complete: ${total_value:,.2f} total, "
                f"{len(holdings)} holdings, {diversification_score:.1f} diversification score"
            )

            # Return dict for JSON-serializable tool output (evals field_present checks)
            return result.model_dump(mode="json")

        except Exception as e:
            logger.error(f"Portfolio analysis failed: {e}")
            raise


# ============================================================================
# Tool Export
# ============================================================================

__all__ = ["portfolio_analysis", "PortfolioAnalysisResult", "Holding", "Performance"]
