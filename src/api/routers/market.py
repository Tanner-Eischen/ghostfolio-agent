"""Market data endpoints for Ghostfolio Agent API.

Market data lookup for symbols.
"""

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/market/{symbol}", tags=["Market"])
async def get_market_data(symbol: str) -> dict[str, Any]:
    """Get current market data for a symbol.

    Args:
        symbol: Stock ticker or crypto symbol

    Returns:
        Current price and market data
    """
    try:
        from src.tools import market_data_lookup

        result = await market_data_lookup.ainvoke({
            "symbols": [symbol.upper()],
        })

        # Handle Pydantic model result
        if hasattr(result, "model_dump"):
            data = result.model_dump()
            # Return first result if available
            if data.get("data") and len(data["data"]) > 0:
                return data["data"][0]
            return data

        # Handle string result
        if isinstance(result, str):
            try:
                data = json.loads(result)
                if data.get("results"):
                    return data["results"][0]
                return data
            except json.JSONDecodeError:
                return {"raw": result}

        return result

    except Exception as e:
        logger.error(f"Market data error for {symbol}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Market data error: {str(e)}",
        )
