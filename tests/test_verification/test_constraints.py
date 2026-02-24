"""Tests for ConstraintValidator verification module."""

import pytest

from src.verification.constraints import (
    ConstraintValidationResult,
    ConstraintValidator,
    ConstraintViolation,
)


class TestConstraintValidator:
    """Test ConstraintValidator class."""

    @pytest.fixture
    def validator(self) -> ConstraintValidator:
        """Create a fresh ConstraintValidator instance."""
        return ConstraintValidator()

    # ========================================================================
    # Test validate_response - Portfolio
    # ========================================================================

    def test_validate_portfolio_response_valid(self, validator: ConstraintValidator) -> None:
        """Test validating a valid portfolio response."""
        response = {
            "total_value": 100000.00,
            "currency": "USD",
            "holdings": [
                {"symbol": "AAPL", "value": 50000, "quantity": 100, "allocation_pct": 50},
                {"symbol": "MSFT", "value": 50000, "quantity": 50, "allocation_pct": 50},
            ],
            "diversification_score": 75.0,
        }

        result = validator.validate_response(response, "portfolio")

        assert result.is_valid is True
        assert len(result.violations) == 0

    def test_validate_portfolio_negative_value(self, validator: ConstraintValidator) -> None:
        """Test validating portfolio with negative total value."""
        response = {
            "total_value": -1000,
            "currency": "USD",
            "holdings": [],
        }

        result = validator.validate_response(response, "portfolio")

        assert result.is_valid is False
        assert any("negative" in v.message.lower() for v in result.violations)

    def test_validate_portfolio_invalid_currency(self, validator: ConstraintValidator) -> None:
        """Test validating portfolio with invalid currency."""
        response = {
            "total_value": 100000,
            "currency": "INVALID",
            "holdings": [],
        }

        result = validator.validate_response(response, "portfolio")

        assert any("currency" in v.message.lower() for v in result.violations)

    def test_validate_portfolio_invalid_diversification_score(
        self, validator: ConstraintValidator
    ) -> None:
        """Test validating portfolio with invalid diversification score."""
        response = {
            "total_value": 100000,
            "currency": "USD",
            "holdings": [],
            "diversification_score": 150,  # Invalid: > 100
        }

        result = validator.validate_response(response, "portfolio")

        assert any("diversification" in v.message.lower() for v in result.violations)

    def test_validate_portfolio_allocations_dont_sum(self, validator: ConstraintValidator) -> None:
        """Test validating portfolio where allocations don't sum to 100%."""
        response = {
            "total_value": 100000,
            "currency": "USD",
            "holdings": [
                {"symbol": "AAPL", "value": 50000, "quantity": 100, "allocation_pct": 30},
                {"symbol": "MSFT", "value": 50000, "quantity": 50, "allocation_pct": 30},
            ],
        }

        result = validator.validate_response(response, "portfolio")

        assert any("allocation" in v.message.lower() for v in result.violations)

    def test_validate_portfolio_negative_quantity(self, validator: ConstraintValidator) -> None:
        """Test validating portfolio with negative quantity."""
        response = {
            "total_value": 100000,
            "currency": "USD",
            "holdings": [
                {"symbol": "AAPL", "value": 50000, "quantity": -10, "allocation_pct": 100},
            ],
        }

        result = validator.validate_response(response, "portfolio")

        assert any("quantity" in v.message.lower() and "negative" in v.message.lower()
                   for v in result.violations)

    # ========================================================================
    # Test validate_response - Transaction
    # ========================================================================

    def test_validate_transaction_response_valid(self, validator: ConstraintValidator) -> None:
        """Test validating a valid transaction response."""
        response = {
            "type": "BUY",
            "symbol": "AAPL",
            "quantity": 100,
            "price": 150.00,
        }

        result = validator.validate_response(response, "transaction")

        assert result.is_valid is True

    def test_validate_transaction_invalid_type(self, validator: ConstraintValidator) -> None:
        """Test validating transaction with invalid type."""
        response = {
            "type": "INVALID_TYPE",
            "symbol": "AAPL",
            "quantity": 100,
            "price": 150.00,
        }

        result = validator.validate_response(response, "transaction")

        assert any("transaction type" in v.message.lower() for v in result.violations)

    def test_validate_transaction_negative_quantity(self, validator: ConstraintValidator) -> None:
        """Test validating transaction with negative quantity."""
        response = {
            "type": "BUY",
            "symbol": "AAPL",
            "quantity": -100,
            "price": 150.00,
        }

        result = validator.validate_response(response, "transaction")

        assert result.is_valid is False

    def test_validate_transaction_negative_price(self, validator: ConstraintValidator) -> None:
        """Test validating transaction with negative price."""
        response = {
            "type": "BUY",
            "symbol": "AAPL",
            "quantity": 100,
            "price": -150.00,
        }

        result = validator.validate_response(response, "transaction")

        assert result.is_valid is False

    def test_validate_transaction_large_value_warning(self, validator: ConstraintValidator) -> None:
        """Test that large transactions generate warnings."""
        response = {
            "type": "BUY",
            "symbol": "AAPL",
            "quantity": 1000,
            "price": 150.00,  # $150,000 > $10,000 threshold
        }

        result = validator.validate_response(response, "transaction")

        # Should be valid but have warning
        assert len(result.warnings) > 0
        assert any("large transaction" in w.lower() for w in result.warnings)

    # ========================================================================
    # Test validate_response - Risk
    # ========================================================================

    def test_validate_risk_response_valid(self, validator: ConstraintValidator) -> None:
        """Test validating a valid risk response."""
        response = {
            "risk_score": 45,
            "risk_level": "MEDIUM",
            "concentration_risk": {
                "top_holdings_pct": 30,
            },
        }

        result = validator.validate_response(response, "risk")

        assert result.is_valid is True

    def test_validate_risk_invalid_score(self, validator: ConstraintValidator) -> None:
        """Test validating risk with invalid score."""
        response = {
            "risk_score": 150,  # Invalid: > 100
            "risk_level": "HIGH",
        }

        result = validator.validate_response(response, "risk")

        assert any("risk score" in v.message.lower() for v in result.violations)

    def test_validate_risk_level_inconsistency(self, validator: ConstraintValidator) -> None:
        """Test validating risk with inconsistent level."""
        response = {
            "risk_score": 80,  # HIGH range
            "risk_level": "LOW",  # Wrong level
        }

        result = validator.validate_response(response, "risk")

        # Should generate warning about inconsistency
        assert len(result.warnings) > 0

    def test_validate_risk_high_concentration_warning(self, validator: ConstraintValidator) -> None:
        """Test that high concentration generates warning."""
        response = {
            "risk_score": 60,
            "risk_level": "HIGH",
            "concentration_risk": {
                "top_holdings_pct": 50,  # > 25% threshold
            },
        }

        result = validator.validate_response(response, "risk")

        assert any("concentration" in w.lower() for w in result.warnings)

    # ========================================================================
    # Test validate_response - Market Data
    # ========================================================================

    def test_validate_market_data_response_valid(self, validator: ConstraintValidator) -> None:
        """Test validating valid market data."""
        response = {
            "data": [
                {"symbol": "AAPL", "price": 150.00},
                {"symbol": "MSFT", "price": 300.00},
            ]
        }

        result = validator.validate_response(response, "market_data")

        assert result.is_valid is True

    def test_validate_market_data_zero_price(self, validator: ConstraintValidator) -> None:
        """Test validating market data with zero price."""
        response = {
            "data": [
                {"symbol": "AAPL", "price": 0},
            ]
        }

        result = validator.validate_response(response, "market_data")

        assert result.is_valid is False

    def test_validate_market_data_negative_price(self, validator: ConstraintValidator) -> None:
        """Test validating market data with negative price."""
        response = {
            "data": [
                {"symbol": "AAPL", "price": -150.00},
            ]
        }

        result = validator.validate_response(response, "market_data")

        assert result.is_valid is False

    # ========================================================================
    # Test individual validators
    # ========================================================================

    def test_validate_quantity_valid(self, validator: ConstraintValidator) -> None:
        """Test valid quantity validation."""
        assert validator.validate_quantity(100) is True
        assert validator.validate_quantity(0) is True
        assert validator.validate_quantity(0.5) is True

    def test_validate_quantity_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid quantity validation."""
        assert validator.validate_quantity(-1) is False
        assert validator.validate_quantity(-100) is False

    def test_validate_price_valid(self, validator: ConstraintValidator) -> None:
        """Test valid price validation."""
        assert validator.validate_price(100) is True
        assert validator.validate_price(0.01) is True

    def test_validate_price_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid price validation."""
        assert validator.validate_price(0) is False
        assert validator.validate_price(-100) is False

    def test_validate_date_range_valid(self, validator: ConstraintValidator) -> None:
        """Test valid date range validation."""
        assert validator.validate_date_range("2024-01-01", "2024-12-31") is True
        assert validator.validate_date_range("2024-01-01", "2024-01-01") is True

    def test_validate_date_range_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid date range validation."""
        assert validator.validate_date_range("2024-12-31", "2024-01-01") is False
        assert validator.validate_date_range("invalid", "2024-01-01") is False

    def test_validate_symbol_valid(self, validator: ConstraintValidator) -> None:
        """Test valid symbol validation."""
        assert validator.validate_symbol("AAPL") is True
        assert validator.validate_symbol("MSFT") is True
        assert validator.validate_symbol("BRK.B") is True
        assert validator.validate_symbol("BRK-B") is True
        assert validator.validate_symbol("A") is True
        assert validator.validate_symbol("1234") is True

    def test_validate_symbol_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid symbol validation."""
        assert validator.validate_symbol("") is False
        assert validator.validate_symbol("TOOLONGSYMBOL") is False  # > 10 chars
        assert validator.validate_symbol("aapl") is True  # lowercase is converted to uppercase

    def test_validate_currency_valid(self, validator: ConstraintValidator) -> None:
        """Test valid currency validation."""
        assert validator.validate_currency("USD") is True
        assert validator.validate_currency("EUR") is True
        assert validator.validate_currency("GBP") is True

    def test_validate_currency_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid currency validation."""
        assert validator.validate_currency("INVALID") is False
        assert validator.validate_currency("XXX") is False

    def test_validate_transaction_type_valid(self, validator: ConstraintValidator) -> None:
        """Test valid transaction type validation."""
        assert validator.validate_transaction_type("BUY") is True
        assert validator.validate_transaction_type("SELL") is True
        assert validator.validate_transaction_type("DIVIDEND") is True
        assert validator.validate_transaction_type("TRANSFER_IN") is True

    def test_validate_transaction_type_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid transaction type validation."""
        assert validator.validate_transaction_type("INVALID") is False
        assert validator.validate_transaction_type("buy") is True  # case insensitive - converted to uppercase

    def test_validate_allocation_valid(self, validator: ConstraintValidator) -> None:
        """Test valid allocation validation."""
        assert validator.validate_allocation([50, 50]) is True
        assert validator.validate_allocation([33.33, 33.33, 33.34]) is True
        assert validator.validate_allocation([100]) is True

    def test_validate_allocation_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid allocation validation."""
        assert validator.validate_allocation([50, 30]) is False  # = 80%
        assert validator.validate_allocation([50, 60]) is False  # = 110%

    def test_validate_timeframe_valid(self, validator: ConstraintValidator) -> None:
        """Test valid timeframe validation."""
        assert validator.validate_timeframe("YTD") is True
        assert validator.validate_timeframe("1Y") is True
        assert validator.validate_timeframe("Max") is True

    def test_validate_timeframe_invalid(self, validator: ConstraintValidator) -> None:
        """Test invalid timeframe validation."""
        assert validator.validate_timeframe("INVALID") is False
        assert validator.validate_timeframe("2Y") is False

    # ========================================================================
    # Test check_concentration_limit
    # ========================================================================

    def test_check_concentration_limit_ok(self, validator: ConstraintValidator) -> None:
        """Test concentration limit check - within limits."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 20},
            {"symbol": "MSFT", "allocation_pct": 20},
            {"symbol": "GOOGL", "allocation_pct": 20},
        ]

        result = validator.check_concentration_limit(holdings, threshold=0.25)

        assert result["has_violation"] is False

    def test_check_concentration_limit_violation(self, validator: ConstraintValidator) -> None:
        """Test concentration limit check - exceeds limits."""
        holdings = [
            {"symbol": "AAPL", "allocation_pct": 50},  # > 25%
            {"symbol": "MSFT", "allocation_pct": 25},
            {"symbol": "GOOGL", "allocation_pct": 25},
        ]

        result = validator.check_concentration_limit(holdings, threshold=0.25)

        assert result["has_violation"] is True
        assert len(result["violations"]) == 1
        assert result["violations"][0]["symbol"] == "AAPL"

    # ========================================================================
    # Test check_daily_change
    # ========================================================================

    def test_check_daily_change_normal(self, validator: ConstraintValidator) -> None:
        """Test daily change check - normal."""
        result = validator.check_daily_change(100000, 95000, threshold=0.20)

        assert result["has_violation"] is False
        assert result["change_pct"] == pytest.approx(5.26, rel=0.1)

    def test_check_daily_change_unusual(self, validator: ConstraintValidator) -> None:
        """Test daily change check - unusual (escalation trigger)."""
        result = validator.check_daily_change(130000, 100000, threshold=0.20)

        assert result["has_violation"] is True
        assert result["change_pct"] == 30.0

    def test_check_daily_change_zero_previous(self, validator: ConstraintValidator) -> None:
        """Test daily change with zero previous value."""
        result = validator.check_daily_change(100000, 0)

        assert result["has_violation"] is False

    # ========================================================================
    # Test violation tracking
    # ========================================================================

    def test_get_violations(self, validator: ConstraintValidator) -> None:
        """Test getting violations."""
        validator.validate_quantity(-1)
        validator.validate_price(-1)

        violations = validator.get_violations()

        assert len(violations) == 2

    def test_clear_violations(self, validator: ConstraintValidator) -> None:
        """Test clearing violations."""
        validator.validate_quantity(-1)
        assert len(validator.get_violations()) == 1

        validator.clear_violations()
        assert len(validator.get_violations()) == 0

    # ========================================================================
    # Test NaN/Inf detection
    # ========================================================================

    def test_validate_nan_value(self, validator: ConstraintValidator) -> None:
        """Test that NaN values are detected."""
        import math

        response = {"value": float("nan")}
        result = validator.validate_response(response, "general")

        assert any("nan" in v.message.lower() or "invalid" in v.message.lower()
                   for v in result.violations)

    def test_validate_inf_value(self, validator: ConstraintValidator) -> None:
        """Test that Inf values are detected."""
        response = {"value": float("inf")}
        result = validator.validate_response(response, "general")

        assert any("inf" in v.message.lower() or "invalid" in v.message.lower()
                   for v in result.violations)


class TestConstraintViolation:
    """Test ConstraintViolation model."""

    def test_valid_violation(self) -> None:
        """Test creating valid violation."""
        violation = ConstraintViolation(
            constraint="quantity",
            value=-100,
            message="Quantity cannot be negative",
            severity="HIGH",
        )

        assert violation.constraint == "quantity"
        assert violation.value == -100
        assert violation.severity == "HIGH"

    def test_severity_values(self) -> None:
        """Test different severity levels."""
        for severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            violation = ConstraintViolation(
                constraint="test",
                value=None,
                message="Test",
                severity=severity,
            )
            assert violation.severity == severity


class TestConstraintValidationResult:
    """Test ConstraintValidationResult model."""

    def test_valid_result(self) -> None:
        """Test creating valid result."""
        result = ConstraintValidationResult(
            is_valid=True,
            violations=[],
            warnings=[],
        )

        assert result.is_valid is True
        assert len(result.violations) == 0

    def test_result_with_violations(self) -> None:
        """Test result with violations."""
        violation = ConstraintViolation(
            constraint="test",
            value=None,
            message="Test violation",
            severity="HIGH",
        )

        result = ConstraintValidationResult(
            is_valid=False,
            violations=[violation],
            warnings=["Warning message"],
        )

        assert result.is_valid is False
        assert len(result.violations) == 1
        assert len(result.warnings) == 1
