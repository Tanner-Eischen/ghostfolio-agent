"""Compliance Check Tool - Validate transactions against financial compliance rules."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.api.ghostfolio import GhostfolioClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Input/Output Models
# ============================================================================


class ComplianceCheckInput(BaseModel):
    """Input schema for compliance_check tool."""

    symbol: str | None = Field(
        default=None,
        description="Optional specific symbol to check. If not provided, checks all symbols.",
    )
    rules: list[str] | None = Field(
        default=None,
        description="Optional list of rules to check. Options: wash_sale, pattern_day_trading, concentration_limit. Default: all rules.",
    )
    account_id: str | None = Field(
        default=None,
        description="Optional account ID to filter transactions.",
    )


class Violation(BaseModel):
    """A compliance violation."""

    rule: str = Field(description="The rule that was violated")
    severity: Literal["low", "medium", "high", "critical"] = Field(
        description="Severity level of the violation"
    )
    description: str = Field(description="Detailed description of the violation")
    symbol: str | None = Field(default=None, description="Symbol involved in the violation")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional details about the violation"
    )


class ComplianceCheckResult(BaseModel):
    """Result of compliance check."""

    compliant: bool = Field(
        description="Whether the portfolio/transactions are compliant (no high/critical violations)"
    )
    violations: list[Violation] = Field(
        default_factory=list,
        description="List of compliance violations found",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="List of potential issues (advisory warnings)",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommended actions to resolve issues",
    )
    checked_rules: list[str] = Field(
        description="List of rules that were checked",
    )
    timestamp: str = Field(
        description="Timestamp of the compliance check",
    )
    account_filter: str | None = Field(
        default=None, description="Account ID if filtered to specific account"
    )


# ============================================================================
# Constants
# ============================================================================

# Valid compliance rules
VALID_RULES = {"wash_sale", "pattern_day_trading", "concentration_limit"}

# PDT threshold
PDT_DAY_TRADE_LIMIT = 3
PDT_LOOKBACK_DAYS = 5
PDT_ACCOUNT_THRESHOLD = 25000.00

# Wash sale window
WASH_SALE_DAYS = 30

# Concentration limit
CONCENTRATION_LIMIT_PCT = 25.0


# ============================================================================
# Rule Implementations
# ============================================================================


def check_wash_sale(
    orders: list[dict[str, Any]],
    symbol: str | None = None,
) -> tuple[list[Violation], list[str], list[str]]:
    """Check for wash sale violations.

    A wash sale occurs when you sell a security at a loss and buy the same
    or substantially identical security within 30 days before or after the sale.

    Args:
        orders: List of order dictionaries
        symbol: Optional specific symbol to check

    Returns:
        Tuple of (violations, warnings, recommendations)
    """
    violations = []
    warnings = []
    recommendations = []

    if not orders:
        return violations, warnings, recommendations

    # Group orders by symbol
    orders_by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for order in orders:
        order_symbol = order.get("symbol", "")
        if order_symbol:
            orders_by_symbol[order_symbol].append(order)

    # Filter to specific symbol if provided
    symbols_to_check = [symbol] if symbol else list(orders_by_symbol.keys())

    for sym in symbols_to_check:
        if sym not in orders_by_symbol:
            continue

        symbol_orders = sorted(
            orders_by_symbol[sym],
            key=lambda x: x.get("date", ""),
        )

        # Find all sells and their dates
        sells = [o for o in symbol_orders if o.get("type") == "SELL"]
        buys = [o for o in symbol_orders if o.get("type") == "BUY"]

        for sell in sells:
            try:
                sell_date = datetime.fromisoformat(sell.get("date", ""))
            except (ValueError, TypeError):
                continue

            sell_price = float(sell.get("unitPrice", sell.get("unit_price", 0)))
            sell_quantity = float(sell.get("quantity", 0))

            # Find the average purchase price to determine if this is a loss
            # Look for buys before this sell
            prior_buys = [
                b
                for b in buys
                if datetime.fromisoformat(b.get("date", "")) < sell_date
            ]

            if not prior_buys:
                continue

            # Calculate average cost basis
            total_cost = sum(
                float(b.get("quantity", 0)) * float(b.get("unitPrice", b.get("unit_price", 0)))
                for b in prior_buys
            )
            total_qty = sum(float(b.get("quantity", 0)) for b in prior_buys)
            avg_cost = total_cost / total_qty if total_qty > 0 else 0

            # Check if sell is at a loss
            is_loss = sell_price < avg_cost

            if not is_loss:
                continue

            # Look for buys within 30 days before or after the sell
            wash_start = sell_date - timedelta(days=WASH_SALE_DAYS)
            wash_end = sell_date + timedelta(days=WASH_SALE_DAYS)

            wash_buys = [
                b
                for b in buys
                if wash_start <= datetime.fromisoformat(b.get("date", "")) <= wash_end
                and datetime.fromisoformat(b.get("date", "")) != sell_date
            ]

            if wash_buys:
                # Found potential wash sale
                for wash_buy in wash_buys:
                    buy_date = datetime.fromisoformat(wash_buy.get("date", ""))
                    days_diff = abs((buy_date - sell_date).days)

                    violations.append(
                        Violation(
                            rule="wash_sale",
                            severity="high",
                            description=(
                                f"Wash sale detected: Sold {sym} at a loss on {sell_date.strftime('%Y-%m-%d')} "
                                f"and repurchased on {buy_date.strftime('%Y-%m-%d')} ({days_diff} days apart). "
                                f"Loss of ${(avg_cost - sell_price) * sell_quantity:.2f} may be disallowed."
                            ),
                            symbol=sym,
                            details={
                                "sell_date": sell_date.strftime("%Y-%m-%d"),
                                "buy_date": buy_date.strftime("%Y-%m-%d"),
                                "days_apart": days_diff,
                                "loss_amount": round((avg_cost - sell_price) * sell_quantity, 2),
                            },
                        )
                    )

                recommendations.append(
                    f"Wait 31 days before repurchasing {sym} to avoid wash sale rule"
                )

    return violations, warnings, recommendations


def check_pattern_day_trading(
    orders: list[dict[str, Any]],
    account_value: float = 0.0,
    symbol: str | None = None,
) -> tuple[list[Violation], list[str], list[str]]:
    """Check for pattern day trading violations.

    Pattern day trading occurs when you execute 4 or more day trades
    (buy and sell same security same day) within 5 business days,
    and this only applies if account value is under $25,000.

    Args:
        orders: List of order dictionaries
        account_value: Current account value
        symbol: Optional specific symbol to check

    Returns:
        Tuple of (violations, warnings, recommendations)
    """
    violations = []
    warnings = []
    recommendations = []

    if not orders:
        return violations, warnings, recommendations

    # PDT rule only applies to accounts under $25,000
    if account_value >= PDT_ACCOUNT_THRESHOLD:
        warnings.append(
            f"Account value (${account_value:,.2f}) exceeds $25,000 - PDT rule does not apply"
        )
        return violations, warnings, recommendations

    # Group orders by date and symbol to find day trades
    orders_by_date: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for order in orders:
        if symbol and order.get("symbol") != symbol:
            continue
        order_date = order.get("date", "")
        order_symbol = order.get("symbol", "")
        if order_date and order_symbol:
            orders_by_date[order_date][order_symbol].append(order)

    # Find day trades (same symbol bought and sold on same day)
    day_trades: list[dict[str, Any]] = []

    for date, symbols in orders_by_date.items():
        for sym, day_orders in symbols.items():
            has_buy = any(o.get("type") == "BUY" for o in day_orders)
            has_sell = any(o.get("type") == "SELL" for o in day_orders)

            if has_buy and has_sell:
                buy_order = next(o for o in day_orders if o.get("type") == "BUY")
                sell_order = next(o for o in day_orders if o.get("type") == "SELL")
                day_trades.append({
                    "date": date,
                    "symbol": sym,
                    "buy_order": buy_order,
                    "sell_order": sell_order,
                })

    if not day_trades:
        return violations, warnings, recommendations

    # Sort day trades by date
    day_trades.sort(key=lambda x: x.get("date", ""))

    # Check rolling 5-day windows for pattern
    for i in range(len(day_trades)):
        current_date = datetime.fromisoformat(day_trades[i].get("date", ""))
        window_end = current_date + timedelta(days=PDT_LOOKBACK_DAYS)

        # Count day trades in window
        window_trades = [
            dt
            for dt in day_trades
            if current_date <= datetime.fromisoformat(dt.get("date", "")) <= window_end
        ]

        trade_count = len(window_trades)

        if trade_count > PDT_DAY_TRADE_LIMIT:
            # Pattern day trading detected
            symbols_traded = list({dt.get("symbol") for dt in window_trades})
            trade_dates = [dt.get("date") for dt in window_trades]

            violations.append(
                Violation(
                    rule="pattern_day_trading",
                    severity="high",
                    description=(
                        f"Pattern day trading detected: {trade_count} day trades within 5 days. "
                        f"Account value (${account_value:,.2f}) is below $25,000 threshold. "
                        f"Trading may be restricted."
                    ),
                    symbol=None,
                    details={
                        "day_trade_count": trade_count,
                        "window_start": current_date.strftime("%Y-%m-%d"),
                        "window_end": window_end.strftime("%Y-%m-%d"),
                        "symbols": symbols_traded,
                        "dates": trade_dates,
                    },
                )
            )

            recommendations.append(
                "Maintain account balance above $25,000 or limit day trades to 3 per week"
            )
            break  # Only report once

        elif trade_count == PDT_DAY_TRADE_LIMIT:
            # Warning: approaching limit
            warnings.append(
                f"Approaching pattern day trading limit: {trade_count} day trades in 5-day period. "
                f"One more day trade will trigger PDT restrictions."
            )

    return violations, warnings, recommendations


def check_concentration_limit(
    holdings: list[dict[str, Any]],
    symbol: str | None = None,
) -> tuple[list[Violation], list[str], list[str]]:
    """Check for concentration limit violations.

    A single position should not exceed 25% of portfolio value
    to maintain proper diversification.

    Args:
        holdings: List of holding dictionaries with allocation percentages
        symbol: Optional specific symbol to check

    Returns:
        Tuple of (violations, warnings, recommendations)
    """
    violations = []
    warnings = []
    recommendations = []

    if not holdings:
        return violations, warnings, recommendations

    # Filter to specific symbol if provided
    holdings_to_check = (
        [h for h in holdings if h.get("symbol") == symbol]
        if symbol
        else holdings
    )

    for holding in holdings_to_check:
        alloc_pct = float(
            holding.get("allocation_pct", holding.get("allocationPct", 0))
        )
        holding_symbol = holding.get("symbol", "UNKNOWN")

        if alloc_pct > CONCENTRATION_LIMIT_PCT:
            violations.append(
                Violation(
                    rule="concentration_limit",
                    severity="medium",
                    description=(
                        f"Concentration risk: {holding_symbol} position is {alloc_pct:.1f}% "
                        f"of portfolio (exceeds {CONCENTRATION_LIMIT_PCT}% limit)"
                    ),
                    symbol=holding_symbol,
                    details={
                        "allocation_pct": round(alloc_pct, 2),
                        "limit_pct": CONCENTRATION_LIMIT_PCT,
                        "value": holding.get("value", 0),
                    },
                )
            )

            recommendations.append(
                f"Reduce {holding_symbol} position to under {CONCENTRATION_LIMIT_PCT}% of portfolio"
            )

        elif alloc_pct > CONCENTRATION_LIMIT_PCT * 0.8:
            # Warning at 80% of limit
            warnings.append(
                f"{holding_symbol} allocation ({alloc_pct:.1f}%) approaching concentration limit"
            )

    return violations, warnings, recommendations


# ============================================================================
# Tool Implementation
# ============================================================================


@tool
async def compliance_check(
    symbol: str | None = None,
    rules: list[str] | None = None,
    account_id: str | None = None,
) -> ComplianceCheckResult:
    """Check transactions or portfolio against financial compliance rules.

    Use this tool when the user asks about:
    - Wash sale violations (selling at loss and repurchasing within 30 days)
    - Pattern day trading (too many day trades in a short period)
    - Portfolio concentration (single position too large)
    - Compliance with trading rules and regulations

    Args:
        symbol: Optional specific symbol to check. If None, checks all symbols.
        rules: Optional list of rules to check. Options: wash_sale, pattern_day_trading,
               concentration_limit. Default: all rules.
        account_id: Optional account ID to filter transactions.

    Returns:
        ComplianceCheckResult with compliant status, violations, warnings, and recommendations
    """
    logger.info(
        f"Running compliance check (symbol={symbol}, rules={rules}, account={account_id})"
    )

    # Determine which rules to check
    if rules:
        # Normalize rule names
        normalized_rules = [r.lower().strip() for r in rules]
        rules_to_check = [r for r in normalized_rules if r in VALID_RULES]
        invalid_rules = [r for r in normalized_rules if r not in VALID_RULES]

        if invalid_rules:
            logger.warning(f"Ignoring invalid rules: {invalid_rules}")
    else:
        rules_to_check = list(VALID_RULES)

    if not rules_to_check:
        logger.warning("No valid rules to check")
        return ComplianceCheckResult(
            compliant=True,
            violations=[],
            warnings=["No valid rules specified for checking"],
            recommendations=[],
            checked_rules=[],
            timestamp=datetime.utcnow().isoformat(),
            account_filter=account_id,
        )

    all_violations: list[Violation] = []
    all_warnings: list[str] = []
    all_recommendations: list[str] = []

    async with GhostfolioClient(use_mock=True) as client:
        try:
            # Fetch necessary data
            orders = await client.get_orders(account_id=account_id, symbol=symbol)
            portfolio = await client.get_portfolio()
            holdings = portfolio.get("holdings", [])

            # Get account value for PDT check
            account_value = 0.0
            if account_id:
                accounts = await client.get_accounts()
                account = next(
                    (a for a in accounts if a.get("id") == account_id), None
                )
                if account:
                    account_value = float(account.get("value", 0))
            else:
                account_value = float(portfolio.get("totalValue", 0))

            # Run each compliance check
            if "wash_sale" in rules_to_check:
                logger.debug("Checking wash sale rule")
                v, w, r = check_wash_sale(orders, symbol)
                all_violations.extend(v)
                all_warnings.extend(w)
                all_recommendations.extend(r)

            if "pattern_day_trading" in rules_to_check:
                logger.debug("Checking pattern day trading rule")
                v, w, r = check_pattern_day_trading(orders, account_value, symbol)
                all_violations.extend(v)
                all_warnings.extend(w)
                all_recommendations.extend(r)

            if "concentration_limit" in rules_to_check:
                logger.debug("Checking concentration limit rule")
                v, w, r = check_concentration_limit(holdings, symbol)
                all_violations.extend(v)
                all_warnings.extend(w)
                all_recommendations.extend(r)

            # Determine overall compliance
            # Compliant if no high or critical violations
            has_blocking_violations = any(
                v.severity in ("high", "critical") for v in all_violations
            )
            compliant = not has_blocking_violations

            # Deduplicate recommendations
            unique_recommendations = list(dict.fromkeys(all_recommendations))

            result = ComplianceCheckResult(
                compliant=compliant,
                violations=all_violations,
                warnings=all_warnings,
                recommendations=unique_recommendations,
                checked_rules=rules_to_check,
                timestamp=datetime.utcnow().isoformat(),
                account_filter=account_id,
            )

            logger.info(
                f"Compliance check complete: compliant={compliant}, "
                f"{len(all_violations)} violations, {len(all_warnings)} warnings"
            )

            return result

        except Exception as e:
            logger.error(f"Compliance check failed: {e}")
            raise


# ============================================================================
# Tool Export
# ============================================================================

__all__ = [
    "compliance_check",
    "ComplianceCheckResult",
    "Violation",
    "check_wash_sale",
    "check_pattern_day_trading",
    "check_concentration_limit",
]
