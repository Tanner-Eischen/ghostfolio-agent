"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def mock_settings():
    """Provide mock settings for testing."""
    from src.utils.config import Settings

    return Settings(
        environment="development",
        log_level="DEBUG",
        openai_api_key="test_key",
        langchain_api_key="test_key",
        ghostfolio_access_token="test_token",
        use_mock_data=True,
    )


@pytest.fixture
def mock_portfolio_data():
    """Provide mock portfolio data for testing."""
    return {
        "total_value": 100000.00,
        "currency": "USD",
        "holdings": [
            {
                "symbol": "AAPL",
                "name": "Apple Inc.",
                "quantity": 50,
                "value": 10000.00,
                "allocation_pct": 10.0,
            },
            {
                "symbol": "MSFT",
                "name": "Microsoft Corporation",
                "quantity": 25,
                "value": 10000.00,
                "allocation_pct": 10.0,
            },
            {
                "symbol": "VTI",
                "name": "Vanguard Total Stock Market ETF",
                "quantity": 100,
                "value": 25000.00,
                "allocation_pct": 25.0,
            },
        ],
        "performance": {
            "absolute_change": 5000.00,
            "relative_change": 0.05,
            "timeframe": "YTD",
        },
    }


@pytest.fixture
def mock_transactions():
    """Provide mock transaction data for testing."""
    return [
        {
            "id": "tx001",
            "type": "BUY",
            "symbol": "AAPL",
            "quantity": 10,
            "price": 180.00,
            "date": "2024-01-15",
        },
        {
            "id": "tx002",
            "type": "DIVIDEND",
            "symbol": "AAPL",
            "quantity": 50,
            "price": 0.24,
            "date": "2024-02-15",
        },
        {
            "id": "tx003",
            "type": "SELL",
            "symbol": "GOOGL",
            "quantity": 5,
            "price": 150.00,
            "date": "2024-03-01",
        },
    ]
