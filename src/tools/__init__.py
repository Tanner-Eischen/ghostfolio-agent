"""Tools module - LangChain tools for portfolio analysis."""

from src.tools.portfolio_analysis import portfolio_analysis
from src.tools.risk_assessment import risk_assessment
from src.tools.market_data_lookup import market_data_lookup

# Core tools - MVP: exactly 3 tools (portfolio_analysis, market_data_lookup, risk_assessment)
CORE_TOOLS = [
    portfolio_analysis,
    market_data_lookup,
    risk_assessment,
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
    "CORE_TOOLS",
    "ALL_TOOLS",  # Backward compatibility
    "get_all_tools",
    "load_generated_tools",
]
