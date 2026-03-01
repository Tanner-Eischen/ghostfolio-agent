"""Token usage and cost tracking for LLM API calls.

Tracks token usage across all API calls and calculates costs based
on model-specific pricing.

Pricing (as of 2024):
- GPT-4o: $2.50/1M input tokens, $10.00/1M output tokens
- GPT-4o-mini: $0.15/1M input, $0.60/1M output
- GPT-4-turbo: $10.00/1M input, $30.00/1M output
"""

import json
import os
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Usage data directory - use environment variable or default to /tmp in production
def _get_data_dir() -> Path:
    """Get data directory, creating it if possible."""
    # Check for environment variable first (for production)
    data_dir_env = os.environ.get("DATA_DIR", os.environ.get("RAILWAY_DATA_DIR"))
    if data_dir_env:
        data_dir = Path(data_dir_env)
    else:
        # Default to ./data relative to project root
        data_dir = Path(__file__).parent.parent.parent / "data"

    # Try to create the directory, fall back to /tmp if permission denied
    try:
        data_dir.mkdir(exist_ok=True, parents=True)
        return data_dir
    except PermissionError:
        # In production containers, fall back to /tmp
        fallback = Path("/tmp/ghostfolio-agent-data")
        fallback.mkdir(exist_ok=True, parents=True)
        logger.warning(f"Could not create {data_dir}, using fallback: {fallback}")
        return fallback

DATA_DIR = _get_data_dir()
USAGE_LOG_FILE = DATA_DIR / "usage_log.json"


# Model pricing (USD per 1M tokens)
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "claude-3-opus": {"input": 15.00, "output": 75.00},
    "claude-3-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def _load_usage_log() -> list[dict[str, Any]]:
    """Load usage log from file."""
    if not USAGE_LOG_FILE.exists():
        return []

    try:
        with open(USAGE_LOG_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Could not load usage log: {e}")
        return []


def _save_usage_log(log: list[dict[str, Any]]) -> None:
    """Save usage log to file."""
    with open(USAGE_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4o-mini",
) -> float:
    """Calculate cost for a token usage.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name (e.g., "gpt-4o-mini")

    Returns:
        Cost in USD
    """
    # Normalize model name (convert underscores to hyphens for consistent matching)
    model_key = model.lower().replace("_", "-")
    if model_key not in MODEL_PRICING:
        # Default to gpt-4o-mini pricing for unknown models
        model_key = "gpt-4o-mini"

    pricing = MODEL_PRICING[model_key]
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def log_usage(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4o-mini",
    session_id: str | None = None,
    query: str | None = None,
    metadata: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> float:
    """Log an API usage event.

    Args:
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        model: Model name
        session_id: Optional session ID
        query: Optional query text (truncated)
        metadata: Optional additional metadata
        run_id: Optional LangSmith run ID to link this usage to a trace

    Returns:
        Calculated cost in USD
    """
    model_str = model if isinstance(model, str) else str(model)
    cost = calculate_cost(input_tokens, output_tokens, model_str)

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "model": model_str,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(cost, 6),
        "session_id": session_id,
        "query": query[:100] if query else None,  # Truncate query
        "metadata": metadata or {},
        "run_id": run_id,
    }

    log = _load_usage_log()
    log.append(entry)
    _save_usage_log(log)

    logger.debug(f"Usage logged: {input_tokens}+{output_tokens} tokens, ${cost:.4f}")
    return cost


def get_cost_by_run_id(run_id: str) -> float | None:
    """Get recorded cost for a LangSmith run ID, if any.

    Args:
        run_id: LangSmith run ID (trace id)

    Returns:
        Cost in USD if found, None otherwise
    """
    log = _load_usage_log()
    for entry in reversed(log):  # Most recent first
        if entry.get("run_id") == run_id:
            return entry.get("cost_usd")
    return None


def get_usage_stats() -> dict[str, Any]:
    """Get aggregated usage statistics.

    Returns:
        Stats dict with total_cost, total_tokens, requests_count, etc.
    """
    log = _load_usage_log()

    if not log:
        return {
            "total_cost": 0.0,
            "total_tokens": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "requests_count": 0,
            "avg_cost_per_request": 0.0,
            "avg_tokens_per_request": 0.0,
            "by_model": {},
        }

    total_cost = sum(entry["cost_usd"] for entry in log)
    total_tokens = sum(entry["total_tokens"] for entry in log)
    total_input = sum(entry["input_tokens"] for entry in log)
    total_output = sum(entry["output_tokens"] for entry in log)
    requests_count = len(log)

    # Aggregate by model
    by_model: dict[str, dict[str, Any]] = {}
    for entry in log:
        model = entry["model"]
        if model not in by_model:
            by_model[model] = {
                "requests": 0,
                "tokens": 0,
                "cost": 0.0,
            }
        by_model[model]["requests"] += 1
        by_model[model]["tokens"] += entry["total_tokens"]
        by_model[model]["cost"] += entry["cost_usd"]

    return {
        "total_cost": round(total_cost, 4),
        "total_tokens": total_tokens,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "requests_count": requests_count,
        "avg_cost_per_request": round(total_cost / requests_count, 6) if requests_count > 0 else 0.0,
        "avg_tokens_per_request": round(total_tokens / requests_count, 1) if requests_count > 0 else 0.0,
        "by_model": by_model,
    }


def get_cost_projections(queries_per_day: int = 100) -> dict[str, Any]:
    """Get cost projections based on historical data.

    Args:
        queries_per_day: Expected queries per day

    Returns:
        Projections dict with daily, monthly, annual costs
    """
    stats = get_usage_stats()

    # Use actual average if we have data, otherwise use estimate
    if stats["requests_count"] > 0:
        avg_cost_per_query = stats["avg_cost_per_request"]
        avg_tokens_per_query = stats["avg_tokens_per_request"]
    else:
        # Default estimates for gpt-4o-mini
        avg_cost_per_query = 0.001  # ~$0.001 per query
        avg_tokens_per_query = 500

    daily_cost = queries_per_day * avg_cost_per_query
    monthly_cost = daily_cost * 30
    annual_cost = daily_cost * 365

    # Estimate token breakdown
    input_ratio = 0.6  # Typically more input tokens
    output_ratio = 0.4

    return {
        "daily_cost": round(daily_cost, 2),
        "monthly_cost": round(monthly_cost, 2),
        "projected_annual": round(annual_cost, 2),
        "cost_breakdown": {
            "input_tokens": int(input_ratio * 100),
            "output_tokens": int(output_ratio * 100),
        },
        "assumptions": {
            "queries_per_day": queries_per_day,
            "avg_cost_per_query": round(avg_cost_per_query, 6),
            "avg_tokens_per_query": int(avg_tokens_per_query),
        },
    }


def reset_usage_log() -> None:
    """Reset the usage log (use with caution)."""
    _save_usage_log([])
    logger.info("Usage log reset")


def seed_demo_usage(
    entries_per_model: int = 12,
    days_back: int = 3,
) -> int:
    """Append synthetic usage entries for all models to populate observability data.

    Each model gets entries_per_model log entries with plausible token counts
    and timestamps spread over the last days_back days. Does not call any LLM.

    Args:
        entries_per_model: Number of fake requests to add per model.
        days_back: Spread timestamps over this many days into the past.

    Returns:
        Total number of entries appended.
    """
    now = datetime.now(timezone.utc)
    log = _load_usage_log()
    total = 0
    for model_id in MODEL_PRICING:
        for i in range(entries_per_model):
            # Vary tokens: input 200-700, output 80-350
            input_tok = random.randint(200, 700)
            output_tok = random.randint(80, 350)
            cost = calculate_cost(input_tok, output_tok, model_id)
            # Spread over last days_back days
            delta = timedelta(
                days=random.randint(0, days_back),
                seconds=random.randint(0, 86400),
            )
            ts = (now - delta).isoformat().replace("+00:00", "Z")
            entry = {
                "timestamp": ts,
                "model": model_id,
                "input_tokens": input_tok,
                "output_tokens": output_tok,
                "total_tokens": input_tok + output_tok,
                "cost_usd": round(cost, 6),
                "session_id": f"demo-{model_id}-{i}",
                "query": None,
                "metadata": {"seed": True},
                "run_id": None,
            }
            log.append(entry)
            total += 1
    _save_usage_log(log)
    logger.info("Seeded %d demo usage entries across %d models", total, len(MODEL_PRICING))
    return total


__all__ = [
    "log_usage",
    "get_usage_stats",
    "get_cost_projections",
    "get_cost_by_run_id",
    "calculate_cost",
    "reset_usage_log",
    "seed_demo_usage",
    "MODEL_PRICING",
]
