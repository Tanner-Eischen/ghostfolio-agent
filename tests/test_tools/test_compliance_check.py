"""Tests for compliance_check tool."""

import pytest

from src.tools.compliance_check import (
    Violation,
    ComplianceCheckResult,
    check_wash_sale,
    check_pattern_day_trading,
    check_concentration_limit,
    compliance_check,
)


# ============================================================================
# Test Data Helpers
# ============================================================================


def create_wash_sale_orders() -> list[dict]:
    """Create orders that trigger a wash sale violation.

    Scenario:
    - Buy AAPL at $180 on 2024-01-01
    - Buy more AAPL at $175 on 2024-01-15 (avg cost now ~$178)
    - Sell AAPL at $160 on 2024-02-01 (loss)
    - Buy AAPL at $162 on 2024-02-15 (within 30 days of sell)
    """
    return [
        {
            "id": "buy1",
            "type": "BUY",
            "symbol": "AAPL",
            "date": "2024-01-01",
            "quantity": 10,
            "unitPrice": 180.00,
        },
        {
            "id": "buy2",
            "type": "BUY",
            "symbol": "AAPL",
            "date": "2024-01-15",
            "quantity": 10,
            "unitPrice": 175.00,
        },
        {
            "id": "sell1",
            "type": "SELL",
            "symbol": "AAPL",
            "date": "2024-02-01",
            "quantity": 20,
            "unitPrice": 160.00,  # Loss compared to avg cost of ~$177.50
        },
        {
            "id": "buy3",
            "type": "BUY",
            "symbol": "AAPL",
            "date": "2024-02-15",  # Within 30 days of sell
            "quantity": 15,
            "unitPrice": 162.00,
        },
    ]


def create_clean_wash_sale_orders() -> list[dict]:
    """Create orders that pass wash sale check (buy after 31 days)."""
    return [
        {
            "id": "buy1",
            "type": "BUY",
            "symbol": "AAPL",
            "date": "2023-12-01",  # More than 30 days before sell
            "quantity": 10,
            "unitPrice": 180.00,
        },
        {
            "id": "sell1",
            "type": "SELL",
            "symbol": "AAPL",
            "date": "2024-01-15",
            "quantity": 10,
            "unitPrice": 160.00,  # Loss
        },
        {
            "id": "buy2",
            "type": "BUY",
            "symbol": "AAPL",
            "date": "2024-02-20",  # 36 days after sell - past 30-day window
            "quantity": 10,
            "unitPrice": 165.00,
        },
    ]


def create_day_trade_orders(count: int = 4) -> list[dict]:
    """Create orders that trigger pattern day trading.

    Args:
        count: Number of day trades to create

    Creates day trades (buy + sell same day) over 5 days.
    """
    orders = []
    for i in range(count):
        day = 5 + i  # Start from Jan 5th
        symbol = f"STOCK{i}"
        orders.extend([
            {
                "id": f"buy_{i}",
                "type": "BUY",
                "symbol": symbol,
                "date": f"2024-01-{day:02d}",
                "quantity": 10,
                "unitPrice": 100.00,
            },
            {
                "id": f"sell_{i}",
                "type": "SELL",
                "symbol": symbol,
                "date": f"2024-01-{day:02d}",
                "quantity": 10,
                "unitPrice": 105.00,
            },
        ])
    return orders


def create_concentrated_holdings() -> list[dict]:
    """Create holdings with concentration violation (>25% in one position)."""
    return [
        {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "value": 50000.00,
            "allocationPct": 50.0,  # 50% - violation
        },
        {
            "symbol": "MSFT",
            "name": "Microsoft",
            "value": 25000.00,
            "allocationPct": 25.0,
        },
        {
            "symbol": "GOOGL",
            "name": "Alphabet",
            "value": 25000.00,
            "allocationPct": 25.0,
        },
    ]


def create_balanced_holdings() -> list[dict]:
    """Create well-diversified holdings (no concentration issues)."""
    return [
        {"symbol": "VTI", "name": "Vanguard Total Market", "value": 25000.00, "allocationPct": 20.0},
        {"symbol": "VXUS", "name": "Vanguard Intl", "value": 20000.00, "allocationPct": 16.0},
        {"symbol": "BND", "name": "Vanguard Bonds", "value": 25000.00, "allocationPct": 20.0},
        {"symbol": "AAPL", "name": "Apple", "value": 15000.00, "allocationPct": 12.0},
        {"symbol": "MSFT", "name": "Microsoft", "value": 15000.00, "allocationPct": 12.0},
        {"symbol": "BTC", "name": "Bitcoin", "value": 25000.00, "allocationPct": 20.0},
    ]


# ============================================================================
# Wash Sale Tests
# ============================================================================


class TestCheckWashSale:
    """Tests for wash sale detection."""

    def test_empty_orders(self):
        """Empty orders should return no violations."""
        violations, warnings, recommendations = check_wash_sale([])
        assert violations == []
        assert warnings == []
        assert recommendations == []

    def test_no_sells(self):
        """Orders with only buys should have no violations."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unitPrice": 180},
            {"type": "BUY", "symbol": "AAPL", "date": "2024-02-01", "quantity": 10, "unitPrice": 175},
        ]
        violations, warnings, recommendations = check_wash_sale(orders)
        assert violations == []

    def test_sell_at_gain_no_violation(self):
        """Sell at gain should not trigger wash sale."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unitPrice": 150},
            {"type": "SELL", "symbol": "AAPL", "date": "2024-01-15", "quantity": 10, "unitPrice": 180},
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-25", "quantity": 10, "unitPrice": 175},
        ]
        violations, warnings, recommendations = check_wash_sale(orders)
        assert violations == []

    def test_wash_sale_detected(self):
        """Should detect wash sale when buying within 30 days of loss sale."""
        orders = create_wash_sale_orders()
        violations, warnings, recommendations = check_wash_sale(orders)

        assert len(violations) >= 1
        assert violations[0].rule == "wash_sale"
        assert violations[0].severity == "high"
        assert violations[0].symbol == "AAPL"
        assert "Wash sale detected" in violations[0].description
        assert len(recommendations) >= 1
        assert "31 days" in recommendations[0]

    def test_wash_sale_pass_after_31_days(self):
        """Should not flag wash sale if repurchase is after 31 days."""
        orders = create_clean_wash_sale_orders()
        violations, warnings, recommendations = check_wash_sale(orders)

        assert violations == []

    def test_wash_sale_specific_symbol_filter(self):
        """Should only check specified symbol."""
        orders = [
            # AAPL - has wash sale
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unitPrice": 180},
            {"type": "SELL", "symbol": "AAPL", "date": "2024-01-15", "quantity": 10, "unitPrice": 160},
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-25", "quantity": 10, "unitPrice": 162},
            # MSFT - no wash sale
            {"type": "BUY", "symbol": "MSFT", "date": "2024-01-01", "quantity": 5, "unitPrice": 400},
        ]
        violations, _, _ = check_wash_sale(orders, symbol="MSFT")
        assert violations == []

    def test_wash_sale_with_unit_price_alias(self):
        """Should handle both unitPrice and unit_price keys."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unit_price": 180},
            {"type": "SELL", "symbol": "AAPL", "date": "2024-01-15", "quantity": 10, "unit_price": 160},
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-25", "quantity": 10, "unit_price": 162},
        ]
        violations, _, _ = check_wash_sale(orders)
        assert len(violations) >= 1


# ============================================================================
# Pattern Day Trading Tests
# ============================================================================


class TestCheckPatternDayTrading:
    """Tests for pattern day trading detection."""

    def test_empty_orders(self):
        """Empty orders should return no violations."""
        violations, warnings, recommendations = check_pattern_day_trading([], 20000)
        assert violations == []

    def test_account_over_threshold_exempt(self):
        """Account over $25,000 should be exempt from PDT rule."""
        orders = create_day_trade_orders(5)
        violations, warnings, recommendations = check_pattern_day_trading(
            orders, account_value=30000.00
        )

        assert violations == []
        assert any("exceeds $25,000" in w for w in warnings)

    def test_no_day_trades(self):
        """Orders without same-day buy/sell should pass."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unitPrice": 180},
            {"type": "SELL", "symbol": "AAPL", "date": "2024-01-15", "quantity": 10, "unitPrice": 190},
            {"type": "BUY", "symbol": "MSFT", "date": "2024-01-02", "quantity": 5, "unitPrice": 400},
        ]
        violations, _, _ = check_pattern_day_trading(orders, account_value=20000)
        assert violations == []

    def test_pattern_day_trading_detected(self):
        """Should detect pattern with 4+ day trades in 5 days."""
        orders = create_day_trade_orders(4)
        violations, warnings, recommendations = check_pattern_day_trading(
            orders, account_value=20000.00
        )

        assert len(violations) >= 1
        assert violations[0].rule == "pattern_day_trading"
        assert violations[0].severity == "high"
        assert "Pattern day trading detected" in violations[0].description
        assert len(recommendations) >= 1
        assert "$25,000" in recommendations[0]

    def test_approaching_pdt_limit_warning(self):
        """Should warn when at 3 day trades (limit is 3)."""
        orders = create_day_trade_orders(3)
        violations, warnings, recommendations = check_pattern_day_trading(
            orders, account_value=20000.00
        )

        # 3 trades is at the limit, not over it
        # The check reports violation for > 3, warning for == 3
        assert any("Approaching" in w or "limit" in w.lower() for w in warnings)

    def test_fewer_than_limit_day_trades(self):
        """1-2 day trades should not trigger violation."""
        orders = create_day_trade_orders(2)
        violations, _, _ = check_pattern_day_trading(orders, account_value=20000.00)
        assert violations == []

    def test_symbol_filter(self):
        """Should filter by symbol if provided."""
        orders = create_day_trade_orders(4)
        # Filter to a symbol that isn't in the day trades
        violations, _, _ = check_pattern_day_trading(
            orders, account_value=20000.00, symbol="NOTRADE"
        )
        assert violations == []


# ============================================================================
# Concentration Limit Tests
# ============================================================================


class TestCheckConcentrationLimit:
    """Tests for concentration limit detection."""

    def test_empty_holdings(self):
        """Empty holdings should return no violations."""
        violations, warnings, recommendations = check_concentration_limit([])
        assert violations == []

    def test_concentration_violation_detected(self):
        """Should detect holdings over 25% allocation."""
        holdings = create_concentrated_holdings()
        violations, warnings, recommendations = check_concentration_limit(holdings)

        assert len(violations) >= 1
        assert violations[0].rule == "concentration_limit"
        assert violations[0].severity == "medium"
        assert violations[0].symbol == "AAPL"
        assert "Concentration risk" in violations[0].description
        assert len(recommendations) >= 1
        assert "Reduce" in recommendations[0]

    def test_balanced_portfolio_passes(self):
        """Well-diversified portfolio should pass."""
        holdings = create_balanced_holdings()
        violations, warnings, recommendations = check_concentration_limit(holdings)

        assert violations == []

    def test_approaching_limit_warning(self):
        """Should warn when allocation approaches 25% (>20%)."""
        holdings = [
            {"symbol": "AAPL", "name": "Apple", "value": 22000.00, "allocationPct": 22.0},
            {"symbol": "MSFT", "name": "Microsoft", "value": 20000.00, "allocationPct": 20.0},
            {"symbol": "GOOGL", "name": "Alphabet", "value": 58000.00, "allocationPct": 58.0},
        ]
        # GOOGL at 58% is a violation, AAPL at 22% should trigger warning
        violations, warnings, _ = check_concentration_limit(holdings)
        assert any("approaching" in w.lower() for w in warnings)

    def test_symbol_filter(self):
        """Should filter to specific symbol."""
        holdings = create_concentrated_holdings()
        violations, _, _ = check_concentration_limit(holdings, symbol="MSFT")
        # MSFT is at exactly 25%, not over
        assert violations == []

    def test_handles_alternate_key_names(self):
        """Should handle both allocationPct and allocation_pct."""
        holdings = [
            {"symbol": "AAPL", "name": "Apple", "value": 50000.00, "allocation_pct": 50.0},
        ]
        violations, _, _ = check_concentration_limit(holdings)
        assert len(violations) >= 1


# ============================================================================
# Violation Model Tests
# ============================================================================


class TestViolation:
    """Tests for Violation model."""

    def test_valid_violation(self):
        """Create a valid violation."""
        v = Violation(
            rule="wash_sale",
            severity="high",
            description="Wash sale detected",
            symbol="AAPL",
            details={"days": 15},
        )
        assert v.rule == "wash_sale"
        assert v.severity == "high"
        assert v.symbol == "AAPL"

    def test_violation_without_optional_fields(self):
        """Violation without optional fields should work."""
        v = Violation(
            rule="concentration_limit",
            severity="medium",
            description="Over 25%",
        )
        assert v.symbol is None
        assert v.details is None


# ============================================================================
# ComplianceCheckResult Tests
# ============================================================================


class TestComplianceCheckResult:
    """Tests for ComplianceCheckResult model."""

    def test_valid_result(self):
        """Create a valid result."""
        result = ComplianceCheckResult(
            compliant=True,
            violations=[],
            warnings=[],
            recommendations=[],
            checked_rules=["wash_sale"],
            timestamp="2024-02-24T12:00:00",
        )
        assert result.compliant is True
        assert len(result.checked_rules) == 1

    def test_non_compliant_with_high_severity(self):
        """Result with high severity violation should be non-compliant."""
        result = ComplianceCheckResult(
            compliant=False,
            violations=[
                Violation(rule="wash_sale", severity="high", description="Test")
            ],
            warnings=[],
            recommendations=["Wait 31 days"],
            checked_rules=["wash_sale"],
            timestamp="2024-02-24T12:00:00",
        )
        assert result.compliant is False


# ============================================================================
# Tool Integration Tests
# ============================================================================


class TestComplianceCheckTool:
    """Tests for the compliance_check tool."""

    @pytest.mark.asyncio
    async def test_basic_compliance_check(self):
        """Test basic compliance check returns valid result."""
        result = await compliance_check.ainvoke({})

        assert isinstance(result, ComplianceCheckResult)
        assert isinstance(result.compliant, bool)
        assert len(result.checked_rules) > 0
        assert result.timestamp is not None

    @pytest.mark.asyncio
    async def test_check_specific_rule(self):
        """Test checking only specific rules."""
        result = await compliance_check.ainvoke({
            "rules": ["concentration_limit"]
        })

        assert result.checked_rules == ["concentration_limit"]

    @pytest.mark.asyncio
    async def test_check_multiple_rules(self):
        """Test checking multiple rules."""
        result = await compliance_check.ainvoke({
            "rules": ["wash_sale", "concentration_limit"]
        })

        assert "wash_sale" in result.checked_rules
        assert "concentration_limit" in result.checked_rules
        assert "pattern_day_trading" not in result.checked_rules

    @pytest.mark.asyncio
    async def test_invalid_rule_ignored(self):
        """Invalid rules should be ignored."""
        result = await compliance_check.ainvoke({
            "rules": ["invalid_rule", "concentration_limit"]
        })

        assert "concentration_limit" in result.checked_rules
        assert "invalid_rule" not in result.checked_rules

    @pytest.mark.asyncio
    async def test_no_valid_rules(self):
        """When no valid rules specified, should return appropriate result."""
        result = await compliance_check.ainvoke({
            "rules": ["invalid1", "invalid2"]
        })

        assert result.compliant is True
        assert len(result.warnings) > 0
        assert any("valid rules" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_with_symbol_filter(self):
        """Test filtering by symbol."""
        result = await compliance_check.ainvoke({
            "symbol": "AAPL"
        })

        # Should only check AAPL-related compliance
        assert isinstance(result, ComplianceCheckResult)

    @pytest.mark.asyncio
    async def test_with_account_filter(self):
        """Test filtering by account."""
        result = await compliance_check.ainvoke({
            "account_id": "acc1"
        })

        assert result.account_filter == "acc1"

    @pytest.mark.asyncio
    async def test_recommendations_deduplicated(self):
        """Recommendations should be deduplicated."""
        result = await compliance_check.ainvoke({})

        # Check no duplicate recommendations
        assert len(result.recommendations) == len(set(result.recommendations))

    @pytest.mark.asyncio
    async def test_compliant_determined_by_severity(self):
        """Compliant status should be based on violation severity."""
        # The mock data should produce consistent results
        result = await compliance_check.ainvoke({})

        has_blocking = any(v.severity in ("high", "critical") for v in result.violations)
        assert result.compliant == (not has_blocking)
