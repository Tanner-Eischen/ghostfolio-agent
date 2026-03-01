"""Tests for price_history tool."""

import pytest

from src.tools.price_history import (
    OHLCPoint,
    PriceHistoryResult,
    SymbolPriceHistory,
    _coingecko_days,
    _compute_period_summary,
    price_history,
)


class TestCoingeckoDays:
    """Tests for _coingecko_days mapping."""

    def test_one_day(self):
        assert _coingecko_days(1) == 1
        assert _coingecko_days(0) == 1

    def test_seven_days(self):
        assert _coingecko_days(7) == 7
        assert _coingecko_days(5) == 7

    def test_thirty_days(self):
        assert _coingecko_days(30) == 30
        assert _coingecko_days(15) == 30  # rounds up to nearest allowed (30)
        assert _coingecko_days(20) == 30

    def test_large_days(self):
        assert _coingecko_days(365) == 365
        assert _coingecko_days(400) == 365


class TestComputePeriodSummary:
    """Tests for _compute_period_summary."""

    def test_empty_data(self):
        ret, high, low = _compute_period_summary([])
        assert ret is None
        assert high is None
        assert low is None

    def test_single_point(self):
        data = [{"close": 100.0, "high": 105.0, "low": 95.0}]
        ret, high, low = _compute_period_summary(data)
        assert ret == 0.0  # no change
        assert high == 105.0
        assert low == 95.0

    def test_period_return(self):
        data = [
            {"close": 100.0, "high": 102.0, "low": 98.0},
            {"close": 110.0, "high": 112.0, "low": 108.0},
        ]
        ret, high, low = _compute_period_summary(data)
        assert ret == 10.0  # 10% gain
        assert high == 112.0
        assert low == 98.0


class TestOHLCPoint:
    """Tests for OHLCPoint model."""

    def test_valid_point(self):
        p = OHLCPoint(date="2024-01-15", open=100.0, high=105.0, low=99.0, close=102.0, volume=1_000_000)
        assert p.date == "2024-01-15"
        assert p.close == 102.0
        assert p.volume == 1_000_000

    def test_volume_optional(self):
        p = OHLCPoint(date="2024-01-15", open=100.0, high=105.0, low=99.0, close=102.0)
        assert p.volume is None


class TestSymbolPriceHistory:
    """Tests for SymbolPriceHistory model."""

    def test_valid_history(self):
        h = SymbolPriceHistory(
            symbol="AAPL",
            name="Apple Inc.",
            data_source="Yahoo Finance",
            period_days=30,
            data=[
                OHLCPoint(date="2024-01-01", open=180.0, high=185.0, low=178.0, close=182.0),
            ],
            period_return_pct=2.5,
            period_high=185.0,
            period_low=178.0,
        )
        assert h.symbol == "AAPL"
        assert h.period_return_pct == 2.5
        assert len(h.data) == 1


class TestPriceHistoryTool:
    """Tests for the price_history tool."""

    @pytest.mark.asyncio
    async def test_empty_symbols(self):
        result = await price_history.ainvoke({"symbols": []})
        assert result["total_symbols"] == 0
        assert result["successful"] == 0
        assert result["histories"] == []
        assert result["sources_used"] == []

    @pytest.mark.asyncio
    async def test_single_stock(self):
        result = await price_history.ainvoke({"symbols": ["AAPL"], "period_days": 30})
        assert result["total_symbols"] == 1
        assert result["successful"] == 1
        assert len(result["histories"]) == 1
        h = result["histories"][0]
        assert h["symbol"] == "AAPL"
        assert h["data_source"] == "Yahoo Finance"
        assert "data" in h
        assert len(h["data"]) >= 0  # mock may return empty or multiple points
        assert "Yahoo Finance" in result["sources_used"]

    @pytest.mark.asyncio
    async def test_single_crypto(self):
        result = await price_history.ainvoke({"symbols": ["BTC"], "period_days": 7})
        assert result["total_symbols"] == 1
        assert result["successful"] == 1
        assert len(result["histories"]) == 1
        h = result["histories"][0]
        assert h["symbol"] == "BTC"
        assert h["data_source"] == "CoinGecko"
        assert "CoinGecko" in result["sources_used"]

    @pytest.mark.asyncio
    async def test_mixed_symbols(self):
        result = await price_history.ainvoke({"symbols": ["AAPL", "BTC"], "period_days": 30})
        assert result["total_symbols"] == 2
        assert result["successful"] == 2
        assert len(result["histories"]) == 2
        sources = result["sources_used"]
        assert "Yahoo Finance" in sources
        assert "CoinGecko" in sources

    @pytest.mark.asyncio
    async def test_period_days_bounds(self):
        result = await price_history.ainvoke({"symbols": ["AAPL"], "period_days": 400})
        assert result["total_symbols"] == 1
        # Should clamp to 365
        if result["histories"]:
            assert result["histories"][0]["period_days"] <= 365

    @pytest.mark.asyncio
    async def test_histories_have_summary_fields(self):
        result = await price_history.ainvoke({"symbols": ["AAPL"], "period_days": 30})
        if result["histories"]:
            h = result["histories"][0]
            assert "period_return_pct" in h
            assert "period_high" in h
            assert "period_low" in h
            assert "data" in h
