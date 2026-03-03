"""Evaluation endpoints for Ghostfolio Agent API.

Evaluation case management and execution.
"""

from fastapi import APIRouter, HTTPException

from src.api.models import (
    EvalCaseResponse,
    EvalResultsResponse,
    EvalSummaryResponse,
    EvalResultResponse,
    EvalRunRequest,
)
from src.utils.logging import get_logger

# Import eval runner API wrapper
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
from evals.runner_api import (
    list_eval_cases as get_real_eval_cases,
    get_latest_results,
    format_results_for_api,
    run_evals_async,
)

router = APIRouter()
logger = get_logger(__name__)


# Need to define TraceDetailResponse for evals
class TraceDetailResponse(dict):
    """Trace detail response for eval results."""
    pass


@router.get("/evals/cases", response_model=list[EvalCaseResponse], tags=["Evals"])
async def list_eval_cases() -> list[EvalCaseResponse]:
    """List available evaluation cases.

    Returns all evaluation cases that can be run.
    """
    cases = get_real_eval_cases()
    return [
        EvalCaseResponse(
            id=case.get("id", ""),
            name=case.get("name", case["id"]),
            description=case.get("description", ""),
            category=case.get("category", "unknown"),
        )
        for case in cases
    ]


@router.post("/evals/run", tags=["Evals"])
async def run_evals_endpoint(request: EvalRunRequest | None = None) -> dict[str, str]:
    """Run all evaluations.

    Triggers evaluation run for all test cases.
    This runs asynchronously and returns a run_id.

    Optionally accepts a config object to override verification settings for this run:
    - fact_checking: bool
    - hallucination_detection: bool
    - confidence_scoring: bool
    - hitl_enabled: bool
    - confidence_threshold: int (0-100)
    - strict_mode: bool
    """
    try:
        config = request.config if request else None
        if config:
            logger.info(f"Running evals with custom config: {config}")
        run_id = await run_evals_async(config)
        logger.info(f"Evaluation run triggered: {run_id}")
        return {"run_id": run_id, "status": "started"}
    except Exception as e:
        logger.error(f"Failed to run evals: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run evaluations: {str(e)}")


@router.get("/evals/results", response_model=EvalResultsResponse, tags=["Evals"])
async def get_eval_results() -> EvalResultsResponse:
    """Get evaluation results.

    Returns latest evaluation results and summary from the eval framework.
    """
    raw_results = get_latest_results()
    formatted = format_results_for_api(raw_results)

    summary = formatted["summary"]
    return EvalResultsResponse(
        summary=EvalSummaryResponse(
            total_cases=summary["total_cases"],
            passed=summary["passed"],
            failed=summary["failed"],
            pass_rate=summary["pass_rate"],
            avg_latency_ms=summary["avg_latency_ms"],
            hallucination_rate=summary["hallucination_rate"],
        ),
        results=[
            EvalResultResponse(
                case_id=r["case_id"],
                passed=r["passed"],
                score=r["score"],
                duration_ms=r["duration_ms"],
                error=r.get("error"),
            )
            for r in formatted["results"]
        ],
    )
