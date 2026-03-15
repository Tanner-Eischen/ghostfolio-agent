"""CoinGecko API Client for cryptocurrency market data."""

from datetime import datetime, timedelta
from typing import Any

import httpx

from src.utils.caching import get_cache
from src.utils.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CoinGeckoError(Exception):
    """Base exception for CoinGecko API errors."""
    pass


class RateLimitError(CoinGeckoError):
    """Rate limit exceeded."""
    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s" if retry_after else "Rate limit exceeded")


class CoinNotFoundError(CoinGeckoError):
    """Coin not found."""
    pass


# Coin ID mapping for common symbols
SYMBOL_TO_ID = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "SOL": "solana",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "SHIB": "shiba-inu",
    "LTC": "litecoin",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "ATOM": "cosmos",
    "UNI": "uniswap",
}

# Mock data for development
MOCK_COINS = {
    "bitcoin": {
        "id": "bitcoin",
        "symbol": "btc",
        "name": "Bitcoin",
        "price_usd": 85000.00,
        "price_change_24h": 2.5,
        "price_change_percentage_24h": 2.5,
        "market_cap": 1650000000000,
        "market_cap_rank": 1,
        "total_volume": 35000000000,
        "high_24h": 86000.00,
        "low_24h": 83000.00,
        "circulating_supply": 19400000,
        "total_supply": 21000000,
        "ath": 100000.00,
        "ath_change_percentage": -15.0,
        "last_updated": datetime.utcnow().isoformat(),
    },
    "ethereum": {
        "id": "ethereum",
        "symbol": "eth",
        "name": "Ethereum",
        "price_usd": 3200.00,
        "price_change_24h": 1.8,
        "price_change_percentage_24h": 1.8,
        "market_cap": 384000000000,
        "market_cap_rank": 2,
        "total_volume": 15000000000,
        "high_24h": 3250.00,
        "low_24h": 3150.00,
        "circulating_supply": 120000000,
        "total_supply": None,
        "ath": 4800.00,
        "ath_change_percentage": -33.0,
        "last_updated": datetime.utcnow().isoformat(),
    },
    "solana": {
        "id": "solana",
        "symbol": "sol",
        "name": "Solana",
        "price_usd": 180.00,
        "price_change_24h": 5.2,
        "price_change_percentage_24h": 5.2,
        "market_cap": 78000000000,
        "market_cap_rank": 3,
        "total_volume": 3000000000,
        "high_24h": 185.00,
        "low_24h": 172.00,
        "circulating_supply": 433000000,
        "total_supply": None,
        "ath": 260.00,
        "ath_change_percentage": -30.0,
        "last_updated": datetime.utcnow().isoformat(),
    },
}


class CoinGeckoClient:
    """Client for CoinGecko API."""

    BASE_URL = "https://api.coingecko.com/api/v3"
    PRO_BASE_URL = "https://pro-api.coingecko.com/api/v3"

    def __init__(self, api_key: str | None = None, use_mock: bool = False) -> None:
        """Initialize CoinGecko client.

        Args:
            api_key: Optional Pro API key for higher rate limits
            use_mock: Whether to use mock data for development
        """
        settings = get_settings()
        self._api_key = api_key or settings.coingecko_api_key
        self._use_mock = use_mock or settings.use_mock_data
        self._cache = get_cache()

        # Use Pro URL if API key is provided
        self._base_url = self.PRO_BASE_URL if self._api_key else self.BASE_URL

        headers = {}
        if self._api_key:
            headers["x-cg-pro-api-key"] = self._api_key

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(15.0, connect=5.0),
            headers=headers,
            limits=httpx.Limits(
                max_keepalive_connections=6,
                max_connections=12,
                keepalive_expiry=20.0,
            ),
        )

        logger.info(f"CoinGeckoClient initialized (mock={self._use_mock}, pro={bool(self._api_key)})")

    def _get_symbol_id(self, symbol: str) -> str:
        """Convert symbol to CoinGecko ID.

        Args:
            symbol: Crypto symbol (e.g., 'BTC', 'bitcoin')

        Returns:
            CoinGecko coin ID
        """
        symbol_upper = symbol.upper()
        if symbol_upper in SYMBOL_TO_ID:
            return SYMBOL_TO_ID[symbol_upper]
        # If already an ID, return as-is
        return symbol.lower()

    async def get_price(
        self,
        coin_ids: list[str],
        vs_currency: str = "usd",
        include_market_cap: bool = True,
        include_24hr_vol: bool = True,
        include_24hr_change: bool = True,
    ) -> dict[str, Any]:
        """Get current prices for coins.

        Args:
            coin_ids: List of CoinGecko coin IDs (e.g., 'bitcoin', 'ethereum')
            vs_currency: Currency to price in (default: usd)
            include_market_cap: Include market cap data
            include_24hr_vol: Include 24h volume data
            include_24hr_change: Include 24h price change

        Returns:
            Price data for requested coins
        """
        if not coin_ids:
            return {}

        # Normalize coin IDs
        coin_ids = [self._get_symbol_id(cid) for cid in coin_ids]

        if self._use_mock:
            logger.debug(f"Returning mock prices for {coin_ids}")
            return self._get_mock_prices(coin_ids, vs_currency)

        # Check cache
        cache_key = f"coingecko:prices:{','.join(sorted(coin_ids))}:{vs_currency}"
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug(f"Returning cached prices for {coin_ids}")
            return cached

        try:
            params = {
                "ids": ",".join(coin_ids),
                "vs_currencies": vs_currency,
                "include_market_cap": str(include_market_cap).lower(),
                "include_24hr_vol": str(include_24hr_vol).lower(),
                "include_24hr_change": str(include_24hr_change).lower(),
                "include_last_updated_at": "true",
            }

            response = await self._client.get("/simple/price", params=params)

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError(int(retry_after) if retry_after else None)

            if response.status_code != 200:
                logger.warning(f"CoinGecko API error: {response.status_code}")
                return self._get_mock_prices(coin_ids, vs_currency)

            data = response.json()

            # Add metadata
            result = {
                "data": data,
                "vs_currency": vs_currency,
                "data_age_seconds": 0,
                "last_updated": datetime.utcnow().isoformat(),
            }

            # Cache for 60 seconds
            self._cache.set(cache_key, result, ttl=60)

            logger.info(f"Retrieved prices for {len(data)} coins")
            return result

        except httpx.RequestError as e:
            logger.warning(f"CoinGecko request error: {e}")
            return self._get_mock_prices(coin_ids, vs_currency)

    def _get_mock_prices(self, coin_ids: list[str], vs_currency: str) -> dict[str, Any]:
        """Get mock price data."""
        data = {}
        for coin_id in coin_ids:
            if coin_id in MOCK_COINS:
                coin = MOCK_COINS[coin_id]
                data[coin_id] = {
                    vs_currency: coin["price_usd"],
                    f"{vs_currency}_market_cap": coin["market_cap"],
                    f"{vs_currency}_24h_vol": coin["total_volume"],
                    f"{vs_currency}_24h_change": coin["price_change_percentage_24h"],
                    "last_updated_at": int(datetime.utcnow().timestamp()),
                }
            else:
                # Generic mock data
                data[coin_id] = {
                    vs_currency: 100.00,
                    f"{vs_currency}_market_cap": 1000000000,
                    f"{vs_currency}_24h_vol": 10000000,
                    f"{vs_currency}_24h_change": 0.0,
                    "last_updated_at": int(datetime.utcnow().timestamp()),
                }

        return {
            "data": data,
            "vs_currency": vs_currency,
            "data_age_seconds": 0,
            "last_updated": datetime.utcnow().isoformat(),
        }

    async def get_market_data(self, coin_id: str) -> dict[str, Any]:
        """Get detailed market data for a coin.

        Args:
            coin_id: CoinGecko coin ID (e.g., 'bitcoin')

        Returns:
            Detailed market data including market cap, volume, supply, etc.
        """
        coin_id = self._get_symbol_id(coin_id)

        if self._use_mock:
            logger.debug(f"Returning mock market data for {coin_id}")
            if coin_id in MOCK_COINS:
                return {**MOCK_COINS[coin_id], "data_age_seconds": 0}
            return self._generate_mock_market_data(coin_id)

        # Check cache
        cache_key = f"coingecko:market:{coin_id}"
        cached = self._cache.get(cache_key)
        if cached:
            logger.debug(f"Returning cached market data for {coin_id}")
            return cached

        try:
            response = await self._client.get(
                f"/coins/{coin_id}",
                params={
                    "localization": "false",
                    "tickers": "false",
                    "market_data": "true",
                    "community_data": "false",
                    "developer_data": "false",
                },
            )

            if response.status_code == 404:
                raise CoinNotFoundError(f"Coin not found: {coin_id}")

            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                raise RateLimitError(int(retry_after) if retry_after else None)

            if response.status_code != 200:
                logger.warning(f"CoinGecko API error: {response.status_code}")
                return self._generate_mock_market_data(coin_id)

            data = response.json()
            market_data = data.get("market_data", {})

            result = {
                "id": data.get("id"),
                "symbol": data.get("symbol"),
                "name": data.get("name"),
                "price_usd": market_data.get("current_price", {}).get("usd"),
                "price_change_24h": market_data.get("price_change_24h"),
                "price_change_percentage_24h": market_data.get("price_change_percentage_24h"),
                "market_cap": market_data.get("market_cap", {}).get("usd"),
                "market_cap_rank": data.get("market_cap_rank"),
                "total_volume": market_data.get("total_volume", {}).get("usd"),
                "high_24h": market_data.get("high_24h", {}).get("usd"),
                "low_24h": market_data.get("low_24h", {}).get("usd"),
                "circulating_supply": market_data.get("circulating_supply"),
                "total_supply": market_data.get("total_supply"),
                "ath": market_data.get("ath", {}).get("usd"),
                "ath_change_percentage": market_data.get("ath_change_percentage", {}).get("usd"),
                "description": data.get("description", {}).get("en", "")[:500] if data.get("description") else None,
                "last_updated": datetime.utcnow().isoformat(),
                "data_age_seconds": 0,
            }

            # Cache for 5 minutes
            self._cache.set(cache_key, result, ttl=300)

            logger.info(f"Retrieved market data for {coin_id}")
            return result

        except httpx.RequestError as e:
            logger.warning(f"CoinGecko request error: {e}")
            return self._generate_mock_market_data(coin_id)

    def _generate_mock_market_data(self, coin_id: str) -> dict[str, Any]:
        """Generate mock market data for unknown coins."""
        return {
            "id": coin_id,
            "symbol": coin_id[:3],
            "name": coin_id.title(),
            "price_usd": 100.00,
            "price_change_24h": 0.0,
            "price_change_percentage_24h": 0.0,
            "market_cap": 1000000000,
            "market_cap_rank": 100,
            "total_volume": 10000000,
            "high_24h": 105.00,
            "low_24h": 95.00,
            "circulating_supply": 10000000,
            "total_supply": None,
            "ath": 200.00,
            "ath_change_percentage": -50.0,
            "description": None,
            "last_updated": datetime.utcnow().isoformat(),
            "data_age_seconds": 0,
        }

    async def get_ohlc(
        self,
        coin_id: str,
        vs_currency: str = "usd",
        days: int = 7,
    ) -> list[dict[str, Any]]:
        """Get OHLC (Open-High-Low-Close) data for a coin.

        Args:
            coin_id: CoinGecko coin ID
            vs_currency: Currency to price in
            days: Number of days of data (1, 7, 14, 30, 90, 180, 365, max)

        Returns:
            List of OHLC data points
        """
        coin_id = self._get_symbol_id(coin_id)

        if self._use_mock:
            logger.debug(f"Returning mock OHLC data for {coin_id}")
            return self._generate_mock_ohlc(days)

        # Check cache
        cache_key = f"coingecko:ohlc:{coin_id}:{days}"
        cached = self._cache.get(cache_key)
        if cached:
            return cached

        try:
            response = await self._client.get(
                f"/coins/{coin_id}/ohlc",
                params={
                    "vs_currency": vs_currency,
                    "days": days,
                },
            )

            if response.status_code != 200:
                return self._generate_mock_ohlc(days)

            # CoinGecko returns: [timestamp, open, high, low, close]
            data = response.json()

            result = [
                {
                    "timestamp": item[0],
                    "date": datetime.utcfromtimestamp(item[0] / 1000).strftime("%Y-%m-%d %H:%M"),
                    "open": item[1],
                    "high": item[2],
                    "low": item[3],
                    "close": item[4],
                }
                for item in data
            ]

            # Cache for 1 hour
            self._cache.set(cache_key, result, ttl=3600)

            return result

        except httpx.RequestError:
            return self._generate_mock_ohlc(days)

    def _generate_mock_ohlc(self, days: int) -> list[dict[str, Any]]:
        """Generate mock OHLC data."""
        import random

        data = []
        base_price = 100.0

        for i in range(min(days, 30)):
            timestamp = int((datetime.utcnow() - timedelta(days=days - i - 1)).timestamp() * 1000)
            change = random.uniform(-5, 5)
            base_price = max(1, base_price + change)

            data.append({
                "timestamp": timestamp,
                "date": datetime.utcfromtimestamp(timestamp / 1000).strftime("%Y-%m-%d"),
                "open": round(base_price - random.uniform(0, 2), 2),
                "high": round(base_price + random.uniform(0, 3), 2),
                "low": round(base_price - random.uniform(0, 3), 2),
                "close": round(base_price, 2),
            })

        return data

    async def search(self, query: str) -> list[dict[str, Any]]:
        """Search for coins by name or symbol.

        Args:
            query: Search query

        Returns:
            List of matching coins
        """
        if self._use_mock:
            results = []
            query_lower = query.lower()
            for coin_id, data in MOCK_COINS.items():
                if (query_lower in coin_id.lower() or
                    query_lower in data["symbol"].lower() or
                    query_lower in data["name"].lower()):
                    results.append({
                        "id": coin_id,
                        "symbol": data["symbol"],
                        "name": data["name"],
                        "market_cap_rank": data["market_cap_rank"],
                    })
            return results

        try:
            response = await self._client.get(
                "/search",
                params={"query": query},
            )

            if response.status_code != 200:
                return []

            data = response.json()
            coins = data.get("coins", [])

            return [
                {
                    "id": coin.get("id"),
                    "symbol": coin.get("symbol"),
                    "name": coin.get("name"),
                    "market_cap_rank": coin.get("market_cap_rank"),
                    "thumb": coin.get("thumb"),
                }
                for coin in coins[:20]
            ]

        except httpx.RequestError as e:
            logger.warning(f"CoinGecko search error: {e}")
            return []

    async def get_trending(self) -> list[dict[str, Any]]:
        """Get trending coins.

        Returns:
            List of trending coins
        """
        if self._use_mock:
            return [
                {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "market_cap_rank": 1},
                {"id": "ethereum", "symbol": "eth", "name": "Ethereum", "market_cap_rank": 2},
                {"id": "solana", "symbol": "sol", "name": "Solana", "market_cap_rank": 3},
            ]

        try:
            response = await self._client.get("/search/trending")

            if response.status_code != 200:
                return []

            data = response.json()
            coins = data.get("coins", [])

            return [
                {
                    "id": coin.get("item", {}).get("id"),
                    "symbol": coin.get("item", {}).get("symbol"),
                    "name": coin.get("item", {}).get("name"),
                    "market_cap_rank": coin.get("item", {}).get("market_cap_rank"),
                    "price_btc": coin.get("item", {}).get("price_btc"),
                }
                for coin in coins[:7]
            ]

        except httpx.RequestError as e:
            logger.warning(f"CoinGecko trending error: {e}")
            return []

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        logger.info("CoinGeckoClient closed")

    async def __aenter__(self) -> "CoinGeckoClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
