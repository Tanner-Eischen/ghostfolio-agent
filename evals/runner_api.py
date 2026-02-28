"""API-friendly wrapper for the evals runner.

Provides simplified functions for the REST API to interact with
the evals framework without dealing with async complexity.

Functions:
- list_eval_cases(): Get all eval cases
- run_evals_async(): Start an eval run (returns run_id)
- get_latest_results(): Get the most recent eval results
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Path to eval cases
EVAL_CASES_DIR = Path(__file__).parent / "eval_cases"
EVAL_RESULTS_DIR = Path(__file__).parent / "results"

# Ensure results directory exists
EVAL_RESULTS_DIR.mkdir(exist_ok=True)


def list_eval_cases() -> list[dict[str, Any]]:
    """List all available eval cases.

    Returns:
        List of eval case dictionaries with id, name, description, category
    """
    cases = []

    # Load MVP evals
    mvp_path = EVAL_CASES_DIR / "mvp_evals.json"
    if mvp_path.exists():
        try:
            with open(mvp_path, "r") as f:
                data = json.load(f)
            for case in data:
                cases.append({
                    "id": case.get("id", "unknown"),
                    "name": case.get("id", "unknown"),  # Use ID as name
                    "description": case.get("description", ""),
                    "category": case.get("category", "unknown"),
                    "input": case.get("input", ""),
                    "criteria_count": len(case.get("criteria", [])),
                })
        except Exception as e:
            logger.error(f"Failed to load MVP evals: {e}")

    return cases


def get_eval_case(case_id: str) -> dict[str, Any] | None:
    """Get a specific eval case by ID.

    Args:
        case_id: The eval case ID

    Returns:
        Eval case dictionary or None if not found
    """
    cases = list_eval_cases()
    for case in cases:
        if case["id"] == case_id:
            return case
    return None


def get_latest_results() -> dict[str, Any] | None:
    """Get the most recent eval results.

    Returns:
        Latest eval results or None if no results exist
    """
    # Find the most recent results file
    results_files = sorted(
        EVAL_RESULTS_DIR.glob("eval_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not results_files:
        return None

    try:
        with open(results_files[0], "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load eval results: {e}")
        return None


def format_results_for_api(results: dict[str, Any]) -> dict[str, Any]:
    """Format eval results for the API response.

    Args:
        results: Raw results from the eval runner

    Returns:
        Formatted results matching the API response model with full details
    """
    if not results:
        return {
            "summary": {
                "total_cases": 0,
                "passed": 0,
                "failed": 0,
                "pass_rate": 0.0,
                "avg_latency_ms": 0,
                "hallucination_rate": 0.0,
            },
            "results": [],
        }

    summary = results.get("summary", {})
    raw_results = results.get("results", [])

    # Format individual results with full detail
    formatted_results = []
    for r in raw_results:
        # Format criteria results with full details
        criteria_results = []
        for c in r.get("criteria_results", []):
            criteria_results.append({
                "id": c.get("id", "unknown"),
                "description": c.get("description", ""),
                "check_type": c.get("check_type", ""),
                "expected": c.get("expected"),
                "actual": c.get("actual"),
                "passed": c.get("passed", False),
                "error": c.get("error", ""),
            })

        formatted_results.append({
            "case_id": r.get("id", "unknown"),
            "category": r.get("category", "unknown"),
            "passed": r.get("passed", False),
            "score": 1.0 if r.get("passed", False) else 0.0,
            "duration_ms": int(r.get("response_time_ms", 0)),
            "error": None if r.get("passed", False) else ", ".join(r.get("errors", [])) or "Test failed",
            # Full details for expandable UI
            "input": r.get("input", ""),
            "response": r.get("response", ""),
            "tool_calls": r.get("tool_calls", []),
            "tool_call_details": r.get("tool_call_details", []),
            "tool_outputs": r.get("tool_outputs", []),
            "confidence": r.get("confidence", 0.0),
            "criteria_results": criteria_results,
        })

    return {
        "summary": {
            "total_cases": summary.get("total_tests", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "pass_rate": summary.get("pass_rate", 0.0),
            "avg_latency_ms": int(summary.get("average_response_time_ms", 0)),
            "hallucination_rate": 0.0,  # Not tracked in current implementation
        },
        "results": formatted_results,
    }


async def run_evals_async(config: dict[str, Any] | None = None) -> str:
    """Run all evals asynchronously.

    This imports and runs the eval runner, saving results to a file.

    Args:
        config: Optional eval configuration dict with keys:
            - fact_checking: bool
            - hallucination_detection: bool
            - confidence_scoring: bool
            - hitl_enabled: bool
            - confidence_threshold: int
            - strict_mode: bool

    Returns:
        The run ID (timestamp-based)
    """
    # Import here to avoid circular imports
    from evals.run_evals import load_eval_cases, run_evaluations, save_report, EvalConfig

    # Generate run ID
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Load cases
    eval_cases = load_eval_cases()

    if not eval_cases:
        logger.warning("No eval cases found")
        return run_id

    # Convert config dict to EvalConfig if provided
    eval_config = None
    if config:
        eval_config = EvalConfig(
            fact_checking=config.get("fact_checking", True),
            hallucination_detection=config.get("hallucination_detection", True),
            confidence_scoring=config.get("confidence_scoring", True),
            hitl_enabled=config.get("hitl_enabled", False),
            confidence_threshold=config.get("confidence_threshold", 70),
            strict_mode=config.get("strict_mode", False),
        )
        logger.info(f"Using provided config: {config}")
    else:
        logger.info("No config provided, will load from config store")

    # Run evaluations
    logger.info(f"Starting eval run {run_id} with {len(eval_cases)} cases")
    report = await run_evaluations(eval_cases, verbose=False, config=eval_config)

    # Save results
    output_path = EVAL_RESULTS_DIR / f"eval_report_{run_id}.json"
    save_report(report, str(output_path))

    logger.info(f"Eval run {run_id} complete: {report.passed}/{report.total_tests} passed")
    return run_id


__all__ = [
    "list_eval_cases",
    "get_eval_case",
    "get_latest_results",
    "format_results_for_api",
    "run_evals_async",
]
