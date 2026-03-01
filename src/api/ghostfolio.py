"""Ghostfolio API Client for interacting with Ghostfolio backend."""

import asyncio
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from src.utils.caching import get_cache
from src.utils.config import get_settings
from src.utils.request_context import get_request_ghostfolio_token, get_request_ghostfolio_api_url
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Response Models
# ============================================================================


class Holding(BaseModel):
    """A single portfolio holding."""

    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    name: str
    quantity: float
    value: float
    allocation_pct: float = Field(alias="allocationPct")
    currency: str = "USD"
    asset_class: str | None = Field(None, alias="assetClass")
    asset_sub_class: str | None = Field(None, alias="assetSubClass")


class Performance(BaseModel):
    """Portfolio performance metrics."""

    model_config = ConfigDict(populate_by_name=True)

    absolute_change: float = Field(alias="absoluteChange")
    relative_change: float = Field(alias="relativeChange")
    timeframe: str = "YTD"
    currency: str = "USD"


class Portfolio(BaseModel):
    """Complete portfolio data."""

    model_config = ConfigDict(populate_by_name=True)

    total_value: float = Field(alias="totalValue")
    currency: str = "USD"
    holdings: list[Holding] = []
    performance: Performance | None = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class Position(BaseModel):
    """A single position in the portfolio."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    symbol: str
    name: str
    quantity: float
    value: float
    currency: str = "USD"
    asset_class: str | None = Field(None, alias="assetClass")
    asset_sub_class: str | None = Field(None, alias="assetSubClass")
    average_purchase_price: float | None = Field(None, alias="averagePurchasePrice")
    market_price: float | None = Field(None, alias="marketPrice")
    transaction_count: int = Field(0, alias="transactionCount")


class Order(BaseModel):
    """A transaction order."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str  # BUY, SELL, DIVIDEND, etc.
    symbol: str
    name: str
    quantity: float
    unit_price: float = Field(alias="unitPrice")
    currency: str = "USD"
    date: str
    account_id: str | None = Field(None, alias="accountId")
    fee: float = 0.0
    comment: str | None = None


class Account(BaseModel):
    """A financial account."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    currency: str = "USD"
    platform_id: str | None = Field(None, alias="platformId")
    balance: float = 0.0
    value: float = 0.0
    transaction_count: int = Field(0, alias="transactionCount")


class PerformanceMetrics(BaseModel):
    """Detailed performance metrics."""

    model_config = ConfigDict(populate_by_name=True)

    absolute_change: float = Field(alias="absoluteChange")
    relative_change: float = Field(alias="relativeChange")
    timeframe: str
    currency: str = "USD"
    annualized_return: float | None = Field(None, alias="annualizedReturn")
    max_drawdown: float | None = Field(None, alias="maxDrawdown")
    volatility: float | None = None
    data_age_seconds: int = 0


# ============================================================================
# Exceptions
# ============================================================================


class GhostfolioAPIError(Exception):
    """Base exception for Ghostfolio API errors."""

    pass


class AuthenticationError(GhostfolioAPIError):
    """Authentication failed."""

    pass


class RateLimitError(GhostfolioAPIError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s" if retry_after else "Rate limit exceeded")


class NotFoundError(GhostfolioAPIError):
    """Resource not found."""

    pass


# ============================================================================
# Mock Data
# ============================================================================


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
        "comment": "Initial purchase",
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
        "comment": None,
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
        "comment": "Q1 Dividend",
    },
    {
        "id": "ord004",
        "type": "BUY",
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "quantity": 25,
        "unitPrice": 390.00,
        "currency": "USD",
        "date": "2024-01-20",
        "accountId": "acc1",
        "fee": 0.0,
        "comment": None,
    },
    {
        "id": "ord005",
        "type": "BUY",
        "symbol": "VTI",
        "name": "Vanguard Total Stock Market ETF",
        "quantity": 100,
        "unitPrice": 225.00,
        "currency": "USD",
        "date": "2024-01-05",
        "accountId": "acc2",
        "fee": 0.0,
        "comment": "Monthly DCA",
    },
    {
        "id": "ord006",
        "type": "BUY",
        "symbol": "BTC",
        "name": "Bitcoin",
        "quantity": 0.25,
        "unitPrice": 68000.00,
        "currency": "USD",
        "date": "2024-01-25",
        "accountId": "acc3",
        "fee": 5.00,
        "comment": None,
    },
    {
        "id": "ord007",
        "type": "SELL",
        "symbol": "GOOGL",
        "name": "Alphabet Inc.",
        "quantity": 15,
        "unitPrice": 145.00,
        "currency": "USD",
        "date": "2024-03-01",
        "accountId": "acc1",
        "fee": 0.0,
        "comment": "Rebalancing",
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


MOCK_PERFORMANCE = {
    "absoluteChange": 12500.00,
    "relativeChange": 0.0909,
    "timeframe": "YTD",
    "currency": "USD",
    "annualizedReturn": 0.12,
    "maxDrawdown": -0.08,
    "volatility": 0.15,
}


# ============================================================================
# Client Implementation
# ============================================================================


class GhostfolioClient:
    """Client for interacting with Ghostfolio API."""

    def __init__(
        self,
        base_url: str | None = None,
        access_token: str | None = None,
        use_mock: bool = False,
    ) -> None:
        """Initialize Ghostfolio client.

        Args:
            base_url: Ghostfolio API base URL
            access_token: Access token for authentication
            use_mock: Whether to use mock data
        """
        settings = get_settings()
        # Per-request token (stateless) overrides arg and env
        request_token = get_request_ghostfolio_token()
        self._access_token = (
            request_token
            or access_token
            or settings.ghostfolio_access_token
        )
        if not (self._access_token and str(self._access_token).strip()):
            self._access_token = None
            token_source = "none (request header and env both empty)"
        elif request_token:
            token_source = "request header"
        else:
            token_source = "env/config"
        # User-provided token (stateless): use their URL if sent, else localhost (free local Ghostfolio)
        request_url = get_request_ghostfolio_api_url() if request_token else None
        if request_token and not base_url:
            raw = (request_url and request_url.strip()) or "http://localhost:3333"
            self._base_url = raw.rstrip("/")
        else:
            self._base_url = base_url or settings.ghostfolio_api_url
        self._use_mock = use_mock or settings.use_mock_data
        self._bearer_token: str | None = None
        self._cache = get_cache()
        self._request_count = 0
        # Don't use shared cache for per-request token (each user's data stays isolated)
        self._per_request_token = bool(request_token)

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"Content-Type": "application/json"},
            limits=httpx.Limits(
                max_keepalive_connections=8,
                max_connections=16,
                keepalive_expiry=30.0,
            ),
        )

        logger.info(
            f"GhostfolioClient initialized (mock={self._use_mock}, url={self._base_url}, token={token_source})"
        )

    async def _get_headers(self) -> dict[str, str]:
        """Get headers with authentication.

        Returns:
            Headers dict with bearer token if authenticated
        """
        headers = {"Content-Type": "application/json"}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        return headers

    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method
            endpoint: API endpoint
            **kwargs: Additional request kwargs

        Returns:
            Response JSON data

        Raises:
            AuthenticationError: If authentication fails
            RateLimitError: If rate limited
            GhostfolioAPIError: For other API errors
        """
        if self._use_mock:
            raise GhostfolioAPIError("Mock mode - should not reach _request_with_retry")

        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                headers = await self._get_headers()
                headers.update(kwargs.pop("headers", {}))

                response = await self._client.request(
                    method,
                    endpoint,
                    headers=headers,
                    **kwargs,
                )
                self._request_count += 1

                if response.status_code == 200:
                    return response.json()

                if response.status_code == 401:
                    raise AuthenticationError("Authentication failed. Check your access token.")

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    retry_seconds = int(retry_after) if retry_after else 60
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_seconds)
                        continue
                    raise RateLimitError(retry_seconds)

                if response.status_code == 404:
                    raise NotFoundError(f"Resource not found: {endpoint}")

                # Other errors
                error_msg = response.text[:200]
                raise GhostfolioAPIError(
                    f"API error {response.status_code}: {error_msg}"
                )

            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(f"Request timeout, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise GhostfolioAPIError("Request timed out after retries")

            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.warning(f"Request error: {e}, retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                raise GhostfolioAPIError(f"Request failed: {e}")

        raise GhostfolioAPIError("Max retries exceeded")

    async def authenticate(self) -> str:
        """Authenticate and get bearer token.

        Uses the anonymous authentication endpoint with the access token.

        Returns:
            Bearer token for subsequent requests

        Raises:
            AuthenticationError: If authentication fails
        """
        if not self._access_token:
            logger.warning(
                "Ghostfolio auth: no token (request header and env both empty). "
                "User must set token in app: avatar -> Connect Ghostfolio -> paste token -> Connect."
            )
            raise AuthenticationError(
                "No Ghostfolio access token provided. In this app, click your avatar (top right) -> "
                "Connect Ghostfolio, paste the token from Ghostfolio Settings -> Security, and click Connect."
            )
        if self._use_mock:
            logger.info("Using mock mode - returning mock token")
            self._bearer_token = "mock_token"
            return self._bearer_token

        # Check cache for existing token (skip when per-request token to avoid cross-user leak)
        if not self._per_request_token:
            cached_token = self._cache.get("ghostfolio:bearer_token")
            if cached_token:
                logger.debug("Using cached bearer token")
                self._bearer_token = cached_token
                return self._bearer_token

        try:
            response = await self._client.post(
                "/api/v1/auth/anonymous",
                json={"accessToken": self._access_token},
            )

            if response.status_code < 200 or response.status_code >= 300:
                logger.warning(
                    "Ghostfolio auth rejected: HTTP %s from %s (check token and that Instance URL matches your Ghostfolio)",
                    response.status_code,
                    self._base_url,
                )
                raise AuthenticationError(
                    f"Authentication failed with status {response.status_code}"
                )

            data = response.json()
            self._bearer_token = data.get("token") or data.get("authToken")

            if not self._bearer_token:
                raise AuthenticationError("No token in authentication response")

            # Cache the token (skip when per-request token)
            if not self._per_request_token:
                self._cache.set("ghostfolio:bearer_token", self._bearer_token)
            logger.info("Successfully authenticated with Ghostfolio")

            return self._bearer_token

        except httpx.RequestError as e:
            raise AuthenticationError(f"Authentication request failed: {e}")

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid bearer token."""
        if not self._bearer_token:
            await self.authenticate()

    async def get_portfolio(self) -> dict[str, Any]:
        """Get portfolio details.

        Returns:
            Portfolio data including accounts and summary
        """
        if self._use_mock:
            logger.debug("Returning mock portfolio data")
            return {**MOCK_PORTFOLIO, "last_updated": datetime.utcnow().isoformat()}

        # Check cache (skip when per-request token)
        cache_key = "ghostfolio:portfolio"
        if not self._per_request_token:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("Returning cached portfolio data")
                return cached

        await self._ensure_authenticated()

        # Ghostfolio API: portfolio data is at /details (not /portfolio)
        raw = await self._request_with_retry(
            "GET", "/api/v1/portfolio/details", params={"range": "max"}
        )
        # Map Ghostfolio details response to our expected shape
        summary = raw.get("summary") or {}
        holdings_obj = raw.get("holdings") or {}
        total_value = float(
            summary.get("currentValueInBaseCurrency")
            or summary.get("totalValueInBaseCurrency")
            or 0
        )
        # holdings is symbol -> position; convert to list for tools
        holdings_list = []
        for symbol, pos in holdings_obj.items():
            if not isinstance(pos, dict):
                continue
            value = float(pos.get("valueInBaseCurrency", 0))
            pct = float(pos.get("valueInPercentage", 0)) * 100 if pos.get("valueInPercentage") is not None else 0
            holdings_list.append({
                "symbol": symbol,
                "name": pos.get("name", symbol),
                "quantity": float(pos.get("quantity", 0)),
                "value": value,
                "allocation_pct": pct,
                "allocationPct": pct,
                "asset_class": pos.get("assetClass"),
                "assetClass": pos.get("assetClass"),
                "currency": pos.get("currency", "USD"),
            })
        data = {
            "total_value": total_value,
            "totalValue": total_value,
            "holdings": holdings_list,
            "summary": summary,
            "accounts": raw.get("accounts"),
            "currency": "USD",
            "last_updated": datetime.utcnow().isoformat(),
        }
        # Cache the result (skip when per-request token)
        if not self._per_request_token:
            self._cache.set(cache_key, data)

        logger.info(f"Retrieved portfolio data with {len(holdings_list)} holdings")
        return data

    async def get_positions(self) -> list[dict[str, Any]]:
        """Get current positions.

        Returns:
            List of current positions
        """
        if self._use_mock:
            logger.debug("Returning mock positions data")
            return MOCK_POSITIONS

        # Check cache (skip when per-request token)
        cache_key = "ghostfolio:positions"
        if not self._per_request_token:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("Returning cached positions data")
                return cached

        await self._ensure_authenticated()

        # Ghostfolio API: positions are at /holdings (returns { holdings: [...] })
        data = await self._request_with_retry(
            "GET", "/api/v1/portfolio/holdings", params={"range": "max"}
        )
        raw_holdings = data.get("holdings", []) if isinstance(data, dict) else []
        if not raw_holdings and isinstance(data.get("holdings"), dict):
            # Details-style: holdings is object keyed by symbol
            raw_holdings = [
                {"symbol": sym, **pos} for sym, pos in (data.get("holdings") or {}).items()
                if isinstance(pos, dict)
            ]
        positions = []
        for h in raw_holdings:
            if not isinstance(h, dict):
                continue
            value = float(h.get("valueInBaseCurrency", h.get("value", 0)))
            positions.append({
                "id": h.get("id", h.get("symbol", "")),
                "symbol": h.get("symbol", ""),
                "name": h.get("name", h.get("symbol", "")),
                "quantity": float(h.get("quantity", 0)),
                "value": value,
                "currency": h.get("currency", "USD"),
                "assetClass": h.get("assetClass"),
                "assetSubClass": h.get("assetSubClass"),
            })

        # Cache the result (skip when per-request token)
        if not self._per_request_token:
            self._cache.set(cache_key, positions)

        logger.info(f"Retrieved {len(positions)} positions")
        return positions

    async def get_orders(
        self,
        filters: dict[str, Any] | None = None,
        account_id: str | None = None,
        symbol: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get orders/transactions.

        Args:
            filters: Optional filters for orders (deprecated, use specific params)
            account_id: Filter by account ID
            symbol: Filter by symbol
            start_date: Filter orders after this date (YYYY-MM-DD)
            end_date: Filter orders before this date (YYYY-MM-DD)

        Returns:
            List of orders/transactions
        """
        if self._use_mock:
            logger.debug("Returning mock orders data")
            orders = MOCK_ORDERS.copy()

            # Apply filters to mock data
            if account_id:
                orders = [o for o in orders if o.get("accountId") == account_id]
            if symbol:
                orders = [o for o in orders if o.get("symbol") == symbol.upper()]
            if start_date:
                orders = [o for o in orders if o.get("date", "") >= start_date]
            if end_date:
                orders = [o for o in orders if o.get("date", "") <= end_date]

            return orders

        # Build query params
        params: dict[str, Any] = {}
        if account_id:
            params["accountId"] = account_id
        if symbol:
            params["symbol"] = symbol.upper()
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date

        # Support legacy filters dict
        if filters:
            params.update(filters)

        # Check cache (skip when per-request token)
        cache_key = f"ghostfolio:orders:{hash(frozenset(params.items()))}"
        if not self._per_request_token:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("Returning cached orders data")
                return cached

        await self._ensure_authenticated()

        data = await self._request_with_retry(
            "GET", "/api/v1/order", params=params if params else None
        )
        orders = data if isinstance(data, list) else data.get("activities", [])

        # Cache the result (skip when per-request token)
        if not self._per_request_token:
            self._cache.set(cache_key, orders)

        logger.info(f"Retrieved {len(orders)} orders")
        return orders

    async def get_accounts(self) -> list[dict[str, Any]]:
        """Get all accounts.

        Returns:
            List of accounts
        """
        if self._use_mock:
            logger.debug("Returning mock accounts data")
            return MOCK_ACCOUNTS

        # Check cache (skip when per-request token)
        cache_key = "ghostfolio:accounts"
        if not self._per_request_token:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("Returning cached accounts data")
                return cached

        await self._ensure_authenticated()

        data = await self._request_with_retry("GET", "/api/v1/account")
        accounts = data if isinstance(data, list) else data.get("accounts", [])

        # Cache the result (skip when per-request token)
        if not self._per_request_token:
            self._cache.set(cache_key, accounts)

        logger.info(f"Retrieved {len(accounts)} accounts")
        return accounts

    async def get_performance(
        self,
        timeframe: str = "YTD",
        account_id: str | None = None,
    ) -> dict[str, Any]:
        """Get portfolio performance.

        Args:
            timeframe: Time period (Today, WTD, MTD, YTD, 1Y, 5Y, Max)
            account_id: Optional account filter

        Returns:
            Performance metrics
        """
        valid_timeframes = ["Today", "WTD", "MTD", "YTD", "1Y", "5Y", "Max"]
        if timeframe not in valid_timeframes:
            logger.warning(f"Invalid timeframe '{timeframe}', using YTD")
            timeframe = "YTD"

        if self._use_mock:
            logger.debug(f"Returning mock performance data for {timeframe}")
            return {**MOCK_PERFORMANCE, "timeframe": timeframe, "data_age_seconds": 0}

        # Check cache (skip when per-request token)
        cache_key = f"ghostfolio:performance:{timeframe}:{account_id or 'all'}"
        if not self._per_request_token:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("Returning cached performance data")
                return cached

        await self._ensure_authenticated()

        params = {"range": timeframe}
        if account_id:
            params["accountId"] = account_id

        data = await self._request_with_retry(
            "GET", "/api/v1/portfolio/performance", params=params
        )

        # Add metadata
        data["timeframe"] = timeframe
        data["data_age_seconds"] = 0
        data["last_updated"] = datetime.utcnow().isoformat()

        # Cache the result (skip when per-request token)
        if not self._per_request_token:
            self._cache.set(cache_key, data)

        logger.info(f"Retrieved performance data for {timeframe}")
        return data

    async def get_public_portfolio(self, access_id: str) -> dict[str, Any]:
        """Get public portfolio by access ID (no auth required).

        Args:
            access_id: Public access ID for the portfolio

        Returns:
            Portfolio data
        """
        if self._use_mock:
            logger.debug("Returning mock public portfolio data")
            return {**MOCK_PORTFOLIO, "access_id": access_id}

        # Check cache (skip when per-request token)
        cache_key = f"ghostfolio:public:{access_id}"
        if not self._per_request_token:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("Returning cached public portfolio data")
                return cached

        data = await self._request_with_retry(
            "GET", f"/api/v1/public/{access_id}/portfolio"
        )

        # Cache the result (skip when per-request token)
        if not self._per_request_token:
            self._cache.set(cache_key, data)

        logger.info(f"Retrieved public portfolio {access_id}")
        return data

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.delete("ghostfolio:bearer_token")
        self._cache.delete("ghostfolio:portfolio")
        self._cache.delete("ghostfolio:positions")
        self._cache.delete("ghostfolio:accounts")
        # Clear orders and performance caches (they have dynamic keys)
        self._cache._cache.clear()  # Clear all cache entries
        logger.info("Cleared all Ghostfolio cache")

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics.

        Returns:
            Stats including request count and cache info
        """
        return {
            "request_count": self._request_count,
            "use_mock": self._use_mock,
            "authenticated": self._bearer_token is not None,
            "base_url": self._base_url,
            "cache": self._cache.get_stats(),
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("GhostfolioClient closed")

    async def __aenter__(self) -> "GhostfolioClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
