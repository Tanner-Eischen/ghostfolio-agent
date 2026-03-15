"""Tools module - LangChain tools for portfolio analysis."""

from src.tools.compliance_check import compliance_check
from src.tools.market_data_lookup import market_data_lookup
from src.tools.portfolio_analysis import portfolio_analysis
from src.tools.price_history import price_history
from src.tools.risk_assessment import risk_assessment
from src.tools.transaction_categorize import transaction_categorize
from src.tools.trending_crypto import trending_crypto

# Core tools - 5 domain + price_history + trending_crypto
CORE_TOOLS = [
    portfolio_analysis,
    market_data_lookup,
    risk_assessment,
    transaction_categorize,
    compliance_check,
    price_history,
    trending_crypto,
]

# Backward compatibility alias
ALL_TOOLS = CORE_TOOLS


def get_all_tools():
    """Get all tools including dynamically generated ones.

    Returns:
        List of all tool instances (core + generated)
    """
    from src.tools.registry import get_all_tools as _get_all_tools
    return _get_all_tools()


def load_generated_tools():
    """Load all generated tools from disk.

    Returns:
        List of generated tool instances
    """
    from src.tools.registry import load_generated_tools as _load_generated_tools
    return _load_generated_tools()


__all__ = [
    "portfolio_analysis",
    "risk_assessment",
    "market_data_lookup",
    "transaction_categorize",
    "compliance_check",
    "price_history",
    "trending_crypto",
    "CORE_TOOLS",
    "ALL_TOOLS",  # Backward compatibility
    "get_all_tools",
    "load_generated_tools",
]
