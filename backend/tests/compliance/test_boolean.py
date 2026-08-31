"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_boolean.py: Comprehensive tests for BooleanEvaluator.

Test matrix:
  Operators: EQUAL, NOT_EQUAL (valid), others (invalid → REVIEW)
  Evidence values:
    - Python bool True / False
    - int 1 / 0
    - string "true", "false", "yes", "no", "1", "0" (case variants)
    - None / missing evidence → REVIEW
    - Invalid strings ("maybe", "yes-ish") → REVIEW
    - Numeric non-0/1 ("2", 99) → REVIEW
    - List / dict → REVIEW
"""
from __future__ import annotations

import pytest

from app.compliance.boolean import BooleanEvaluator
from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.models import BidderEvidence, Requirement, RuleDefinition
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID, make_evidence

evaluator = BooleanEvaluator()


def make_bool_req(operator: Operator, required: object, field: str = "gst_registered") -> Requirement:
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.STATUTORY,
        field=field,
        rule_type=RuleType.BOOLEAN,
        rule_definition=RuleDefinition(
            operator=operator,
            required_value=required,
        ),
    )


# ===========================================================================
# EQUAL — required = True
# ===========================================================================

class TestEqualRequiredTrue:

    def test_true_evidence_pass(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.PASS
        assert "true" in result.reason.lower()
        assert "satisfies" in result.reason.lower()

    def test_false_evidence_fail(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", False)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.FAIL
        assert "false" in result.reason.lower()
        assert "mandates" in result.reason.lower()

    # --- String coercions ---

    def test_string_true_pass(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "true")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_string_true_uppercase_pass(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "TRUE")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_string_yes_pass(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "yes")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_string_one_pass(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "1")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_int_one_pass(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", 1)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_string_false_fail(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "false")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_string_no_fail(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "no")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_int_zero_fail(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", 0)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# EQUAL — required = False
# ===========================================================================

class TestEqualRequiredFalse:

    def test_false_evidence_pass(self):
        req = make_bool_req(Operator.EQUAL, False, field="blacklisted")
        ev = make_evidence("blacklisted", False)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_true_evidence_fail(self):
        req = make_bool_req(Operator.EQUAL, False, field="blacklisted")
        ev = make_evidence("blacklisted", True)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL

    def test_string_zero_pass(self):
        req = make_bool_req(Operator.EQUAL, False, field="blacklisted")
        ev = make_evidence("blacklisted", "0")
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS


# ===========================================================================
# NOT_EQUAL
# ===========================================================================

class TestNotEqual:

    def test_opposite_value_pass(self):
        """not_blacklisted: must NOT equal True → providing False should PASS."""
        req = make_bool_req(Operator.NOT_EQUAL, True, field="blacklisted")
        ev = make_evidence("blacklisted", False)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.PASS

    def test_same_value_fail(self):
        req = make_bool_req(Operator.NOT_EQUAL, True, field="blacklisted")
        ev = make_evidence("blacklisted", True)
        assert evaluator.evaluate(req, ev).status == ComplianceStatus.FAIL


# ===========================================================================
# Missing / None evidence
# ===========================================================================

class TestMissingEvidence:

    def test_none_evidence_object_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        result = evaluator.evaluate(req, None)
        assert result.status == ComplianceStatus.REVIEW
        assert "No evidence" in result.reason

    def test_none_evidence_value_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", None)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_missing_required_value_review(self):
        req = make_bool_req(Operator.EQUAL, None)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "missing" in result.reason.lower()


# ===========================================================================
# Invalid / ambiguous evidence
# ===========================================================================

class TestInvalidEvidence:

    def test_ambiguous_string_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "maybe")
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "could not be interpreted" in result.reason

    def test_numeric_non_binary_review(self):
        """Integer 2 is not a valid boolean (only 0 and 1 are)."""
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", 2)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_large_int_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", 99)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_list_value_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", [True, False])
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_dict_value_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", {"registered": True})
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_empty_string_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", "")
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_invalid_required_value_review(self):
        """required_value = "maybe" cannot be interpreted as bool."""
        req = make_bool_req(Operator.EQUAL, "maybe")
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "could not be interpreted" in result.reason or "misconfigured" in result.reason


# ===========================================================================
# Invalid operators
# ===========================================================================

class TestInvalidOperators:

    def test_numeric_operator_on_boolean_field_review(self):
        """GTE is meaningless for boolean fields → REVIEW."""
        req = make_bool_req(Operator.GREATER_THAN_OR_EQUAL, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "not valid" in result.reason.lower()

    def test_minimum_operator_review(self):
        req = make_bool_req(Operator.MINIMUM, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW

    def test_between_operator_review(self):
        req = make_bool_req(Operator.BETWEEN, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW


# ===========================================================================
# Low-confidence evidence
# ===========================================================================

class TestLowConfidence:

    def test_low_confidence_review(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", True, confidence=0.2)
        result = evaluator.evaluate(req, ev)
        assert result.status == ComplianceStatus.REVIEW
        assert "low extraction confidence" in result.reason.lower()


# ===========================================================================
# Result audit fields
# ===========================================================================

class TestResultAuditFields:

    def test_actual_value_stored(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.actual_value is True

    def test_required_value_stored(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.required_value is True

    def test_rule_type_stored(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.rule_type == RuleType.BOOLEAN

    def test_operator_stored(self):
        req = make_bool_req(Operator.EQUAL, True)
        ev = make_evidence("gst_registered", True)
        result = evaluator.evaluate(req, ev)
        assert result.operator_used == Operator.EQUAL
