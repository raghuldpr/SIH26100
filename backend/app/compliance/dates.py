"""
Phase 09 — Compliance Rule Engine
dates.py: Deterministic date and duration evaluator.

Handles:
  certificate_validity_date  (must be BEFORE / AFTER / BETWEEN dates)
  experience_end_date        (must be AFTER some reference date)
  tender_deadline            (bidder submission date must be BEFORE deadline)
  financial_year_range       (DATE_BETWEEN for FY windows)

Supported operators  (all in app.compliance.enums.Operator):
  DATE_EQUAL
  DATE_BEFORE
  DATE_AFTER
  DATE_BEFORE_OR_EQUAL
  DATE_AFTER_OR_EQUAL
  DATE_BETWEEN

Evaluation contract:
  1. Missing evidence (None)                  → REVIEW
  2. Low-confidence evidence (< 0.5)          → REVIEW
  3. Evidence value cannot be coerced to date → REVIEW
  4. required_value is None / unparseable     → REVIEW
  5. DATE_BETWEEN: required_value must be [start, end]
  6. Comparison succeeds                      → PASS
  7. Comparison fails                         → FAIL

All dates are normalised to datetime.date before comparison so that
date/datetime evidence is always compatible with date-only rule values.

The engine does NOT interpret natural language ("preceding 3 FYs").
All reference dates must already be resolved by upstream normalisation.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from app.compliance.enums import Operator, RuleType
from app.compliance.evaluator import BaseEvaluator, LOW_CONFIDENCE_THRESHOLD
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement
from app.compliance.operators import coerce_to_date, compare_dates, format_date

logger = logging.getLogger("app.compliance.dates")

# Set of operators this evaluator handles
_DATE_OPERATORS = {
    Operator.DATE_EQUAL,
    Operator.DATE_BEFORE,
    Operator.DATE_AFTER,
    Operator.DATE_BEFORE_OR_EQUAL,
    Operator.DATE_AFTER_OR_EQUAL,
    Operator.DATE_BETWEEN,
}

# Human-readable descriptions used in reason strings
_OPERATOR_PHRASES: dict[Operator, str] = {
    Operator.DATE_EQUAL:            "equal to",
    Operator.DATE_BEFORE:           "before",
    Operator.DATE_AFTER:            "after",
    Operator.DATE_BEFORE_OR_EQUAL:  "on or before",
    Operator.DATE_AFTER_OR_EQUAL:   "on or after",
    Operator.DATE_BETWEEN:          "within the range",
}


def _op_phrase(op: Operator) -> str:
    return _OPERATOR_PHRASES.get(op, op.value.lower().replace("_", " "))


class DateEvaluator(BaseEvaluator):
    """
    Evaluates date-based compliance requirements deterministically.

    Supported operators: DATE_EQUAL, DATE_BEFORE, DATE_AFTER,
    DATE_BEFORE_OR_EQUAL, DATE_AFTER_OR_EQUAL, DATE_BETWEEN.

    All values are normalised to datetime.date before comparison, so
    datetime objects (with or without timezone) are handled transparently.
    """

    @property
    def rule_type(self) -> RuleType:
        return RuleType.DATE_RANGE

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        rid = requirement.requirement_id
        field = requirement.field
        rule_def = requirement.rule_definition
        operator = rule_def.operator
        field_label = field.replace("_", " ").title()

        # ------------------------------------------------------------------
        # 1. Operator validation
        # ------------------------------------------------------------------
        if operator not in _DATE_OPERATORS:
            bidder_id = evidence.bidder_id if evidence else rid
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Operator '{operator}' is not a date operator. "
                    f"DateEvaluator supports: {', '.join(o.value for o in _DATE_OPERATORS)}. "
                    "Rule is misconfigured — manual review required."
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
                    f"No date evidence provided for field '{field}'. "
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
        # 4. DATE_BETWEEN — validate required_value is [start, end]
        # ------------------------------------------------------------------
        if operator == Operator.DATE_BETWEEN:
            return self._evaluate_between(requirement, evidence, field_label)

        # ------------------------------------------------------------------
        # 5. Coerce evidence to date
        # ------------------------------------------------------------------
        actual_date = coerce_to_date(evidence.value)
        if actual_date is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Evidence value '{evidence.value}' for field '{field}' "
                    "could not be interpreted as a date. "
                    "Manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=evidence.value,
                required_value=rule_def.required_value,
            )

        # ------------------------------------------------------------------
        # 6. Validate required_value
        # ------------------------------------------------------------------
        required_raw = rule_def.required_value
        if required_raw is None:
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
                actual_value=actual_date,
            )

        required_date = coerce_to_date(required_raw)
        if required_date is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Rule required_value '{required_raw}' for field '{field}' "
                    "could not be interpreted as a date. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_date,
                required_value=required_raw,
            )

        # ------------------------------------------------------------------
        # 7. Perform comparison
        # ------------------------------------------------------------------
        result = compare_dates(actual_date, required_date, operator)

        if result is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Date comparison could not be determined for '{field}'. "
                    "Manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_date,
                required_value=required_date,
            )

        # ------------------------------------------------------------------
        # 8. Build deterministic reason string
        # ------------------------------------------------------------------
        actual_fmt = format_date(actual_date)
        required_fmt = format_date(required_date)
        op_phrase = _op_phrase(operator)

        if result:
            reason = (
                f"{field_label} date {actual_fmt} is {op_phrase} "
                f"the reference date {required_fmt}."
            )
            return ComplianceResult.pass_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=reason,
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_date,
                required_value=required_date,
            )
        else:
            reason = (
                f"{field_label} date {actual_fmt} is NOT {op_phrase} "
                f"the reference date {required_fmt}."
            )
            return ComplianceResult.fail_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=reason,
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_date,
                required_value=required_date,
            )

    # ------------------------------------------------------------------
    # DATE_BETWEEN helper
    # ------------------------------------------------------------------

    def _evaluate_between(
        self,
        requirement: Requirement,
        evidence: BidderEvidence,
        field_label: str,
    ) -> ComplianceResult:
        rid = requirement.requirement_id
        bidder_id = evidence.bidder_id
        field = requirement.field
        rule_def = requirement.rule_definition
        required_raw = rule_def.required_value

        # Coerce evidence
        actual_date = coerce_to_date(evidence.value)
        if actual_date is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Evidence value '{evidence.value}' for '{field}' "
                    "could not be converted to a date (DATE_BETWEEN check). "
                    "Manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.DATE_BETWEEN,
                actual_value=evidence.value,
                required_value=required_raw,
            )

        # Validate [start, end] pair
        if not isinstance(required_raw, (list, tuple)) or len(required_raw) != 2:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"DATE_BETWEEN rule for '{field}' has invalid required_value "
                    f"'{required_raw}'. Expected [start_date, end_date]. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.DATE_BETWEEN,
                actual_value=actual_date,
                required_value=required_raw,
            )

        start_date = coerce_to_date(required_raw[0])
        end_date = coerce_to_date(required_raw[1])

        if start_date is None or end_date is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"DATE_BETWEEN bounds for '{field}' could not be parsed as dates. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.DATE_BETWEEN,
                actual_value=actual_date,
                required_value=required_raw,
            )

        result = compare_dates(actual_date, [start_date, end_date], Operator.DATE_BETWEEN)
        actual_fmt = format_date(actual_date)
        start_fmt = format_date(start_date)
        end_fmt = format_date(end_date)

        if result:
            return ComplianceResult.pass_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"{field_label} date {actual_fmt} is within the "
                    f"required range [{start_fmt}, {end_fmt}]."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.DATE_BETWEEN,
                actual_value=actual_date,
                required_value=[start_date, end_date],
            )
        else:
            return ComplianceResult.fail_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"{field_label} date {actual_fmt} is NOT within the "
                    f"required range [{start_fmt}, {end_fmt}]."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=Operator.DATE_BETWEEN,
                actual_value=actual_date,
                required_value=[start_date, end_date],
            )

