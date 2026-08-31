"""
Phase 09 — Compliance Rule Engine
operators.py: Comparison operator dispatch.

Principles:
- Uses Decimal for all numeric comparisons to avoid floating-point rounding errors
  on monetary amounts (e.g. ₹15,00,000 == Decimal("1500000")).
- Returns None for indeterminate results so callers can safely map None → REVIEW.
- Never raises — always returns bool | None.
- MINIMUM is an alias for GREATER_THAN_OR_EQUAL.
- MAXIMUM is an alias for LESS_THAN_OR_EQUAL.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, List, Optional, Sequence, Union

from app.compliance.enums import Operator

# ---------------------------------------------------------------------------
# Currency string normaliser (thin wrapper; the full normaliser lives in
# app.services.tender_requirement_normalizer).  The compliance engine should
# receive already-normalised numeric values from upstream, but we tolerate
# common string forms here as a defensive fallback.
# ---------------------------------------------------------------------------

_CURRENCY_RE = re.compile(
    r"^[₹Rs.\s]*([\d,]+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lac|thousand|k)?$",
    re.IGNORECASE,
)
_MULTIPLIERS: dict[str, Decimal] = {
    "crore": Decimal("10000000"),
    "cr": Decimal("10000000"),
    "lakh": Decimal("100000"),
    "lac": Decimal("100000"),
    "thousand": Decimal("1000"),
    "k": Decimal("1000"),
}


def coerce_to_decimal(value: Any) -> Optional[Decimal]:
    """
    Attempt to convert *value* to a Decimal.

    Accepted forms:
        - int / float / Decimal          → direct conversion
        - "1500000" / "1,500,000"        → strip commas, convert
        - "₹15 lakh" / "Rs. 15 Crore"   → parse currency shorthand

    Returns None if the value cannot be sensibly converted.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        # bool is a subclass of int; treat as non-numeric here so that boolean
        # evidence fields are not accidentally compared as 0/1.
        return None

    if isinstance(value, Decimal):
        return value

    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None

    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        # Try plain number (with optional commas)
        plain = cleaned.replace(",", "")
        try:
            return Decimal(plain)
        except InvalidOperation:
            pass
        # Try currency shorthand
        m = _CURRENCY_RE.match(cleaned)
        if m:
            num_str = m.group(1).replace(",", "")
            unit = (m.group(2) or "").lower().rstrip("s")  # strip plural 's'
            try:
                num = Decimal(num_str)
                multiplier = _MULTIPLIERS.get(unit, Decimal("1"))
                return num * multiplier
            except InvalidOperation:
                return None

    return None


def coerce_to_bool(value: Any) -> Optional[bool]:
    """
    Attempt to interpret *value* as a boolean.

    Accepted forms:
        - True / False
        - 1 / 0  (int)
        - "true" / "false" / "yes" / "no" / "1" / "0"  (case-insensitive)

    Returns None if the value cannot be determined.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "yes", "1"):
            return True
        if s in ("false", "no", "0"):
            return False
    return None


# ---------------------------------------------------------------------------
# Core comparison dispatcher
# ---------------------------------------------------------------------------

def compare(
    actual: Any,
    required: Any,
    operator: Operator,
) -> Optional[bool]:
    """
    Compare *actual* against *required* using *operator*.

    Returns:
        True   — comparison succeeds (→ PASS).
        False  — comparison fails (→ FAIL).
        None   — indeterminate (→ REVIEW); e.g. incompatible types.

    Numeric operators (EQUAL, NOT_EQUAL, GTE, GT, LTE, LT, MINIMUM, MAXIMUM,
    BETWEEN) coerce both operands to Decimal.

    PRESENT / ABSENT operators ignore *required* and inspect *actual* alone.
    IN / NOT_IN expect *required* to be a sequence.
    """
    # ---- presence operators ------------------------------------------------
    if operator == Operator.PRESENT:
        return actual is not None

    if operator == Operator.ABSENT:
        return actual is None

    # ---- BETWEEN ------------------------------------------------------------
    if operator == Operator.BETWEEN:
        a = coerce_to_decimal(actual)
        if a is None:
            return None
        if not isinstance(required, (list, tuple)) or len(required) != 2:
            return None
        lo = coerce_to_decimal(required[0])
        hi = coerce_to_decimal(required[1])
        if lo is None or hi is None:
            return None
        return lo <= a <= hi

    # ---- membership operators -----------------------------------------------
    if operator in (Operator.IN, Operator.NOT_IN):
        if not isinstance(required, (list, tuple, set)):
            return None
        contained = actual in required
        return contained if operator == Operator.IN else not contained

    # ---- MINIMUM alias ------------------------------------------------------
    if operator == Operator.MINIMUM:
        operator = Operator.GREATER_THAN_OR_EQUAL

    # ---- MAXIMUM alias ------------------------------------------------------
    if operator == Operator.MAXIMUM:
        operator = Operator.LESS_THAN_OR_EQUAL

    # ---- numeric operators --------------------------------------------------
    if operator in (
        Operator.EQUAL,
        Operator.NOT_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
    ):
        a = coerce_to_decimal(actual)
        r = coerce_to_decimal(required)

        if a is None or r is None:
            return None  # Indeterminate — caller maps to REVIEW

        if operator == Operator.EQUAL:
            return a == r
        if operator == Operator.NOT_EQUAL:
            return a != r
        if operator == Operator.GREATER_THAN:
            return a > r
        if operator == Operator.GREATER_THAN_OR_EQUAL:
            return a >= r
        if operator == Operator.LESS_THAN:
            return a < r
        if operator == Operator.LESS_THAN_OR_EQUAL:
            return a <= r

    # Unknown operator — should never reach here if enums are used correctly
    return None


def compare_bool(
    actual: Any,
    required: Any,
    operator: Operator,
) -> Optional[bool]:
    """
    Boolean-specific comparison.  Only EQUAL and NOT_EQUAL are meaningful for
    boolean fields.

    Returns None if either value cannot be coerced to bool.
    """
    a = coerce_to_bool(actual)
    r = coerce_to_bool(required)
    if a is None or r is None:
        return None
    if operator in (Operator.EQUAL, Operator.MINIMUM, Operator.MAXIMUM):
        return a == r
    if operator == Operator.NOT_EQUAL:
        return a != r
    return None


def coerce_to_date(value: Any) -> Optional[date]:
    """
    Attempt to convert *value* to a ``datetime.date``.

    Accepted forms:
        - datetime.date              → returned as-is
        - datetime.datetime          → .date() extracted (timezone-aware or naive)
        - ISO 8601 string            → "2026-09-15", "2026-09-15T00:00:00"
        - Other string formats       → common patterns attempted

    Returns None if the value cannot be sensibly converted.
    The caller is responsible for mapping None → REVIEW.
    """
    if value is None:
        return None

    # Already a date (but not datetime — datetime IS a subclass of date)
    if type(value) is date:  # exact type check, not isinstance
        return value

    # datetime → strip time component
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        # Try ISO 8601 date-only: "2026-09-15"
        try:
            return date.fromisoformat(s)
        except ValueError:
            pass
        # Try ISO 8601 datetime: "2026-09-15T10:30:00" or "2026-09-15 10:30:00"
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d %b %Y",   # "15 Sep 2026"
            "%d %B %Y",   # "15 September 2026"
        ):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    return None


# Human-readable date operator descriptions
_DATE_OPERATOR_PHRASES: dict["Operator", str] = {}


def compare_dates(
    actual: Any,
    required: Any,
    operator: "Operator",
) -> Optional[bool]:
    """
    Compare *actual* date against *required* date using a DATE_* operator.

    Both operands are coerced to ``datetime.date`` first.
    For DATE_BETWEEN, *required* must be ``[start_date, end_date]``.

    Returns:
        True   — comparison succeeds (→ PASS)
        False  — comparison fails  (→ FAIL)
        None   — indeterminate     (→ REVIEW); malformed or missing values
    """
    from app.compliance.enums import Operator as Op  # local import avoids circular

    if operator == Op.DATE_BETWEEN:
        actual_d = coerce_to_date(actual)
        if actual_d is None:
            return None
        if not isinstance(required, (list, tuple)) or len(required) != 2:
            return None
        start = coerce_to_date(required[0])
        end = coerce_to_date(required[1])
        if start is None or end is None:
            return None
        return start <= actual_d <= end

    actual_d = coerce_to_date(actual)
    required_d = coerce_to_date(required)

    if actual_d is None or required_d is None:
        return None

    if operator == Op.DATE_EQUAL:
        return actual_d == required_d
    if operator == Op.DATE_BEFORE:
        return actual_d < required_d
    if operator == Op.DATE_AFTER:
        return actual_d > required_d
    if operator == Op.DATE_BEFORE_OR_EQUAL:
        return actual_d <= required_d
    if operator == Op.DATE_AFTER_OR_EQUAL:
        return actual_d >= required_d

    return None  # Unknown date operator


def format_date(value: Any) -> str:
    """Format a date/datetime value as ISO 8601 (YYYY-MM-DD) for use in reasons."""
    d = coerce_to_date(value)
    if d is None:
        return repr(value)
    return d.isoformat()


def format_inr(value: Any) -> str:
    """
    Format a numeric value as a human-readable INR string.

    Examples:
        1500000   → "₹15,00,000"
        2100000   → "₹21,00,000"
        50000000  → "₹5,00,00,000"
    """
    d = coerce_to_decimal(value)
    if d is None:
        return str(value)
    # Convert to int if no fractional part
    if d == d.to_integral_value():
        amount = int(d)
    else:
        # Keep 2 decimal places for paise
        return f"₹{d:,.2f}"

    # Indian comma formatting: last 3 digits, then groups of 2
    s = str(amount)
    if len(s) <= 3:
        return f"₹{s}"
    result = s[-3:]
    s = s[:-3]
    while s:
        result = s[-2:] + "," + result
        s = s[:-2]
    return "₹" + result
