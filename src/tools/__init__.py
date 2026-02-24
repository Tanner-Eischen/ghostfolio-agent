"""Tools module - LangChain tools for portfolio analysis."""

from src.tools.portfolio_analysis import portfolio_analysis
from src.tools.transaction_categorize import transaction_categorize
from src.tools.risk_assessment import risk_assessment
from src.tools.market_data_lookup import market_data_lookup
from src.tools.compliance_check import compliance_check

# Tool registry for easy access
ALL_TOOLS = [
    portfolio_analysis,
    transaction_categorize,
    risk_assessment,
    market_data_lookup,
    compliance_check,
]

__all__ = [
    "portfolio_analysis",
    "transaction_categorize",
    "risk_assessment",
    "market_data_lookup",
    "compliance_check",
    "ALL_TOOLS",
]
