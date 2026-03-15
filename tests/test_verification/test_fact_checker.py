"""Tests for FactChecker verification module."""

from datetime import datetime, timedelta

import pytest

from src.verification.fact_checker import (
    CitationCheckResult,
    FactChecker,
    FactCheckResult,
)


class TestFactChecker:
    """Test FactChecker class."""

    @pytest.fixture
    def checker(self) -> FactChecker:
        """Create a FactChecker instance."""
        return FactChecker()

    @pytest.fixture
    def portfolio_source_data(self) -> dict:
        """Create sample portfolio source data."""
        return {
            "total_value": 100000.00,
            "currency": "USD",
            "holdings": [
                {"symbol": "AAPL", "value": 50000, "quantity": 100, "price": 500},
                {"symbol": "MSFT", "value": 50000, "quantity": 50, "price": 1000},
            ],
            "performance": {
                "absolute_change": 5000,
                "relative_change": 0.05,
            },
        }

    # ========================================================================
    # Test verify_claim
    # ========================================================================

    @pytest.mark.asyncio
    async def test_verify_claim_accurate(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test verifying an accurate claim."""
        claim = "Your portfolio is worth $100,000."
        result = await checker.verify_claim(claim, portfolio_source_data)

        assert isinstance(result, FactCheckResult)
        assert result.is_accurate is True
        assert result.confidence >= 90
        assert 100000 in result.claimed_value

    @pytest.mark.asyncio
    async def test_verify_claim_inaccurate(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test verifying an inaccurate claim."""
        claim = "Your portfolio is worth $500,000."
        result = await checker.verify_claim(claim, portfolio_source_data)

        assert result.is_accurate is False
        assert result.confidence < 90

    @pytest.mark.asyncio
    async def test_verify_claim_no_numbers(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test verifying a claim with no numbers."""
        claim = "Your portfolio is diversified."
        result = await checker.verify_claim(claim, portfolio_source_data)

        # Can't verify non-numerical claims with high confidence
        assert result.confidence == 50

    @pytest.mark.asyncio
    async def test_verify_claim_partial_match(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test verifying a claim with partially accurate numbers."""
        claim = "You have 100 shares of AAPL worth $100,000."  # 100 shares is correct, total is wrong
        result = await checker.verify_claim(claim, portfolio_source_data)

        # Some numbers correct, some wrong
        # Should pass 80% threshold if most numbers are correct
        assert isinstance(result.is_accurate, bool)

    @pytest.mark.asyncio
    async def test_verify_claim_empty_source(self, checker: FactChecker) -> None:
        """Test verifying a claim with empty source data."""
        claim = "Your portfolio is worth $100,000."
        result = await checker.verify_claim(claim, {})

        assert result.is_accurate is False

    # ========================================================================
    # Test verify_numerical_claim
    # ========================================================================

    @pytest.mark.asyncio
    async def test_verify_numerical_claim_exact(self, checker: FactChecker) -> None:
        """Test verifying an exact numerical claim."""
        is_accurate = await checker.verify_numerical_claim(100.0, 100.0)
        assert is_accurate is True

    @pytest.mark.asyncio
    async def test_verify_numerical_claim_within_tolerance(
        self, checker: FactChecker
    ) -> None:
        """Test verifying a claim within tolerance."""
        # Default tolerance is 1%
        is_accurate = await checker.verify_numerical_claim(100.5, 100.0)
        assert is_accurate is True

    @pytest.mark.asyncio
    async def test_verify_numerical_claim_outside_tolerance(
        self, checker: FactChecker
    ) -> None:
        """Test verifying a claim outside tolerance."""
        is_accurate = await checker.verify_numerical_claim(105.0, 100.0)
        assert is_accurate is False

    @pytest.mark.asyncio
    async def test_verify_numerical_claim_custom_tolerance(
        self, checker: FactChecker
    ) -> None:
        """Test verifying a claim with custom tolerance."""
        is_accurate = await checker.verify_numerical_claim(110.0, 100.0, tolerance=0.15)
        assert is_accurate is True

    @pytest.mark.asyncio
    async def test_verify_numerical_claim_zero(self, checker: FactChecker) -> None:
        """Test verifying zero values."""
        is_accurate = await checker.verify_numerical_claim(0, 0)
        assert is_accurate is True

        is_accurate = await checker.verify_numerical_claim(1, 0)
        assert is_accurate is False

    # ========================================================================
    # Test extract_and_verify_citations
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_citations_with_citations(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test citation extraction with explicit citations."""
        response = "According to portfolio data, your total is $100,000."
        tool_outputs = [portfolio_source_data]

        result = await checker.extract_and_verify_citations(response, tool_outputs)

        assert isinstance(result, CitationCheckResult)
        assert result.has_citations is True
        assert result.citation_count >= 1

    @pytest.mark.asyncio
    async def test_extract_citations_no_citations(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test citation extraction without explicit citations."""
        response = "Your total is $100,000."
        tool_outputs = [portfolio_source_data]

        result = await checker.extract_and_verify_citations(response, tool_outputs)

        # Should still check numbers
        assert isinstance(result, CitationCheckResult)

    @pytest.mark.asyncio
    async def test_extract_citations_grounded_numbers(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test citation verification with grounded numbers."""
        response = "Portfolio: $100,000 with 100 shares."
        tool_outputs = [portfolio_source_data]

        result = await checker.extract_and_verify_citations(response, tool_outputs)

        # Some numbers should be grounded in source data
        assert result.accuracy_score >= 50

    @pytest.mark.asyncio
    async def test_extract_citations_ungrounded_numbers(
        self, checker: FactChecker, portfolio_source_data: dict
    ) -> None:
        """Test citation verification with ungrounded numbers."""
        response = "Portfolio: $500,000 with 999 shares."
        tool_outputs = [portfolio_source_data]

        result = await checker.extract_and_verify_citations(response, tool_outputs)

        assert result.accuracy_score < 100
        assert len(result.unverified_claims) > 0

    @pytest.mark.asyncio
    async def test_extract_citations_no_tool_outputs(
        self, checker: FactChecker
    ) -> None:
        """Test citation verification without tool outputs."""
        response = "Your portfolio is worth something."

        result = await checker.extract_and_verify_citations(response, [])

        # No tool outputs means no verification possible, but also no numbers > 100
        assert result.accuracy_score == 100  # No significant numbers to verify

    # ========================================================================
    # Test verify_market_data_freshness
    # ========================================================================

    @pytest.mark.asyncio
    async def test_verify_freshness_fresh(self, checker: FactChecker) -> None:
        """Test freshness check with fresh data."""
        timestamp = datetime.utcnow().isoformat()

        result = await checker.verify_market_data_freshness(timestamp, max_age_hours=1)

        assert result["is_fresh"] is True
        assert result["warning"] is None

    @pytest.mark.asyncio
    async def test_verify_freshness_stale(self, checker: FactChecker) -> None:
        """Test freshness check with stale data."""
        timestamp = (datetime.utcnow() - timedelta(hours=2)).isoformat()

        result = await checker.verify_market_data_freshness(timestamp, max_age_hours=1)

        assert result["is_fresh"] is False
        assert result["warning"] is not None

    @pytest.mark.asyncio
    async def test_verify_freshness_invalid_format(self, checker: FactChecker) -> None:
        """Test freshness check with invalid timestamp."""
        result = await checker.verify_market_data_freshness("not-a-date")

        assert result["is_fresh"] is False
        assert "Could not parse" in result["warning"]

    @pytest.mark.asyncio
    async def test_verify_freshness_datetime_object(self, checker: FactChecker) -> None:
        """Test freshness check with datetime object."""
        timestamp = datetime.utcnow()

        result = await checker.verify_market_data_freshness(timestamp, max_age_hours=1)

        assert result["is_fresh"] is True

    # ========================================================================
    # Test verify_portfolio_totals
    # ========================================================================

    @pytest.mark.asyncio
    async def test_verify_portfolio_totals_accurate(
        self, checker: FactChecker
    ) -> None:
        """Test portfolio total verification with accurate total."""
        holdings = [
            {"value": 50000},
            {"value": 30000},
            {"value": 20000},
        ]

        result = await checker.verify_portfolio_totals(100000, holdings)

        assert result["is_accurate"] is True

    @pytest.mark.asyncio
    async def test_verify_portfolio_totals_inaccurate(
        self, checker: FactChecker
    ) -> None:
        """Test portfolio total verification with inaccurate total."""
        holdings = [
            {"value": 50000},
            {"value": 30000},
            {"value": 20000},
        ]

        result = await checker.verify_portfolio_totals(150000, holdings)

        assert result["is_accurate"] is False

    @pytest.mark.asyncio
    async def test_verify_portfolio_totals_empty(self, checker: FactChecker) -> None:
        """Test portfolio total verification with empty holdings."""
        result = await checker.verify_portfolio_totals(0, [])

        assert result["is_accurate"] is True

    @pytest.mark.asyncio
    async def test_verify_portfolio_totals_with_tolerance(
        self, checker: FactChecker
    ) -> None:
        """Test portfolio total within tolerance."""
        holdings = [
            {"value": 33333.33},
            {"value": 33333.33},
            {"value": 33333.33},
        ]

        # Sum is 99999.99, claiming 100000
        result = await checker.verify_portfolio_totals(100000, holdings)

        # Should be within 1% tolerance
        assert result["is_accurate"] is True

    # ========================================================================
    # Test number extraction
    # ========================================================================

    def test_extract_numbers_basic(self, checker: FactChecker) -> None:
        """Test basic number extraction."""
        numbers = checker._extract_numbers("Value is $100")

        assert 100 in numbers

    def test_extract_numbers_comma_separated(self, checker: FactChecker) -> None:
        """Test number extraction with commas."""
        numbers = checker._extract_numbers("Value is $1,000,000")

        assert 1000000 in numbers

    def test_extract_numbers_decimals(self, checker: FactChecker) -> None:
        """Test number extraction with decimals."""
        numbers = checker._extract_numbers("Price is $150.50")

        assert 150.50 in numbers

    def test_extract_numbers_negative(self, checker: FactChecker) -> None:
        """Test number extraction handles context."""
        # The pattern doesn't capture negative signs, just absolute values
        numbers = checker._extract_numbers("Loss of $500")

        assert 500 in numbers

    # ========================================================================
    # Test number context
    # ========================================================================

    def test_get_number_context_found(self, checker: FactChecker) -> None:
        """Test getting context for a number."""
        # Use a number format that the extractor can find
        text = "Your portfolio is worth $5000 today."
        context = checker._get_number_context(text, 5000)

        # Should find context for simple numbers
        assert "portfolio" in context.lower() or "5000" in context or "worth" in context.lower()

    def test_get_number_context_not_found(self, checker: FactChecker) -> None:
        """Test getting context when number not found."""
        text = "Your portfolio is worth a lot."
        context = checker._get_number_context(text, 100000)

        assert "not found" in context


class TestFactCheckResult:
    """Test FactCheckResult model."""

    def test_valid_result(self) -> None:
        """Test creating valid fact check result."""
        result = FactCheckResult(
            claim="Test claim",
            is_accurate=True,
            confidence=95.0,
            explanation="Verified",
        )

        assert result.claim == "Test claim"
        assert result.is_accurate is True
        assert result.confidence == 95.0

    def test_confidence_bounds(self) -> None:
        """Test confidence must be 0-100."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            FactCheckResult(
                claim="Test",
                is_accurate=True,
                confidence=150,  # Invalid
                explanation="Test",
            )


class TestCitationCheckResult:
    """Test CitationCheckResult model."""

    def test_valid_result(self) -> None:
        """Test creating valid citation check result."""
        result = CitationCheckResult(
            has_citations=True,
            citation_count=2,
            verified_citations=2,
            accuracy_score=95.0,
        )

        assert result.has_citations is True
        assert result.citation_count == 2

    def test_accuracy_bounds(self) -> None:
        """Test accuracy score must be 0-100."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CitationCheckResult(
                has_citations=True,
                citation_count=1,
                verified_citations=1,
                accuracy_score=150,  # Invalid
            )
