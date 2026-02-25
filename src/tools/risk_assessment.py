"""Risk Assessment Tool - Evaluate portfolio risk metrics."""

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


class RiskAssessmentInput(BaseModel):
    """Input schema for risk_assessment tool."""

    portfolio_data: dict | None = Field(
        default=None,
        description="Optional portfolio data to analyze. If not provided, uses current portfolio.",
    )


class SectorExposure(BaseModel):
    """Exposure to a single sector."""

    sector: str = Field(description="Sector name")
    percentage: float = Field(description="Percentage allocation")


class AssetClassExposure(BaseModel):
    """Exposure to a single asset class."""

    asset_class: str = Field(description="Asset class name")
    percentage: float = Field(description="Percentage allocation")


class GeographicExposure(BaseModel):
    """Exposure to a geographic region."""

    region: str = Field(description="Region name")
    percentage: float = Field(description="Percentage allocation")


class ConcentrationRisk(BaseModel):
    """Concentration risk metrics."""

    top_holdings_pct: float = Field(description="Sum of top 3 holdings percentages")
    single_asset_max: float = Field(description="Largest single holding percentage")
    top_holdings: list[dict[str, Any]] = Field(
        default=[],
        description="Top 3 holdings with symbol and percentage",
    )
    top_sectors: list[SectorExposure] = Field(
        default=[],
        description="Top sectors and their percentages",
    )


class DiversificationMetrics(BaseModel):
    """Diversification metrics."""

    sectors: list[SectorExposure] = Field(
        default=[],
        description="Sector exposures with percentages",
    )
    asset_types: list[AssetClassExposure] = Field(
        default=[],
        description="Asset class exposures with percentages",
    )
    geographic: list[GeographicExposure] = Field(
        default=[],
        description="Geographic region exposures if available",
    )
    num_sectors: int = Field(default=0, description="Number of sectors represented")
    num_asset_types: int = Field(default=0, description="Number of asset types")
    num_holdings: int = Field(default=0, description="Total number of holdings")


class VolatilityMetrics(BaseModel):
    """Volatility metrics (if available)."""

    portfolio_volatility: float | None = Field(
        default=None, description="Portfolio volatility (annualized)"
    )
    max_drawdown: float | None = Field(
        default=None, description="Maximum drawdown percentage"
    )
    beta: float | None = Field(
        default=None, description="Portfolio beta vs benchmark"
    )


class RiskAssessmentResult(BaseModel):
    """Result of risk assessment."""

    overall_risk_score: float = Field(
        description="Overall risk score from 0-100 (0=lowest risk, 100=highest risk)",
        ge=0,
        le=100,
    )
    risk_level: str = Field(
        description="Risk level label: LOW, MEDIUM, HIGH, VERY_HIGH",
    )
    concentration_risk: ConcentrationRisk = Field(
        description="Concentration risk details",
    )
    diversification: DiversificationMetrics = Field(
        description="Diversification metrics",
    )
    volatility_metrics: VolatilityMetrics | None = Field(
        default=None,
        description="Volatility metrics if available",
    )
    recommendations: list[str] = Field(
        description="Recommendations for risk reduction",
    )
    warnings: list[str] = Field(
        default=[],
        description="Any risk warnings or concerns",
    )
    last_updated: str = Field(
        description="Timestamp of the assessment",
    )
    data_source: str = Field(
        default="ghostfolio",
        description="Source of portfolio data",
    )


# ============================================================================
# Risk Calculation Functions
# ============================================================================


@traceable(name="calculate_concentration_score", run_type="tool")
def calculate_concentration_score(holdings: list[dict[str, Any]]) -> tuple[float, float, str | None]:
    """Calculate concentration risk score.

    Args:
        holdings: List of holding dictionaries with allocation_pct

    Returns:
        Tuple of (score 0-40, single_asset_max percentage, symbol of max holding)
    """
    if not holdings:
        return 0.0, 0.0, None

    # Get allocation percentages
    allocations = []
    for h in holdings:
        pct = h.get("allocation_pct", h.get("allocationPct", 0))
        symbol = h.get("symbol", "UNKNOWN")
        allocations.append((pct, symbol))

    # Sort by allocation descending
    allocations.sort(key=lambda x: x[0], reverse=True)

    # Get single asset max
    single_asset_max = allocations[0][0] if allocations else 0
    max_symbol = allocations[0][1] if allocations else None

    # Calculate score based on single asset concentration
    score = 0.0

    if single_asset_max > 50:
        score += 40
    elif single_asset_max > 30:
        score += 25
    elif single_asset_max > 20:
        score += 15

    # Add additional points if top 3 holdings > 70%
    top_3_sum = sum(a[0] for a in allocations[:3])
    if top_3_sum > 70:
        score += 20

    return min(40, score), single_asset_max, max_symbol


@traceable(name="calculate_diversification_asset_score", run_type="tool")
def calculate_diversification_asset_score(holdings: list[dict[str, Any]]) -> int:
    """Calculate diversification score based on asset classes.

    Args:
        holdings: List of holding dictionaries with asset_class

    Returns:
        Score from 5-30 (lower = more diversified, higher = less diversified)
    """
    asset_classes = set()
    for h in holdings:
        asset_class = h.get("asset_class", h.get("assetClass", "UNKNOWN"))
        if asset_class:
            asset_classes.add(asset_class)

    num_classes = len(asset_classes)

    if num_classes < 3:
        return 30
    elif num_classes <= 5:
        return 15
    else:
        return 5


@traceable(name="calculate_sector_concentration_score", run_type="tool")
def calculate_sector_concentration_score(
    holdings: list[dict[str, Any]],
) -> tuple[int, dict[str, float]]:
    """Calculate sector concentration score.

    Args:
        holdings: List of holding dictionaries

    Returns:
        Tuple of (score 10-30, sector allocations dict)
    """
    # Group by sector (using asset_sub_class as proxy for sector in mock data)
    sector_allocations: dict[str, float] = {}

    for h in holdings:
        # Use asset_class as sector for simplicity
        sector = h.get("asset_sub_class", h.get("assetSubClass"))
        if not sector:
            sector = h.get("asset_class", h.get("assetClass", "UNKNOWN"))

        pct = h.get("allocation_pct", h.get("allocationPct", 0))
        sector_allocations[sector] = sector_allocations.get(sector, 0) + pct

    if not sector_allocations:
        return 10, {}

    # Find top sector
    top_sector_pct = max(sector_allocations.values())

    # Calculate score
    if top_sector_pct > 60:
        return 30, sector_allocations
    elif top_sector_pct > 40:
        return 20, sector_allocations
    else:
        return 10, sector_allocations


@traceable(name="generate_risk_recommendations", run_type="tool")
def generate_recommendations(
    single_asset_max: float,
    max_symbol: str | None,
    num_asset_classes: int,
    top_3_sum: float,
    overall_score: float,
) -> list[str]:
    """Generate risk reduction recommendations.

    Args:
        single_asset_max: Maximum single asset allocation percentage
        max_symbol: Symbol of the largest holding
        num_asset_classes: Number of asset classes
        top_3_sum: Sum of top 3 holdings percentages
        overall_score: Overall risk score

    Returns:
        List of recommendation strings
    """
    recommendations = []

    # Single asset concentration
    if single_asset_max > 30 and max_symbol:
        recommendations.append(
            f"Consider reducing position in {max_symbol} to below 30% of your portfolio"
        )

    # Asset class diversification
    if num_asset_classes <= 2:
        recommendations.append(
            "Diversify across more asset classes (bonds, international equities, real estate, etc.)"
        )

    # Top holdings concentration
    if top_3_sum > 70:
        recommendations.append(
            "Your top 3 holdings represent over 70% of your portfolio. "
            "Consider broad market ETFs to reduce concentration risk"
        )

    # High overall risk
    if overall_score > 70:
        recommendations.append(
            "Your portfolio has high overall risk. Consider adding fixed income "
            "or other lower-volatility assets"
        )

    # Always provide at least one recommendation
    if not recommendations:
        if overall_score > 50:
            recommendations.append(
                "Consider further diversification to reduce portfolio risk"
            )
        else:
            recommendations.append(
                "Your portfolio is well-diversified. Continue monitoring and rebalancing periodically"
            )

    return recommendations


def get_risk_level(score: float) -> str:
    """Convert risk score to risk level label.

    Args:
        score: Risk score 0-100

    Returns:
        Risk level string
    """
    if score < 25:
        return "LOW"
    elif score < 50:
        return "MEDIUM"
    elif score < 75:
        return "HIGH"
    else:
        return "VERY_HIGH"


# ============================================================================
# Tool Implementation
# ============================================================================


@tool
async def risk_assessment(
    portfolio_data: dict | None = None,
) -> RiskAssessmentResult:
    """Assess portfolio risk including diversification, concentration, and volatility.

    Use this tool when the user asks about:
    - How risky their portfolio is
    - Whether they're diversified enough
    - Concentration in specific holdings
    - Risk reduction recommendations

    Args:
        portfolio_data: Optional portfolio data to analyze. Uses current portfolio if not provided.

    Returns:
        RiskAssessmentResult with risk score, concentration, diversification, and recommendations
    """
    logger.info("Starting risk assessment")

    async with GhostfolioClient(use_mock=True) as client:
        try:
            # Get portfolio data either from input or from API
            if portfolio_data:
                data = portfolio_data
                holdings_data = data.get("holdings", [])
            else:
                data = await client.get_portfolio()
                holdings_data = data.get("holdings", [])

            # Also get performance data for volatility metrics
            performance_data = await client.get_performance(timeframe="1Y")

            if not holdings_data:
                logger.warning("No holdings data available for risk assessment")
                return RiskAssessmentResult(
                    overall_risk_score=0.0,
                    risk_level="LOW",
                    concentration_risk=ConcentrationRisk(
                        top_holdings_pct=0.0,
                        single_asset_max=0.0,
                    ),
                    diversification=DiversificationMetrics(),
                    recommendations=["Add holdings to your portfolio to begin tracking risk"],
                    last_updated=datetime.utcnow().isoformat(),
                )

            # Calculate concentration risk score
            concentration_score, single_asset_max, max_symbol = calculate_concentration_score(
                holdings_data
            )

            # Calculate diversification (asset class) score
            asset_div_score = calculate_diversification_asset_score(holdings_data)

            # Calculate sector concentration score
            sector_score, sector_allocations = calculate_sector_concentration_score(holdings_data)

            # Total risk score (0-100)
            overall_score = concentration_score + asset_div_score + sector_score
            overall_score = min(100, max(0, overall_score))

            # Get top 3 holdings info
            sorted_holdings = sorted(
                holdings_data,
                key=lambda h: h.get("allocation_pct", h.get("allocationPct", 0)),
                reverse=True,
            )
            top_3_holdings = [
                {
                    "symbol": h.get("symbol", "UNKNOWN"),
                    "percentage": h.get("allocation_pct", h.get("allocationPct", 0)),
                }
                for h in sorted_holdings[:3]
            ]
            top_3_sum = sum(h["percentage"] for h in top_3_holdings)

            # Build sector exposures
            sector_exposures = [
                SectorExposure(sector=sector, percentage=round(pct, 2))
                for sector, pct in sorted(
                    sector_allocations.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ]

            # Build asset class exposures
            asset_class_allocations: dict[str, float] = {}
            for h in holdings_data:
                asset_class = h.get("asset_class", h.get("assetClass", "UNKNOWN"))
                pct = h.get("allocation_pct", h.get("allocationPct", 0))
                asset_class_allocations[asset_class] = asset_class_allocations.get(asset_class, 0) + pct

            asset_class_exposures = [
                AssetClassExposure(asset_class=ac, percentage=round(pct, 2))
                for ac, pct in sorted(
                    asset_class_allocations.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
            ]

            # Build concentration risk result
            concentration_risk = ConcentrationRisk(
                top_holdings_pct=round(top_3_sum, 2),
                single_asset_max=round(single_asset_max, 2),
                top_holdings=top_3_holdings,
                top_sectors=sector_exposures[:5],
            )

            # Build diversification metrics
            diversification = DiversificationMetrics(
                sectors=sector_exposures,
                asset_types=asset_class_exposures,
                geographic=[],  # Geographic data not available in mock
                num_sectors=len(sector_exposures),
                num_asset_types=len(asset_class_exposures),
                num_holdings=len(holdings_data),
            )

            # Build volatility metrics if available
            volatility_metrics = None
            if performance_data:
                volatility_metrics = VolatilityMetrics(
                    portfolio_volatility=performance_data.get("volatility"),
                    max_drawdown=performance_data.get("maxDrawdown"),
                    beta=None,  # Beta not typically available in basic portfolio data
                )

            # Generate recommendations
            recommendations = generate_recommendations(
                single_asset_max=single_asset_max,
                max_symbol=max_symbol,
                num_asset_classes=len(asset_class_allocations),
                top_3_sum=top_3_sum,
                overall_score=overall_score,
            )

            # Generate warnings
            warnings = []
            if single_asset_max > 50:
                warnings.append(
                    f"High concentration: {max_symbol} represents over 50% of your portfolio"
                )
            if len(asset_class_allocations) == 1:
                warnings.append(
                    "All holdings are in a single asset class"
                )

            # Get risk level
            risk_level = get_risk_level(overall_score)

            result = RiskAssessmentResult(
                overall_risk_score=round(overall_score, 1),
                risk_level=risk_level,
                concentration_risk=concentration_risk,
                diversification=diversification,
                volatility_metrics=volatility_metrics,
                recommendations=recommendations,
                warnings=warnings,
                last_updated=datetime.utcnow().isoformat(),
                data_source="ghostfolio",
            )

            logger.info(
                f"Risk assessment complete: score={overall_score:.1f}, level={risk_level}"
            )

            return result

        except Exception as e:
            logger.error(f"Risk assessment failed: {e}")
            raise


# ============================================================================
# Tool Export
# ============================================================================

__all__ = [
    "risk_assessment",
    "RiskAssessmentResult",
    "ConcentrationRisk",
    "DiversificationMetrics",
    "VolatilityMetrics",
]
