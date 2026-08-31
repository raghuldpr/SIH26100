"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_numeric.py: Comprehensive tests for NumericEvaluator.

Test matrix:
  Operators:  EQUAL, NOT_EQUAL, GT, GTE, LT, LTE, MINIMUM, MAXIMUM, BETWEEN
  Evidence:   exact boundary values, above, below, missing, None, invalid type,
              string numbers, comma-formatted INR, Decimal, float, int, bool (invalid)
  Monetary:   Decimal precision, ₹ formatting in reasons
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.compliance.enums import ComplianceStatus, EvidenceSource, Operator, RuleType
from app.compliance.models import BidderEvidence, Requirement, RuleDefinition
from app.compliance.numeric import NumericEvaluator
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID, make_evidence

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

evaluator = NumericEvaluator()


def make_req(operator: Operator, required_value, field: str = "annual_turnover") -> Requirement:
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.FINANCIAL,
        field=field,
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=operator,
            required_value=required_value,
            unit="INR",
        ),
    )


# ===========================================================================
# GREATER_THAN_OR_EQUAL (GTE)
# ===========================================================================

class TestGTE:
    REQ = Decimal("1500000")  # ₹15,00,000

    def test_above_threshold_pass(self):
        """₹21,00,000 >= ₹15,00,000 → PASS"""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("2100000"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "greater than or equal to" in result.reason
        assert "₹21,00,000" in result.reason
        assert "₹15,00,000" in result.reason

    def test_exact_boundary_pass(self):
        """₹15,00,000 >= ₹15,00,000 → PASS (exact boundary)"""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("1500000"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS

    def test_below_threshold_fail(self):
        """₹8,00,000 >= ₹15,00,000 → FAIL"""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("800000"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.FAIL
        assert "NOT" in result.reason

    def test_one_rupee_below_boundary_fail(self):
        """₹14,99,999 — just below boundary → FAIL"""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("1499999"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.FAIL

    def test_one_rupee_above_boundary_pass(self):
        """₹15,00,001 — just above boundary → PASS"""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("1500001"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS


# ===========================================================================
# GREATER_THAN (GT)
# ===========================================================================

class TestGT:
    REQ = Decimal("1500000")

    def test_above_pass(self):
        req = make_req(Operator.GREATER_THAN, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("2000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_exact_boundary_fail(self):
        """Exact boundary fails for strict GT."""
        req = make_req(Operator.GREATER_THAN, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("1500000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_below_fail(self):
        req = make_req(Operator.GREATER_THAN, self.REQ)
        ev = make_evidence("annual_turnover", Decimal("1000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# LESS_THAN_OR_EQUAL (LTE)
# ===========================================================================

class TestLTE:
    REQ = Decimal("5000000")  # ₹50,00,000 max

    def test_below_threshold_pass(self):
        req = make_req(Operator.LESS_THAN_OR_EQUAL, self.REQ, field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("3000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_exact_boundary_pass(self):
        req = make_req(Operator.LESS_THAN_OR_EQUAL, self.REQ, field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("5000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_above_threshold_fail(self):
        req = make_req(Operator.LESS_THAN_OR_EQUAL, self.REQ, field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("6000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# LESS_THAN (LT)
# ===========================================================================

class TestLT:
    REQ = Decimal("5000000")

    def test_below_pass(self):
        req = make_req(Operator.LESS_THAN, self.REQ, field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("4999999"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_exact_boundary_fail(self):
        req = make_req(Operator.LESS_THAN, self.REQ, field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("5000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_above_fail(self):
        req = make_req(Operator.LESS_THAN, self.REQ, field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("5000001"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# EQUAL
# ===========================================================================

class TestEqual:
    REQ = Decimal("1000000")

    def test_equal_pass(self):
        req = make_req(Operator.EQUAL, self.REQ, field="emd_amount")
        ev = make_evidence("emd_amount", Decimal("1000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_not_equal_fail(self):
        req = make_req(Operator.EQUAL, self.REQ, field="emd_amount")
        ev = make_evidence("emd_amount", Decimal("999999"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_slightly_above_fail(self):
        req = make_req(Operator.EQUAL, self.REQ, field="emd_amount")
        ev = make_evidence("emd_amount", Decimal("1000001"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# NOT_EQUAL
# ===========================================================================

class TestNotEqual:
    REQ = Decimal("0")

    def test_nonzero_pass(self):
        req = make_req(Operator.NOT_EQUAL, self.REQ, field="outstanding_dues")
        ev = make_evidence("outstanding_dues", Decimal("500"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_zero_fail(self):
        req = make_req(Operator.NOT_EQUAL, self.REQ, field="outstanding_dues")
        ev = make_evidence("outstanding_dues", Decimal("0"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# MINIMUM alias (→ GTE)
# ===========================================================================

class TestMinimumAlias:
    def test_minimum_alias_pass(self):
        """MINIMUM should behave identically to GREATER_THAN_OR_EQUAL."""
        req = make_req(Operator.MINIMUM, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert result.operator_used == Operator.MINIMUM

    def test_minimum_alias_exact_boundary_pass(self):
        req = make_req(Operator.MINIMUM, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("1500000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_minimum_alias_below_fail(self):
        req = make_req(Operator.MINIMUM, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("800000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# MAXIMUM alias (→ LTE)
# ===========================================================================

class TestMaximumAlias:
    def test_maximum_alias_pass(self):
        req = make_req(Operator.MAXIMUM, Decimal("5000000"), field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("3000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_maximum_alias_exact_boundary_pass(self):
        req = make_req(Operator.MAXIMUM, Decimal("5000000"), field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("5000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_maximum_alias_above_fail(self):
        req = make_req(Operator.MAXIMUM, Decimal("5000000"), field="bid_amount")
        ev = make_evidence("bid_amount", Decimal("5000001"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# BETWEEN
# ===========================================================================

class TestBetween:
    def test_in_range_pass(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="project_value",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.BETWEEN,
                required_value=[Decimal("1000000"), Decimal("5000000")],
                unit="INR",
            ),
        )
        ev = make_evidence("project_value", Decimal("3000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_at_lower_bound_pass(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="project_value",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.BETWEEN,
                required_value=[Decimal("1000000"), Decimal("5000000")],
                unit="INR",
            ),
        )
        ev = make_evidence("project_value", Decimal("1000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_at_upper_bound_pass(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="project_value",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.BETWEEN,
                required_value=[Decimal("1000000"), Decimal("5000000")],
                unit="INR",
            ),
        )
        ev = make_evidence("project_value", Decimal("5000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_below_range_fail(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="project_value",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.BETWEEN,
                required_value=[Decimal("1000000"), Decimal("5000000")],
                unit="INR",
            ),
        )
        ev = make_evidence("project_value", Decimal("500000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_above_range_fail(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="project_value",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.BETWEEN,
                required_value=[Decimal("1000000"), Decimal("5000000")],
                unit="INR",
            ),
        )
        ev = make_evidence("project_value", Decimal("6000000"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_invalid_between_bounds_review(self):
        """BETWEEN with a single-value required_value → REVIEW (misconfigured rule)."""
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="project_value",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.BETWEEN,
                required_value=1000000,  # Not a [lo, hi] pair
                unit="INR",
            ),
        )
        ev = make_evidence("project_value", Decimal("3000000"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "misconfigured" in result.reason.lower()


# ===========================================================================
# Missing evidence
# ===========================================================================

class TestMissingEvidence:
    def test_none_evidence_object_review(self):
        """Passing None as the evidence object → REVIEW."""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        result = evaluator.evaluate(req, None)
        assert result.status == ComplianceStatus.REVIEW
        assert "No numeric evidence" in result.reason

    def test_none_evidence_value_review(self):
        """Evidence object exists but value is None → REVIEW."""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", None)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_missing_required_value_review(self):
        """Rule is misconfigured — required_value is None → REVIEW."""
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="annual_turnover",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.GREATER_THAN_OR_EQUAL,
                required_value=None,
            ),
        )
        ev = make_evidence("annual_turnover", Decimal("2000000"))
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "misconfigured" in result.reason.lower()


# ===========================================================================
# Invalid / non-numeric evidence types
# ===========================================================================

class TestInvalidEvidence:
    def test_string_non_numeric_review(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", "not a number")
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "could not be interpreted" in result.reason

    def test_boolean_value_review(self):
        """Bool is not a valid numeric evidence value for a numeric field."""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_list_value_review(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", [1000000, 2000000])
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_empty_string_review(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", "")
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW


# ===========================================================================
# Numeric type coercion (int, float, string numbers)
# ===========================================================================

class TestTypeCoercion:
    def test_integer_evidence_pass(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", 2100000)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_float_evidence_pass(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", 2100000.0)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_string_integer_evidence_pass(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", "2100000")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_comma_formatted_string_evidence_pass(self):
        """₹21,00,000 string form should be coerced correctly."""
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", "21,00,000")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_decimal_precision_boundary(self):
        """Decimal boundary check does not have float rounding errors."""
        req = make_req(Operator.EQUAL, Decimal("1500000.50"))
        ev = make_evidence("annual_turnover", Decimal("1500000.50"))
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS


# ===========================================================================
# Low-confidence evidence
# ===========================================================================

class TestLowConfidence:
    def test_low_confidence_triggers_review(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"), confidence=0.3)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "low extraction confidence" in result.reason.lower()

    def test_exact_threshold_confidence_passes(self):
        """confidence == LOW_CONFIDENCE_THRESHOLD is still treated as acceptable."""
        from app.compliance.evaluator import LOW_CONFIDENCE_THRESHOLD
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"), confidence=LOW_CONFIDENCE_THRESHOLD)
        # At exactly 0.5, we do NOT trigger low-confidence review
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS

    def test_just_below_threshold_review(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"), confidence=0.49)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW


# ===========================================================================
# Result audit fields
# ===========================================================================

class TestResultAuditFields:
    def test_actual_value_preserved_in_result(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"))
        result = evaluator.evaluate(req, ev)
        assert result.actual_value == Decimal("2100000")

    def test_required_value_preserved_in_result(self):
        req = make_req(Operator.GREATER_THAN_OR_EQUAL, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"))
        result = evaluator.evaluate(req, ev)
        assert result.required_value == Decimal("1500000")

    def test_rule_type_in_result(self):
        req = make_req(Operator.MINIMUM, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"))
        result = evaluator.evaluate(req, ev)
        assert result.rule_type == RuleType.NUMERIC

    def test_operator_in_result(self):
        req = make_req(Operator.MINIMUM, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"))
        result = evaluator.evaluate(req, ev)
        assert result.operator_used == Operator.MINIMUM

    def test_evidence_reference_in_result(self):
        req = make_req(Operator.MINIMUM, Decimal("1500000"))
        ev = make_evidence("annual_turnover", Decimal("2100000"))
        result = evaluator.evaluate(req, ev)
        assert result.evidence_reference == "test_doc.pdf"
