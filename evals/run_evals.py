#!/usr/bin/env python3
"""Evaluation runner for Ghostfolio Agent.

Runs MVP eval cases against the Ghostfolio Agent and generates reports
on tool calls and response structure.

Usage:
    python evals/run_evals.py                    # Run MVP evals
    python evals/run_evals.py --category mvp     # Run MVP category
    python evals/run_evals.py --validate         # Validate eval case format
    python evals/run_evals.py --save            # Save report to JSON

MVP schema: id, category, input, description, expected_tool_calls,
expected_output_fields, criteria[] with check_type: tool_called | field_present.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure LangSmith tracing before any other imports
from src.utils.tracing import configure_langsmith
_tracing_enabled = configure_langsmith()

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

console = Console(force_terminal=True)

# Windows-compatible checkmarks
CHECK_MARK = "[green]PASS[/green]"
X_MARK = "[red]FAIL[/red]"

# Eval case directory
EVAL_CASES_DIR = Path(__file__).parent / "eval_cases"


@dataclass
class EvalConfig:
    """Configuration for eval execution, mirrors VerificationConfig."""
    fact_checking: bool = True
    hallucination_detection: bool = True
    confidence_scoring: bool = True
    hitl_enabled: bool = False
    confidence_threshold: int = 70
    strict_mode: bool = False  # If True, fail tests on low confidence


@dataclass
class EvalCriterion:
    """Atomic check criterion for an eval case."""
    id: str
    description: str
    check_type: str  # tool_called, tool_not_called, field_present, field_matches, response_time_ms, confidence_min
    expected: Any
    passed: bool = False
    actual: Any = None
    error: str = ""


@dataclass
class EvalCase:
    """Represents a single evaluation case (new atomic format)."""
    id: str
    category: str
    input: str
    description: str = ""
    expected_tool_calls: list[str] = field(default_factory=list)
    expected_output_fields: list[str] = field(default_factory=list)
    criteria: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        """Create EvalCase from dictionary."""
        return cls(
            id=data.get("id", "unknown"),
            category=data.get("category", "unknown"),
            input=data.get("input", ""),
            description=data.get("description", ""),
            expected_tool_calls=data.get("expected_tool_calls", []),
            expected_output_fields=data.get("expected_output_fields", []),
            criteria=data.get("criteria", []),
        )


@dataclass
class EvalResult:
    """Result of running a single eval case."""
    eval_case: EvalCase
    passed: bool = False
    response: str = ""
    tool_calls: list[str] = field(default_factory=list)
    confidence: float = 0.0
    response_time_ms: float = 0.0
    errors: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)
    criteria_results: list[EvalCriterion] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    feedback_adjusted: bool = False
    feedback_info: dict[str, Any] = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        return self.eval_case.id

    @property
    def case_category(self) -> str:
        return self.eval_case.category


@dataclass
class EvalReport:
    """Aggregated evaluation report."""
    timestamp: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    results: list[EvalResult] = field(default_factory=list)
    category_summary: dict[str, dict[str, int]] = field(default_factory=dict)
    average_confidence: float = 0.0
    average_response_time_ms: float = 0.0
    total_duration_s: float = 0.0
    config_used: dict[str, Any] = field(default_factory=dict)
    feedback_stats: dict[str, Any] = field(default_factory=dict)
    # Performance: single-tool vs multi-step latency (G4 targets: <5s single, <15s multi)
    avg_response_time_ms_single_tool: float = 0.0
    avg_response_time_ms_multi_step: float = 0.0
    # Tool success: cases where every tool call had a corresponding output
    tool_success_count: int = 0
    tool_total_count: int = 0

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100

    @property
    def tool_success_rate(self) -> float:
        """Tool success rate (0-100)."""
        if self.tool_total_count == 0:
            return 100.0
        return (self.tool_success_count / self.tool_total_count) * 100


def evaluate_criterion(
    criterion: EvalCriterion,
    response: dict[str, Any],
    tool_calls: list[str],
    response_time_ms: float,
    confidence: float,
) -> EvalCriterion:
    """Evaluate a single atomic criterion.

    Args:
        criterion: The criterion to evaluate
        response: Full response dict from agent
        tool_calls: List of tool names that were called
        response_time_ms: Response time in milliseconds
        confidence: Confidence score (0-100)

    Returns:
        Updated criterion with pass/fail status
    """
    criterion = EvalCriterion(
        id=criterion.id,
        description=criterion.description,
        check_type=criterion.check_type,
        expected=criterion.expected,
    )

    try:
        if criterion.check_type == "tool_called":
            criterion.actual = tool_calls
            criterion.passed = criterion.expected in tool_calls

        elif criterion.check_type == "field_present":
            # MVP strict: pass only if expected exists as top-level key in tool_outputs
            tool_outputs = response.get("tool_outputs", [])
            if tool_outputs and isinstance(tool_outputs, list):
                field_name = criterion.expected.split(".")[0]  # top-level only
                found = any(
                    isinstance(obj, dict) and field_name in obj
                    for obj in tool_outputs
                )
                criterion.actual = found
                criterion.passed = found
            else:
                # Fallback: check response dict (e.g. message, tool_calls)
                field_path = criterion.expected.split(".")
                current = response
                found = True
                for part in field_path:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    elif part == "length" and isinstance(current, (list, dict)):
                        current = len(current)
                        break
                    else:
                        found = False
                        break
                criterion.actual = found
                criterion.passed = found

        elif criterion.check_type == "tool_not_called":
            criterion.actual = tool_calls
            criterion.passed = criterion.expected not in tool_calls

        elif criterion.check_type == "field_matches":
            # Expected: {"field": "total_value", "value": 150000, "tolerance": 0.01}
            tool_outputs = response.get("tool_outputs", [])
            expected = criterion.expected if isinstance(criterion.expected, dict) else {}
            field_name = expected.get("field", "")
            expected_value = expected.get("value")
            tolerance = expected.get("tolerance", 0.0)

            # Search for field in tool_outputs
            actual_value = None
            found = False
            for obj in tool_outputs:
                if isinstance(obj, dict) and field_name in obj:
                    actual_value = obj[field_name]
                    found = True
                    break

            if not found:
                criterion.actual = None
                criterion.passed = False
                criterion.error = f"Field '{field_name}' not found in tool_outputs"
            else:
                criterion.actual = actual_value
                if tolerance > 0 and isinstance(actual_value, (int, float)) and isinstance(expected_value, (int, float)):
                    # Tolerance-based comparison
                    lower = expected_value * (1 - tolerance)
                    upper = expected_value * (1 + tolerance)
                    criterion.passed = lower <= actual_value <= upper
                else:
                    # Exact match
                    criterion.passed = actual_value == expected_value

        elif criterion.check_type == "value_in_range":
            # Expected: {"field": "confidence", "min": 0, "max": 100}
            tool_outputs = response.get("tool_outputs", [])
            expected = criterion.expected if isinstance(criterion.expected, dict) else {}
            field_name = expected.get("field", "")
            min_val = expected.get("min")
            max_val = expected.get("max")

            # For confidence, use top-level response field
            if field_name == "confidence":
                actual_value = confidence
            else:
                # Search for field in tool_outputs
                actual_value = None
                for obj in tool_outputs:
                    if isinstance(obj, dict) and field_name in obj:
                        actual_value = obj[field_name]
                        break

            criterion.actual = actual_value
            if actual_value is None:
                criterion.passed = False
                criterion.error = f"Field '{field_name}' not found"
            else:
                try:
                    actual_num = float(actual_value)
                    in_range = True
                    if min_val is not None:
                        in_range = in_range and actual_num >= min_val
                    if max_val is not None:
                        in_range = in_range and actual_num <= max_val
                    criterion.passed = in_range
                except (ValueError, TypeError):
                    criterion.passed = False
                    criterion.error = f"Could not convert '{actual_value}' to number"

        elif criterion.check_type == "timestamp_fresh":
            # Expected: {"field": "timestamp", "max_age_seconds": 86400}
            tool_outputs = response.get("tool_outputs", [])
            expected = criterion.expected if isinstance(criterion.expected, dict) else {}
            field_name = expected.get("field", "timestamp")
            max_age_seconds = expected.get("max_age_seconds", 86400)

            # Search for timestamp field
            timestamp_value = None
            for obj in tool_outputs:
                if isinstance(obj, dict) and field_name in obj:
                    timestamp_value = obj[field_name]
                    break

            criterion.actual = timestamp_value
            if timestamp_value is None:
                criterion.passed = False
                criterion.error = f"Timestamp field '{field_name}' not found"
            else:
                try:
                    # Parse timestamp (ISO format expected)
                    if isinstance(timestamp_value, str):
                        ts = datetime.fromisoformat(timestamp_value.replace("Z", "+00:00"))
                    elif isinstance(timestamp_value, (int, float)):
                        ts = datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
                    else:
                        ts = timestamp_value

                    now = datetime.now(timezone.utc)
                    age_seconds = (now - ts).total_seconds()
                    criterion.passed = age_seconds <= max_age_seconds
                    criterion.actual = f"{age_seconds:.0f}s old (max: {max_age_seconds}s)"
                except (ValueError, TypeError) as e:
                    criterion.passed = False
                    criterion.error = f"Could not parse timestamp: {e}"

        elif criterion.check_type == "not_contains":
            # Expected: string or list of strings that should NOT appear in response
            forbidden = criterion.expected
            if isinstance(forbidden, str):
                forbidden = [forbidden]

            response_text = response.get("message", "")
            found_forbidden = []
            for term in forbidden:
                if term.lower() in response_text.lower():
                    found_forbidden.append(term)

            criterion.actual = found_forbidden if found_forbidden else "none"
            criterion.passed = len(found_forbidden) == 0

        elif criterion.check_type == "verification_gate":
            # Expected: {"gate_name": "syntactic", "output_type": "portfolio"}
            # Runs a single verification gate check on tool_outputs
            from evals.verification_evaluator import VerificationEvaluator

            expected = criterion.expected if isinstance(criterion.expected, dict) else {}
            gate_name = expected.get("gate_name", "syntactic")
            output_type = expected.get("output_type", "general")

            tool_outputs = response.get("tool_outputs", [])
            if not tool_outputs:
                criterion.actual = "No tool outputs to verify"
                criterion.passed = False
            else:
                # Run verification on first tool output
                evaluator = VerificationEvaluator()
                output_to_check = tool_outputs[0] if isinstance(tool_outputs[0], dict) else {}

                try:
                    verdict = evaluator.evaluate_output(output_to_check, output_type)
                    gate_result = verdict.gates.get(gate_name)

                    if gate_result:
                        criterion.passed = gate_result.passed
                        criterion.actual = f"Gate '{gate_name}': {gate_result.evidence}"
                        if not gate_result.passed:
                            criterion.error = "; ".join(gate_result.remediation)
                    else:
                        criterion.passed = False
                        criterion.error = f"Gate '{gate_name}' not found in verdict"
                        criterion.actual = f"Available gates: {list(verdict.gates.keys())}"
                except Exception as e:
                    criterion.passed = False
                    criterion.error = f"Verification failed: {e}"
                    criterion.actual = "Evaluator error"

        elif criterion.check_type == "response_time_ms":
            # Expected: max allowed ms (e.g. 5000). Pass if response_time_ms <= expected.
            max_ms = criterion.expected
            if isinstance(max_ms, dict):
                max_ms = max_ms.get("max_ms", max_ms.get("max", 0))
            criterion.actual = response_time_ms
            criterion.passed = response_time_ms <= float(max_ms)

        elif criterion.check_type == "confidence_min":
            # Expected: minimum confidence (0-100). Pass if confidence >= expected.
            min_conf = criterion.expected
            if isinstance(min_conf, dict):
                min_conf = min_conf.get("min_confidence", min_conf.get("min", 0))
            criterion.actual = confidence
            criterion.passed = confidence >= float(min_conf)

        elif criterion.check_type == "verification_verdict":
            # Expected: {"output_type": "portfolio", "min_confidence": 0.5}
            # Runs full 4-gate verification and checks overall verdict
            from evals.verification_evaluator import VerificationEvaluator

            expected = criterion.expected if isinstance(criterion.expected, dict) else {}
            output_type = expected.get("output_type", "general")
            min_confidence = expected.get("min_confidence", 0.5)
            require_all_gates = expected.get("require_all_gates", False)

            tool_outputs = response.get("tool_outputs", [])
            if not tool_outputs:
                criterion.actual = "No tool outputs to verify"
                criterion.passed = False
            else:
                evaluator = VerificationEvaluator()
                output_to_check = tool_outputs[0] if isinstance(tool_outputs[0], dict) else {}

                try:
                    verdict = evaluator.evaluate_output(output_to_check, output_type)

                    passed_gates = verdict.passed_count
                    total_gates = len(verdict.gates)

                    if require_all_gates:
                        criterion.passed = verdict.all_passed
                    else:
                        criterion.passed = verdict.confidence_score >= min_confidence

                    criterion.actual = (
                        f"Confidence: {verdict.confidence_score:.2f}, "
                        f"Gates: {passed_gates}/{total_gates}, "
                        f"Action: {verdict.recommended_action}"
                    )

                    if not criterion.passed:
                        criterion.error = "; ".join(verdict.remediation_steps[:3])  # Top 3 remediation steps
                except Exception as e:
                    criterion.passed = False
                    criterion.error = f"Verification failed: {e}"
                    criterion.actual = "Evaluator error"

        else:
            criterion.actual = f"Unknown check_type: {criterion.check_type}"
            criterion.passed = False

    except Exception as e:
        criterion.error = str(e)
        criterion.passed = False

    return criterion


def load_eval_cases(category: str | None = None) -> list[EvalCase]:
    """Load eval cases from JSON files in eval_cases/ directory.

    Args:
        category: Optional category filter. If None, loads all categories.

    Returns:
        List of EvalCase objects.
    """
    eval_cases = []

    # MVP-only eval cases
    category_files = {"mvp": "mvp_evals.json"}

    if category:
        if category not in category_files:
            console.print(f"[red]Unknown category: {category}[/red]")
            console.print(f"Valid categories: {list(category_files.keys())}")
            sys.exit(1)
        files_to_load = {category: category_files[category]}
    else:
        files_to_load = category_files

    for cat, filename in files_to_load.items():
        filepath = EVAL_CASES_DIR / filename
        if not filepath.exists():
            console.print(f"[yellow]Warning: Eval file not found: {filepath}[/yellow]")
            continue

        try:
            with open(filepath, "r") as f:
                data = json.load(f)

            for case_data in data:
                eval_cases.append(EvalCase.from_dict(case_data))

        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing {filepath}: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error loading {filepath}: {e}[/red]")

    return eval_cases


def validate_eval_cases(eval_cases: list[EvalCase]) -> list[str]:
    """Validate eval case format and completeness.

    Args:
        eval_cases: List of eval cases to validate.

    Returns:
        List of validation error messages.
    """
    errors = []
    seen_ids = set()

    valid_check_types = [
        "tool_called",
        "tool_not_called",
        "field_present",
        "field_matches",
        "value_in_range",
        "timestamp_fresh",
        "not_contains",
        "verification_gate",
        "verification_verdict",
        "response_time_ms",
        "confidence_min",
    ]

    for ec in eval_cases:
        # Check for duplicate IDs
        if ec.id in seen_ids:
            errors.append(f"Duplicate eval ID: {ec.id}")
        seen_ids.add(ec.id)

        # Check required fields
        if not ec.id:
            errors.append("Eval case missing 'id' field")
        if not ec.category:
            errors.append(f"Eval case {ec.id}: missing 'category' field")
        if ec.input is None:
            errors.append(f"Eval case {ec.id}: missing 'input' field")

        # Validate criteria (empty criteria is valid for edge cases with no expected tools)
        for i, crit in enumerate(ec.criteria):
            if "id" not in crit:
                errors.append(f"Eval case {ec.id}: criterion {i} missing 'id'")
            if "check_type" not in crit:
                errors.append(f"Eval case {ec.id}: criterion {crit.get('id', i)} missing 'check_type'")
            elif crit["check_type"] not in valid_check_types:
                errors.append(f"Eval case {ec.id}: criterion {crit.get('id', i)} has invalid check_type '{crit['check_type']}'")
            if "expected" not in crit:
                errors.append(f"Eval case {ec.id}: criterion {crit.get('id', i)} missing 'expected'")

    return errors


async def run_single_eval(agent, eval_case: EvalCase) -> EvalResult:
    """Run a single eval case against the agent (new atomic format).

    Args:
        agent: GhostfolioAgent instance
        eval_case: Eval case to run

    Returns:
        EvalResult with test outcome
    """
    result = EvalResult(eval_case=eval_case, passed=False)

    try:
        start_time = time.time()

        # Run the agent
        response = await agent.chat_with_context(
            eval_case.input,
            session_id=f"eval-{eval_case.id}",
        )

        result.response_time_ms = (time.time() - start_time) * 1000
        result.response = response.get("message", "")
        result.tool_calls = [tc.get("tool", "") for tc in response.get("tool_calls", [])]
        result.confidence = response.get("confidence", 0.0)
        result.details = response

        # Evaluate each criterion atomically
        all_passed = True
        for crit_data in eval_case.criteria:
            criterion = EvalCriterion(
                id=crit_data.get("id", "unknown"),
                description=crit_data.get("description", ""),
                check_type=crit_data.get("check_type", ""),
                expected=crit_data.get("expected"),
            )

            evaluated = evaluate_criterion(
                criterion,
                response,
                result.tool_calls,
                result.response_time_ms,
                result.confidence,
            )

            result.criteria_results.append(evaluated)
            result.checks[evaluated.id] = evaluated.passed

            if not evaluated.passed:
                all_passed = False

        result.passed = all_passed

        # Check for linked feedback and apply adjustment
        try:
            from evals.feedback_eval_bridge import adjust_score_by_feedback, get_feedback_for_eval_case

            feedback_entries = get_feedback_for_eval_case(eval_case.id)
            if feedback_entries:
                # Calculate base score from criteria
                passed_criteria = sum(1 for c in result.criteria_results if c.passed)
                total_criteria = len(result.criteria_results)
                base_score = passed_criteria / total_criteria if total_criteria > 0 else 0.0

                # Adjust score by feedback
                adjusted = adjust_score_by_feedback(
                    base_score,
                    eval_case_id=eval_case.id,
                    session_id=f"eval-{eval_case.id}",
                )

                result.feedback_adjusted = adjusted.feedback_count > 0
                result.feedback_info = adjusted.to_dict()

                # If feedback is strongly negative, mark as failed
                if adjusted.negative_count > adjusted.positive_count:
                    result.passed = False
                    result.errors.append(f"Negative feedback outweighs positive ({adjusted.negative_count} vs {adjusted.positive_count})")

        except Exception as e:
            # Don't fail the eval if feedback adjustment fails
            result.feedback_info = {"error": str(e)}

    except Exception as e:
        result.errors.append(str(e))
        result.passed = False
        result.checks["exception"] = False

    return result


async def run_evaluations(
    eval_cases: list[EvalCase],
    verbose: bool = False,
    dry_run: bool = False,
    config: EvalConfig | None = None,
) -> EvalReport:
    """Run all eval cases and generate report.

    Args:
        eval_cases: List of eval cases to run
        verbose: Whether to print detailed output
        dry_run: If True, don't actually run tests (just validate)
        config: Optional eval configuration. If None, loads from verification config store.

    Returns:
        EvalReport with results
    """
    report = EvalReport(
        timestamp=datetime.now().isoformat(),
        total_tests=len(eval_cases),
    )

    if dry_run:
        console.print("[yellow]Dry run mode - not executing tests[/yellow]")
        return report

    # Load config from store if not provided
    if config is None:
        try:
            from src.utils.config_store import get_verification_config_store
            store = get_verification_config_store()
            stored = store.get_all()
            config = EvalConfig(
                fact_checking=stored.get("fact_checking", True),
                hallucination_detection=stored.get("hallucination_detection", True),
                confidence_scoring=stored.get("confidence_scoring", True),
                hitl_enabled=stored.get("hitl_enabled", False),
                confidence_threshold=stored.get("confidence_threshold", 70),
                strict_mode=False,
            )
            console.print("[dim]Loaded config from verification config store[/dim]")
        except Exception as e:
            console.print(f"[yellow]Could not load config store: {e}. Using defaults.[/yellow]")
            config = EvalConfig()

    # Store config in report metadata
    report.config_used = {
        "fact_checking": config.fact_checking,
        "hallucination_detection": config.hallucination_detection,
        "confidence_scoring": config.confidence_scoring,
        "hitl_enabled": config.hitl_enabled,
        "confidence_threshold": config.confidence_threshold,
        "strict_mode": config.strict_mode,
    }

    # Import agent here to avoid issues if dependencies missing
    try:
        from src.agent import GhostfolioAgent
    except ImportError as e:
        console.print(f"[red]Error importing agent: {e}[/red]")
        console.print("[yellow]Make sure you're running from the project root directory[/yellow]")
        sys.exit(1)

    console.print(f"\n[bold]Initializing Ghostfolio Agent...[/bold]")
    console.print(f"[dim]Config: fact_checking={config.fact_checking}, hitl={config.hitl_enabled}, threshold={config.confidence_threshold}%[/dim]")

    agent = GhostfolioAgent(
        use_verification=config.fact_checking,
        verification_strict_mode=config.strict_mode,
    )

    start_time = time.time()

    total_items = len(eval_cases)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Running {total_items} evals...",
            total=total_items,
        )

        # Run new eval cases
        for eval_case in eval_cases:
            progress.update(task, description=f"[cyan]Running {eval_case.id}...")

            result = await run_single_eval(agent, eval_case)
            report.results.append(result)

            if result.passed:
                report.passed += 1
            else:
                report.failed += 1

            # Update category summary
            cat = eval_case.category
            if cat not in report.category_summary:
                report.category_summary[cat] = {"passed": 0, "failed": 0, "total": 0}
            report.category_summary[cat]["total"] += 1
            if result.passed:
                report.category_summary[cat]["passed"] += 1
            else:
                report.category_summary[cat]["failed"] += 1

            if verbose:
                status = CHECK_MARK if result.passed else X_MARK
                console.print(f"  {status} {eval_case.id}: {result.response_time_ms:.0f}ms, {result.confidence:.0f}% confidence")

            progress.advance(task)

    report.total_duration_s = time.time() - start_time

    # Calculate averages
    if report.results:
        report.average_response_time_ms = sum(r.response_time_ms for r in report.results) / len(report.results)
        report.average_confidence = sum(r.confidence for r in report.results) / len(report.results)

        # Latency breakdown: single-tool vs multi-step (G4: <5s single, <15s multi)
        single_tool_times = [
            r.response_time_ms for r in report.results
            if len(r.eval_case.expected_tool_calls) == 1
        ]
        multi_step_times = [
            r.response_time_ms for r in report.results
            if len(r.eval_case.expected_tool_calls) >= 2
        ]
        if single_tool_times:
            report.avg_response_time_ms_single_tool = sum(single_tool_times) / len(single_tool_times)
        if multi_step_times:
            report.avg_response_time_ms_multi_step = sum(multi_step_times) / len(multi_step_times)

        # Tool success rate: each result contributes 1 if all tool calls have outputs, else 0
        for r in report.results:
            tool_calls = r.details.get("tool_calls", [])
            tool_outputs = r.details.get("tool_outputs", [])
            if not tool_calls:
                report.tool_total_count += 1
                report.tool_success_count += 1  # no tools = success
            else:
                report.tool_total_count += 1
                if not r.errors and len(tool_outputs) >= len(tool_calls):
                    report.tool_success_count += 1

    return report


def print_report(report: EvalReport, verbose: bool = False):
    """Print evaluation report to console.

    Args:
        report: Evaluation report to print
        verbose: Whether to print detailed results
    """
    console.print()

    # Summary panel
    summary_text = (
        f"Total Tests: {report.total_tests}\n"
        f"[green]Passed: {report.passed}[/green]\n"
        f"[red]Failed: {report.failed}[/red]\n"
        f"Pass Rate: {report.pass_rate:.1f}%\n\n"
        f"Avg Response Time: {report.average_response_time_ms:.0f}ms\n"
        f"Avg single-tool: {report.avg_response_time_ms_single_tool:.0f}ms | "
        f"Avg multi-step: {report.avg_response_time_ms_multi_step:.0f}ms\n"
        f"Tool Success: {report.tool_success_count}/{report.tool_total_count} ({report.tool_success_rate:.0f}%)\n"
        f"Avg Confidence: {report.average_confidence:.1f}%\n"
        f"Total Duration: {report.total_duration_s:.1f}s"
    )

    console.print(Panel(
        summary_text,
        title="[bold]Evaluation Report[/bold]",
        subtitle=f"Timestamp: {report.timestamp}",
    ))

    # Category breakdown table
    if report.category_summary:
        console.print("\n[bold]Results by Category:[/bold]")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Category")
        table.add_column("Passed", justify="right")
        table.add_column("Failed", justify="right")
        table.add_column("Total", justify="right")
        table.add_column("Pass Rate", justify="right")

        for cat, stats in sorted(report.category_summary.items()):
            pass_rate = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            rate_color = "green" if pass_rate >= 80 else "yellow" if pass_rate >= 50 else "red"
            table.add_row(
                cat,
                str(stats["passed"]),
                str(stats["failed"]),
                str(stats["total"]),
                f"[{rate_color}]{pass_rate:.0f}%[/{rate_color}]",
            )

        console.print(table)

    # Failed tests details
    if verbose or report.failed > 0:
        failed_results = [r for r in report.results if not r.passed]
        if failed_results:
            console.print(f"\n[bold red]Failed Tests ({len(failed_results)}):[/bold red]")

            for result in failed_results[:10]:  # Show first 10 failures
                console.print(f"\n[yellow]{result.case_id}[/yellow]: {result.eval_case.input[:50]}...")

                if result.errors:
                    console.print(f"  [red]Errors: {', '.join(result.errors)}[/red]")

                # Show failed criteria
                if result.criteria_results:
                    failed_criteria = [c for c in result.criteria_results if not c.passed]
                    for fc in failed_criteria:
                        console.print(f"  [red]Criterion {fc.id}: {fc.description}[/red]")
                        if fc.error:
                            console.print(f"    [red]Error: {fc.error}[/red]")
                        elif fc.actual is not None:
                            console.print(f"    [red]Expected: {fc.expected}, Got: {fc.actual}[/red]")

                failed_checks = [k for k, v in result.checks.items() if not v]
                if failed_checks:
                    console.print(f"  [red]Failed checks: {', '.join(failed_checks)}[/red]")

                if result.response:
                    console.print(f"  Response: {result.response[:100]}...")

            if len(failed_results) > 10:
                console.print(f"\n[yellow]... and {len(failed_results) - 10} more failures[/yellow]")

    # Detailed results if verbose
    if verbose:
        console.print("\n[bold]Detailed Results:[/bold]")
        for result in report.results:
            status = CHECK_MARK if result.passed else X_MARK
            checks_str = ", ".join(
                f"[green]{k}[/green]" if v else f"[red]{k}[/red]"
                for k, v in result.checks.items()
            )
            console.print(
                f"{status} {result.case_id}: "
                f"{result.response_time_ms:.0f}ms, "
                f"{result.confidence:.0f}% confidence | "
                f"Checks: {checks_str}"
            )


def save_report(report: EvalReport, output_path: str | None = None):
    """Save report to JSON file.

    Args:
        report: Evaluation report to save
        output_path: Optional output path. Defaults to evals/results/
    """
    if output_path is None:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = results_dir / f"eval_report_{timestamp}.json"

    # Convert report to dict
    report_dict = {
        "timestamp": report.timestamp,
        "config_used": report.config_used,
        "feedback_stats": report.feedback_stats,
        "summary": {
            "total_tests": report.total_tests,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
            "pass_rate": report.pass_rate,
            "average_confidence": report.average_confidence,
            "average_response_time_ms": report.average_response_time_ms,
            "avg_response_time_ms_single_tool": report.avg_response_time_ms_single_tool,
            "avg_response_time_ms_multi_step": report.avg_response_time_ms_multi_step,
            "tool_success_count": report.tool_success_count,
            "tool_total_count": report.tool_total_count,
            "tool_success_rate": report.tool_success_rate,
            "total_duration_s": report.total_duration_s,
        },
        "category_summary": report.category_summary,
        "results": [
            {
                "id": r.case_id,
                "category": r.case_category,
                "input": r.eval_case.input,
                "passed": r.passed,
                "response": r.response,
                "tool_calls": r.tool_calls,
                # Full tool call payloads (name + args) from agent response
                "tool_call_details": r.details.get("tool_calls", []),
                # Structured/raw tool outputs used by atomic field_present checks
                "tool_outputs": r.details.get("tool_outputs", []),
                "confidence": r.confidence,
                "response_time_ms": r.response_time_ms,
                "checks": r.checks,
                "criteria_results": [
                    {
                        "id": c.id,
                        "description": c.description,
                        "check_type": c.check_type,
                        "expected": c.expected,
                        "actual": c.actual,
                        "passed": c.passed,
                        "error": c.error,
                    }
                    for c in r.criteria_results
                ],
                "errors": r.errors,
                "feedback_adjusted": r.feedback_adjusted,
                "feedback_info": r.feedback_info,
            }
            for r in report.results
        ],
    }

    with open(output_path, "w") as f:
        json.dump(report_dict, f, indent=2)

    console.print(f"\n[green]Report saved to: {output_path}[/green]")


def main():
    """Main entry point for eval runner."""
    parser = argparse.ArgumentParser(
        description="Run evaluation tests for Ghostfolio Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python evals/run_evals.py                     # Run MVP evals
    python evals/run_evals.py --category mvp      # Run MVP category
    python evals/run_evals.py --validate          # Validate eval case format
    python evals/run_evals.py -v                  # Verbose output
    python evals/run_evals.py --save              # Save report to file
        """,
    )

    parser.add_argument(
        "--category", "-c",
        type=str,
        choices=["mvp"],
        help="Run tests for specific category only",
    )
    parser.add_argument(
        "--validate", "-V",
        action="store_true",
        help="Validate test case format without running",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed output",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be run without executing",
    )
    parser.add_argument(
        "--save", "-s",
        action="store_true",
        help="Save report to JSON file",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file path for report",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all test cases without running",
    )
    args = parser.parse_args()

    eval_cases = load_eval_cases(args.category)

    if len(eval_cases) == 0:
        console.print("[red]No eval cases found![/red]")
        sys.exit(1)

    console.print(f"\n[bold]Loaded {len(eval_cases)} eval cases[/bold]")

    if args.list:
        for ec in eval_cases:
            console.print(f"  [{ec.category}] {ec.id}: {ec.input[:50]}... ({len(ec.criteria)} criteria)")
        return

    if args.validate:
        errors = validate_eval_cases(eval_cases)
        if errors:
            console.print(f"\n[red]Found {len(errors)} validation errors:[/red]")
            for error in errors:
                console.print(f"  {X_MARK} {error}")
            sys.exit(1)
        console.print("\n[green]All eval cases are valid![/green]")
        return

    report = asyncio.run(run_evaluations(
        eval_cases,
        verbose=args.verbose,
        dry_run=args.dry_run,
    ))

    # Print report
    print_report(report, verbose=args.verbose)

    # Save if requested
    if args.save or args.output:
        save_report(report, args.output)

    # Exit with appropriate code
    if report.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
