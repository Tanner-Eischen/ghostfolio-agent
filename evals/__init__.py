"""Evals package - Evaluation framework for Ghostfolio Agent.

This module provides tools for running evaluation tests against the agent:

1. **Test Cases** - JSON-based test cases in categories:
   - happy_path: Standard portfolio queries
   - edge_case: Boundary conditions and edge cases
   - adversarial: Prompt injection and harmful requests
   - multi_step: Complex multi-tool analysis

2. **Eval Runner** - Comprehensive test execution:
   - Loads and validates test cases
   - Runs tests against the agent
   - Checks tool selection, response content, confidence, timing
   - Generates detailed reports

3. **Report Generation** - Multiple output formats:
   - Console output with rich formatting
   - JSON reports for CI/CD integration
   - Per-category breakdowns

Usage:
    ```bash
    # Run all evaluations
    python evals/run_evals.py

    # Run specific category
    python evals/run_evals.py --category happy_path

    # Validate test case format
    python evals/run_evals.py --validate

    # Verbose output with saved report
    python evals/run_evals.py -v --save
    ```

Example test case format:
    ```json
    {
        "id": "HP-001",
        "category": "happy_path",
        "input": "What's my portfolio worth?",
        "expected_tools": ["portfolio_analysis"],
        "expected_output_contains": ["value", "portfolio"],
        "pass_criteria": {
            "tool_selection_correct": true,
            "response_time_ms_max": 15000,
            "contains_expected_phrases": true,
            "no_errors": true,
            "confidence_min": 70
        }
    }
    ```
"""

from evals.run_evals import (
    EvalReport,
    EvalResult,
    TestCase,
    load_test_cases,
    run_evaluations,
    run_single_test,
    validate_test_cases,
)

__all__ = [
    "TestCase",
    "EvalResult",
    "EvalReport",
    "load_test_cases",
    "validate_test_cases",
    "run_single_test",
    "run_evaluations",
]
