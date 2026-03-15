"""Pytest configuration and fixtures."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure project root is on sys.path for 'src.*' imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force mock mode for all tests BEFORE importing any src modules
# This ensures GhostfolioClient uses mock data instead of trying to connect
os.environ["USE_MOCK_DATA"] = "true"
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "test_key_for_pytest")
os.environ["LANGCHAIN_API_KEY"] = os.environ.get("LANGCHAIN_API_KEY", "test_key_for_pytest")


# ============================================================================
# Mock Fixtures for GhostfolioClient
# ============================================================================

# Mock portfolio data matching real Ghostfolio structure
MOCK_PORTFOLIO = {
    "totalValue": 150000.00,
    "currency": "USD",
    "holdings": [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "quantity": 100,
            "value": 18500.00,
            "allocationPct": 12.33,
            "currency": "USD",
            "assetClass": "EQUITY",
            "assetSubClass": "STOCK",
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft Corporation",
            "quantity": 50,
            "value": 21000.00,
            "allocationPct": 14.0,
            "currency": "USD",
            "assetClass": "EQUITY",
            "assetSubClass": "STOCK",
        },
        {
            "symbol": "VTI",
            "name": "Vanguard Total Stock Market ETF",
            "quantity": 200,
            "value": 48000.00,
            "allocationPct": 32.0,
            "currency": "USD",
            "assetClass": "EQUITY",
            "assetSubClass": "ETF",
        },
        {
            "symbol": "BTC",
            "name": "Bitcoin",
            "quantity": 0.5,
            "value": 42500.00,
            "allocationPct": 28.33,
            "currency": "USD",
            "assetClass": "CRYPTOCURRENCY",
            "assetSubClass": "CRYPTOCURRENCY",
        },
        {
            "symbol": "BND",
            "name": "Vanguard Total Bond Market ETF",
            "quantity": 150,
            "value": 10500.00,
            "allocationPct": 7.0,
            "currency": "USD",
            "assetClass": "FIXED_INCOME",
            "assetSubClass": "BOND",
        },
        {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "quantity": 25,
            "value": 9500.00,
            "allocationPct": 6.34,
            "currency": "USD",
            "assetClass": "EQUITY",
            "assetSubClass": "STOCK",
        },
    ],
    "performance": {
        "absoluteChange": 12500.00,
        "relativeChange": 0.0909,
        "timeframe": "YTD",
        "currency": "USD",
    },
}

# Mock orders/transactions for compliance checks
MOCK_ORDERS = [
    {
        "id": "ord001",
        "type": "BUY",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "quantity": 20,
        "unitPrice": 170.00,
        "currency": "USD",
        "date": "2024-01-15",
        "accountId": "acc1",
        "fee": 0.0,
    },
    {
        "id": "ord002",
        "type": "BUY",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "quantity": 30,
        "unitPrice": 175.00,
        "currency": "USD",
        "date": "2024-02-10",
        "accountId": "acc1",
        "fee": 0.0,
    },
    {
        "id": "ord003",
        "type": "DIVIDEND",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "quantity": 50,
        "unitPrice": 0.24,
        "currency": "USD",
        "date": "2024-02-15",
        "accountId": "acc1",
        "fee": 0.0,
    },
    {
        "id": "ord004",
        "type": "SELL",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "quantity": 10,
        "unitPrice": 160.00,  # Loss sale
        "currency": "USD",
        "date": "2024-02-20",
        "accountId": "acc1",
        "fee": 0.0,
    },
    {
        "id": "ord005",
        "type": "BUY",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "quantity": 15,
        "unitPrice": 162.00,  # Within 30 days of loss sale - wash sale!
        "currency": "USD",
        "date": "2024-03-01",
        "accountId": "acc1",
        "fee": 0.0,
    },
    {
        "id": "ord006",
        "type": "BUY",
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "quantity": 25,
        "unitPrice": 390.00,
        "currency": "USD",
        "date": "2024-01-20",
        "accountId": "acc1",
        "fee": 0.0,
    },
    {
        "id": "ord007",
        "type": "SELL",
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "quantity": 25,
        "unitPrice": 400.00,
        "currency": "USD",
        "date": "2024-01-20",  # Same day as buy - day trade!
        "accountId": "acc1",
        "fee": 0.0,
    },
    {
        "id": "ord008",
        "type": "BUY",
        "symbol": "VTI",
        "name": "Vanguard Total Stock Market ETF",
        "quantity": 100,
        "unitPrice": 225.00,
        "currency": "USD",
        "date": "2024-01-05",
        "accountId": "acc2",
        "fee": 0.0,
    },
    {
        "id": "ord009",
        "type": "BUY",
        "symbol": "BTC",
        "name": "Bitcoin",
        "quantity": 0.25,
        "unitPrice": 68000.00,
        "currency": "USD",
        "date": "2024-01-25",
        "accountId": "acc3",
        "fee": 5.00,
    },
    {
        "id": "ord010",
        "type": "SELL",
        "symbol": "GOOGL",
        "name": "Alphabet Inc.",
        "quantity": 15,
        "unitPrice": 145.00,
        "currency": "USD",
        "date": "2024-03-01",
        "accountId": "acc1",
        "fee": 0.0,
    },
]

MOCK_ACCOUNTS = [
    {
        "id": "acc1",
        "name": "Robinhood",
        "currency": "USD",
        "platformId": "robinhood",
        "balance": 2500.00,
        "value": 71500.00,
        "transactionCount": 25,
    },
    {
        "id": "acc2",
        "name": "Fidelity",
        "currency": "USD",
        "platformId": "fidelity",
        "balance": 5000.00,
        "value": 48000.00,
        "transactionCount": 15,
    },
    {
        "id": "acc3",
        "name": "Coinbase",
        "currency": "USD",
        "platformId": "coinbase",
        "balance": 500.00,
        "value": 42500.00,
        "transactionCount": 5,
    },
]

MOCK_POSITIONS = [
    {
        "id": "pos1",
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "quantity": 100,
        "value": 18500.00,
        "currency": "USD",
        "assetClass": "EQUITY",
        "assetSubClass": "STOCK",
        "averagePurchasePrice": 165.00,
        "marketPrice": 185.00,
        "transactionCount": 5,
    },
    {
        "id": "pos2",
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "quantity": 50,
        "value": 21000.00,
        "currency": "USD",
        "assetClass": "EQUITY",
        "assetSubClass": "STOCK",
        "averagePurchasePrice": 380.00,
        "marketPrice": 420.00,
        "transactionCount": 3,
    },
    {
        "id": "pos3",
        "symbol": "VTI",
        "name": "Vanguard Total Stock Market ETF",
        "quantity": 200,
        "value": 48000.00,
        "currency": "USD",
        "assetClass": "EQUITY",
        "assetSubClass": "ETF",
        "averagePurchasePrice": 220.00,
        "marketPrice": 240.00,
        "transactionCount": 8,
    },
    {
        "id": "pos4",
        "symbol": "BTC",
        "name": "Bitcoin",
        "quantity": 0.5,
        "value": 42500.00,
        "currency": "USD",
        "assetClass": "CRYPTOCURRENCY",
        "assetSubClass": "CRYPTOCURRENCY",
        "averagePurchasePrice": 65000.00,
        "marketPrice": 85000.00,
        "transactionCount": 2,
    },
    {
        "id": "pos5",
        "symbol": "BND",
        "name": "Vanguard Total Bond Market ETF",
        "quantity": 150,
        "value": 10500.00,
        "currency": "USD",
        "assetClass": "FIXED_INCOME",
        "assetSubClass": "BOND",
        "averagePurchasePrice": 72.00,
        "marketPrice": 70.00,
        "transactionCount": 3,
    },
    {
        "id": "pos6",
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "quantity": 25,
        "value": 9500.00,
        "currency": "USD",
        "assetClass": "EQUITY",
        "assetSubClass": "STOCK",
        "averagePurchasePrice": 300.00,
        "marketPrice": 380.00,
        "transactionCount": 2,
    },
]

MOCK_PERFORMANCE = {
    "absoluteChange": 12500.00,
    "relativeChange": 0.0909,
    "timeframe": "YTD",
    "currency": "USD",
    "annualizedReturn": 0.12,
    "maxDrawdown": -0.08,
    "volatility": 0.15,
}


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
    return MOCK_PORTFOLIO


@pytest.fixture
def mock_orders():
    """Provide mock order/transaction data for testing."""
    return MOCK_ORDERS


@pytest.fixture
def mock_accounts():
    """Provide mock account data for testing."""
    return MOCK_ACCOUNTS


@pytest.fixture
def mock_positions():
    """Provide mock position data for testing."""
    return MOCK_POSITIONS


# ============================================================================
# Pytest Configuration
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires external services)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
