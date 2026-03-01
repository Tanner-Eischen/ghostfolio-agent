"""Price History Tool - Historical OHLC data for stocks (Yahoo) and crypto (CoinGecko)."""

from datetime import datetime
from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.api.coingecko import SYMBOL_TO_ID, CoinGeckoClient
from src.api.yahoo_finance import YahooFinanceClient
from src.tools.market_data_lookup import classify_symbols
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Input/Output Models
# ============================================================================


class OHLCPoint(BaseModel):
    """Single OHLC data point."""

    date: str = Field(description="Date (YYYY-MM-DD)")
    open: float = Field(description="Open price")
    high: float = Field(description="High price")
    low: float = Field(description="Low price")
    close: float = Field(description="Close price")
    volume: float | None = Field(default=None, description="Volume (stocks only)")


class SymbolPriceHistory(BaseModel):
    """Price history for one symbol."""

    symbol: str = Field(description="Asset symbol")
    name: str = Field(description="Display name")
    data_source: str = Field(description="Yahoo Finance or CoinGecko")
    period_days: int = Field(description="Number of days of history")
    data: list[OHLCPoint] = Field(description="OHLC data points")
    period_return_pct: float | None = Field(
        default=None,
        description="Period return (first close to last close) as percentage",
    )
    period_high: float | None = Field(default=None, description="Highest price in period")
    period_low: float | None = Field(default=None, description="Lowest price in period")


class PriceHistoryResult(BaseModel):
    """Result of price history lookup."""

    histories: list[SymbolPriceHistory] = Field(description="Per-symbol price history")
    total_symbols: int = Field(description="Number of symbols requested")
    successful: int = Field(description="Number of successful lookups")
    sources_used: list[str] = Field(description="Data sources used")


# CoinGecko OHLC only supports specific day values
COINGECKO_OHLC_DAYS = (1, 7, 14, 30, 90, 180, 365)


def _coingecko_days(days: int) -> int:
    """Map requested days to CoinGecko allowed value."""
    if days <= 1:
        return 1
    for d in COINGECKO_OHLC_DAYS:
        if days <= d:
            return d
    return 365


def _compute_period_summary(data: list[dict[str, Any]]) -> tuple[float | None, float | None, float | None]:
    """Compute period return %, period high, period low from OHLC data."""
    if not data:
        return None, None, None
    closes = [p.get("close") for p in data if p.get("close") is not None]
    highs = [p.get("high") for p in data if p.get("high") is not None]
    lows = [p.get("low") for p in data if p.get("low") is not None]
    if not closes:
        return None, None, None
    first_close = float(closes[0])
    last_close = float(closes[-1])
    period_return = ((last_close - first_close) / first_close * 100) if first_close else None
    period_high = max(float(h) for h in highs) if highs else None
    period_low = min(float(l) for l in lows) if lows else None
    return period_return, period_high, period_low


@tool
async def price_history(
    symbols: list[str],
    period_days: int = 30,
) -> dict[str, Any]:
    """Fetch historical price (OHLC) data for stocks and/or cryptocurrencies.

    Use this tool when the user asks about:
    - How an asset performed over a time period
    - Historical prices, charts, or price movement
    - Comparing performance of multiple assets over time
    - Period return (e.g. "How did AAPL do over the last 30 days?")

    Args:
        symbols: List of ticker symbols (e.g. ['AAPL', 'BTC', 'MSFT']).
            Stocks/ETFs: use ticker symbols (AAPL, MSFT, VTI).
            Crypto: use symbols (BTC, ETH, SOL).
        period_days: Number of days of history (default 30). For crypto, CoinGecko
            uses nearest of 1, 7, 14, 30, 90, 180, 365.

    Returns:
        PriceHistoryResult with per-symbol OHLC series and optional period return/high/low.
    """
    if not symbols:
        logger.warning("Empty symbols list for price_history")
        return PriceHistoryResult(
            histories=[],
            total_symbols=0,
            successful=0,
            sources_used=[],
        ).model_dump(mode="json")

    symbols = [s.upper().strip() for s in symbols if s and s.strip()]
    period_days = max(1, min(365, period_days))
    total_symbols = len(symbols)

    crypto_symbols, stock_symbols = classify_symbols(symbols)
    histories: list[SymbolPriceHistory] = []
    sources_used: set[str] = set()

    # Crypto: CoinGecko OHLC
    for symbol in crypto_symbols:
        try:
            coin_id = SYMBOL_TO_ID.get(symbol, symbol.lower())
            cg_days = _coingecko_days(period_days)
            async with CoinGeckoClient() as client:
                ohlc_list = await client.get_ohlc(coin_id, vs_currency="usd", days=cg_days)
            points = [
                OHLCPoint(
                    date=p.get("date", "")[:10],
                    open=float(p.get("open", 0)),
                    high=float(p.get("high", 0)),
                    low=float(p.get("low", 0)),
                    close=float(p.get("close", 0)),
                    volume=None,
                )
                for p in ohlc_list
            ]
            period_return, period_high, period_low = _compute_period_summary(
                [{"close": p.close, "high": p.high, "low": p.low} for p in points]
            )
            histories.append(
                SymbolPriceHistory(
                    symbol=symbol,
                    name=symbol.title(),
                    data_source="CoinGecko",
                    period_days=cg_days,
                    data=points,
                    period_return_pct=period_return,
                    period_high=period_high,
                    period_low=period_low,
                )
            )
            sources_used.add("CoinGecko")
        except Exception as e:
            logger.warning(f"Price history failed for {symbol}: {e}")

    # Stocks: Yahoo Finance historical
    for symbol in stock_symbols:
        try:
            async with YahooFinanceClient() as client:
                raw = await client.get_historical(symbol, days=period_days)
            data_list = raw.get("data", [])
            points = [
                OHLCPoint(
                    date=p.get("date", ""),
                    open=float(p.get("open", 0)),
                    high=float(p.get("high", 0)),
                    low=float(p.get("low", 0)),
                    close=float(p.get("close", 0)),
                    volume=float(p["volume"]) if p.get("volume") is not None else None,
                )
                for p in data_list
            ]
            period_return, period_high, period_low = _compute_period_summary(data_list)
            histories.append(
                SymbolPriceHistory(
                    symbol=symbol,
                    name=raw.get("name", symbol),
                    data_source="Yahoo Finance",
                    period_days=period_days,
                    data=points,
                    period_return_pct=period_return,
                    period_high=period_high,
                    period_low=period_low,
                )
            )
            sources_used.add("Yahoo Finance")
        except Exception as e:
            logger.warning(f"Price history failed for {symbol}: {e}")

    result = PriceHistoryResult(
        histories=histories,
        total_symbols=total_symbols,
        successful=len(histories),
        sources_used=sorted(sources_used),
    )
    logger.info(f"Price history: {len(histories)}/{total_symbols} symbols, sources: {sources_used}")
    return result.model_dump(mode="json")


__all__ = ["price_history", "PriceHistoryResult", "SymbolPriceHistory", "OHLCPoint"]
