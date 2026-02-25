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
from datetime import datetime
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

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100


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

    valid_check_types = ["tool_called", "field_present"]

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

        # Validate criteria
        if not ec.criteria:
            errors.append(f"Eval case {ec.id}: missing 'criteria'")

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

    except Exception as e:
        result.errors.append(str(e))
        result.passed = False
        result.checks["exception"] = False

    return result


async def run_evaluations(
    eval_cases: list[EvalCase],
    verbose: bool = False,
    dry_run: bool = False,
) -> EvalReport:
    """Run all eval cases and generate report.

    Args:
        eval_cases: List of eval cases to run
        verbose: Whether to print detailed output
        dry_run: If True, don't actually run tests (just validate)

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

    # Import agent here to avoid issues if dependencies missing
    try:
        from src.agent import GhostfolioAgent
    except ImportError as e:
        console.print(f"[red]Error importing agent: {e}[/red]")
        console.print("[yellow]Make sure you're running from the project root directory[/yellow]")
        sys.exit(1)

    console.print(f"\n[bold]Initializing Ghostfolio Agent...[/bold]")
    agent = GhostfolioAgent(
        use_verification=True,
        verification_strict_mode=False,
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
        "summary": {
            "total_tests": report.total_tests,
            "passed": report.passed,
            "failed": report.failed,
            "skipped": report.skipped,
            "pass_rate": report.pass_rate,
            "average_confidence": report.average_confidence,
            "average_response_time_ms": report.average_response_time_ms,
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
