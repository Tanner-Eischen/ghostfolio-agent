"""Trace endpoints for Ghostfolio Agent API.

LangSmith trace retrieval and management.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from src.api.models import TraceResponse, TraceDetailResponse
from src.utils.langsmith_client import get_recent_runs, get_run_details
from src.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/traces", response_model=list[TraceResponse], tags=["Traces"])
async def list_traces(
    limit: int = 20,
    session_id: str | None = None,
) -> list[TraceResponse]:
    """Get recent LangSmith traces.

    Args:
        limit: Maximum number of traces to return
        session_id: Filter by session ID

    Returns:
        List of recent traces
    """
    runs = get_recent_runs(limit=limit)

    traces = []
    for run in runs:
        # Calculate cost if available
        total_tokens = 0
        total_cost = None
        if hasattr(run, "total_tokens") and run.total_tokens:
            total_tokens = run.total_tokens
        if hasattr(run, "total_cost") and run.total_cost:
            total_cost = run.total_cost

        traces.append(TraceResponse(
            id=str(run.id) if hasattr(run, "id") else "",
            name=run.name or "",
            start_time=run.start_time.isoformat() if hasattr(run, "start_time") and run.start_time else "",
            end_time=run.end_time.isoformat() if hasattr(run, "end_time") and run.end_time else None,
            status=run.status or "unknown",
            inputs=run.inputs or {},
            outputs=run.outputs or {},
            metadata=run.extra or {},
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
        ))

    return traces


@router.get("/traces/{trace_id}", response_model=TraceDetailResponse, tags=["Traces"])
async def get_trace(trace_id: str) -> TraceDetailResponse:
    """Get detailed trace information.

    Args:
        trace_id: Trace ID to retrieve

    Returns:
        Detailed trace with child runs and tool calls
    """
    run = get_run_details(trace_id)

    if not run:
        raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")

    # Extract tool calls from the run
    tool_calls: list[dict[str, Any]] = []
    child_runs: list[dict[str, Any]] = []

    if hasattr(run, "child_runs") and run.child_runs:
        for child in run.child_runs:
            child_runs.append({
                "id": str(child.id) if hasattr(child, "id") else "",
                "name": child.name or "",
                "start_time": child.start_time.isoformat() if hasattr(child, "start_time") and child.start_time else "",
                "end_time": child.end_time.isoformat() if hasattr(child, "end_time") and child.end_time else None,
                "status": child.status or "unknown",
            })

    return TraceDetailResponse(
        id=str(run.id) if hasattr(run, "id") else trace_id,
        name=run.name or "",
        start_time=run.start_time.isoformat() if hasattr(run, "start_time") and run.start_time else "",
        end_time=run.end_time.isoformat() if hasattr(run, "end_time") and run.end_time else None,
        status=run.status or "unknown",
        inputs=run.inputs or {},
        outputs=run.outputs or {},
        metadata=run.extra or {},
        total_tokens=run.total_tokens if hasattr(run, "total_tokens") else 0,
        total_cost_usd=run.total_cost if hasattr(run, "total_cost") else None,
        child_runs=child_runs,
        tool_calls=tool_calls,
    )
