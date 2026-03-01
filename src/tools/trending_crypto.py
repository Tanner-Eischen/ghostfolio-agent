"""Trending Crypto Tool - CoinGecko trending coins."""

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.api.coingecko import CoinGeckoClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Output Models
# ============================================================================


class TrendingCoin(BaseModel):
    """A single trending coin from CoinGecko."""

    id: str = Field(description="CoinGecko coin ID")
    symbol: str = Field(description="Symbol (e.g. btc, eth)")
    name: str = Field(description="Display name")
    market_cap_rank: int | None = Field(default=None, description="Market cap rank if available")


class TrendingCryptoResult(BaseModel):
    """Result of trending crypto lookup."""

    coins: list[TrendingCoin] = Field(description="List of trending coins")
    source: str = Field(default="CoinGecko", description="Data source")


@tool
async def trending_crypto() -> dict[str, Any]:
    """Fetch currently trending cryptocurrencies from CoinGecko.

    Use this tool when the user asks about:
    - What crypto is trending
    - Trending coins or tokens
    - What's hot in crypto right now
    - Popular or most-searched cryptocurrencies

    Returns:
        TrendingCryptoResult with list of trending coins (id, symbol, name, market_cap_rank).
    """
    try:
        async with CoinGeckoClient() as client:
            raw = await client.get_trending()
        coins = [
            TrendingCoin(
                id=c.get("id", ""),
                symbol=c.get("symbol", ""),
                name=c.get("name", ""),
                market_cap_rank=c.get("market_cap_rank"),
            )
            for c in raw
        ]
        result = TrendingCryptoResult(coins=coins, source="CoinGecko")
        logger.info(f"Trending crypto: {len(coins)} coins")
        return result.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Trending crypto failed: {e}")
        return TrendingCryptoResult(coins=[], source="CoinGecko").model_dump(mode="json")


__all__ = ["trending_crypto", "TrendingCryptoResult", "TrendingCoin"]
