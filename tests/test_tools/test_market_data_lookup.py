"""Tests for market_data_lookup tool."""

import pytest

from src.tools.market_data_lookup import (
    MarketDataLookupResult,
    MarketDataPoint,
    classify_symbols,
    filter_data_point,
    is_crypto_symbol,
    market_data_lookup,
    should_include_metric,
)


class TestIsCryptoSymbol:
    """Tests for crypto symbol detection."""

    def test_btc_is_crypto(self):
        """BTC should be detected as crypto."""
        assert is_crypto_symbol("BTC") is True

    def test_eth_is_crypto(self):
        """ETH should be detected as crypto."""
        assert is_crypto_symbol("ETH") is True

    def test_sol_is_crypto(self):
        """SOL should be detected as crypto."""
        assert is_crypto_symbol("SOL") is True

    def test_aapl_is_not_crypto(self):
        """AAPL should not be detected as crypto."""
        assert is_crypto_symbol("AAPL") is False

    def test_case_insensitive(self):
        """Symbol detection should be case-insensitive."""
        assert is_crypto_symbol("btc") is True
        assert is_crypto_symbol("Btc") is True
        assert is_crypto_symbol("BTC") is True

    def test_all_known_crypto_symbols(self):
        """All known crypto symbols should be detected."""
        crypto_symbols = ["BTC", "ETH", "BNB", "XRP", "ADA", "DOGE", "SOL", "DOT",
                         "MATIC", "SHIB", "LTC", "AVAX", "LINK", "ATOM", "UNI"]
        for symbol in crypto_symbols:
            assert is_crypto_symbol(symbol) is True, f"{symbol} should be detected as crypto"


class TestClassifySymbols:
    """Tests for symbol classification."""

    def test_empty_list(self):
        """Empty list should return empty classifications."""
        crypto, stocks = classify_symbols([])
        assert crypto == []
        assert stocks == []

    def test_all_crypto(self):
        """All crypto symbols should be classified correctly."""
        crypto, stocks = classify_symbols(["BTC", "ETH", "SOL"])
        assert crypto == ["BTC", "ETH", "SOL"]
        assert stocks == []

    def test_all_stocks(self):
        """All stock symbols should be classified correctly."""
        crypto, stocks = classify_symbols(["AAPL", "MSFT", "GOOGL"])
        assert crypto == []
        assert stocks == ["AAPL", "MSFT", "GOOGL"]

    def test_mixed_symbols(self):
        """Mixed symbols should be classified correctly."""
        crypto, stocks = classify_symbols(["AAPL", "BTC", "MSFT", "ETH"])
        assert crypto == ["BTC", "ETH"]
        assert stocks == ["AAPL", "MSFT"]

    def test_symbols_are_uppercased(self):
        """Symbols should be normalized to uppercase."""
        crypto, stocks = classify_symbols(["aapl", "btc", "MsFt"])
        assert crypto == ["BTC"]
        assert stocks == ["AAPL", "MSFT"]


class TestShouldIncludeMetric:
    """Tests for metric inclusion logic."""

    def test_include_all_when_none(self):
        """When metrics is None, all metrics should be included."""
        assert should_include_metric(None, "price") is True
        assert should_include_metric(None, "change_24h") is True
        assert should_include_metric(None, "market_cap") is True
        assert should_include_metric(None, "volume") is True

    def test_include_all_when_empty(self):
        """When metrics is empty list, all metrics should be included."""
        assert should_include_metric([], "price") is True
        assert should_include_metric([], "change_24h") is True

    def test_include_requested_metric(self):
        """Requested metrics should be included."""
        metrics = ["price", "market_cap"]
        assert should_include_metric(metrics, "price") is True
        assert should_include_metric(metrics, "market_cap") is True

    def test_exclude_non_requested_metric(self):
        """Non-requested metrics should be excluded."""
        metrics = ["price"]
        assert should_include_metric(metrics, "change_24h") is False
        assert should_include_metric(metrics, "market_cap") is False
        assert should_include_metric(metrics, "volume") is False


class TestFilterDataPoint:
    """Tests for data point filtering."""

    def test_filter_returns_base_fields(self):
        """Filter should always return base fields."""
        data_point = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "price": 185.00,
            "currency": "USD",
            "data_source": "Yahoo Finance",
            "last_updated": "2024-01-01T12:00:00",
            "change_24h": 2.50,
            "change_percent": 1.37,
            "market_cap": 2850000000000,
            "volume": 52340000,
        }

        result = filter_data_point(data_point, None)

        assert result["symbol"] == "AAPL"
        assert result["name"] == "Apple Inc."
        assert result["price"] == 185.00
        assert result["currency"] == "USD"
        assert result["data_source"] == "Yahoo Finance"

    def test_filter_includes_all_when_no_metrics(self):
        """Filter should include all metrics when None."""
        data_point = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "price": 185.00,
            "currency": "USD",
            "data_source": "Yahoo Finance",
            "last_updated": "2024-01-01T12:00:00",
            "change_24h": 2.50,
            "change_percent": 1.37,
            "market_cap": 2850000000000,
            "volume": 52340000,
        }

        result = filter_data_point(data_point, None)

        assert result["change_24h"] == 2.50
        assert result["change_percent"] == 1.37
        assert result["market_cap"] == 2850000000000
        assert result["volume"] == 52340000

    def test_filter_excludes_non_requested(self):
        """Filter should exclude metrics not requested."""
        data_point = {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "price": 185.00,
            "currency": "USD",
            "data_source": "Yahoo Finance",
            "last_updated": "2024-01-01T12:00:00",
            "change_24h": 2.50,
            "change_percent": 1.37,
            "market_cap": 2850000000000,
            "volume": 52340000,
        }

        result = filter_data_point(data_point, ["price", "volume"])

        assert result["change_24h"] is None
        assert result["change_percent"] is None
        assert result["market_cap"] is None
        assert result["volume"] == 52340000


class TestMarketDataPoint:
    """Tests for MarketDataPoint model."""

    def test_valid_data_point(self):
        """Create a valid market data point."""
        point = MarketDataPoint(
            symbol="AAPL",
            name="Apple Inc.",
            price=185.00,
            change_24h=2.50,
            change_percent=1.37,
            market_cap=2850000000000,
            volume=52340000,
            currency="USD",
            data_source="Yahoo Finance",
            last_updated="2024-01-01T12:00:00",
        )
        assert point.symbol == "AAPL"
        assert point.price == 185.00
        assert point.data_source == "Yahoo Finance"

    def test_minimal_data_point(self):
        """Create a minimal data point with only required fields."""
        point = MarketDataPoint(
            symbol="BTC",
            name="Bitcoin",
            price=85000.00,
            data_source="CoinGecko",
            last_updated="2024-01-01T12:00:00",
        )
        assert point.symbol == "BTC"
        assert point.change_24h is None
        assert point.market_cap is None
        assert point.currency == "USD"


class TestMarketDataLookupResult:
    """Tests for MarketDataLookupResult model."""

    def test_valid_result(self):
        """Create a valid result."""
        result = MarketDataLookupResult(
            data=[
                MarketDataPoint(
                    symbol="AAPL",
                    name="Apple Inc.",
                    price=185.00,
                    data_source="Yahoo Finance",
                    last_updated="2024-01-01T12:00:00",
                )
            ],
            total_symbols=1,
            successful_lookups=1,
            data_age_seconds=0,
            sources_used=["Yahoo Finance"],
        )
        assert result.total_symbols == 1
        assert result.successful_lookups == 1
        assert len(result.data) == 1

    def test_empty_result(self):
        """Create an empty result."""
        result = MarketDataLookupResult(
            data=[],
            total_symbols=0,
            successful_lookups=0,
            data_age_seconds=0,
            sources_used=[],
        )
        assert result.total_symbols == 0
        assert result.successful_lookups == 0
        assert result.data == []


class TestMarketDataLookupTool:
    """Tests for the market_data_lookup tool."""

    @pytest.mark.asyncio
    async def test_single_stock_lookup(self):
        """Test looking up a single stock."""
        result = await market_data_lookup.ainvoke({"symbols": ["AAPL"]})

        assert isinstance(result, MarketDataLookupResult)
        assert result.total_symbols == 1
        assert result.successful_lookups == 1
        assert len(result.data) == 1
        assert result.data[0].symbol == "AAPL"
        assert result.data[0].data_source == "Yahoo Finance"
        assert "Yahoo Finance" in result.sources_used

    @pytest.mark.asyncio
    async def test_single_crypto_lookup(self):
        """Test looking up a single cryptocurrency."""
        result = await market_data_lookup.ainvoke({"symbols": ["BTC"]})

        assert isinstance(result, MarketDataLookupResult)
        assert result.total_symbols == 1
        assert result.successful_lookups == 1
        assert len(result.data) == 1
        assert result.data[0].symbol == "BTC"
        assert result.data[0].data_source == "CoinGecko"
        assert "CoinGecko" in result.sources_used

    @pytest.mark.asyncio
    async def test_multiple_stocks_lookup(self):
        """Test looking up multiple stocks."""
        result = await market_data_lookup.ainvoke({"symbols": ["AAPL", "MSFT", "GOOGL"]})

        assert result.total_symbols == 3
        assert result.successful_lookups == 3
        assert len(result.data) == 3
        symbols = [d.symbol for d in result.data]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "GOOGL" in symbols

    @pytest.mark.asyncio
    async def test_multiple_crypto_lookup(self):
        """Test looking up multiple cryptocurrencies."""
        result = await market_data_lookup.ainvoke({"symbols": ["BTC", "ETH", "SOL"]})

        assert result.total_symbols == 3
        assert result.successful_lookups == 3
        assert len(result.data) == 3
        symbols = [d.symbol for d in result.data]
        assert "BTC" in symbols
        assert "ETH" in symbols
        assert "SOL" in symbols

    @pytest.mark.asyncio
    async def test_mixed_symbols_lookup(self):
        """Test looking up mixed stocks and crypto."""
        result = await market_data_lookup.ainvoke({"symbols": ["AAPL", "BTC", "MSFT"]})

        assert result.total_symbols == 3
        assert result.successful_lookups == 3
        assert len(result.data) == 3

        # Check that both sources were used
        assert "Yahoo Finance" in result.sources_used
        assert "CoinGecko" in result.sources_used

        # Verify data sources for each symbol
        aapl_data = next(d for d in result.data if d.symbol == "AAPL")
        btc_data = next(d for d in result.data if d.symbol == "BTC")
        msft_data = next(d for d in result.data if d.symbol == "MSFT")

        assert aapl_data.data_source == "Yahoo Finance"
        assert btc_data.data_source == "CoinGecko"
        assert msft_data.data_source == "Yahoo Finance"

    @pytest.mark.asyncio
    async def test_empty_symbols_list(self):
        """Test with empty symbols list."""
        result = await market_data_lookup.ainvoke({"symbols": []})

        assert result.total_symbols == 0
        assert result.successful_lookups == 0
        assert result.data == []

    @pytest.mark.asyncio
    async def test_metrics_filter_price_only(self):
        """Test filtering to only price metric."""
        result = await market_data_lookup.ainvoke({
            "symbols": ["AAPL"],
            "metrics": ["price"],
        })

        assert result.successful_lookups == 1
        data = result.data[0]
        assert data.price is not None
        assert data.change_24h is None
        assert data.change_percent is None
        assert data.market_cap is None
        assert data.volume is None

    @pytest.mark.asyncio
    async def test_metrics_filter_multiple(self):
        """Test filtering to multiple metrics."""
        result = await market_data_lookup.ainvoke({
            "symbols": ["AAPL"],
            "metrics": ["price", "change_24h", "market_cap"],
        })

        data = result.data[0]
        assert data.price is not None
        assert data.change_24h is not None
        assert data.change_percent is not None
        assert data.market_cap is not None
        assert data.volume is None  # Not requested

    @pytest.mark.asyncio
    async def test_all_metrics_returned_by_default(self):
        """Test that all metrics are returned when not filtering."""
        result = await market_data_lookup.ainvoke({"symbols": ["AAPL"]})

        data = result.data[0]
        assert data.price is not None
        assert data.change_24h is not None
        assert data.change_percent is not None
        assert data.market_cap is not None
        assert data.volume is not None

    @pytest.mark.asyncio
    async def test_data_age_seconds_included(self):
        """Test that data_age_seconds is included in result."""
        result = await market_data_lookup.ainvoke({"symbols": ["AAPL"]})

        assert result.data_age_seconds >= 0

    @pytest.mark.asyncio
    async def test_case_insensitive_symbols(self):
        """Test that symbols are handled case-insensitively."""
        result = await market_data_lookup.ainvoke({"symbols": ["aapl", "btc", "MsFt"]})

        symbols = [d.symbol for d in result.data]
        assert "AAPL" in symbols
        assert "BTC" in symbols
        assert "MSFT" in symbols

    @pytest.mark.asyncio
    async def test_unknown_stock_symbol_still_returns_data(self):
        """Test that unknown stock symbols still return data (mock fallback)."""
        result = await market_data_lookup.ainvoke({"symbols": ["UNKNOWN"]})

        # Mock data should return generic data for unknown symbols
        assert result.successful_lookups == 1
        assert result.data[0].symbol == "UNKNOWN"
        assert result.data[0].price == 100.00  # Mock fallback price

    @pytest.mark.asyncio
    async def test_sources_used_sorted(self):
        """Test that sources_used list is sorted."""
        result = await market_data_lookup.ainvoke({"symbols": ["BTC", "AAPL"]})

        # Should be sorted alphabetically
        assert result.sources_used == sorted(result.sources_used)

    @pytest.mark.asyncio
    async def test_whitespace_in_symbols_handled(self):
        """Test that whitespace in symbols is handled."""
        result = await market_data_lookup.ainvoke({"symbols": [" AAPL ", "  BTC"]})

        symbols = [d.symbol for d in result.data]
        assert "AAPL" in symbols
        assert "BTC" in symbols

    @pytest.mark.asyncio
    async def test_empty_strings_filtered(self):
        """Test that empty strings in symbols are filtered out."""
        result = await market_data_lookup.ainvoke({"symbols": ["AAPL", "", "MSFT"]})

        # Empty strings are filtered, leaving 2 valid symbols
        assert result.total_symbols == 2
        symbols = [d.symbol for d in result.data]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
