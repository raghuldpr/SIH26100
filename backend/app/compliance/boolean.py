"""
Phase 09 — Compliance Rule Engine
boolean.py: Deterministic boolean evaluator.

Handles: gst_registered, pan_verified, udyam_registered, mii_compliant, etc.

Evaluation rules:
1. Missing evidence → REVIEW
2. Low-confidence evidence → REVIEW
3. Evidence value cannot be interpreted as bool → REVIEW
4. Required value must be a valid bool → REVIEW if misconfigured
5. EQUAL comparison succeeds → PASS
6. EQUAL comparison fails → FAIL

Note: Only EQUAL and NOT_EQUAL are meaningful operators for boolean fields.
Any other operator produces REVIEW with a configuration error reason.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.compliance.enums import Operator, RuleType
from app.compliance.evaluator import BaseEvaluator, LOW_CONFIDENCE_THRESHOLD
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement
from app.compliance.operators import coerce_to_bool

logger = logging.getLogger("app.compliance.boolean")

_BOOLEAN_OPERATORS = {Operator.EQUAL, Operator.NOT_EQUAL}


class BooleanEvaluator(BaseEvaluator):
    """
    Evaluates boolean compliance flags deterministically.

    Supported operators: EQUAL, NOT_EQUAL.
    """

    @property
    def rule_type(self) -> RuleType:
        return RuleType.BOOLEAN

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
        if operator not in _BOOLEAN_OPERATORS:
            bidder_id = evidence.bidder_id if evidence else rid
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Operator '{operator}' is not valid for a boolean field. "
                    f"Expected EQUAL or NOT_EQUAL. "
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
                    f"No evidence provided for boolean field '{field}'. "
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
        # 4. Coerce evidence value to bool
        # ------------------------------------------------------------------
        actual_bool = coerce_to_bool(evidence.value)
        if actual_bool is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Evidence value '{evidence.value}' for field '{field}' "
                    "could not be interpreted as a boolean (true/false). "
                    "Manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=evidence.value,
                required_value=rule_def.required_value,
            )

        # ------------------------------------------------------------------
        # 5. Validate required_value
        # ------------------------------------------------------------------
        required_raw = rule_def.required_value
        if required_raw is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Rule definition for boolean field '{field}' is missing "
                    "'required_value'. Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_bool,
            )

        required_bool = coerce_to_bool(required_raw)
        if required_bool is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Rule required_value '{required_raw}' for field '{field}' "
                    "could not be interpreted as a boolean. "
                    "Rule is misconfigured — manual review required."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_bool,
                required_value=required_raw,
            )

        # ------------------------------------------------------------------
        # 6. Perform comparison
        # ------------------------------------------------------------------
        if operator == Operator.EQUAL:
            match = (actual_bool == required_bool)
        else:  # NOT_EQUAL
            match = (actual_bool != required_bool)

        actual_str = str(actual_bool).lower()
        required_str = str(required_bool).lower()

        if match:
            if operator == Operator.EQUAL:
                reason = (
                    f"{field_label} is {actual_str}, "
                    f"which satisfies the requirement (must be {required_str})."
                )
            else:
                reason = (
                    f"{field_label} is {actual_str}, "
                    f"which satisfies the requirement (must not be {required_str})."
                )
            return ComplianceResult.pass_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=reason,
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_bool,
                required_value=required_bool,
            )
        else:
            if operator == Operator.EQUAL:
                reason = (
                    f"{field_label} is {actual_str}, "
                    f"but the requirement mandates {required_str}."
                )
            else:
                reason = (
                    f"{field_label} is {actual_str}, "
                    f"but the requirement mandates it must not be {required_str}."
                )
            return ComplianceResult.fail_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=reason,
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=operator,
                actual_value=actual_bool,
                required_value=required_bool,
            )
