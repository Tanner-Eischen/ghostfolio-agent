"""Tests for transaction_categorize tool."""

import pytest

from src.tools.transaction_categorize import (
    Category,
    TransactionCategorizationResult,
    detect_patterns,
    generate_insights,
    transaction_categorize,
)


class TestDetectPatterns:
    """Tests for pattern detection."""

    def test_empty_orders(self):
        """Empty orders should return appropriate message."""
        patterns = detect_patterns([])
        assert patterns == ["No transactions to analyze"]

    def test_single_buy(self):
        """Single buy should show no significant patterns."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-15", "quantity": 10, "unitPrice": 180}
        ]
        patterns = detect_patterns(orders)
        assert "No significant patterns detected" in patterns[0]

    def test_dca_detection(self):
        """Should detect dollar-cost averaging pattern."""
        orders = [
            {"type": "BUY", "symbol": "VTI", "date": "2024-01-01", "quantity": 10, "unitPrice": 220},
            {"type": "BUY", "symbol": "VTI", "date": "2024-02-15", "quantity": 10, "unitPrice": 225},
            {"type": "BUY", "symbol": "VTI", "date": "2024-04-01", "quantity": 10, "unitPrice": 230},
            {"type": "BUY", "symbol": "VTI", "date": "2024-05-15", "quantity": 10, "unitPrice": 235},
        ]
        patterns = detect_patterns(orders)
        assert any("Dollar-cost averaging" in p for p in patterns)
        assert any("VTI" in p for p in patterns)

    def test_dividend_detection(self):
        """Should detect dividend income."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 100, "unitPrice": 180},
            {"type": "DIVIDEND", "symbol": "AAPL", "date": "2024-02-15", "quantity": 100, "unitPrice": 0.24},
            {"type": "DIVIDEND", "symbol": "MSFT", "date": "2024-03-15", "quantity": 50, "unitPrice": 0.75},
        ]
        patterns = detect_patterns(orders)
        assert any("Dividend income" in p for p in patterns)

    def test_frequent_trading_detection(self):
        """Should detect frequent trading."""
        # Create 15 orders over 30 days (high frequency)
        orders = [
            {"type": "BUY", "symbol": f"STOCK{i}", "date": f"2024-01-{(i % 28) + 1:02d}", "quantity": 10, "unitPrice": 100}
            for i in range(15)
        ]
        patterns = detect_patterns(orders)
        assert any("Frequent trading" in p for p in patterns)

    def test_long_term_holding_pattern(self):
        """Should detect long-term holding pattern."""
        # Need 3+ buy-only symbols (bought but never sold)
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unitPrice": 180},
            {"type": "BUY", "symbol": "MSFT", "date": "2024-01-15", "quantity": 5, "unitPrice": 400},
            {"type": "BUY", "symbol": "GOOGL", "date": "2024-02-01", "quantity": 8, "unitPrice": 150},
            {"type": "BUY", "symbol": "NVDA", "date": "2024-02-15", "quantity": 3, "unitPrice": 450},
            {"type": "SELL", "symbol": "AAPL", "date": "2024-03-01", "quantity": 10, "unitPrice": 190},
        ]
        patterns = detect_patterns(orders)
        assert any("Long-term holding" in p for p in patterns)

    def test_concentrated_buying(self):
        """Should detect concentrated buying in single symbol."""
        orders = [
            {"type": "BUY", "symbol": "NVDA", "date": "2024-01-01", "quantity": 10, "unitPrice": 400},
            {"type": "BUY", "symbol": "NVDA", "date": "2024-01-15", "quantity": 5, "unitPrice": 420},
            {"type": "BUY", "symbol": "NVDA", "date": "2024-02-01", "quantity": 8, "unitPrice": 450},
            {"type": "BUY", "symbol": "AAPL", "date": "2024-02-15", "quantity": 2, "unitPrice": 180},
        ]
        patterns = detect_patterns(orders)
        assert any("Concentrated buying" in p and "NVDA" in p for p in patterns)

    def test_rebalancing_detection(self):
        """Should detect potential rebalancing activity."""
        orders = [
            {"type": "SELL", "symbol": "AAPL", "date": "2024-01-15", "quantity": 20, "unitPrice": 185},
            {"type": "SELL", "symbol": "MSFT", "date": "2024-01-16", "quantity": 10, "unitPrice": 400},
            {"type": "BUY", "symbol": "BND", "date": "2024-01-20", "quantity": 50, "unitPrice": 72},
            {"type": "BUY", "symbol": "VTI", "date": "2024-01-22", "quantity": 30, "unitPrice": 230},
        ]
        patterns = detect_patterns(orders)
        assert any("rebalancing" in p.lower() for p in patterns)


class TestGenerateInsights:
    """Tests for insight generation."""

    def test_empty_orders(self):
        """Empty orders should return appropriate insight."""
        insights = generate_insights([], {}, {})
        assert "Add transactions" in insights[0]

    def test_buy_only_portfolio(self):
        """Should suggest rebalancing for buy-only portfolio."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unitPrice": 180},
            {"type": "BUY", "symbol": "MSFT", "date": "2024-02-01", "quantity": 5, "unitPrice": 400},
        ]
        categories = {"BUY": {"count": 2, "total": 3800}}
        insights = generate_insights(orders, categories, {"EQUITY": {"count": 2}})
        assert any("only buying" in i.lower() for i in insights)

    def test_single_asset_class(self):
        """Should suggest diversification for single asset class."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 10, "unitPrice": 180},
            {"type": "BUY", "symbol": "MSFT", "date": "2024-02-01", "quantity": 5, "unitPrice": 400},
        ]
        categories = {"BUY": {"count": 2}, "SELL": {"count": 0}}
        asset_classes = {"EQUITY": {"count": 2}}
        insights = generate_insights(orders, categories, asset_classes)
        assert any("single asset class" in i.lower() for i in insights)

    def test_dividend_insight(self):
        """Should provide dividend insight."""
        orders = [
            {"type": "BUY", "symbol": "AAPL", "date": "2024-01-01", "quantity": 100, "unitPrice": 180},
            {"type": "DIVIDEND", "symbol": "AAPL", "date": "2024-02-15", "quantity": 100, "unitPrice": 0.24},
        ]
        categories = {"BUY": {"count": 1}, "DIVIDEND": {"count": 1}}
        insights = generate_insights(orders, categories, {"EQUITY": {"count": 2}})
        assert any("dividend" in i.lower() for i in insights)

    def test_good_diversification(self):
        """Should recognize good asset class diversification."""
        orders = [
            {"type": "BUY", "symbol": "VTI", "date": "2024-01-01", "quantity": 10, "unitPrice": 230, "assetClass": "EQUITY"},
            {"type": "BUY", "symbol": "BND", "date": "2024-02-01", "quantity": 20, "unitPrice": 72, "assetClass": "FIXED_INCOME"},
            {"type": "BUY", "symbol": "BTC", "date": "2024-03-01", "quantity": 0.5, "unitPrice": 50000, "assetClass": "CRYPTOCURRENCY"},
            {"type": "BUY", "symbol": "GLD", "date": "2024-04-01", "quantity": 5, "unitPrice": 200, "assetClass": "COMMODITY"},
        ]
        categories = {"BUY": {"count": 4}, "SELL": {"count": 0}}
        asset_classes = {
            "EQUITY": {"count": 1},
            "FIXED_INCOME": {"count": 1},
            "CRYPTOCURRENCY": {"count": 1},
            "COMMODITY": {"count": 1},
        }
        insights = generate_insights(orders, categories, asset_classes)
        assert any("diversification" in i.lower() for i in insights)


class TestCategory:
    """Tests for Category model."""

    def test_valid_category(self):
        """Create a valid category."""
        cat = Category(
            name="Stocks",
            total=50000.00,
            count=25,
            percentage=45.5,
        )
        assert cat.name == "Stocks"
        assert cat.total == 50000.00
        assert cat.count == 25
        assert cat.percentage == 45.5

    def test_category_with_avg_size(self):
        """Create category with average transaction size."""
        cat = Category(
            name="Dividends",
            total=1200.00,
            count=12,
            percentage=20.0,
            avg_transaction_size=100.0,
        )
        assert cat.avg_transaction_size == 100.0


class TestTransactionCategorizationResult:
    """Tests for TransactionCategorizationResult model."""

    def test_valid_result(self):
        """Create a valid result."""
        result = TransactionCategorizationResult(
            categories=[
                Category(name="BUY", total=50000.00, count=20, percentage=80.0),
                Category(name="SELL", total=10000.00, count=5, percentage=20.0),
            ],
            patterns=["DCA detected for VTI"],
            insights=["Consider rebalancing"],
            total_transactions=25,
            total_value=60000.00,
            date_range="2024-01-01 to 2024-06-01",
        )
        assert result.total_transactions == 25
        assert len(result.categories) == 2
        assert len(result.patterns) == 1


class TestTransactionCategorizeTool:
    """Tests for the transaction_categorize tool."""

    @pytest.mark.asyncio
    async def test_basic_categorization(self):
        """Test basic transaction categorization."""
        result = await transaction_categorize.ainvoke({})

        assert isinstance(result, TransactionCategorizationResult)
        assert result.total_transactions > 0
        assert len(result.categories) > 0
        assert len(result.patterns) > 0
        assert len(result.insights) > 0

    @pytest.mark.asyncio
    async def test_categorization_with_date_filter(self):
        """Test categorization with date range filter."""
        result = await transaction_categorize.ainvoke({
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
        })

        assert isinstance(result, TransactionCategorizationResult)
        # Date range should reflect the filter
        assert result.date_range is not None

    @pytest.mark.asyncio
    async def test_categorization_with_account_filter(self):
        """Test categorization with account filter."""
        result = await transaction_categorize.ainvoke({
            "account_id": "acc1",
        })

        assert isinstance(result, TransactionCategorizationResult)
        assert result.account_filter == "acc1"

    @pytest.mark.asyncio
    async def test_categories_have_valid_percentages(self):
        """Categories should have percentages that sum to ~100%."""
        result = await transaction_categorize.ainvoke({})

        if result.total_transactions > 0:
            total_pct = sum(c.percentage for c in result.categories)
            # Allow small rounding errors
            assert 99 <= total_pct <= 101

    @pytest.mark.asyncio
    async def test_asset_class_breakdown(self):
        """Should include asset class breakdown."""
        result = await transaction_categorize.ainvoke({})

        # Mock data has multiple asset classes
        assert len(result.asset_class_breakdown) > 0
