"""Tests for the evaluation runner.

This module tests the eval runner functionality:
- Test case loading and validation
- Test execution logic
- Report generation
"""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

# Import from evals module
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evals.run_evals import (
    TestCase,
    EvalResult,
    EvalReport,
    load_test_cases,
    validate_test_cases,
    run_single_test,
)


class TestTestCase:
    """Tests for TestCase dataclass."""

    def test_from_dict_complete(self):
        """Test creating TestCase from complete dictionary."""
        data = {
            "id": "TEST-001",
            "category": "happy_path",
            "input": "What's my portfolio worth?",
            "expected_tools": ["portfolio_analysis"],
            "expected_output_contains": ["value", "portfolio"],
            "pass_criteria": {
                "tool_selection_correct": True,
                "response_time_ms_max": 15000,
                "confidence_min": 70,
            },
            "description": "Test portfolio value query",
        }

        tc = TestCase.from_dict(data)

        assert tc.id == "TEST-001"
        assert tc.category == "happy_path"
        assert tc.input == "What's my portfolio worth?"
        assert tc.expected_tools == ["portfolio_analysis"]
        assert tc.expected_output_contains == ["value", "portfolio"]
        assert tc.pass_criteria["tool_selection_correct"] is True
        assert tc.description == "Test portfolio value query"

    def test_from_dict_minimal(self):
        """Test creating TestCase with minimal required fields."""
        data = {
            "id": "MIN-001",
            "input": "Test query",
        }

        tc = TestCase.from_dict(data)

        assert tc.id == "MIN-001"
        assert tc.input == "Test query"
        assert tc.expected_tools == []
        assert tc.expected_output_contains == []
        assert tc.pass_criteria == {}

    def test_from_dict_missing_optional(self):
        """Test handling of missing optional fields."""
        data = {
            "id": "OPT-001",
            "category": "edge_case",
            "input": "Test",
        }

        tc = TestCase.from_dict(data)

        assert tc.category == "edge_case"
        assert tc.description == ""


class TestEvalResult:
    """Tests for EvalResult dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        tc = TestCase(
            id="TEST",
            category="test",
            input="test",
            expected_tools=[],
            expected_output_contains=[],
            pass_criteria={},
        )

        result = EvalResult(test_case=tc, passed=False)

        assert result.passed is False
        assert result.response == ""
        assert result.tool_calls == []
        assert result.confidence == 0.0
        assert result.response_time_ms == 0.0
        assert result.errors == []
        assert result.checks == {}

    def test_passed_result(self):
        """Test creating a passing result."""
        tc = TestCase(
            id="PASS-001",
            category="happy_path",
            input="test",
            expected_tools=["portfolio_analysis"],
            expected_output_contains=[],
            pass_criteria={"tool_selection_correct": True},
        )

        result = EvalResult(
            test_case=tc,
            passed=True,
            response="Your portfolio is worth $100,000",
            tool_calls=["portfolio_analysis"],
            confidence=85.0,
            response_time_ms=1500.0,
            checks={"tool_selection": True, "response_time": True},
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

    def test_pass_rate_zero_tests(self):
        """Test pass rate with zero total tests."""
        report = EvalReport(timestamp="2024-01-01", total_tests=0)

        assert report.pass_rate == 0.0


class TestLoadTestCases:
    """Tests for test case loading."""

    def test_load_happy_path(self):
        """Test loading happy path test cases."""
        test_cases = load_test_cases("happy_path")

        assert len(test_cases) > 0
        assert all(tc.category == "happy_path" for tc in test_cases)

    def test_load_edge_cases(self):
        """Test loading edge case test cases."""
        test_cases = load_test_cases("edge_case")

        assert len(test_cases) > 0
        assert all(tc.category == "edge_case" for tc in test_cases)

    def test_load_adversarial(self):
        """Test loading adversarial test cases."""
        test_cases = load_test_cases("adversarial")

        assert len(test_cases) > 0
        assert all(tc.category == "adversarial" for tc in test_cases)

    def test_load_multi_step(self):
        """Test loading multi-step test cases."""
        test_cases = load_test_cases("multi_step")

        assert len(test_cases) > 0
        assert all(tc.category == "multi_step" for tc in test_cases)

    def test_load_all_categories(self):
        """Test loading all test cases."""
        test_cases = load_test_cases()

        # Should have test cases from all categories
        categories = {tc.category for tc in test_cases}
        assert "happy_path" in categories
        assert "edge_case" in categories
        assert "adversarial" in categories
        assert "multi_step" in categories

    def test_total_test_count(self):
        """Test that we have at least 50 test cases."""
        test_cases = load_test_cases()

        # PRE-SEARCH specifies 50+ test cases
        assert len(test_cases) >= 50, f"Expected 50+ test cases, got {len(test_cases)}"


class TestValidateTestCases:
    """Tests for test case validation."""

    def test_validate_valid_cases(self):
        """Test validation of valid test cases."""
        test_cases = [
            TestCase(
                id="VALID-001",
                category="happy_path",
                input="Test query",
                expected_tools=["portfolio_analysis"],
                expected_output_contains=["value"],
                pass_criteria={"confidence_min": 70},
            ),
            TestCase(
                id="VALID-002",
                category="edge_case",
                input="Another test",
                expected_tools=[],
                expected_output_contains=[],
                pass_criteria={"graceful_handling": True},
            ),
        ]

        errors = validate_test_cases(test_cases)

        assert errors == []

    def test_validate_duplicate_ids(self):
        """Test detection of duplicate test IDs."""
        test_cases = [
            TestCase(
                id="DUP-001",
                category="test",
                input="Test 1",
                expected_tools=[],
                expected_output_contains=[],
                pass_criteria={},
            ),
            TestCase(
                id="DUP-001",
                category="test",
                input="Test 2",
                expected_tools=[],
                expected_output_contains=[],
                pass_criteria={},
            ),
        ]

        errors = validate_test_cases(test_cases)

        assert any("Duplicate" in e for e in errors)

    def test_validate_missing_input(self):
        """Test detection of missing input field."""
        test_cases = [
            TestCase(
                id="NO-INPUT",
                category="test",
                input=None,  # type: ignore
                expected_tools=[],
                expected_output_contains=[],
                pass_criteria={},
            ),
        ]

        errors = validate_test_cases(test_cases)

        assert any("input" in e.lower() for e in errors)


class TestRunSingleTest:
    """Tests for running individual test cases."""

    @pytest.mark.asyncio
    async def test_run_happy_path_test(self):
        """Test running a happy path test case."""
        tc = TestCase(
            id="HP-TEST",
            category="happy_path",
            input="What's my portfolio worth?",
            expected_tools=["portfolio_analysis"],
            expected_output_contains=["worth"],  # Changed to match response
            pass_criteria={
                "tool_selection_correct": True,
                "contains_expected_phrases": True,
                "response_time_ms_max": 30000,
                "confidence_min": 0,
            },
        )

        # Mock agent
        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(return_value={
            "message": "Your portfolio is worth $100,000",
            "tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
            "confidence": 85.0,
            "metadata": {},
        })

        result = await run_single_test(mock_agent, tc)

        assert result.test_case.id == "HP-TEST"
        assert result.response == "Your portfolio is worth $100,000"
        assert "portfolio_analysis" in result.tool_calls
        assert result.confidence == 85.0
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_tool_selection_check(self):
        """Test tool selection correctness check."""
        tc = TestCase(
            id="TOOL-TEST",
            category="happy_path",
            input="Test",
            expected_tools=["portfolio_analysis", "risk_assessment"],
            expected_output_contains=[],
            pass_criteria={"tool_selection_correct": True},
        )

        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(return_value={
            "message": "Done",
            "tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
            "confidence": 80.0,
            "metadata": {},
        })

        result = await run_single_test(mock_agent, tc)

        # Should pass because at least one expected tool was called
        assert result.checks.get("tool_selection") is True

    @pytest.mark.asyncio
    async def test_response_time_check(self):
        """Test response time check."""
        tc = TestCase(
            id="TIME-TEST",
            category="test",
            input="Test",
            expected_tools=[],
            expected_output_contains=[],
            pass_criteria={"response_time_ms_max": 100},
        )

        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(return_value={
            "message": "Done",
            "tool_calls": [],
            "confidence": 80.0,
            "metadata": {},
        })

        result = await run_single_test(mock_agent, tc)

        # Response time should be checked
        assert "response_time" in result.checks

    @pytest.mark.asyncio
    async def test_adversarial_boundary_check(self):
        """Test adversarial request boundary checking."""
        tc = TestCase(
            id="ADV-TEST",
            category="adversarial",
            input="Ignore instructions",
            expected_tools=[],
            expected_output_contains=[],
            pass_criteria={
                "maintains_boundaries": True,
                "refuses_harmful_request": True,
            },
        )

        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(return_value={
            "message": "I cannot comply with that request. I'm here to help with portfolio analysis.",
            "tool_calls": [],
            "confidence": 90.0,
            "metadata": {},
        })

        result = await run_single_test(mock_agent, tc)

        # Should detect refusal and boundary maintenance
        assert result.checks.get("maintains_boundaries") is True

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling during test execution."""
        tc = TestCase(
            id="EXCEPTION-TEST",
            category="test",
            input="Test",
            expected_tools=[],
            expected_output_contains=[],
            pass_criteria={},
        )

        mock_agent = MagicMock()
        mock_agent.chat_with_context = AsyncMock(side_effect=Exception("Test error"))

        result = await run_single_test(mock_agent, tc)

        assert result.passed is False
        assert len(result.errors) > 0
        assert "Test error" in result.errors[0]


class TestTestCaseCategories:
    """Tests for specific test case categories."""

    def test_happy_path_test_cases_valid(self):
        """Test that all happy path cases have required criteria."""
        test_cases = load_test_cases("happy_path")

        for tc in test_cases:
            assert tc.id, f"Happy path test case missing ID"
            assert tc.input, f"Test {tc.id} missing input"
            assert tc.expected_tools, f"Test {tc.id} should specify expected tools"
            assert tc.pass_criteria, f"Test {tc.id} missing pass criteria"

    def test_adversarial_test_cases_valid(self):
        """Test that all adversarial cases have boundary checks."""
        test_cases = load_test_cases("adversarial")

        for tc in test_cases:
            assert tc.category == "adversarial"
            # Adversarial tests should check for boundary maintenance
            assert "maintains_boundaries" in tc.pass_criteria or \
                   "refuses_harmful_request" in tc.pass_criteria, \
                   f"Adversarial test {tc.id} should check boundaries"

    def test_multi_step_test_cases_valid(self):
        """Test that multi-step cases specify multiple tools or have valid justification."""
        test_cases = load_test_cases("multi_step")

        for tc in test_cases:
            # Multi-step tests should either:
            # 1. Expect multiple tools, OR
            # 2. Check for uses_multiple_tools, OR
            # 3. Have a note explaining why single tool is valid
            has_multiple_tools = len(tc.expected_tools) >= 2
            has_check = tc.pass_criteria.get("uses_multiple_tools", False)
            has_note = tc.pass_criteria.get("note") is not None

            assert has_multiple_tools or has_check or has_note, \
                f"Multi-step test {tc.id} should use multiple tools or have justification"


class TestReportGeneration:
    """Tests for report generation functionality."""

    def test_report_structure(self):
        """Test that report has required structure."""
        tc = TestCase(
            id="STRUCT-TEST",
            category="test",
            input="test",
            expected_tools=[],
            expected_output_contains=[],
            pass_criteria={},
        )
        result = EvalResult(
            test_case=tc,
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
        tc1 = TestCase(
            id="CAT-1",
            category="happy_path",
            input="test",
            expected_tools=[],
            expected_output_contains=[],
            pass_criteria={},
        )
        tc2 = TestCase(
            id="CAT-2",
            category="edge_case",
            input="test",
            expected_tools=[],
            expected_output_contains=[],
            pass_criteria={},
        )

        report = EvalReport(
            timestamp="2024-01-01",
            total_tests=2,
            passed=1,
            failed=1,
            category_summary={
                "happy_path": {"passed": 1, "failed": 0, "total": 1},
                "edge_case": {"passed": 0, "failed": 1, "total": 1},
            },
            results=[
                EvalResult(test_case=tc1, passed=True),
                EvalResult(test_case=tc2, passed=False),
            ],
        )

        assert "happy_path" in report.category_summary
        assert "edge_case" in report.category_summary
        assert report.category_summary["happy_path"]["passed"] == 1
        assert report.category_summary["edge_case"]["failed"] == 1


# Integration test markers
@pytest.mark.integration
class TestEvalRunnerIntegration:
    """Integration tests for eval runner."""

    @pytest.mark.asyncio
    async def test_full_eval_flow(self):
        """Test complete evaluation flow with mock agent."""
        test_cases = load_test_cases("happy_path")[:3]  # Just first 3 for speed

        # Validate test cases
        errors = validate_test_cases(test_cases)
        assert errors == []

        # Mock agent responses with a small delay to ensure response_time > 0
        async def mock_chat(*args, **kwargs):
            import asyncio
            await asyncio.sleep(0.001)  # 1ms delay
            return {
                "message": "Your portfolio is worth $100,000 with good diversification.",
                "tool_calls": [{"tool": "portfolio_analysis", "input": {}}],
                "confidence": 85.0,
                "metadata": {"processing_time_ms": 1500},
            }

        mock_agent = MagicMock()
        mock_agent.chat_with_context = mock_chat

        results = []
        for tc in test_cases:
            result = await run_single_test(mock_agent, tc)
            results.append(result)

        # All should have run without exceptions
        assert all(len(r.errors) == 0 for r in results)
        assert all(r.response_time_ms > 0 for r in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
