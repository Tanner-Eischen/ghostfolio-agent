"""Transaction Categorization Tool - Classify and analyze transaction patterns."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from langchain_core.tools import tool
from langsmith import traceable
from pydantic import BaseModel, Field

from src.api.ghostfolio import GhostfolioClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Input/Output Models
# ============================================================================


class TransactionCategorizeInput(BaseModel):
    """Input schema for transaction_categorize tool."""

    start_date: str | None = Field(
        default=None,
        description="Start date for analysis (ISO format: YYYY-MM-DD)",
    )
    end_date: str | None = Field(
        default=None,
        description="End date for analysis (ISO format: YYYY-MM-DD)",
    )
    account_id: str | None = Field(
        default=None,
        description="Optional specific account to analyze",
    )


class Category(BaseModel):
    """A transaction category with statistics."""

    name: str = Field(description="Category name (e.g., Stocks, Dividends)")
    total: float = Field(description="Total value in this category")
    count: int = Field(description="Number of transactions")
    percentage: float = Field(description="Percentage of total transactions")
    avg_transaction_size: float = Field(default=0.0, description="Average transaction size")


class TransactionCategorizationResult(BaseModel):
    """Result of transaction categorization."""

    categories: list[Category] = Field(description="Transaction categories by type")
    asset_class_breakdown: list[Category] = Field(
        default_factory=list,
        description="Breakdown by asset class (stocks, ETFs, crypto, etc.)",
    )
    patterns: list[str] = Field(description="Identified transaction patterns")
    insights: list[str] = Field(description="Actionable insights from the analysis")
    total_transactions: int = Field(description="Total number of transactions analyzed")
    total_value: float = Field(description="Total value of all transactions")
    date_range: str = Field(description="Date range of analyzed transactions")
    account_filter: str | None = Field(
        default=None, description="Account ID if filtered to specific account"
    )


# ============================================================================
# Pattern Detection
# ============================================================================


@traceable(name="detect_transaction_patterns", run_type="tool")
def detect_patterns(orders: list[dict[str, Any]]) -> list[str]:
    """Detect transaction patterns from order history.

    Args:
        orders: List of order dictionaries

    Returns:
        List of detected pattern descriptions
    """
    patterns = []

    if not orders:
        return ["No transactions to analyze"]

    # Sort orders by date
    sorted_orders = sorted(orders, key=lambda x: x.get("date", ""))

    # 1. Check for Dollar Cost Averaging (DCA)
    # Pattern: Regular purchases of the same symbol over time
    symbol_purchase_dates: dict[str, list[str]] = defaultdict(list)
    for order in orders:
        if order.get("type") == "BUY":
            symbol = order.get("symbol", "")
            date = order.get("date", "")
            if symbol and date:
                symbol_purchase_dates[symbol].append(date)

    dca_symbols = []
    for symbol, dates in symbol_purchase_dates.items():
        if len(dates) >= 3:
            # Check if purchases are spread over time (at least 2 weeks apart)
            date_objs = sorted([datetime.fromisoformat(d) for d in dates])
            time_spans = [(date_objs[i + 1] - date_objs[i]).days for i in range(len(date_objs) - 1)]
            avg_span = sum(time_spans) / len(time_spans) if time_spans else 0
            if avg_span >= 14:  # Average 2+ weeks between purchases
                dca_symbols.append(symbol)

    if dca_symbols:
        patterns.append(f"Dollar-cost averaging (DCA) detected for: {', '.join(dca_symbols)}")

    # 2. Check for dividend reinvestment
    dividend_symbols = set()
    for order in orders:
        if order.get("type") == "DIVIDEND":
            dividend_symbols.add(order.get("symbol", ""))

    if dividend_symbols:
        patterns.append(f"Dividend income from: {', '.join(sorted(dividend_symbols))}")

    # 3. Check for rebalancing activity
    # Pattern: Sells followed by buys of different assets within short period
    sells = [o for o in orders if o.get("type") == "SELL"]
    buys = [o for o in orders if o.get("type") == "BUY"]

    if len(sells) >= 2 and len(buys) >= 2:
        # Check if there's selling and buying in same time period
        sell_dates = [datetime.fromisoformat(o.get("date", "2000-01-01")) for o in sells]
        buy_dates = [datetime.fromisoformat(o.get("date", "2000-01-01")) for o in buys]

        if sell_dates and buy_dates:
            recent_activity = (
                max(sell_dates) - min(buy_dates) < timedelta(days=30)
                or max(buy_dates) - min(sell_dates) < timedelta(days=30)
            )
            if recent_activity:
                patterns.append("Potential portfolio rebalancing activity detected")

    # 4. Check for frequent trading
    if len(orders) >= 10:
        date_range_days = _calculate_date_range_days(sorted_orders)
        if date_range_days > 0:
            trades_per_month = (len(orders) / date_range_days) * 30
            if trades_per_month > 8:
                patterns.append(f"Frequent trading: ~{trades_per_month:.1f} trades/month")

    # 5. Check for concentrated buying
    buy_symbols = [o.get("symbol") for o in buys]
    if buy_symbols:
        symbol_counts = defaultdict(int)
        for s in buy_symbols:
            symbol_counts[s] += 1

        top_symbol, top_count = max(symbol_counts.items(), key=lambda x: x[1])
        if top_count >= 3 and top_count / len(buys) > 0.5:
            patterns.append(f"Concentrated buying in {top_symbol} ({top_count} purchases)")

    # 6. Long-term holding pattern
    if sells:
        sell_symbols = {o.get("symbol") for o in sells}
        buy_only_symbols = set(buy_symbols) - sell_symbols
        if len(buy_only_symbols) >= 3:
            patterns.append("Long-term holding pattern: multiple positions never sold")

    if not patterns:
        patterns.append("No significant patterns detected in transaction history")

    return patterns


@traceable(name="generate_transaction_insights", run_type="tool")
def generate_insights(
    orders: list[dict[str, Any]],
    categories: dict[str, dict[str, Any]],
    asset_classes: dict[str, dict[str, Any]],
) -> list[str]:
    """Generate actionable insights from transaction analysis.

    Args:
        orders: List of order dictionaries
        categories: Category statistics by transaction type
        asset_classes: Statistics by asset class

    Returns:
        List of actionable insights
    """
    insights = []

    if not orders:
        return ["Add transactions to get personalized insights"]

    # 1. Transaction type insights
    buy_count = categories.get("BUY", {}).get("count", 0)
    sell_count = categories.get("SELL", {}).get("count", 0)

    if buy_count > 0 and sell_count == 0:
        insights.append("You're only buying - consider if rebalancing or tax-loss harvesting might be beneficial")
    elif sell_count > buy_count:
        insights.append("More sells than buys - ensure this aligns with your investment strategy")

    # 2. Diversification insights from asset classes
    if len(asset_classes) == 1:
        insights.append("All transactions in single asset class - consider diversifying across asset types")
    elif len(asset_classes) >= 4:
        insights.append("Good asset class diversification in your transactions")

    # 3. Fee awareness
    total_fees = sum(o.get("fee", 0) for o in orders)
    if total_fees > 0:
        avg_fee_pct = (total_fees / sum(o.get("quantity", 0) * o.get("unitPrice", o.get("unit_price", 0)) for o in orders)) * 100 if orders else 0
        if avg_fee_pct > 1:
            insights.append(f"Average transaction fees: {avg_fee_pct:.2f}% - consider lower-fee alternatives")

    # 4. Dividend insight
    dividend_count = categories.get("DIVIDEND", {}).get("count", 0)
    if dividend_count > 0:
        insights.append(f"Received {dividend_count} dividend payments - reinvesting can compound returns")

    # 5. Trading frequency insight
    sorted_orders = sorted(orders, key=lambda x: x.get("date", ""))
    date_range_days = _calculate_date_range_days(sorted_orders)

    if date_range_days > 0 and len(orders) > 0:
        trades_per_month = (len(orders) / date_range_days) * 30
        if trades_per_month > 10:
            insights.append("High trading frequency may impact returns through fees and taxes")
        elif trades_per_month < 2:
            insights.append("Low trading frequency suggests a passive investment approach")

    # 6. Time-based insight
    if orders:
        recent_orders = [
            o
            for o in orders
            if datetime.fromisoformat(o.get("date", "2000-01-01"))
            > datetime.now() - timedelta(days=30)
        ]
        if len(recent_orders) == 0:
            insights.append("No transactions in the last 30 days - portfolio is stable")
        elif len(recent_orders) > 5:
            insights.append(f"Active month: {len(recent_orders)} transactions in the last 30 days")

    if not insights:
        insights.append("Continue monitoring your transaction patterns for optimization opportunities")

    return insights


def _calculate_date_range_days(sorted_orders: list[dict[str, Any]]) -> int:
    """Calculate the date range in days from sorted orders."""
    if not sorted_orders:
        return 0

    try:
        first_date = datetime.fromisoformat(sorted_orders[0].get("date", ""))
        last_date = datetime.fromisoformat(sorted_orders[-1].get("date", ""))
        return max(1, (last_date - first_date).days)
    except (ValueError, TypeError):
        return 0


# ============================================================================
# Tool Implementation
# ============================================================================


@tool
async def transaction_categorize(
    start_date: str | None = None,
    end_date: str | None = None,
    account_id: str | None = None,
) -> TransactionCategorizationResult:
    """Categorize transactions and identify spending/investment patterns.

    Use this tool when the user asks about:
    - What types of transactions they've made
    - Patterns in their trading activity
    - Breakdown of their transaction history
    - Insights about their investment behavior

    Args:
        start_date: Optional start date for analysis (ISO format)
        end_date: Optional end date for analysis (ISO format)
        account_id: Optional specific account to analyze

    Returns:
        TransactionCategorizationResult with categories, patterns, and insights
    """
    logger.info(
        f"Categorizing transactions (account={account_id}, start={start_date}, end={end_date})"
    )

    async with GhostfolioClient() as client:
        try:
            # Fetch orders with filters
            orders = await client.get_orders(
                account_id=account_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Calculate date range string
            if orders:
                sorted_orders = sorted(orders, key=lambda x: x.get("date", ""))
                first_date = sorted_orders[0].get("date", "Unknown")
                last_date = sorted_orders[-1].get("date", "Unknown")
                date_range = f"{first_date} to {last_date}"
            else:
                date_range = "No transactions"

            # Categorize by transaction type
            type_categories: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"total": 0.0, "count": 0}
            )
            asset_classes: dict[str, dict[str, Any]] = defaultdict(
                lambda: {"total": 0.0, "count": 0}
            )

            total_value = 0.0

            for order in orders:
                order_type = order.get("type", "UNKNOWN")
                quantity = float(order.get("quantity", 0))
                unit_price = float(order.get("unitPrice", order.get("unit_price", 0)))
                value = quantity * unit_price

                # Categorize by type
                type_categories[order_type]["total"] += value
                type_categories[order_type]["count"] += 1

                # Track total
                total_value += value

                # Categorize by asset class (from mock data or default)
                # In real implementation, this would come from the API
                asset_class = order.get("assetClass", "EQUITY")
                asset_classes[asset_class]["total"] += value
                asset_classes[asset_class]["count"] += 1

            # Build category list
            total_transactions = len(orders)
            categories = []
            for cat_name, cat_data in sorted(
                type_categories.items(), key=lambda x: x[1]["total"], reverse=True
            ):
                percentage = (cat_data["count"] / total_transactions * 100) if total_transactions > 0 else 0
                avg_size = cat_data["total"] / cat_data["count"] if cat_data["count"] > 0 else 0
                categories.append(
                    Category(
                        name=cat_name.title(),
                        total=round(cat_data["total"], 2),
                        count=cat_data["count"],
                        percentage=round(percentage, 1),
                        avg_transaction_size=round(avg_size, 2),
                    )
                )

            # Build asset class breakdown
            asset_breakdown = []
            for class_name, class_data in sorted(
                asset_classes.items(), key=lambda x: x[1]["total"], reverse=True
            ):
                percentage = (class_data["count"] / total_transactions * 100) if total_transactions > 0 else 0
                avg_size = class_data["total"] / class_data["count"] if class_data["count"] > 0 else 0
                asset_breakdown.append(
                    Category(
                        name=class_name.replace("_", " ").title(),
                        total=round(class_data["total"], 2),
                        count=class_data["count"],
                        percentage=round(percentage, 1),
                        avg_transaction_size=round(avg_size, 2),
                    )
                )

            # Detect patterns
            patterns = detect_patterns(orders)

            # Generate insights
            insights = generate_insights(orders, type_categories, asset_classes)

            result = TransactionCategorizationResult(
                categories=categories,
                asset_class_breakdown=asset_breakdown,
                patterns=patterns,
                insights=insights,
                total_transactions=total_transactions,
                total_value=round(total_value, 2),
                date_range=date_range,
                account_filter=account_id,
            )

            logger.info(
                f"Transaction categorization complete: {total_transactions} transactions, "
                f"{len(categories)} categories, {len(patterns)} patterns"
            )

            return result

        except Exception as e:
            logger.error(f"Transaction categorization failed: {e}")
            raise


# ============================================================================
# Tool Export
# ============================================================================

__all__ = ["transaction_categorize", "TransactionCategorizationResult", "Category"]
