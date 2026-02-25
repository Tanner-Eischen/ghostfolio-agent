"""Evals package - MVP evaluation framework for Ghostfolio Agent.

Runs eval cases against the agent and generates reports on tool calls
and response structure.

MVP schema:
    - id, category, input, description
    - expected_tool_calls, expected_output_fields
    - criteria[] with check_type: tool_called | field_present

Usage:
    python evals/run_evals.py                    # Run MVP evals
    python evals/run_evals.py --category mvp     # Run MVP category
    python evals/run_evals.py --validate         # Validate format
    python evals/run_evals.py -v --save          # Verbose + save report
"""

from evals.run_evals import (
    EvalCase,
    EvalCriterion,
    EvalReport,
    EvalResult,
    load_eval_cases,
    print_report,
    run_evaluations,
    save_report,
    validate_eval_cases,
)

__all__ = [
    "EvalCase",
    "EvalCriterion",
    "EvalReport",
    "EvalResult",
    "load_eval_cases",
    "print_report",
    "run_evaluations",
    "save_report",
    "validate_eval_cases",
]
