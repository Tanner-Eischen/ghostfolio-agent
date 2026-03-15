"""Constraint validation verification module.

Validates responses against domain constraints:
1. Financial constraints - no negative quantities, valid prices
2. Data constraints - valid dates, symbols, currencies
3. Business rules - allocation sums, risk thresholds
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from src.utils.logging import get_logger

logger = get_logger(__name__)


class ConstraintViolation(BaseModel):
    """A single constraint violation."""

    constraint: str = Field(description="Name of the violated constraint")
    value: Any = Field(description="The value that violated the constraint")
    message: str = Field(description="Human-readable violation message")
    severity: str = Field(description="Severity: LOW, MEDIUM, HIGH, CRITICAL")


class ConstraintValidationResult(BaseModel):
    """Result of constraint validation."""

    is_valid: bool = Field(description="Whether all constraints passed")
    violations: list[ConstraintViolation] = Field(
        default_factory=list,
        description="List of violations found"
    )
    warnings: list[str] = Field(default_factory=list, description="Non-blocking warnings")


class ConstraintValidator:
    """Validate responses against domain constraints."""

    # Valid currency codes (ISO 4217 subset)
    VALID_CURRENCIES = {
        "USD", "EUR", "GBP", "CHF", "JPY", "CAD", "AUD", "NZD", "CNY", "INR",
        "HKD", "SGD", "SEK", "NOK", "DKK", "KRW", "BRL", "MXN", "ZAR", "RUB"
    }

    # Valid transaction types (Ghostfolio compatible)
    VALID_TRANSACTION_TYPES = {
        "BUY", "SELL", "DIVIDEND", "FEE", "INTEREST", "LIABILITY",
        "ITEM", "TRANSFER_IN", "TRANSFER_OUT"
    }

    # Valid asset classes
    VALID_ASSET_CLASSES = {
        "EQUITY", "FIXED_INCOME", "CASH", "COMMODITY", "REAL_ESTATE",
        "CRYPTOCURRENCY", "DERIVATIVE", "ALTERNATIVE", "ETF", "MUTUAL_FUND"
    }

    # Valid timeframes
    VALID_TIMEFRAMES = {"Today", "WTD", "MTD", "YTD", "1Y", "5Y", "Max"}

    # Risk score thresholds
    RISK_THRESHOLDS = {
        "LOW": (0, 24),
        "MEDIUM": (25, 49),
        "HIGH": (50, 74),
        "VERY_HIGH": (75, 100),
    }

    # Escalation thresholds from PRE-SEARCH.md
    LARGE_TRANSACTION_THRESHOLD = 10000  # $10,000
    DAILY_CHANGE_THRESHOLD = 0.20  # 20%
    CONCENTRATION_THRESHOLD = 0.25  # 25% in single position

    def __init__(self) -> None:
        """Initialize constraint validator."""
        self.violations: list[ConstraintViolation] = []
        self.warnings: list[str] = []

    def validate_response(
        self,
        response: dict[str, Any],
        response_type: str = "general",
    ) -> ConstraintValidationResult:
        """Validate a complete response against constraints.

        Args:
            response: Response dictionary to validate
            response_type: Type of response (portfolio, transaction, risk, etc.)

        Returns:
            ConstraintValidationResult with all violations
        """
        self.clear_violations()

        # Validate based on response type
        if response_type == "portfolio":
            self._validate_portfolio_response(response)
        elif response_type == "transaction":
            self._validate_transaction_response(response)
        elif response_type == "risk":
            self._validate_risk_response(response)
        elif response_type == "market_data":
            self._validate_market_data_response(response)
        else:
            # General validation
            self._validate_general_response(response)

        return ConstraintValidationResult(
            is_valid=len(self.violations) == 0,
            violations=self.violations.copy(),
            warnings=self.warnings.copy(),
        )

    def _validate_portfolio_response(self, response: dict[str, Any]) -> None:
        """Validate portfolio analysis response."""
        # Check total value
        total_value = response.get("total_value", 0)
        if total_value < 0:
            self._add_violation(
                "total_value",
                total_value,
                f"Portfolio total value cannot be negative: {total_value}",
                "HIGH",
            )

        # Check holdings
        holdings = response.get("holdings", [])
        if holdings:
            self._validate_holdings(holdings)

            # Check allocations sum to ~100%
            allocations = [
                h.get("allocation_pct", h.get("allocationPct", 0))
                for h in holdings
            ]
            self.validate_allocation(allocations)

        # Check diversification score
        div_score = response.get("diversification_score", 0) or 0
        if not (0 <= div_score <= 100):
            self._add_violation(
                "diversification_score",
                div_score,
                f"Diversification score must be 0-100: {div_score}",
                "MEDIUM",
            )

        # Check currency
        currency = response.get("currency", "USD")
        if not self.validate_currency(currency):
            self._add_violation(
                "currency",
                currency,
                f"Invalid currency code: {currency}",
                "LOW",
            )

    def _validate_transaction_response(self, response: dict[str, Any]) -> None:
        """Validate transaction response."""
        transactions = response.get("transactions", [response]) if "transactions" not in response else response["transactions"]

        for tx in transactions:
            # Check transaction type
            tx_type = tx.get("type", tx.get("Type", ""))
            if not self.validate_transaction_type(tx_type):
                self._add_violation(
                    "transaction_type",
                    tx_type,
                    f"Invalid transaction type: {tx_type}",
                    "MEDIUM",
                )

            # Check quantity
            quantity = tx.get("quantity", tx.get("Quantity", 0))
            if quantity < 0:
                self._add_violation(
                    "quantity",
                    quantity,
                    f"Transaction quantity cannot be negative: {quantity}",
                    "HIGH",
                )

            # Check price
            price = tx.get("price", tx.get("UnitPrice", 0))
            if price < 0:
                self._add_violation(
                    "price",
                    price,
                    f"Transaction price cannot be negative: {price}",
                    "HIGH",
                )

            # Check for large transactions (escalation trigger)
            value = quantity * price if quantity and price else 0
            if value > self.LARGE_TRANSACTION_THRESHOLD:
                self.warnings.append(
                    f"Large transaction detected: ${value:,.2f} (>{self.LARGE_TRANSACTION_THRESHOLD})"
                )

            # Check symbol
            symbol = tx.get("symbol", tx.get("Symbol", ""))
            if symbol and not self.validate_symbol(symbol):
                self._add_violation(
                    "symbol",
                    symbol,
                    f"Invalid symbol format: {symbol}",
                    "LOW",
                )

    def _validate_risk_response(self, response: dict[str, Any]) -> None:
        """Validate risk assessment response."""
        # Check risk score
        risk_score = response.get("risk_score", response.get("overall_risk_score", 0)) or 0
        if not (0 <= risk_score <= 100):
            self._add_violation(
                "risk_score",
                risk_score,
                f"Risk score must be 0-100: {risk_score}",
                "MEDIUM",
            )

        # Check risk level consistency
        risk_level = response.get("risk_level", "")
        if risk_level:
            expected_range = self.RISK_THRESHOLDS.get(risk_level.upper())
            if expected_range and not (expected_range[0] <= risk_score <= expected_range[1]):
                self.warnings.append(
                    f"Risk level '{risk_level}' inconsistent with score {risk_score}"
                )

        # Check concentration risk
        concentration = response.get("concentration_risk", {})
        if concentration:
            top_holding_pct = concentration.get("top_holdings_pct", 0)
            if top_holding_pct > self.CONCENTRATION_THRESHOLD * 100:
                self.warnings.append(
                    f"High concentration: {top_holding_pct:.1f}% in top holding(s)"
                )

    def _validate_market_data_response(self, response: dict[str, Any]) -> None:
        """Validate market data response."""
        data_points = response.get("data", [response]) if "data" not in response else response["data"]

        for dp in data_points:
            # Check price
            price = dp.get("price", 0)
            if price <= 0:
                self._add_violation(
                    "price",
                    price,
                    f"Invalid market price: {price}",
                    "HIGH",
                )

            # Check symbol
            symbol = dp.get("symbol", "")
            if symbol and not self.validate_symbol(symbol):
                self._add_violation(
                    "symbol",
                    symbol,
                    f"Invalid symbol format: {symbol}",
                    "LOW",
                )

    def _validate_general_response(self, response: dict[str, Any]) -> None:
        """General validation for any response."""
        # Check for error status
        if response.get("status") == "error" or response.get("error"):
            self.warnings.append(f"Response contains error: {response.get('error', 'Unknown')}")

        # Validate any nested numbers
        self._validate_numbers_in_dict(response)

    def _validate_holdings(self, holdings: list[dict[str, Any]]) -> None:
        """Validate a list of holdings."""
        for h in holdings:
            # Check quantity
            quantity = h.get("quantity", 0)
            if quantity < 0:
                self._add_violation(
                    "quantity",
                    quantity,
                    f"Holding quantity cannot be negative for {h.get('symbol', 'unknown')}",
                    "HIGH",
                )

            # Check value
            value = h.get("value", h.get("marketValue", 0))
            if value < 0:
                self._add_violation(
                    "value",
                    value,
                    f"Holding value cannot be negative for {h.get('symbol', 'unknown')}",
                    "HIGH",
                )

            # Check allocation percentage
            allocation = h.get("allocation_pct", h.get("allocationPct", 0))
            if allocation < 0 or allocation > 100:
                self._add_violation(
                    "allocation",
                    allocation,
                    f"Invalid allocation percentage for {h.get('symbol', 'unknown')}: {allocation}%",
                    "MEDIUM",
                )

            # Check symbol
            symbol = h.get("symbol", "")
            if symbol and not self.validate_symbol(symbol):
                self._add_violation(
                    "symbol",
                    symbol,
                    f"Invalid symbol format: {symbol}",
                    "LOW",
                )

    def _validate_numbers_in_dict(self, data: Any, path: str = "") -> None:
        """Recursively validate numbers in a dictionary."""
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                self._validate_numbers_in_dict(value, new_path)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._validate_numbers_in_dict(item, f"{path}[{i}]")
        elif isinstance(data, (int, float)) and not isinstance(data, bool):
            # Check for NaN or Inf
            import math
            if math.isnan(data) or math.isinf(data):
                self._add_violation(
                    "numeric_value",
                    data,
                    f"Invalid numeric value at {path}: {data}",
                    "MEDIUM",
                )

    def validate_quantity(self, quantity: float) -> bool:
        """Validate that quantity is non-negative.

        Args:
            quantity: Quantity value

        Returns:
            True if valid, False otherwise
        """
        if quantity < 0:
            self._add_violation(
                "quantity",
                quantity,
                f"Quantity cannot be negative: {quantity}",
                "HIGH",
            )
            return False
        return True

    def validate_price(self, price: float) -> bool:
        """Validate that price is positive.

        Args:
            price: Price value

        Returns:
            True if valid, False otherwise
        """
        if price <= 0:
            self._add_violation(
                "price",
                price,
                f"Price must be positive: {price}",
                "HIGH",
            )
            return False
        return True

    def validate_date_range(
        self,
        start_date: str,
        end_date: str,
    ) -> bool:
        """Validate date range is valid.

        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)

        Returns:
            True if valid, False otherwise
        """
        try:
            start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if start > end:
                self._add_violation(
                    "date_range",
                    f"{start_date} to {end_date}",
                    f"Start date after end date: {start_date} > {end_date}",
                    "MEDIUM",
                )
                return False
            return True
        except ValueError as e:
            self._add_violation(
                "date_format",
                f"{start_date}, {end_date}",
                f"Invalid date format: {e}",
                "MEDIUM",
            )
            return False

    def validate_symbol(self, symbol: str) -> bool:
        """Validate symbol format.

        Valid symbols:
        - 1-10 uppercase letters/numbers
        - Optional dot or hyphen for class shares (BRK.B, BRK-B)

        Args:
            symbol: Asset symbol

        Returns:
            True if valid, False otherwise
        """
        # Allow letters, numbers, dots, and hyphens
        pattern = r"^[A-Z0-9][A-Z0-9.\-]{0,9}$"
        if not re.match(pattern, symbol.upper()):
            self._add_violation(
                "symbol",
                symbol,
                f"Invalid symbol format: {symbol}",
                "LOW",
            )
            return False
        return True

    def validate_currency(self, currency: str) -> bool:
        """Validate currency code.

        Args:
            currency: Currency code

        Returns:
            True if valid, False otherwise
        """
        if currency.upper() not in self.VALID_CURRENCIES:
            self._add_violation(
                "currency",
                currency,
                f"Invalid currency code: {currency}",
                "LOW",
            )
            return False
        return True

    def validate_transaction_type(self, tx_type: str) -> bool:
        """Validate transaction type.

        Args:
            tx_type: Transaction type

        Returns:
            True if valid, False otherwise
        """
        if tx_type.upper() not in self.VALID_TRANSACTION_TYPES:
            self._add_violation(
                "transaction_type",
                tx_type,
                f"Invalid transaction type: {tx_type}",
                "MEDIUM",
            )
            return False
        return True

    def validate_allocation(
        self,
        allocations: list[float],
    ) -> bool:
        """Validate that allocations sum to 100%.

        Args:
            allocations: List of allocation percentages

        Returns:
            True if valid, False otherwise
        """
        if not allocations:
            return True  # Empty is fine

        total = sum(allocations)
        # Allow 1% tolerance for rounding
        if not (99.0 <= total <= 101.0):
            self._add_violation(
                "allocation_sum",
                total,
                f"Allocations sum to {total:.1f}%, should be ~100%",
                "MEDIUM",
            )
            return False
        return True

    def validate_timeframe(self, timeframe: str) -> bool:
        """Validate timeframe string.

        Args:
            timeframe: Timeframe string

        Returns:
            True if valid, False otherwise
        """
        if timeframe not in self.VALID_TIMEFRAMES:
            self._add_violation(
                "timeframe",
                timeframe,
                f"Invalid timeframe: {timeframe}. Valid: {self.VALID_TIMEFRAMES}",
                "LOW",
            )
            return False
        return True

    def check_concentration_limit(
        self,
        holdings: list[dict[str, Any]],
        threshold: float = 0.25,
    ) -> dict[str, Any]:
        """Check if any holding exceeds concentration limit.

        Args:
            holdings: List of holdings with allocation_pct
            threshold: Maximum allowed allocation (default 25%)

        Returns:
            Check result with any violations
        """
        violations = []
        for h in holdings:
            allocation = h.get("allocation_pct", h.get("allocationPct", 0)) / 100
            if allocation > threshold:
                violations.append({
                    "symbol": h.get("symbol"),
                    "allocation": allocation * 100,
                    "threshold": threshold * 100,
                })

        return {
            "has_violation": len(violations) > 0,
            "violations": violations,
            "threshold": threshold * 100,
        }

    def check_daily_change(
        self,
        current_value: float,
        previous_value: float,
        threshold: float = 0.20,
    ) -> dict[str, Any]:
        """Check for unusual daily portfolio changes.

        Args:
            current_value: Current portfolio value
            previous_value: Previous day's value
            threshold: Change threshold (default 20%)

        Returns:
            Check result
        """
        if previous_value == 0:
            return {
                "has_violation": False,
                "change_pct": None,
                "message": "No previous value to compare",
            }

        change_pct = abs(current_value - previous_value) / previous_value

        return {
            "has_violation": change_pct > threshold,
            "change_pct": round(change_pct * 100, 2),
            "threshold": threshold * 100,
            "message": f"Portfolio changed {change_pct*100:.1f}% "
                      f"({'exceeds' if change_pct > threshold else 'within'} threshold)",
        }

    def _add_violation(
        self,
        constraint: str,
        value: Any,
        message: str,
        severity: str,
    ) -> None:
        """Add a constraint violation.

        Args:
            constraint: Constraint name
            value: Violating value
            message: Human-readable message
            severity: Violation severity
        """
        violation = ConstraintViolation(
            constraint=constraint,
            value=value,
            message=message,
            severity=severity,
        )
        self.violations.append(violation)
        logger.warning(f"Constraint violation: {message}")

    def get_violations(self) -> list[ConstraintViolation]:
        """Get all constraint violations."""
        return self.violations

    def get_warnings(self) -> list[str]:
        """Get all warnings."""
        return self.warnings

    def clear_violations(self) -> None:
        """Clear all recorded violations and warnings."""
        self.violations = []
        self.warnings = []


__all__ = [
    "ConstraintValidator",
    "ConstraintViolation",
    "ConstraintValidationResult",
]
