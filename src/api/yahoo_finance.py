"""Yahoo Finance API Client for market data."""

import asyncio
from datetime import datetime, timedelta
from typing import Any

import httpx

from src.utils.caching import get_cache
from src.utils.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class YahooFinanceError(Exception):
    """Base exception for Yahoo Finance API errors."""
    pass


class RateLimitError(YahooFinanceError):
    """Rate limit exceeded."""
    pass


class SymbolNotFoundError(YahooFinanceError):
    """Symbol not found."""
    pass


# Mock data for development
MOCK_QUOTES = {
    "AAPL": {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 185.00,
        "change": 2.50,
        "change_percent": 1.37,
        "volume": 52340000,
        "market_cap": 2850000000000,
        "pe_ratio": 28.5,
        "day_high": 186.50,
        "day_low": 183.20,
        "open": 183.50,
        "previous_close": 182.50,
        "currency": "USD",
        "exchange": "NASDAQ",
        "last_updated": datetime.utcnow().isoformat(),
    },
    "MSFT": {
        "symbol": "MSFT",
        "name": "Microsoft Corporation",
        "price": 420.00,
        "change": 5.25,
        "change_percent": 1.27,
        "volume": 21340000,
        "market_cap": 3100000000000,
        "pe_ratio": 35.2,
        "day_high": 422.00,
        "day_low": 416.50,
        "open": 417.00,
        "previous_close": 414.75,
        "currency": "USD",
        "exchange": "NASDAQ",
        "last_updated": datetime.utcnow().isoformat(),
    },
    "VTI": {
        "symbol": "VTI",
        "name": "Vanguard Total Stock Market ETF",
        "price": 240.00,
        "change": 1.80,
        "change_percent": 0.76,
        "volume": 3456000,
        "market_cap": 1500000000000,
        "pe_ratio": 22.1,
        "day_high": 241.20,
        "day_low": 239.00,
        "open": 239.50,
        "previous_close": 238.20,
        "currency": "USD",
        "exchange": "NYSE ARCA",
        "last_updated": datetime.utcnow().isoformat(),
    },
    "NVDA": {
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "price": 380.00,
        "change": 12.50,
        "change_percent": 3.40,
        "volume": 45670000,
        "market_cap": 940000000000,
        "pe_ratio": 65.3,
        "day_high": 385.00,
        "day_low": 370.00,
        "open": 372.00,
        "previous_close": 367.50,
        "currency": "USD",
        "exchange": "NASDAQ",
        "last_updated": datetime.utcnow().isoformat(),
    },
    "BND": {
        "symbol": "BND",
        "name": "Vanguard Total Bond Market ETF",
        "price": 70.00,
        "change": -0.15,
        "change_percent": -0.21,
        "volume": 8765000,
        "market_cap": 95000000000,
        "pe_ratio": None,
        "day_high": 70.25,
        "day_low": 69.80,
        "open": 70.10,
        "previous_close": 70.15,
        "currency": "USD",
        "exchange": "NYSE ARCA",
        "last_updated": datetime.utcnow().isoformat(),
    },
    "GOOGL": {
        "symbol": "GOOGL",
        "name": "Alphabet Inc.",
        "price": 145.00,
        "change": 1.25,
        "change_percent": 0.87,
        "volume": 18930000,
        "market_cap": 1800000000000,
        "pe_ratio": 24.5,
        "day_high": 146.50,
        "day_low": 144.00,
        "open": 144.50,
        "previous_close": 143.75,
        "currency": "USD",
        "exchange": "NASDAQ",
        "last_updated": datetime.utcnow().isoformat(),
    },
}

MOCK_HISTORICAL = {
    "AAPL": [
        {"date": "2024-01-01", "open": 180.00, "high": 182.00, "low": 179.50, "close": 181.50, "volume": 45000000},
        {"date": "2024-01-02", "open": 181.50, "high": 183.00, "low": 180.00, "close": 182.00, "volume": 42000000},
        {"date": "2024-01-03", "open": 182.00, "high": 184.00, "low": 181.50, "close": 183.00, "volume": 38000000},
    ]
}


class YahooFinanceClient:
    """Client for Yahoo Finance API (free, no API key required)."""

    BASE_URL = "https://query1.finance.yahoo.com"

    def __init__(self, use_mock: bool = False) -> None:
        """Initialize Yahoo Finance client.

        Args:
            use_mock: Whether to use mock data for development
        """
        settings = get_settings()
        self._use_mock = use_mock or settings.use_mock_data
        self._cache = get_cache()

        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=10.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )

        logger.info(f"YahooFinanceClient initialized (mock={self._use_mock})")

    async def get_quote(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Get current quotes for symbols.

        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'MSFT'])

        Returns:
            List of quote data with price, change, volume, etc.
        """
        if not symbols:
            return []

        # Normalize symbols
        symbols = [s.upper() for s in symbols]

        if self._use_mock:
            logger.debug(f"Returning mock quotes for {symbols}")
            results = []
            for symbol in symbols:
                if symbol in MOCK_QUOTES:
                    results.append({**MOCK_QUOTES[symbol], "data_age_seconds": 0})
                else:
                    # Generate generic mock data for unknown symbols
                    results.append({
                        "symbol": symbol,
                        "name": f"{symbol} Inc.",
                        "price": 100.00,
                        "change": 0.00,
                        "change_percent": 0.00,
                        "volume": 1000000,
                        "market_cap": None,
                        "pe_ratio": None,
                        "day_high": 101.00,
                        "day_low": 99.00,
                        "open": 100.00,
                        "previous_close": 100.00,
                        "currency": "USD",
                        "exchange": "UNKNOWN",
                        "last_updated": datetime.utcnow().isoformat(),
                        "data_age_seconds": 0,
                    })
            return results

        # Check cache
        cache_key = f"yahoo:quotes:{','.join(sorted(symbols))}"
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug(f"Returning cached quotes for {symbols}")
            return cached

        try:
            # Yahoo Finance v8 API for quotes
            symbols_str = ",".join(symbols)
            response = await self._client.get(
                "/v8/finance/chart/",
                params={
                    "symbols": symbols_str,
                    "interval": "1d",
                    "range": "1d",
                },
            )

            if response.status_code == 429:
                raise RateLimitError("Yahoo Finance rate limit exceeded")

            if response.status_code != 200:
                logger.warning(f"Yahoo Finance API error: {response.status_code}")
                # Fall back to mock data
                return await self._get_mock_quotes(symbols)

            data = response.json()
            results = self._parse_quotes_response(data, symbols)

            # Cache results
            self._cache.set(cache_key, results, ttl=60)  # 1 minute cache

            logger.info(f"Retrieved quotes for {len(results)} symbols")
            return results

        except httpx.RequestError as e:
            logger.warning(f"Yahoo Finance request error: {e}, falling back to mock")
            return await self._get_mock_quotes(symbols)

    async def _get_mock_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Get mock quotes as fallback."""
        results = []
        for symbol in symbols:
            if symbol.upper() in MOCK_QUOTES:
                results.append({**MOCK_QUOTES[symbol.upper()], "data_age_seconds": 0})
            else:
                results.append({
                    "symbol": symbol.upper(),
                    "name": f"{symbol.upper()} Inc.",
                    "price": 100.00,
                    "change": 0.00,
                    "change_percent": 0.00,
                    "volume": 1000000,
                    "market_cap": None,
                    "pe_ratio": None,
                    "day_high": 101.00,
                    "day_low": 99.00,
                    "open": 100.00,
                    "previous_close": 100.00,
                    "currency": "USD",
                    "exchange": "UNKNOWN",
                    "last_updated": datetime.utcnow().isoformat(),
                    "data_age_seconds": 0,
                })
        return results

    def _parse_quotes_response(self, data: dict[str, Any], symbols: list[str]) -> list[dict[str, Any]]:
        """Parse Yahoo Finance quotes response."""
        results = []

        chart_data = data.get("chart", {}).get("result", [])

        for item in chart_data:
            meta = item.get("meta", {})
            symbol = meta.get("symbol", "")

            # Get current price from regularMarketPrice
            price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("previousClose", 0)
            change = price - prev_close if price and prev_close else 0
            change_percent = (change / prev_close * 100) if prev_close else 0

            results.append({
                "symbol": symbol,
                "name": meta.get("shortName", meta.get("longName", symbol)),
                "price": round(price, 2),
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "volume": meta.get("regularMarketVolume", 0),
                "market_cap": meta.get("marketCap"),
                "pe_ratio": None,
                "day_high": meta.get("regularMarketDayHigh"),
                "day_low": meta.get("regularMarketDayLow"),
                "open": meta.get("regularMarketOpen"),
                "previous_close": prev_close,
                "currency": meta.get("currency", "USD"),
                "exchange": meta.get("exchangeName", "UNKNOWN"),
                "last_updated": datetime.utcnow().isoformat(),
                "data_age_seconds": 0,
            })

        return results

    async def get_historical(
        self,
        symbol: str,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get historical data for a symbol.

        Args:
            symbol: Stock symbol
            days: Number of days of history (default 30)

        Returns:
            Historical price data with OHLCV values
        """
        symbol = symbol.upper()

        if self._use_mock:
            logger.debug(f"Returning mock historical data for {symbol}")
            return {
                "symbol": symbol,
                "data": self._generate_mock_historical(days),
                "start_date": (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d"),
                "end_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "data_age_seconds": 0,
            }

        # Check cache
        cache_key = f"yahoo:historical:{symbol}:{days}"
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug(f"Returning cached historical data for {symbol}")
            return cached

        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            response = await self._client.get(
                f"/v8/finance/chart/{symbol}",
                params={
                    "period1": int(start_date.timestamp()),
                    "period2": int(end_date.timestamp()),
                    "interval": "1d",
                },
            )

            if response.status_code == 404:
                raise SymbolNotFoundError(f"Symbol not found: {symbol}")

            if response.status_code == 429:
                raise RateLimitError("Yahoo Finance rate limit exceeded")

            if response.status_code != 200:
                logger.warning(f"Yahoo Finance API error: {response.status_code}")
                # Fall back to mock data
                return {
                    "symbol": symbol,
                    "data": self._generate_mock_historical(days),
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "data_age_seconds": 0,
                }

            data = response.json()
            result = self._parse_historical_response(data, symbol, days)

            # Cache results
            self._cache.set(cache_key, result, ttl=300)  # 5 minute cache

            logger.info(f"Retrieved {len(result.get('data', []))} historical data points for {symbol}")
            return result

        except httpx.RequestError as e:
            logger.warning(f"Yahoo Finance request error: {e}")
            return {
                "symbol": symbol,
                "data": self._generate_mock_historical(days),
                "start_date": (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d"),
                "end_date": datetime.utcnow().strftime("%Y-%m-%d"),
                "data_age_seconds": 0,
            }

    def _generate_mock_historical(self, days: int) -> list[dict[str, Any]]:
        """Generate mock historical data."""
        import random

        data = []
        base_price = 150.0

        for i in range(days):
            date = datetime.utcnow() - timedelta(days=days - i - 1)
            # Random walk price simulation
            change = random.uniform(-2, 2)
            base_price = max(1, base_price + change)

            data.append({
                "date": date.strftime("%Y-%m-%d"),
                "open": round(base_price - random.uniform(0, 1), 2),
                "high": round(base_price + random.uniform(0, 2), 2),
                "low": round(base_price - random.uniform(0, 2), 2),
                "close": round(base_price, 2),
                "volume": random.randint(1000000, 50000000),
            })

        return data

    def _parse_historical_response(
        self, data: dict[str, Any], symbol: str, days: int
    ) -> dict[str, Any]:
        """Parse Yahoo Finance historical response."""
        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {}).get("quote", [{}])[0]

        historical_data = []
        for i, ts in enumerate(timestamps):
            try:
                date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                historical_data.append({
                    "date": date,
                    "open": round(indicators.get("open", [0])[i], 2),
                    "high": round(indicators.get("high", [0])[i], 2),
                    "low": round(indicators.get("low", [0])[i], 2),
                    "close": round(indicators.get("close", [0])[i], 2),
                    "volume": indicators.get("volume", [0])[i],
                })
            except (IndexError, TypeError):
                continue

        return {
            "symbol": symbol,
            "name": meta.get("shortName", symbol),
            "data": historical_data,
            "start_date": timestamps[0] if timestamps else None,
            "end_date": timestamps[-1] if timestamps else None,
            "data_age_seconds": 0,
        }

    async def search(self, query: str) -> list[dict[str, Any]]:
        """Search for symbols by name or ticker.

        Args:
            query: Search query

        Returns:
            List of matching symbols
        """
        if self._use_mock:
            # Simple mock search
            results = []
            query_lower = query.lower()
            for symbol, data in MOCK_QUOTES.items():
                if query_lower in symbol.lower() or query_lower in data["name"].lower():
                    results.append({
                        "symbol": symbol,
                        "name": data["name"],
                        "exchange": data["exchange"],
                        "type": "EQUITY",
                    })
            return results

        try:
            response = await self._client.get(
                "/v1/finance/search",
                params={"q": query, "quotes_count": 10},
            )

            if response.status_code != 200:
                return []

            data = response.json()
            quotes = data.get("quotes", [])

            return [
                {
                    "symbol": q.get("symbol"),
                    "name": q.get("shortname") or q.get("longname", ""),
                    "exchange": q.get("exchange", ""),
                    "type": q.get("quoteType", "EQUITY"),
                }
                for q in quotes[:10]
            ]

        except httpx.RequestError as e:
            logger.warning(f"Yahoo Finance search error: {e}")
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("YahooFinanceClient closed")

    async def __aenter__(self) -> "YahooFinanceClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
