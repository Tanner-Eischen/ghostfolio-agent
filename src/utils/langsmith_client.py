"""LangSmith API client for retrieving traces and runs.

Provides functions to retrieve execution traces from LangSmith for the
Observability page UI.

Uses the LangSmith Python SDK Client for API access.
"""

from datetime import datetime
from typing import Any

from langsmith import Client

from src.utils.config import get_settings
from src.utils.logging import get_logger
from src.utils.tracing import is_tracing_enabled, get_langsmith_client

logger = get_logger(__name__)


def get_recent_runs(
    project_name: str | None = None,
    limit: int = 50,
    run_type: str | None = None,
) -> list[dict[str, Any]]:
    """Get recent runs from LangSmith.

    Args:
        project_name: Project name (defaults to configured project)
        limit: Maximum number of runs to return
        run_type: Filter by run type (chain, llm, tool, etc.)

    Returns:
        List of run dictionaries with id, name, status, tokens, duration
    """
    client = get_langsmith_client()
    if not client:
        logger.warning("LangSmith client not configured")
        return []

    settings = get_settings()
    project = project_name or settings.langsmith_project

    try:
        # List runs from LangSmith
        runs = list(client.list_runs(
            project_name=project,
            run_type=run_type,
            limit=limit,
        ))

        # Transform to UI-friendly format
        result = []
        for run in runs:
            # Calculate duration
            duration_ms = 0
            if run.start_time and run.end_time:
                duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)

            # Get token usage from run metadata
            tokens_used = 0
            if run.total_tokens:
                tokens_used = run.total_tokens
            elif run.prompt_tokens and run.completion_tokens:
                tokens_used = run.prompt_tokens + run.completion_tokens

            result.append({
                "id": str(run.id),
                "name": run.name or "unnamed",
                "run_type": run.run_type,
                "timestamp": run.start_time.isoformat() if run.start_time else None,
                "duration_ms": duration_ms,
                "tokens_used": tokens_used,
                "status": "success" if run.status == "completed" else run.status or "unknown",
                "tags": run.tags or [],
                "metadata": run.extra or {},
            })

        return result

    except Exception as e:
        logger.error(f"Failed to get runs from LangSmith: {e}")
        return []


def get_run_details(run_id: str) -> dict[str, Any] | None:
    """Get detailed information about a specific run.

    Args:
        run_id: The run ID to retrieve

    Returns:
        Run details with steps/spans, or None if not found
    """
    client = get_langsmith_client()
    if not client:
        logger.warning("LangSmith client not configured")
        return None

    try:
        # Read the run
        run = client.read_run(run_id)

        # Calculate duration
        duration_ms = 0
        if run.start_time and run.end_time:
            duration_ms = int((run.end_time - run.start_time).total_seconds() * 1000)

        # Get token usage
        tokens_used = 0
        if run.total_tokens:
            tokens_used = run.total_tokens
        elif run.prompt_tokens and run.completion_tokens:
            tokens_used = run.prompt_tokens + run.completion_tokens

        # Get child runs (steps/spans)
        steps = []
        try:
            child_runs = list(client.list_runs(
                reference_example_id=None,  # Not filtering by example
                query=f"parent_run_id = '{run_id}'",
                limit=100,
            ))

            for child in child_runs:
                child_duration = 0
                if child.start_time and child.end_time:
                    child_duration = int((child.end_time - child.start_time).total_seconds() * 1000)

                steps.append({
                    "name": child.name or "unnamed",
                    "run_type": child.run_type,
                    "input": child.inputs or {},
                    "output": child.outputs or {},
                    "duration_ms": child_duration,
                    "status": "success" if child.status == "completed" else child.status or "unknown",
                })
        except Exception as e:
            logger.debug(f"Could not fetch child runs: {e}")

        # Extract tool calls from the run
        tool_calls = []
        if run.run_type == "chain" and steps:
            tool_calls = [
                step["name"] for step in steps
                if step.get("run_type") == "tool"
            ]

        return {
            "id": str(run.id),
            "name": run.name or "unnamed",
            "run_type": run.run_type,
            "timestamp": run.start_time.isoformat() if run.start_time else None,
            "duration_ms": duration_ms,
            "tokens_used": tokens_used,
            "status": "success" if run.status == "completed" else run.status or "unknown",
            "tool_calls": tool_calls,
            "steps": steps,
            "tags": run.tags or [],
            "metadata": run.extra or {},
            "inputs": run.inputs or {},
            "outputs": run.outputs or {},
        }

    except Exception as e:
        logger.error(f"Failed to get run details from LangSmith: {e}")
        return None


def get_observability_summary() -> dict[str, Any]:
    """Get a summary of observability data.

    Returns:
        Summary with total runs, error rate, avg latency, etc.
    """
    runs = get_recent_runs(limit=100)

    if not runs:
        return {
            "total_runs": 0,
            "error_rate": 0.0,
            "avg_latency_ms": 0,
            "total_tokens": 0,
        }

    total = len(runs)
    errors = sum(1 for r in runs if r["status"] != "success")
    total_duration = sum(r["duration_ms"] for r in runs)
    total_tokens = sum(r["tokens_used"] for r in runs)

    return {
        "total_runs": total,
        "error_rate": (errors / total * 100) if total > 0 else 0.0,
        "avg_latency_ms": total_duration // total if total > 0 else 0,
        "total_tokens": total_tokens,
    }


__all__ = [
    "get_recent_runs",
    "get_run_details",
    "get_observability_summary",
]
