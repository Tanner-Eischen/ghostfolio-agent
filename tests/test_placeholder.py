"""Placeholder test to verify pytest setup."""


def test_placeholder() -> None:
    """Placeholder test that always passes."""
    assert True


def test_imports() -> None:
    """Test that all modules can be imported."""
    # Test utils imports
    from src.utils import get_logger, get_settings, CacheManager
    from src.utils.config import Settings
    from src.utils.logging import setup_logging
    from src.utils.caching import cached

    # Test agent imports
    from src.agent import GhostfolioAgent, AgentState
    from src.agent.state import create_initial_state
    from src.agent.prompts import SYSTEM_PROMPT

    # Test tools imports (the @tool decorator registers them)
    from src.tools import ALL_TOOLS

    # Test verification imports
    from src.verification import FactChecker, ConfidenceScorer, ConstraintValidator

    # Test API imports
    from src.api import GhostfolioClient, YahooFinanceClient, CoinGeckoClient

    assert True
