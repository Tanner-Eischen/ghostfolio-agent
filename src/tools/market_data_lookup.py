"""Market Data Lookup Tool - Fetch current market data for stocks, ETFs, or cryptocurrencies."""

from datetime import datetime
from typing import Any

from langchain_core.tools import tool
from langsmith import traceable
from pydantic import BaseModel, Field

from src.api.coingecko import SYMBOL_TO_ID, CoinGeckoClient
from src.api.yahoo_finance import YahooFinanceClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Input/Output Models
# ============================================================================


class MarketDataLookupInput(BaseModel):
    """Input schema for market_data_lookup tool."""

    symbols: list[str] = Field(
        description="List of ticker symbols to look up (e.g., ['AAPL', 'BTC', 'MSFT'])"
    )
    metrics: list[str] | None = Field(
        default=None,
        description="Optional metrics to include: 'price', 'change_24h', 'market_cap', 'volume'. If None, returns all.",
    )


class MarketDataPoint(BaseModel):
    """Market data for a single symbol."""

    symbol: str = Field(description="Asset symbol (e.g., AAPL, BTC)")
    name: str = Field(description="Full name of the asset")
    price: float = Field(description="Current price")
    change_24h: float | None = Field(default=None, description="24-hour price change (absolute)")
    change_percent: float | None = Field(default=None, description="24-hour price change percentage")
    market_cap: float | None = Field(default=None, description="Market capitalization")
    volume: float | None = Field(default=None, description="24-hour trading volume")
    currency: str = Field(default="USD", description="Price currency")
    data_source: str = Field(description="Data source (Yahoo Finance or CoinGecko)")
    last_updated: str = Field(description="Timestamp of last data update")


class MarketDataLookupResult(BaseModel):
    """Result of market data lookup."""

    data: list[MarketDataPoint] = Field(description="Market data for requested symbols")
    total_symbols: int = Field(description="Total number of symbols requested")
    successful_lookups: int = Field(description="Number of successful lookups")
    data_age_seconds: int = Field(description="Age of the data in seconds")
    sources_used: list[str] = Field(description="Data sources that were used")


# ============================================================================
# Symbol Classification
# ============================================================================

# Known crypto symbols (case-insensitive lookup)
CRYPTO_SYMBOLS = set(SYMBOL_TO_ID.keys())


def is_crypto_symbol(symbol: str) -> bool:
    """Determine if a symbol is a cryptocurrency.

    Args:
        symbol: The ticker symbol to check

    Returns:
        True if the symbol is a known cryptocurrency
    """
    return symbol.upper() in CRYPTO_SYMBOLS


@traceable(name="classify_symbols", run_type="tool")
def classify_symbols(symbols: list[str]) -> tuple[list[str], list[str]]:
    """Classify symbols into crypto and stock/ETF categories.

    Args:
        symbols: List of ticker symbols

    Returns:
        Tuple of (crypto_symbols, stock_symbols)
    """
    crypto = []
    stocks = []

    for symbol in symbols:
        if is_crypto_symbol(symbol):
            crypto.append(symbol.upper())
        else:
            stocks.append(symbol.upper())

    return crypto, stocks


# ============================================================================
# Metrics Filtering
# ============================================================================

VALID_METRICS = {"price", "change_24h", "market_cap", "volume"}


def should_include_metric(requested_metrics: list[str] | None, metric_name: str) -> bool:
    """Determine if a metric should be included based on request.

    Args:
        requested_metrics: List of requested metrics, or None for all
        metric_name: The metric to check

    Returns:
        True if the metric should be included
    """
    if requested_metrics is None or len(requested_metrics) == 0:
        return True
    return metric_name in requested_metrics


def filter_data_point(
    data_point: dict[str, Any],
    metrics: list[str] | None,
) -> dict[str, Any]:
    """Filter a data point based on requested metrics.

    Args:
        data_point: Raw data point from API
        metrics: Requested metrics or None for all

    Returns:
        Filtered data point with only requested fields
    """
    # Always include these base fields
    result = {
        "symbol": data_point.get("symbol"),
        "name": data_point.get("name"),
        "price": data_point.get("price"),
        "currency": data_point.get("currency", "USD"),
        "data_source": data_point.get("data_source"),
        "last_updated": data_point.get("last_updated"),
        # Initialize optional fields to None
        "change_24h": None,
        "change_percent": None,
        "market_cap": None,
        "volume": None,
    }

    # Conditionally include optional metrics
    if should_include_metric(metrics, "change_24h"):
        result["change_24h"] = data_point.get("change_24h")
        result["change_percent"] = data_point.get("change_percent")

    if should_include_metric(metrics, "market_cap"):
        result["market_cap"] = data_point.get("market_cap")

    if should_include_metric(metrics, "volume"):
        result["volume"] = data_point.get("volume")

    return result


# ============================================================================
# Tool Implementation
# ============================================================================


@tool
async def market_data_lookup(
    symbols: list[str],
    metrics: list[str] | None = None,
) -> MarketDataLookupResult:
    """Fetch current market data for stocks, ETFs, or cryptocurrencies.

    Use this tool when the user asks about:
    - Current stock prices
    - Cryptocurrency prices
    - Market cap or volume for assets
    - 24-hour price changes
    - Multiple asset prices at once

    Args:
        symbols: List of ticker symbols (e.g., ['AAPL', 'BTC', 'MSFT'])
            - Stocks/ETFs: Use ticker symbols (AAPL, MSFT, VTI, etc.)
            - Crypto: Use symbols (BTC, ETH, SOL, etc.)
        metrics: Optional list of metrics to include:
            - "price": Current price (always included)
            - "change_24h": 24-hour price change and percentage
            - "market_cap": Market capitalization
            - "volume": 24-hour trading volume
            If None, returns all available metrics.

    Returns:
        MarketDataLookupResult with market data for each symbol
    """
    if not symbols:
        logger.warning("Empty symbols list provided")
        return MarketDataLookupResult(
            data=[],
            total_symbols=0,
            successful_lookups=0,
            data_age_seconds=0,
            sources_used=[],
        )

    # Validate and normalize symbols
    symbols = [s.upper().strip() for s in symbols if s and s.strip()]
    total_symbols = len(symbols)

    if total_symbols == 0:
        return MarketDataLookupResult(
            data=[],
            total_symbols=0,
            successful_lookups=0,
            data_age_seconds=0,
            sources_used=[],
        )

    # Validate metrics if provided
    if metrics:
        metrics = [m.lower().strip() for m in metrics if m and m.strip()]
        invalid_metrics = [m for m in metrics if m not in VALID_METRICS]
        if invalid_metrics:
            logger.warning(f"Ignoring invalid metrics: {invalid_metrics}")
            metrics = [m for m in metrics if m in VALID_METRICS]

    logger.info(f"Looking up market data for {total_symbols} symbols: {symbols}")

    # Classify symbols by type
    crypto_symbols, stock_symbols = classify_symbols(symbols)

    logger.debug(f"Classified: {len(crypto_symbols)} crypto, {len(stock_symbols)} stocks")

    data_points: list[dict[str, Any]] = []
    sources_used: set[str] = set()
    max_data_age = 0

    # Fetch crypto data from CoinGecko
    if crypto_symbols:
        try:
            async with CoinGeckoClient() as client:
                # Convert symbols to coin ids
                coin_ids = [SYMBOL_TO_ID.get(s, s.lower()) for s in crypto_symbols]

                # Batch fetch prices
                price_data = await client.get_price(
                    coin_ids=coin_ids,
                    vs_currency="usd",
                    include_market_cap=should_include_metric(metrics, "market_cap"),
                    include_24hr_vol=should_include_metric(metrics, "volume"),
                    include_24hr_change=should_include_metric(metrics, "change_24h"),
                )

                raw_data = price_data.get("data", {})
                data_age = price_data.get("data_age_seconds", 0)
                max_data_age = max(max_data_age, data_age)

                # Map back to symbols
                for symbol in crypto_symbols:
                    coin_id = SYMBOL_TO_ID.get(symbol, symbol.lower())
                    if coin_id in raw_data:
                        coin_data = raw_data[coin_id]
                        data_points.append({
                            "symbol": symbol,
                            "name": symbol.title(),  # CoinGecko simple price doesn't include name
                            "price": coin_data.get("usd", 0),
                            "change_24h": coin_data.get("usd_24h_change"),
                            "change_percent": coin_data.get("usd_24h_change"),
                            "market_cap": coin_data.get("usd_market_cap"),
                            "volume": coin_data.get("usd_24h_vol"),
                            "currency": "USD",
                            "data_source": "CoinGecko",
                            "last_updated": price_data.get("last_updated", datetime.utcnow().isoformat()),
                        })

                sources_used.add("CoinGecko")
                logger.info(f"Retrieved data for {len([d for d in data_points if d.get('data_source') == 'CoinGecko'])} crypto symbols")

        except Exception as e:
            logger.error(f"CoinGecko lookup failed: {e}")
            # Don't fail the entire request - continue with stocks

    # Fetch stock data from Yahoo Finance
    if stock_symbols:
        try:
            async with YahooFinanceClient() as client:
                quotes = await client.get_quote(stock_symbols)

                for quote in quotes:
                    data_age = quote.get("data_age_seconds", 0)
                    max_data_age = max(max_data_age, data_age)

                    data_points.append({
                        "symbol": quote.get("symbol"),
                        "name": quote.get("name", quote.get("symbol")),
                        "price": quote.get("price", 0),
                        "change_24h": quote.get("change"),
                        "change_percent": quote.get("change_percent"),
                        "market_cap": quote.get("market_cap"),
                        "volume": quote.get("volume"),
                        "currency": quote.get("currency", "USD"),
                        "data_source": "Yahoo Finance",
                        "last_updated": quote.get("last_updated", datetime.utcnow().isoformat()),
                    })

                sources_used.add("Yahoo Finance")
                logger.info(f"Retrieved data for {len([d for d in data_points if d.get('data_source') == 'Yahoo Finance'])} stock symbols")

        except Exception as e:
            logger.error(f"Yahoo Finance lookup failed: {e}")
            # Don't fail the entire request

    # Apply metrics filtering
    filtered_points = [filter_data_point(dp, metrics) for dp in data_points]

    # Convert to MarketDataPoint models
    market_data = []
    for point in filtered_points:
        try:
            market_data.append(MarketDataPoint(**point))
        except Exception as e:
            logger.warning(f"Failed to create MarketDataPoint for {point.get('symbol')}: {e}")

    result = MarketDataLookupResult(
        data=market_data,
        total_symbols=total_symbols,
        successful_lookups=len(market_data),
        data_age_seconds=max_data_age,
        sources_used=sorted(list(sources_used)),
    )

    logger.info(
        f"Market data lookup complete: {len(market_data)}/{total_symbols} symbols, "
        f"sources: {sources_used}"
    )

    return result


# ============================================================================
# Tool Export
# ============================================================================

__all__ = ["market_data_lookup", "MarketDataLookupResult", "MarketDataPoint"]
