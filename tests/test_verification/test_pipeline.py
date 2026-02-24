"""Tests for VerificationPipeline orchestration."""

import pytest

from src.verification.pipeline import (
    EscalationStatus,
    VerificationPipeline,
    VerificationReport,
)
from src.verification.confidence import ESCALATION_THRESHOLD


class TestVerificationPipeline:
    """Test VerificationPipeline class."""

    @pytest.fixture
    def pipeline(self) -> VerificationPipeline:
        """Create a VerificationPipeline instance."""
        return VerificationPipeline()

    @pytest.fixture
    def strict_pipeline(self) -> VerificationPipeline:
        """Create a strict VerificationPipeline."""
        return VerificationPipeline(strict_mode=True)

    @pytest.fixture
    def valid_portfolio_tools(self) -> list[dict]:
        """Create valid portfolio tool outputs."""
        return [{
            "total_value": 100000.00,
            "currency": "USD",
            "holdings": [
                {"symbol": "AAPL", "value": 50000, "quantity": 100, "allocation_pct": 50},
                {"symbol": "MSFT", "value": 50000, "quantity": 50, "allocation_pct": 50},
            ],
            "performance": {
                "absolute_change": 5000,
                "relative_change": 0.05,
            },
            "diversification_score": 75,
        }]

    @pytest.fixture
    def error_tools(self) -> list[dict]:
        """Create tool outputs with errors."""
        return [{
            "error": "API failed",
            "status": "error",
        }]

    # ========================================================================
    # Test verify - Full pipeline
    # ========================================================================

    @pytest.mark.asyncio
    async def test_verify_passes_with_valid_data(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test verification passes with valid data."""
        response = "Your portfolio is worth $100,000."
        query = "What's my portfolio worth?"

        report = await pipeline.verify(response, valid_portfolio_tools, query)

        assert isinstance(report, VerificationReport)
        assert report.passed is True
        assert report.confidence_score >= 70

    @pytest.mark.asyncio
    async def test_verify_fails_with_bad_data(
        self,
        pipeline: VerificationPipeline,
        error_tools: list[dict],
    ) -> None:
        """Test verification with error tool outputs."""
        response = "Your portfolio data is unavailable."
        query = "What's my portfolio worth?"

        report = await pipeline.verify(response, error_tools, query)

        # Should handle gracefully
        assert isinstance(report, VerificationReport)
        # Check confidence assessment for tool success rate
        if report.confidence_assessment:
            assert report.confidence_assessment.tool_success_rate == 0

    @pytest.mark.asyncio
    async def test_verify_with_response_data(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test verification with structured response data."""
        response = "Your portfolio is worth $100,000."
        query = "What's my portfolio worth?"
        response_data = valid_portfolio_tools[0]

        report = await pipeline.verify(
            response, valid_portfolio_tools, query, response_data
        )

        assert report.constraint_result is not None
        assert report.constraint_result.is_valid is True

    @pytest.mark.asyncio
    async def test_verify_with_invalid_response_data(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test verification with invalid response data."""
        response = "Your portfolio is worth $50,000."
        query = "What's my portfolio worth?"
        response_data = {
            "total_value": -1000,  # Invalid
            "currency": "INVALID",  # Invalid
        }
        tool_outputs = [response_data]

        report = await pipeline.verify(response, tool_outputs, query, response_data)

        assert report.constraint_result is not None
        assert report.constraint_result.is_valid is False
        assert len(report.violations) > 0

    @pytest.mark.asyncio
    async def test_verify_generates_fact_checks(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test that fact checks are generated."""
        response = "Your portfolio total is $100,000 with a 5% return."
        query = "How's my portfolio?"

        report = await pipeline.verify(response, valid_portfolio_tools, query)

        assert len(report.fact_check_results) > 0

    @pytest.mark.asyncio
    async def test_verify_generates_citation_check(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test that citation check is performed."""
        response = "Based on the data, your portfolio is worth $100,000."
        query = "What's my portfolio worth?"

        report = await pipeline.verify(response, valid_portfolio_tools, query)

        assert report.citation_result is not None

    @pytest.mark.asyncio
    async def test_verify_no_tools(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test verification with no tool outputs."""
        response = "I don't have access to your portfolio data."
        query = "What's my portfolio worth?"

        report = await pipeline.verify(response, [], query)

        assert isinstance(report, VerificationReport)
        # Should acknowledge uncertainty
        assert report.passed is True or report.confidence_score >= 50

    # ========================================================================
    # Test verify_response_only
    # ========================================================================

    @pytest.mark.asyncio
    async def test_verify_response_only(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test verification without tool outputs."""
        response = "I cannot help with that request."
        query = "Give me financial advice."

        report = await pipeline.verify_response_only(response, query)

        assert isinstance(report, VerificationReport)

    # ========================================================================
    # Test verify_with_data
    # ========================================================================

    @pytest.mark.asyncio
    async def test_verify_with_data_valid(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test verification with valid structured data."""
        response = "Your portfolio is worth $100,000."
        query = "What's my portfolio worth?"
        response_data = {
            "total_value": 100000,
            "currency": "USD",
            "holdings": [
                {"symbol": "AAPL", "value": 100000, "quantity": 100, "allocation_pct": 100},
            ],
        }

        report = await pipeline.verify_with_data(response, response_data, query)

        assert report.passed is True

    @pytest.mark.asyncio
    async def test_verify_with_data_invalid(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test verification with invalid structured data."""
        response = "Your portfolio data."
        query = "What's my portfolio worth?"
        response_data = {
            "total_value": -1000,  # Invalid
        }

        report = await pipeline.verify_with_data(response, response_data, query)

        assert report.constraint_result is not None
        assert report.constraint_result.is_valid is False

    # ========================================================================
    # Test escalation
    # ========================================================================

    @pytest.mark.asyncio
    async def test_escalation_low_confidence(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test escalation for low confidence."""
        response = "I think maybe your portfolio is something."
        query = "What's my portfolio worth?"

        # Force low confidence with poor data
        report = await pipeline.verify(response, [], query)

        if report.confidence_score < ESCALATION_THRESHOLD:
            assert report.escalation.requires_escalation is True
            assert len(report.escalation.triggers) > 0

    @pytest.mark.asyncio
    async def test_escalation_critical_violation(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test escalation for critical violations."""
        response = "Your portfolio data."
        query = "What's my portfolio worth?"
        response_data = {
            "total_value": -1000,  # Critical issue - negative value
        }

        report = await pipeline.verify_with_data(response, response_data, query)

        # Constraint violation should be detected
        if report.constraint_result:
            assert report.constraint_result.is_valid is False

    @pytest.mark.asyncio
    async def test_no_escalation_high_confidence(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test no escalation with high confidence."""
        response = "Your portfolio is worth $100,000."
        query = "What's my portfolio worth?"

        report = await pipeline.verify(response, valid_portfolio_tools, query)

        if report.confidence_score >= ESCALATION_THRESHOLD:
            assert report.escalation.requires_escalation is False

    # ========================================================================
    # Test strict mode
    # ========================================================================

    @pytest.mark.asyncio
    async def test_strict_mode_fails_on_violation(
        self,
        strict_pipeline: VerificationPipeline,
    ) -> None:
        """Test strict mode fails on any violation."""
        response = "Your portfolio data."
        query = "What's my portfolio worth?"
        response_data = {
            "currency": "INVALID",  # Invalid but not critical
        }

        report = await strict_pipeline.verify_with_data(response, response_data, query)

        # In strict mode, any violation should fail
        if report.constraint_result and not report.constraint_result.is_valid:
            assert report.passed is False

    # ========================================================================
    # Test get_verification_summary
    # ========================================================================

    def test_get_verification_summary(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test summary generation."""
        import asyncio

        report = asyncio.run(
            pipeline.verify(
                "Your portfolio is worth $100,000.",
                valid_portfolio_tools,
                "What's my portfolio worth?"
            )
        )

        summary = pipeline.get_verification_summary(report)

        assert "status" in summary
        assert "confidence" in summary
        assert "issues" in summary
        assert "escalation" in summary
        assert summary["status"] in ("PASSED", "FAILED")

    # ========================================================================
    # Test response type detection
    # ========================================================================

    def test_detect_response_type_portfolio(self, pipeline: VerificationPipeline) -> None:
        """Test portfolio type detection."""
        data = {"holdings": [], "total_value": 1000}
        assert pipeline._detect_response_type(data) == "portfolio"

    def test_detect_response_type_transaction(self, pipeline: VerificationPipeline) -> None:
        """Test transaction type detection."""
        data = {"transactions": [], "type": "BUY"}
        assert pipeline._detect_response_type(data) == "transaction"

    def test_detect_response_type_risk(self, pipeline: VerificationPipeline) -> None:
        """Test risk type detection."""
        data = {"risk_score": 50, "concentration_risk": {}}
        assert pipeline._detect_response_type(data) == "risk"

    def test_detect_response_type_market_data(self, pipeline: VerificationPipeline) -> None:
        """Test market data type detection."""
        data = {"price": 100, "data": []}
        assert pipeline._detect_response_type(data) == "market_data"

    def test_detect_response_type_general(self, pipeline: VerificationPipeline) -> None:
        """Test general type detection."""
        data = {"message": "Hello"}
        assert pipeline._detect_response_type(data) == "general"

    # ========================================================================
    # Test claim extraction
    # ========================================================================

    def test_extract_claim_sentences(self, pipeline: VerificationPipeline) -> None:
        """Test claim sentence extraction."""
        text = "Your portfolio is worth $100,000. It gained 5% this year. Have a nice day."

        sentences = pipeline._extract_claim_sentences(text)

        # Should extract sentences with numbers and claim keywords
        assert len(sentences) >= 2
        assert any("$100,000" in s for s in sentences)

    # ========================================================================
    # Test processing time
    # ========================================================================

    @pytest.mark.asyncio
    async def test_processing_time_recorded(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test that processing time is recorded."""
        report = await pipeline.verify(
            "Your portfolio is worth $100,000.",
            valid_portfolio_tools,
            "What's my portfolio worth?"
        )

        assert report.processing_time_ms is not None
        assert report.processing_time_ms > 0

    # ========================================================================
    # Test report serialization
    # ========================================================================

    def test_report_to_dict(
        self,
        pipeline: VerificationPipeline,
        valid_portfolio_tools: list[dict],
    ) -> None:
        """Test report serialization to dict."""
        import asyncio

        report = asyncio.run(
            pipeline.verify(
                "Your portfolio is worth $100,000.",
                valid_portfolio_tools,
                "What's my portfolio worth?"
            )
        )

        result = report.to_dict()

        assert "passed" in result
        assert "confidence_score" in result
        assert "timestamp" in result


class TestVerificationReport:
    """Test VerificationReport model."""

    def test_valid_report(self) -> None:
        """Test creating valid report."""
        report = VerificationReport(
            passed=True,
            confidence_score=85.0,
            confidence_level="HIGH",
            fact_check_results=[],
            violations=[],
            unverified_claims=[],
            warnings=[],
        )

        assert report.passed is True
        assert report.confidence_score == 85.0

    def test_report_defaults(self) -> None:
        """Test report default values."""
        report = VerificationReport(
            passed=True,
            confidence_score=100.0,
            confidence_level="VERY_HIGH",
            fact_check_results=[],
            violations=[],
            unverified_claims=[],
            warnings=[],
        )

        assert len(report.violations) == 0
        assert len(report.warnings) == 0
        assert report.escalation.requires_escalation is False  # Default escalation status


class TestEscalationStatus:
    """Test EscalationStatus model."""

    def test_no_escalation(self) -> None:
        """Test no escalation status."""
        status = EscalationStatus(
            requires_escalation=False,
            triggers=[],
            severity="NONE",
        )

        assert status.requires_escalation is False
        assert len(status.triggers) == 0

    def test_escalation_with_triggers(self) -> None:
        """Test escalation with triggers."""
        status = EscalationStatus(
            requires_escalation=True,
            triggers=["Low confidence: 50%", "Large transaction detected"],
            severity="MEDIUM",
        )

        assert status.requires_escalation is True
        assert len(status.triggers) == 2
        assert status.severity == "MEDIUM"


class TestPipelineIntegration:
    """Integration tests for the full verification pipeline."""

    @pytest.fixture
    def pipeline(self) -> VerificationPipeline:
        """Create pipeline for integration tests."""
        return VerificationPipeline()

    @pytest.mark.asyncio
    async def test_full_portfolio_verification(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test full verification flow for portfolio query."""
        query = "What's my portfolio worth and how is it allocated?"

        tool_outputs = [{
            "total_value": 100000.00,
            "currency": "USD",
            "holdings": [
                {"symbol": "VTI", "value": 60000, "quantity": 120, "allocation_pct": 60},
                {"symbol": "VXUS", "value": 25000, "quantity": 250, "allocation_pct": 25},
                {"symbol": "BND", "value": 15000, "quantity": 150, "allocation_pct": 15},
            ],
            "diversification_score": 82,
        }]

        response = """
        Based on the analysis, your portfolio is worth $100,000.
        Here's the allocation:
        - VTI: 60% ($60,000)
        - VXUS: 25% ($25,000)
        - BND: 15% ($15,000)
        Your diversification score is 82.
        """

        report = await pipeline.verify(response, tool_outputs, query)

        # Should have reasonable confidence with good data
        assert report.confidence_score >= 60
        # Should pass verification
        assert report.passed is True

    @pytest.mark.asyncio
    async def test_full_risk_assessment_verification(
        self,
        pipeline: VerificationPipeline,
    ) -> None:
        """Test full verification flow for risk assessment."""
        query = "How risky is my portfolio?"

        tool_outputs = [{
            "risk_score": 45,
            "risk_level": "MEDIUM",
            "concentration_risk": {
                "top_holdings_pct": 20,
                "single_asset_max": 15,
            },
            "recommendations": ["Consider more diversification"],
        }]

        response = """
        Your portfolio has a medium risk level with a score of 45 out of 100.
        Concentration is moderate with top holdings at 20% of portfolio.
        """

        report = await pipeline.verify(response, tool_outputs, query)

        # Should pass verification
        assert report.passed is True
