"""Tests for the evaluation runner.

Tests the MVP eval runner:
- Eval case loading and validation
- Atomic criteria evaluation (tool_called, field_present)
- Report generation
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys_path = Path(__file__).parent.parent.parent
import sys

sys.path.insert(0, str(sys_path))

from evals.run_evals import (
    EvalCase,
    EvalCriterion,
    EvalReport,
    EvalResult,
    evaluate_criterion,
    load_eval_cases,
    run_single_eval,
    validate_eval_cases,
)


class TestEvalCase:
    """Tests for EvalCase dataclass."""

    def test_from_dict_complete(self):
        """Test creating EvalCase from complete dictionary."""
        data = {
            "id": "MVP-001",
            "category": "mvp",
            "input": "What's my portfolio worth?",
            "description": "Portfolio value query",
            "expected_tool_calls": ["portfolio_analysis"],
            "expected_output_fields": ["total_value"],
            "criteria": [
                {"id": "C1", "description": "Tool called", "check_type": "tool_called", "expected": "portfolio_analysis"},
                {"id": "C2", "description": "Field present", "check_type": "field_present", "expected": "total_value"},
            ],
        }

        ec = EvalCase.from_dict(data)

        assert ec.id == "MVP-001"
        assert ec.category == "mvp"
        assert ec.input == "What's my portfolio worth?"
        assert ec.expected_tool_calls == ["portfolio_analysis"]
        assert ec.expected_output_fields == ["total_value"]
        assert len(ec.criteria) == 2
        assert ec.criteria[0]["check_type"] == "tool_called"
        assert ec.criteria[1]["check_type"] == "field_present"

    def test_from_dict_minimal(self):
        """Test creating EvalCase with minimal required fields."""
        data = {
            "id": "MVP-MIN",
            "category": "mvp",
            "input": "Test query",
            "criteria": [{"id": "C1", "check_type": "tool_called", "expected": "x"}],
        }

        ec = EvalCase.from_dict(data)

        assert ec.id == "MVP-MIN"
        assert ec.input == "Test query"
        assert ec.expected_tool_calls == []
        assert ec.expected_output_fields == []
        assert len(ec.criteria) == 1


class TestEvalResult:
    """Tests for EvalResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        ec = EvalCase(
            id="TEST",
            category="mvp",
            input="test",
            criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}],
        )

        result = EvalResult(eval_case=ec, passed=False)

        assert result.passed is False
        assert result.response == ""
        assert result.tool_calls == []
        assert result.confidence == 0.0
        assert result.response_time_ms == 0.0
        assert result.errors == []
        assert result.checks == {}
        assert result.case_id == "TEST"
        assert result.case_category == "mvp"

    def test_passed_result(self):
        """Test creating a passing result."""
        ec = EvalCase(
            id="PASS-001",
            category="mvp",
            input="test",
            criteria=[{"id": "C1", "check_type": "tool_called", "expected": "portfolio_analysis"}],
        )

        result = EvalResult(
            eval_case=ec,
            passed=True,
            response="Your portfolio is worth $100,000",
            tool_calls=["portfolio_analysis"],
            confidence=85.0,
            response_time_ms=1500.0,
            criteria_results=[EvalCriterion(id="C1", description="", check_type="tool_called", expected="portfolio_analysis", passed=True)],
        )

        assert result.passed is True
        assert result.confidence == 85.0
        assert "portfolio_analysis" in result.tool_calls


class TestEvalReport:
    """Tests for EvalReport dataclass."""

    def test_pass_rate_empty(self):
        """Test pass rate with no tests."""
        report = EvalReport(timestamp="2024-01-01")

        assert report.pass_rate == 0.0

    def test_pass_rate_calculation(self):
        """Test pass rate calculation."""
        report = EvalReport(
            timestamp="2024-01-01",
            total_tests=10,
            passed=8,
            failed=2,
        )

        assert report.pass_rate == 80.0


class TestLoadEvalCases:
    """Tests for eval case loading."""

    def test_load_mvp(self):
        """Test loading MVP eval cases."""
        eval_cases = load_eval_cases("mvp")

        assert len(eval_cases) >= 5
        # Check that at least the first 5 complete cases have proper input and criteria
        complete_cases = [ec for ec in eval_cases if ec.input and ec.criteria]
        assert len(complete_cases) >= 5, f"Expected at least 5 complete cases, got {len(complete_cases)}"
        # Verify IDs are present on all cases
        assert all(ec.id for ec in eval_cases)

    def test_load_all_defaults_to_mvp(self):
        """Test loading all eval cases (defaults to MVP)."""
        eval_cases = load_eval_cases()

        assert len(eval_cases) >= 5
        # Check that at least the first 5 complete cases have proper input and criteria
        complete_cases = [ec for ec in eval_cases if ec.input and ec.criteria]
        assert len(complete_cases) >= 5, f"Expected at least 5 complete cases, got {len(complete_cases)}"
        # Verify IDs are present on all cases
        assert all(ec.id for ec in eval_cases)

    def test_load_unknown_category_exits(self):
        """Test that unknown category causes exit."""
        with pytest.raises(SystemExit):
            load_eval_cases("unknown_category")


class TestValidateEvalCases:
    """Tests for eval case validation."""

    def test_validate_valid_cases(self):
        """Test validation of valid eval cases."""
        eval_cases = [
            EvalCase(
                id="VALID-001",
                category="mvp",
                input="Test query",
                criteria=[
                    {"id": "C1", "description": "Tool", "check_type": "tool_called", "expected": "portfolio_analysis"},
                ],
            ),
        ]

        errors = validate_eval_cases(eval_cases)

        assert errors == []

    def test_validate_duplicate_ids(self):
        """Test detection of duplicate eval IDs."""
        eval_cases = [
            EvalCase(id="DUP-001", category="mvp", input="Test 1", criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}]),
            EvalCase(id="DUP-001", category="mvp", input="Test 2", criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}]),
        ]

        errors = validate_eval_cases(eval_cases)

        assert any("Duplicate" in e for e in errors)

    def test_validate_missing_input(self):
        """Test detection of missing input field."""
        eval_cases = [
            EvalCase(
                id="NO-INPUT",
                category="mvp",
                input=None,  # type: ignore
                criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}],
            ),
        ]

        errors = validate_eval_cases(eval_cases)

        assert any("input" in e.lower() for e in errors)

    def test_validate_missing_criteria(self):
        """Test that empty criteria is allowed (edge cases with no expected tools)."""
        eval_cases = [
            EvalCase(id="NO-CRITERIA", category="mvp", input="Test", criteria=[]),
        ]

        errors = validate_eval_cases(eval_cases)

        # Empty criteria is allowed for edge cases - no error expected
        assert len(errors) == 0

    def test_validate_invalid_check_type(self):
        """Test detection of invalid check_type."""
        eval_cases = [
            EvalCase(
                id="BAD-CHECK",
                category="mvp",
                input="Test",
                criteria=[{"id": "C1", "check_type": "invalid_type", "expected": "x"}],
            ),
        ]

        errors = validate_eval_cases(eval_cases)

        assert any("check_type" in e.lower() or "invalid" in e.lower() for e in errors)


class TestEvaluateCriterion:
    """Tests for atomic criterion evaluation."""

    def test_tool_called_pass(self):
        """Test tool_called criterion passes when tool is in list."""
        crit = EvalCriterion(
            id="C1",
            description="portfolio_analysis called",
            check_type="tool_called",
            expected="portfolio_analysis",
        )
        result = evaluate_criterion(
            crit,
            response={},
            tool_calls=["portfolio_analysis", "risk_assessment"],
            response_time_ms=100.0,
            confidence=80.0,
        )
        assert result.passed is True
        assert result.actual == ["portfolio_analysis", "risk_assessment"]

    def test_tool_called_fail(self):
        """Test tool_called criterion fails when tool not in list."""
        crit = EvalCriterion(
            id="C1",
            description="portfolio_analysis called",
            check_type="tool_called",
            expected="portfolio_analysis",
        )
        result = evaluate_criterion(
            crit,
            response={},
            tool_calls=["risk_assessment"],
            response_time_ms=100.0,
            confidence=80.0,
        )
        assert result.passed is False

    def test_field_present_pass(self):
        """Test field_present criterion passes when field exists in tool_outputs."""
        crit = EvalCriterion(
            id="C2",
            description="total_value present",
            check_type="field_present",
            expected="total_value",
        )
        result = evaluate_criterion(
            crit,
            response={"tool_outputs": [{"total_value": 100000, "holdings": []}]},
            tool_calls=[],
            response_time_ms=100.0,
            confidence=80.0,
        )
        assert result.passed is True

    def test_field_present_fail(self):
        """Test field_present criterion fails when field missing."""
        crit = EvalCriterion(
            id="C2",
            description="total_value present",
            check_type="field_present",
            expected="total_value",
        )
        result = evaluate_criterion(
            crit,
            response={"tool_outputs": [{"holdings": []}]},
            tool_calls=[],
            response_time_ms=100.0,
            confidence=80.0,
        )
        assert result.passed is False

    def test_unknown_check_type_fails(self):
        """Test unknown check_type fails."""
        crit = EvalCriterion(
            id="C3",
            description="Unknown",
            check_type="unknown",
            expected="x",
        )
        result = evaluate_criterion(
            crit,
            response={},
            tool_calls=[],
            response_time_ms=100.0,
            confidence=80.0,
        )
        assert result.passed is False
        assert "Unknown" in str(result.actual)


class TestRunSingleEval:
    """Tests for running individual eval cases."""

    @pytest.mark.asyncio
    async def test_run_eval_case(self):
        """Test running a single eval case."""
        ec = EvalCase(
            id="MVP-TEST",
            category="mvp",
            input="What's my portfolio worth?",
            criteria=[
                {"id": "C1", "description": "Tool called", "check_type": "tool_called", "expected": "portfolio_analysis"},
                {"id": "C2", "description": "Field present", "check_type": "field_present", "expected": "total_value"},
            ],
        )

        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(return_value={
            "message": "Your portfolio is worth $100,000",
            "tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
            "tool_outputs": [{"total_value": 100000, "holdings": []}],
            "confidence": 85.0,
            "metadata": {},
        })

        result = await run_single_eval(mock_agent, ec)

        assert result.eval_case.id == "MVP-TEST"
        assert result.response == "Your portfolio is worth $100,000"
        assert "portfolio_analysis" in result.tool_calls
        assert result.confidence == 85.0
        assert result.passed is True
        assert len(result.criteria_results) == 2
        assert all(c.passed for c in result.criteria_results)

    @pytest.mark.asyncio
    async def test_run_eval_case_partial_fail(self):
        """Test eval case when one criterion fails."""
        ec = EvalCase(
            id="PARTIAL-TEST",
            category="mvp",
            input="Test",
            criteria=[
                {"id": "C1", "description": "Tool called", "check_type": "tool_called", "expected": "portfolio_analysis"},
                {"id": "C2", "description": "Field present", "check_type": "field_present", "expected": "missing_field"},
            ],
        )

        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(return_value={
            "message": "Done",
            "tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
            "tool_outputs": [{}],
            "confidence": 80.0,
            "metadata": {},
        })

        result = await run_single_eval(mock_agent, ec)

        assert result.passed is False
        assert len(result.criteria_results) == 2
        passed = [c for c in result.criteria_results if c.passed]
        failed = [c for c in result.criteria_results if not c.passed]
        assert len(passed) == 1
        assert len(failed) == 1

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling during eval execution."""
        ec = EvalCase(
            id="EXCEPTION-TEST",
            category="mvp",
            input="Test",
            criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}],
        )

        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(side_effect=Exception("Test error"))

        result = await run_single_eval(mock_agent, ec)

        assert result.passed is False
        assert len(result.errors) > 0
        assert "Test error" in result.errors[0]


class TestReportGeneration:
    """Tests for report generation."""

    def test_report_structure(self):
        """Test that report has required structure."""
        ec = EvalCase(
            id="STRUCT-TEST",
            category="mvp",
            input="test",
            criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}],
        )
        result = EvalResult(
            eval_case=ec,
            passed=True,
            confidence=80.0,
        )

        report = EvalReport(
            timestamp="2024-01-01T00:00:00",
            total_tests=1,
            passed=1,
            failed=0,
            results=[result],
        )

        assert report.total_tests == 1
        assert report.passed == 1
        assert report.failed == 0
        assert report.pass_rate == 100.0
        assert len(report.results) == 1

    def test_category_summary(self):
        """Test category summary generation."""
        ec1 = EvalCase(id="CAT-1", category="mvp", input="test", criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}])
        ec2 = EvalCase(id="CAT-2", category="mvp", input="test", criteria=[{"id": "C1", "check_type": "tool_called", "expected": "x"}])

        report = EvalReport(
            timestamp="2024-01-01",
            total_tests=2,
            passed=1,
            failed=1,
            category_summary={
                "mvp": {"passed": 1, "failed": 1, "total": 2},
            },
            results=[
                EvalResult(eval_case=ec1, passed=True),
                EvalResult(eval_case=ec2, passed=False),
            ],
        )

        assert "mvp" in report.category_summary
        assert report.category_summary["mvp"]["passed"] == 1
        assert report.category_summary["mvp"]["failed"] == 1


# Integration test markers
@pytest.mark.integration
class TestEvalRunnerIntegration:
    """Integration tests for eval runner."""

    @pytest.mark.asyncio
    async def test_full_eval_flow(self):
        """Test complete evaluation flow with mock agent."""
        eval_cases = load_eval_cases("mvp")[:3]

        errors = validate_eval_cases(eval_cases)
        assert errors == []

        async def mock_chat(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.001)
            return {
                "message": "Your portfolio is worth $100,000.",
                "tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
                "tool_outputs": [{"total_value": 100000}],
                "confidence": 85.0,
                "metadata": {},
            }

        mock_agent = MagicMock()
        mock_agent.chat_with_context = mock_chat

        results = []
        for ec in eval_cases:
            result = await run_single_eval(mock_agent, ec)
            results.append(result)

        assert all(len(r.errors) == 0 for r in results)
        assert all(r.response_time_ms > 0 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
