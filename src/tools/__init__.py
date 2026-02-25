"""Tools module - LangChain tools for portfolio analysis."""

from src.tools.portfolio_analysis import portfolio_analysis
from src.tools.risk_assessment import risk_assessment
from src.tools.market_data_lookup import market_data_lookup

# Tool registry - MVP: exactly 3 tools (portfolio_analysis, market_data_lookup, risk_assessment)
ALL_TOOLS = [
    portfolio_analysis,
    market_data_lookup,
    risk_assessment,
]

__all__ = [
    "portfolio_analysis",
    "risk_assessment",
    "market_data_lookup",
    "ALL_TOOLS",
]
