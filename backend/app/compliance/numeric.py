"""
Phase 09 — Compliance Rule Engine
numeric.py: Deterministic numeric evaluator.

Handles: annual_turnover, net_worth, emd_amount, bid_security, paid_up_capital,
         and any other requirement whose evidence value is a number.

Evaluation rules:
1. Missing evidence (None) → REVIEW
2. Low-confidence evidence (< 0.5) → REVIEW
3. Evidence value cannot be coerced to Decimal → REVIEW
4. Required value missing from rule_definition → REVIEW
5. Comparison succeeds → PASS
6. Comparison fails → FAIL

All monetary values are compared using Decimal to avoid floating-point
rounding errors on Indian currency amounts.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Optional

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.evaluator import BaseEvaluator, LOW_CONFIDENCE_THRESHOLD
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement
from app.compliance.operators import coerce_to_decimal, compare, format_inr

logger = logging.getLogger("app.compliance.numeric")

# Operators supported by this evaluator
_NUMERIC_OPERATORS = {
    Operator.EQUAL,
    Operator.NOT_EQUAL,
    Operator.GREATER_THAN,
    Operator.GREATER_THAN_OR_EQUAL,
    Operator.LESS_THAN,
    Operator.LESS_THAN_OR_EQUAL,
    Operator.MINIMUM,   # alias → GTE
    Operator.MAXIMUM,   # alias → LTE
    Operator.BETWEEN,
}

# Human-readable operator descriptions for reason strings
_OPERATOR_PHRASES: dict[Operator, str] = {
    Operator.EQUAL:                  "equal to",
    Operator.NOT_EQUAL:              "not equal to",
    Operator.GREATER_THAN:           "greater than",
    Operator.GREATER_THAN_OR_EQUAL:  "greater than or equal to",
    Operator.LESS_THAN:              "less than",
    Operator.LESS_THAN_OR_EQUAL:     "less than or equal to",
    Operator.MINIMUM:                "greater than or equal to",
    Operator.MAXIMUM:                "less than or equal to",
}


def _describe_operator(op: Operator) -> str:
    return _OPERATOR_PHRASES.get(op, op.value.lower().replace("_", " "))


def _format_value(value, unit: Optional[str]) -> str:
    """Format a numeric value with optional unit for human-readable reasons."""
    if unit and unit.upper() in ("INR", "₹", "RS"):
        return format_inr(value)
    d = coerce_to_decimal(value)
    if d is None:
        return str(value)
    unit_suffix = f" {unit}" if unit else ""
    # Display as integer when no fractional component
    if d == d.to_integral_value():
        return f"{int(d)}{unit_suffix}"
    return f"{d}{unit_suffix}"


class NumericEvaluator(BaseEvaluator):
    """
    Evaluates numeric thresholds deterministically using Decimal arithmetic.

    Supported operators: EQUAL, NOT_EQUAL, GT, GTE, LT, LTE, MINIMUM, MAXIMUM, BETWEEN.
    """

    @property
    def rule_type(self) -> RuleType:
        return RuleType.NUMERIC

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        rid = requirement.requirement_id
        field = requirement.field
        rule_def = requirement.rule_definition
        operator = rule_def.operator
        unit = rule_def.unit

        # ------------------------------------------------------------------
        # 1. Validate operator support
        # ------------------------------------------------------------------
        if operator not in _NUMERIC_OPERATORS:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=evidence.bidder_id if evidence else rid,  # fallback
                reason=(
                    f"Operator '{operator}' is not supported by NumericEvaluator. "
                    "Manual review required."
                ),
                rule_type=self.rule_type,
                operator_used=operator,
            )

        # ------------------------------------------------------------------
        # 2. Missing evidence → REVIEW
        # ------------------------------------------------------------------
        if evidence is None or evidence.value is None:
            bidder_id = evidence.bidder_id if evidence else rid
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"No numeric evidence provided for field '{field}'. "
                    "Manual review required."
                ),
                rule_type=self.rule_type,
                operator_used=operator,
                required_value=rule_def.required_value,
            )

        bidder_id = evidence.bidder_id

        # ------------------------------------------------------------------
        # 3. Low-confidence evidence → REVIEW
        # ------------------------------------------------------------------
        if evidence.confidence < LOW_CONFIDENCE_THRESHOLD:
            return self._low_confidence_review(requirement, evidence)

        # ------------------------------------------------------------------
        # 4. Required value validation
        # ------------------------------------------------------------------
        required_raw = rule_def.required_value
        if required_raw is None and operator not in (Operator.PRESENT, Operator.ABSENT):
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Rule definition for '{field}' is missing 'required_value'. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=evidence.value,
            )

        # ------------------------------------------------------------------
        # 5. BETWEEN — special handling for [low, high] pair
        # ------------------------------------------------------------------
        if operator == Operator.BETWEEN:
            return self._evaluate_between(requirement, evidence, unit)

        # ------------------------------------------------------------------
        # 6. Coerce evidence to Decimal
        # ------------------------------------------------------------------
        actual_decimal = coerce_to_decimal(evidence.value)
        if actual_decimal is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Evidence value '{evidence.value}' for field '{field}' "
                    "could not be interpreted as a number. "
                    "Manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=evidence.value,
                required_value=required_raw,
            )

        # ------------------------------------------------------------------
        # 7. Coerce required_value to Decimal
        # ------------------------------------------------------------------
        required_decimal = coerce_to_decimal(required_raw)
        if required_decimal is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Rule required_value '{required_raw}' for field '{field}' "
                    "could not be interpreted as a number. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=evidence.value,
                required_value=required_raw,
            )

        # ------------------------------------------------------------------
        # 8. Perform comparison
        # ------------------------------------------------------------------
        result = compare(actual_decimal, required_decimal, operator)

        if result is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Comparison could not be determined for '{field}' "
                    f"({actual_decimal} {operator} {required_decimal}). "
                    "Manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_decimal,
                required_value=required_decimal,
            )

        # ------------------------------------------------------------------
        # 9. Build reason string
        # ------------------------------------------------------------------
        actual_fmt = _format_value(actual_decimal, unit)
        required_fmt = _format_value(required_decimal, unit)
        op_phrase = _describe_operator(operator)
        field_label = field.replace("_", " ").title()

        if result:
            reason = (
                f"{field_label} {actual_fmt} is {op_phrase} "
                f"the required {required_fmt}."
            )
            return ComplianceResult.pass_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=reason,
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_decimal,
                required_value=required_decimal,
            )
        else:
            reason = (
                f"{field_label} {actual_fmt} is NOT {op_phrase} "
                f"the required {required_fmt}."
            )
            return ComplianceResult.fail_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=reason,
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_decimal,
                required_value=required_decimal,
            )

    # ------------------------------------------------------------------
    # BETWEEN helper
    # ------------------------------------------------------------------

    def _evaluate_between(
        self,
        requirement: Requirement,
        evidence: BidderEvidence,
        unit: Optional[str],
    ) -> ComplianceResult:
        rid = requirement.requirement_id
        bidder_id = evidence.bidder_id
        field = requirement.field
        rule_def = requirement.rule_definition
        required_raw = rule_def.required_value

        actual_decimal = coerce_to_decimal(evidence.value)
        if actual_decimal is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Evidence value '{evidence.value}' for '{field}' "
                    "could not be converted to a number (BETWEEN check). "
                    "Manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.BETWEEN,
                actual_value=evidence.value,
                required_value=required_raw,
            )

        if not isinstance(required_raw, (list, tuple)) or len(required_raw) != 2:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"BETWEEN rule for '{field}' has invalid required_value "
                    f"'{required_raw}'. Expected [low, high]. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.BETWEEN,
                actual_value=actual_decimal,
                required_value=required_raw,
            )

        lo = coerce_to_decimal(required_raw[0])
        hi = coerce_to_decimal(required_raw[1])
        if lo is None or hi is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"BETWEEN bounds for '{field}' could not be parsed as numbers. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.BETWEEN,
                actual_value=actual_decimal,
                required_value=required_raw,
            )

        result = compare(actual_decimal, [lo, hi], Operator.BETWEEN)
        actual_fmt = _format_value(actual_decimal, unit)
        lo_fmt = _format_value(lo, unit)
        hi_fmt = _format_value(hi, unit)
        field_label = field.replace("_", " ").title()

        if result:
            return ComplianceResult.pass_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=f"{field_label} {actual_fmt} is within the required range [{lo_fmt}, {hi_fmt}].",
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.BETWEEN,
                actual_value=actual_decimal,
                required_value=[lo, hi],
            )
        else:
            return ComplianceResult.fail_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=f"{field_label} {actual_fmt} is NOT within the required range [{lo_fmt}, {hi_fmt}].",
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.BETWEEN,
                actual_value=actual_decimal,
                required_value=[lo, hi],
            )
