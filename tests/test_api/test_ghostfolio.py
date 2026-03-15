"""Tests for Ghostfolio API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.api.ghostfolio import (
    MOCK_ACCOUNTS,
    MOCK_ORDERS,
    MOCK_PORTFOLIO,
    MOCK_POSITIONS,
    Account,
    AuthenticationError,
    GhostfolioAPIError,
    GhostfolioClient,
    Holding,
    NotFoundError,
    Order,
    PerformanceMetrics,
    Portfolio,
    Position,
    RateLimitError,
)


class TestGhostfolioClientMock:
    """Tests using mock data mode."""

    @pytest.fixture
    def mock_client(self):
        """Create a client in mock mode."""
        return GhostfolioClient(use_mock=True)

    @pytest.mark.asyncio
    async def test_authenticate_returns_mock_token(self, mock_client):
        """Authentication should return mock token in mock mode."""
        token = await mock_client.authenticate()
        assert token == "mock_token"

    @pytest.mark.asyncio
    async def test_get_portfolio_returns_mock_data(self, mock_client):
        """get_portfolio should return mock portfolio in mock mode."""
        portfolio = await mock_client.get_portfolio()

        assert portfolio["totalValue"] == MOCK_PORTFOLIO["totalValue"]
        assert len(portfolio["holdings"]) == len(MOCK_PORTFOLIO["holdings"])
        assert "last_updated" in portfolio

    @pytest.mark.asyncio
    async def test_get_positions_returns_mock_data(self, mock_client):
        """get_positions should return mock positions in mock mode."""
        positions = await mock_client.get_positions()

        assert len(positions) == len(MOCK_POSITIONS)
        assert positions[0]["symbol"] == MOCK_POSITIONS[0]["symbol"]

    @pytest.mark.asyncio
    async def test_get_orders_returns_mock_data(self, mock_client):
        """get_orders should return mock orders in mock mode."""
        orders = await mock_client.get_orders()

        assert len(orders) == len(MOCK_ORDERS)
        assert orders[0]["symbol"] == MOCK_ORDERS[0]["symbol"]

    @pytest.mark.asyncio
    async def test_get_orders_filters_by_account(self, mock_client):
        """get_orders should filter by account_id."""
        orders = await mock_client.get_orders(account_id="acc1")

        assert all(o["accountId"] == "acc1" for o in orders)

    @pytest.mark.asyncio
    async def test_get_orders_filters_by_symbol(self, mock_client):
        """get_orders should filter by symbol."""
        orders = await mock_client.get_orders(symbol="AAPL")

        assert all(o["symbol"] == "AAPL" for o in orders)

    @pytest.mark.asyncio
    async def test_get_orders_filters_by_date_range(self, mock_client):
        """get_orders should filter by date range."""
        orders = await mock_client.get_orders(
            start_date="2024-02-01",
            end_date="2024-02-28"
        )

        for order in orders:
            assert "2024-02-01" <= order["date"] <= "2024-02-28"

    @pytest.mark.asyncio
    async def test_get_accounts_returns_mock_data(self, mock_client):
        """get_accounts should return mock accounts in mock mode."""
        accounts = await mock_client.get_accounts()

        assert len(accounts) == len(MOCK_ACCOUNTS)
        assert accounts[0]["id"] == MOCK_ACCOUNTS[0]["id"]

    @pytest.mark.asyncio
    async def test_get_performance_returns_mock_data(self, mock_client):
        """get_performance should return mock performance in mock mode."""
        performance = await mock_client.get_performance(timeframe="YTD")

        assert performance["timeframe"] == "YTD"
        assert "absoluteChange" in performance
        assert "relativeChange" in performance

    @pytest.mark.asyncio
    async def test_get_performance_validates_timeframe(self, mock_client):
        """get_performance should validate and correct invalid timeframe."""
        performance = await mock_client.get_performance(timeframe="INVALID")

        # Should default to YTD for invalid timeframe
        assert performance["timeframe"] == "YTD"

    @pytest.mark.asyncio
    async def test_get_stats_returns_client_info(self, mock_client):
        """get_stats should return client statistics."""
        # First authenticate to set the token
        await mock_client.authenticate()

        stats = mock_client.get_stats()

        assert stats["use_mock"] is True
        assert stats["authenticated"] is True  # Mock mode has token after authenticate()
        assert "request_count" in stats
        assert "cache" in stats

    @pytest.mark.asyncio
    async def test_clear_cache_clears_data(self, mock_client):
        """clear_cache should clear all cached data."""
        # Get some data to populate cache
        await mock_client.get_portfolio()

        # Clear cache
        mock_client.clear_cache()

        # Cache should be cleared (check via stats)
        stats = mock_client.get_stats()
        assert stats["cache"]["size"] == 0

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_client):
        """Client should work as async context manager."""
        async with GhostfolioClient(use_mock=True) as client:
            portfolio = await client.get_portfolio()
            assert portfolio is not None
        # Client should be closed after context exit


class TestGhostfolioClientLive:
    """Tests for live API mode (using mocked HTTP)."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for live mode tests."""
        with patch("src.api.ghostfolio.get_settings") as mock:
            settings = MagicMock()
            settings.ghostfolio_api_url = "https://test.ghostfolio.com"
            settings.ghostfolio_access_token = "test_token"
            settings.use_mock_data = False
            settings.cache_ttl_seconds = 300
            mock.return_value = settings
            yield mock

    @pytest.mark.asyncio
    async def test_authenticate_success(self, mock_settings):
        """Authentication should succeed with valid token."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"token": "test_bearer_token"}
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = GhostfolioClient(use_mock=False)
            client._client = mock_client

            token = await client.authenticate()

            assert token == "test_bearer_token"
            mock_client.post.assert_called_once_with(
                "/api/v1/auth/anonymous",
                json={"accessToken": "test_token"},
            )

    @pytest.mark.asyncio
    async def test_authenticate_failure(self, mock_settings):
        """Authentication should raise error on failure."""
        with patch("src.api.ghostfolio.get_cache") as mock_cache:
            mock_cache_obj = MagicMock()
            mock_cache_obj.get.return_value = None  # No cached token
            mock_cache.return_value = mock_cache_obj

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_response = MagicMock()
                mock_response.status_code = 401
                mock_client.post.return_value = mock_response
                mock_client.request.return_value = mock_response
                mock_client_class.return_value = mock_client

                client = GhostfolioClient(use_mock=False)
                client._client = mock_client

                with pytest.raises(AuthenticationError):
                    await client.authenticate()

    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, mock_settings):
        """Client should retry on rate limit."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            # First call: rate limited
            rate_limited_response = MagicMock()
            rate_limited_response.status_code = 429
            rate_limited_response.headers = {"Retry-After": "1"}

            # Second call: success
            success_response = MagicMock()
            success_response.status_code = 200
            success_response.json.return_value = {"test": "data"}

            mock_client.request.side_effect = [rate_limited_response, success_response]
            mock_client_class.return_value = mock_client

            client = GhostfolioClient(use_mock=False)
            client._client = mock_client
            client._bearer_token = "test_token"

            # Mock sleep to speed up test
            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._request_with_retry("GET", "/test")

            assert result == {"test": "data"}

    @pytest.mark.asyncio
    async def test_not_found_error(self, mock_settings):
        """Client should raise NotFoundError on 404."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client

            client = GhostfolioClient(use_mock=False)
            client._client = mock_client
            client._bearer_token = "test_token"

            with pytest.raises(NotFoundError):
                await client._request_with_retry("GET", "/nonexistent")

    @pytest.mark.asyncio
    async def test_timeout_retry(self, mock_settings):
        """Client should retry on timeout."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()

            # First call: timeout
            mock_client.request.side_effect = [
                httpx.TimeoutException("timeout"),
                MagicMock(status_code=200, json=lambda: {"test": "data"}),
            ]
            mock_client_class.return_value = mock_client

            client = GhostfolioClient(use_mock=False)
            client._client = mock_client
            client._bearer_token = "test_token"

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._request_with_retry("GET", "/test")

            assert result == {"test": "data"}


class TestPydanticModels:
    """Tests for Pydantic response models."""

    def test_holding_model(self):
        """Holding model should parse correctly."""
        holding = Holding(
            symbol="AAPL",
            name="Apple Inc.",
            quantity=100,
            value=18500.00,
            allocationPct=12.33,
        )

        assert holding.symbol == "AAPL"
        assert holding.allocation_pct == 12.33

    def test_portfolio_model(self):
        """Portfolio model should parse correctly."""
        portfolio = Portfolio(
            totalValue=150000.00,
            currency="USD",
            holdings=[
                Holding(
                    symbol="AAPL",
                    name="Apple Inc.",
                    quantity=100,
                    value=18500.00,
                    allocationPct=12.33,
                )
            ],
        )

        assert portfolio.total_value == 150000.00
        assert len(portfolio.holdings) == 1

    def test_position_model(self):
        """Position model should parse correctly."""
        position = Position(
            id="pos1",
            symbol="AAPL",
            name="Apple Inc.",
            quantity=100,
            value=18500.00,
            averagePurchasePrice=165.00,
            marketPrice=185.00,
        )

        assert position.id == "pos1"
        assert position.average_purchase_price == 165.00

    def test_order_model(self):
        """Order model should parse correctly."""
        order = Order(
            id="ord1",
            type="BUY",
            symbol="AAPL",
            name="Apple Inc.",
            quantity=10,
            unitPrice=180.00,
            date="2024-01-15",
        )

        assert order.type == "BUY"
        assert order.unit_price == 180.00

    def test_account_model(self):
        """Account model should parse correctly."""
        account = Account(
            id="acc1",
            name="Fidelity",
            currency="USD",
            balance=5000.00,
            value=50000.00,
        )

        assert account.name == "Fidelity"
        assert account.value == 50000.00

    def test_performance_metrics_model(self):
        """PerformanceMetrics model should parse correctly."""
        metrics = PerformanceMetrics(
            absoluteChange=5000.00,
            relativeChange=0.05,
            timeframe="YTD",
            annualizedReturn=0.12,
        )

        assert metrics.absolute_change == 5000.00
        assert metrics.relative_change == 0.05


class TestExceptions:
    """Tests for custom exceptions."""

    def test_ghostfolio_api_error(self):
        """GhostfolioAPIError should be raisable."""
        with pytest.raises(GhostfolioAPIError):
            raise GhostfolioAPIError("Test error")

    def test_authentication_error_inherits(self):
        """AuthenticationError should inherit from GhostfolioAPIError."""
        error = AuthenticationError("Auth failed")
        assert isinstance(error, GhostfolioAPIError)

    def test_rate_limit_error_with_retry_after(self):
        """RateLimitError should store retry_after."""
        error = RateLimitError(retry_after=60)
        assert error.retry_after == 60
        assert "60" in str(error)

    def test_not_found_error_inherits(self):
        """NotFoundError should inherit from GhostfolioAPIError."""
        error = NotFoundError("Not found")
        assert isinstance(error, GhostfolioAPIError)


class TestMockDataIntegrity:
    """Tests to verify mock data structure matches expected format."""

    def test_mock_portfolio_structure(self):
        """Mock portfolio should have all required fields."""
        assert "totalValue" in MOCK_PORTFOLIO
        assert "currency" in MOCK_PORTFOLIO
        assert "holdings" in MOCK_PORTFOLIO
        assert "performance" in MOCK_PORTFOLIO

        for holding in MOCK_PORTFOLIO["holdings"]:
            assert "symbol" in holding
            assert "name" in holding
            assert "quantity" in holding
            assert "value" in holding
            assert "allocationPct" in holding

    def test_mock_positions_structure(self):
        """Mock positions should have all required fields."""
        for position in MOCK_POSITIONS:
            assert "id" in position
            assert "symbol" in position
            assert "name" in position
            assert "quantity" in position
            assert "value" in position

    def test_mock_orders_structure(self):
        """Mock orders should have all required fields."""
        for order in MOCK_ORDERS:
            assert "id" in order
            assert "type" in order
            assert "symbol" in order
            assert "quantity" in order
            assert "unitPrice" in order
            assert "date" in order

    def test_mock_accounts_structure(self):
        """Mock accounts should have all required fields."""
        for account in MOCK_ACCOUNTS:
            assert "id" in account
            assert "name" in account
            assert "currency" in account
            assert "balance" in account
            assert "value" in account

    def test_mock_data_consistency(self):
        """Mock data should be internally consistent."""
        # Sum of holdings allocations should be close to 100%
        total_allocation = sum(h["allocationPct"] for h in MOCK_PORTFOLIO["holdings"])
        assert 99 <= total_allocation <= 101  # Allow for rounding

        # Holdings should match positions (at least symbols)
        holding_symbols = {h["symbol"] for h in MOCK_PORTFOLIO["holdings"]}
        position_symbols = {p["symbol"] for p in MOCK_POSITIONS}
        assert holding_symbols == position_symbols
