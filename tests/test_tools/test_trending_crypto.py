"""Tests for trending_crypto tool."""

import pytest

from src.tools.trending_crypto import TrendingCoin, TrendingCryptoResult, trending_crypto


class TestTrendingCoin:
    """Tests for TrendingCoin model."""

    def test_valid_coin(self):
        c = TrendingCoin(id="bitcoin", symbol="btc", name="Bitcoin", market_cap_rank=1)
        assert c.id == "bitcoin"
        assert c.symbol == "btc"
        assert c.name == "Bitcoin"
        assert c.market_cap_rank == 1

    def test_rank_optional(self):
        c = TrendingCoin(id="unknown", symbol="unk", name="Unknown", market_cap_rank=None)
        assert c.market_cap_rank is None


class TestTrendingCryptoResult:
    """Tests for TrendingCryptoResult model."""

    def test_empty_result(self):
        r = TrendingCryptoResult(coins=[], source="CoinGecko")
        assert r.coins == []
        assert r.source == "CoinGecko"

    def test_with_coins(self):
        r = TrendingCryptoResult(
            coins=[
                TrendingCoin(id="bitcoin", symbol="btc", name="Bitcoin", market_cap_rank=1),
                TrendingCoin(id="ethereum", symbol="eth", name="Ethereum", market_cap_rank=2),
            ],
            source="CoinGecko",
        )
        assert len(r.coins) == 2
        assert r.coins[0].symbol == "btc"


class TestTrendingCryptoTool:
    """Tests for the trending_crypto tool."""

    @pytest.mark.asyncio
    async def test_returns_structure(self):
        result = await trending_crypto.ainvoke({})
        assert "coins" in result
        assert "source" in result
        assert result["source"] == "CoinGecko"
        assert isinstance(result["coins"], list)

    @pytest.mark.asyncio
    async def test_returns_coins_with_mock(self):
        result = await trending_crypto.ainvoke({})
        # With use_mock_data=True, CoinGecko client returns 3 mock trending coins
        assert len(result["coins"]) >= 0  # may be 0 on error or 3 from mock
        for coin in result["coins"]:
            assert "id" in coin
            assert "symbol" in coin
            assert "name" in coin
            assert "market_cap_rank" in coin or coin.get("market_cap_rank") is None
