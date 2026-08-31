"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_conditional.py: Comprehensive ConditionalEvaluator tests.

Test matrix
-----------
Condition outcomes:
  PASS   → evaluate THEN requirement, return its result
  FAIL   → NOT_APPLICABLE (collapses to PASS externally)
  REVIEW → REVIEW (uncertain applicability)

Consequence outcomes when condition=PASS:
  PASS   → PASS
  FAIL   → FAIL
  REVIEW → REVIEW

Nested:
  Condition itself is a LOGICAL rule
  Consequence itself is a LOGICAL rule

Misconfiguration:
  Wrong logical_operator (not "IF")
  Missing sub_rules
  Only 1 sub_rule (need 2)
  Condition sub_rule misconfigured
  Consequence sub_rule misconfigured

Examples:
  IF bidder_type == OEM → oem_authorization == True
  IF blacklisted == False → (no further check needed → NOT_APPLICABLE if blacklisted)
  IF turnover >= threshold → further checks
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.compliance.conditional import ConditionalEvaluator
from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.compliance.engine import ComplianceEngine
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID
from tests.compliance.test_logical import (
    _bool_sub, _numeric_sub, _missing_sub, make_logical_req,
)

S = ComplianceStatus
local_engine = ComplianceEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_conditional_req(
    condition_def: RuleDefinition,
    consequence_def: RuleDefinition,
    field: str = "conditional_check",
) -> Requirement:
    """Build a CONDITIONAL requirement from condition + consequence sub-rules."""
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category="FINANCIAL",
        field=field,
        rule_type=RuleType.CONDITIONAL,
        rule_definition=RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator="IF",
            sub_rules=[condition_def, consequence_def],
        ),
    )


def _bool_cond(field: str, required: bool, evidence: bool, confidence: float = 1.0) -> RuleDefinition:
    """Shorthand for a BOOLEAN condition sub-rule."""
    return _bool_sub(field, required, evidence, confidence)


def _numeric_cond(
    field: str, op: Operator, req_val, ev_val, confidence: float = 1.0
) -> RuleDefinition:
    return _numeric_sub(field, op, req_val, ev_val, confidence)


def _nested_logical_cond(
    logical_op: str,
    *sub_defs: RuleDefinition,
    field: str = "nested_cond",
) -> RuleDefinition:
    """A LOGICAL sub-rule embedded as a condition."""
    return RuleDefinition(
        operator=Operator.EQUAL,
        required_value=None,
        logical_operator=logical_op,
        sub_rules=list(sub_defs),
        extra={"field": field, "rule_type": "LOGICAL"},
    )


# ===========================================================================
# Condition = PASS → evaluate THEN
# ===========================================================================

class TestConditionPass:

    def test_condition_pass_consequence_pass_gives_pass(self):
        """
        IF bidder_type == OEM (PASS)
        THEN oem_authorization == True (PASS)
        → PASS
        """
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = _bool_cond("oem_authorization",  True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.PASS
        assert "Condition" in result.reason or "was PASS" in result.reason

    def test_condition_pass_consequence_fail_gives_fail(self):
        """
        IF bidder_type == OEM (PASS)
        THEN oem_authorization == True (FAIL — not authorized)
        → FAIL
        """
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = _bool_cond("oem_authorization",  True, False)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.FAIL
        assert "was PASS" in result.reason

    def test_condition_pass_consequence_review_gives_review(self):
        """
        IF bidder_type == OEM (PASS)
        THEN oem_authorization evidence missing → REVIEW
        → REVIEW
        """
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = _missing_sub("oem_authorization")   # no evidence → REVIEW
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW

    def test_condition_pass_numeric_consequence_pass(self):
        """
        IF turnover >= 10L (PASS — 20L given)
        THEN emd_amount >= 1L (PASS — 2L given)
        → PASS
        """
        cond = _numeric_cond("annual_turnover", Operator.MINIMUM, Decimal("1000000"), Decimal("2000000"))
        cons = _numeric_cond("emd_amount",      Operator.MINIMUM, Decimal("100000"),  Decimal("200000"))
        req  = make_conditional_req(cond, cons)
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_condition_pass_numeric_consequence_fail(self):
        cond = _numeric_cond("annual_turnover", Operator.MINIMUM, Decimal("1000000"), Decimal("2000000"))
        cons = _numeric_cond("emd_amount",      Operator.MINIMUM, Decimal("100000"),  Decimal("50000"))
        req  = make_conditional_req(cond, cons)
        assert local_engine.evaluate(req, None).status == S.FAIL


# ===========================================================================
# Condition = FAIL → NOT_APPLICABLE
# ===========================================================================

class TestConditionFail:

    def test_condition_fail_returns_not_applicable(self):
        """
        IF bidder_type == OEM (FAIL — bidder is not OEM)
        THEN oem_authorization == True (not evaluated)
        → NOT_APPLICABLE
        """
        cond = _bool_cond("bidder_type_is_oem", True, False)  # FAIL
        cons = _bool_cond("oem_authorization",  True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.NOT_APPLICABLE
        assert result.external_status == S.PASS   # collapses externally
        assert result.is_pass is True

    def test_condition_fail_reason_mentions_not_applicable(self):
        cond = _bool_cond("bidder_type_is_oem", True, False)
        cons = _bool_cond("oem_authorization",  True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert "NOT_APPLICABLE" in result.reason or "not applicable" in result.reason.lower()

    def test_condition_fail_consequence_not_evaluated(self):
        """Even if consequence would FAIL, result stays NOT_APPLICABLE."""
        cond = _bool_cond("bidder_type_is_oem", True, False)
        cons = _bool_cond("oem_authorization",  True, False)  # would fail
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.NOT_APPLICABLE

    def test_blacklist_check(self):
        """
        IF blacklisted == True (FAIL — bidder is NOT blacklisted)
        THEN blacklist_waiver == True (not evaluated)
        → NOT_APPLICABLE
        """
        cond = _bool_cond("blacklisted", True, False)  # blacklisted == True? FAIL
        cons = _bool_cond("blacklist_waiver", True, True)
        req  = make_conditional_req(cond, cons, field="blacklist_gate")
        result = local_engine.evaluate(req, None)
        assert result.status == S.NOT_APPLICABLE


# ===========================================================================
# Condition = REVIEW → REVIEW (uncertain applicability)
# ===========================================================================

class TestConditionReview:

    def test_condition_review_gives_review(self):
        """
        IF bidder_type_is_oem — no evidence (REVIEW)
        → uncertain applicability → REVIEW
        """
        cond = _missing_sub("bidder_type_is_oem")  # no evidence → REVIEW
        cons = _bool_cond("oem_authorization", True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW
        assert "uncertain" in result.reason.lower() or "REVIEW" in result.reason

    def test_condition_low_confidence_gives_review(self):
        """Low-confidence condition evidence → REVIEW on condition → REVIEW overall."""
        cond = _bool_cond("bidder_type_is_oem", True, True, confidence=0.3)  # low conf → REVIEW
        cons = _bool_cond("oem_authorization",  True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW

    def test_condition_review_consequence_not_evaluated(self):
        """Consequence must NOT be evaluated when condition is REVIEW."""
        cond = _missing_sub("bidder_type_is_oem")
        # Consequence that would FAIL if evaluated
        cons = _bool_cond("oem_authorization", True, False)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        # If consequence had been evaluated we'd get FAIL; we should get REVIEW
        assert result.status == S.REVIEW


# ===========================================================================
# Nested conditional: condition itself is a LOGICAL rule
# ===========================================================================

class TestNestedConditionals:

    def test_condition_is_logical_and_passes(self):
        """
        IF (oem == True AND gst == True) — both True → PASS
        THEN authorization == True (True) → PASS
        """
        cond = _nested_logical_cond(
            "AND",
            _bool_sub("oem",  True, True),
            _bool_sub("gst",  True, True),
            field="oem_and_gst",
        )
        cons = _bool_cond("authorization", True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.PASS

    def test_condition_is_logical_and_fails(self):
        """
        IF (oem == True AND gst == True) — gst False → AND = FAIL
        → NOT_APPLICABLE
        """
        cond = _nested_logical_cond(
            "AND",
            _bool_sub("oem", True, True),
            _bool_sub("gst", True, False),   # FAIL
            field="oem_and_gst",
        )
        cons = _bool_cond("authorization", True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.NOT_APPLICABLE

    def test_condition_is_logical_or_one_passes(self):
        """
        IF (a == True OR b == True) — b True → OR = PASS
        THEN requirement_pass → PASS
        """
        cond = _nested_logical_cond(
            "OR",
            _bool_sub("a", True, False),
            _bool_sub("b", True, True),
            field="a_or_b",
        )
        cons = _numeric_cond("emd", Operator.MINIMUM, Decimal("1000"), Decimal("5000"))
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.PASS

    def test_consequence_is_logical_rule(self):
        """
        IF oem == True (PASS)
        THEN (authorization == True AND region_approved == True) — both True → PASS
        """
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator="AND",
            sub_rules=[
                _bool_sub("oem_authorization",  True, True),
                _bool_sub("region_approved",     True, True),
            ],
            extra={"field": "oem_requirements", "rule_type": "LOGICAL"},
        )
        req = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.PASS

    def test_consequence_logical_rule_partial_fail(self):
        """
        IF oem == True (PASS)
        THEN (authorization == True AND region_approved == True) — region FAIL → FAIL
        """
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator="AND",
            sub_rules=[
                _bool_sub("oem_authorization", True, True),
                _bool_sub("region_approved",   True, False),  # FAIL
            ],
            extra={"field": "oem_requirements", "rule_type": "LOGICAL"},
        )
        req = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.FAIL

    def test_nested_conditional_inside_and(self):
        """
        (turnover >= 15L) AND (IF oem THEN oem_auth)
        turnover PASS, oem PASS, oem_auth PASS → PASS
        """
        conditional_def = RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator="IF",
            sub_rules=[
                _bool_cond("bidder_type_is_oem", True, True),
                _bool_cond("oem_authorization",  True, True),
            ],
            extra={"field": "oem_gate", "rule_type": "CONDITIONAL"},
        )
        outer = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="outer_composite", rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None, logical_operator="AND",
                sub_rules=[
                    _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2000000")),
                    conditional_def,
                ],
            ),
        )
        result = local_engine.evaluate(outer, None)
        assert result.status == S.PASS

    def test_nested_conditional_condition_fail_inside_and(self):
        """
        (turnover >= 15L) AND (IF oem THEN oem_auth)
        oem FAIL → conditional = NOT_APPLICABLE = PASS externally
        → outer AND = PASS AND PASS = PASS
        """
        conditional_def = RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator="IF",
            sub_rules=[
                _bool_cond("bidder_type_is_oem", True, False),   # condition FAIL → N/A
                _bool_cond("oem_authorization",  True, True),
            ],
            extra={"field": "oem_gate", "rule_type": "CONDITIONAL"},
        )
        outer = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="outer_composite", rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None, logical_operator="AND",
                sub_rules=[
                    _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2000000")),
                    conditional_def,
                ],
            ),
        )
        result = local_engine.evaluate(outer, None)
        # NOT_APPLICABLE collapses to PASS, so AND result is PASS AND PASS = PASS
        assert result.status == S.PASS


# ===========================================================================
# Misconfiguration paths
# ===========================================================================

class TestMisconfiguredConditional:

    def test_wrong_logical_operator_review(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="bad_cond", rule_type=RuleType.CONDITIONAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None,
                logical_operator="AND",   # wrong — should be "IF"
                sub_rules=[
                    _bool_cond("a", True, True),
                    _bool_cond("b", True, True),
                ],
            ),
        )
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW
        assert "misconfigured" in result.reason.lower()

    def test_only_one_sub_rule_review(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="bad_cond", rule_type=RuleType.CONDITIONAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None,
                logical_operator="IF",
                sub_rules=[_bool_cond("a", True, True)],  # need 2
            ),
        )
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW

    def test_no_sub_rules_review(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="bad_cond", rule_type=RuleType.CONDITIONAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None,
                logical_operator="IF",
                sub_rules=[],
            ),
        )
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW

    def test_condition_sub_rule_missing_field_review(self):
        """Condition missing 'field' in extra → REVIEW."""
        bad_cond = RuleDefinition(
            operator=Operator.EQUAL, required_value=True,
            extra={"rule_type": "BOOLEAN"},  # no "field"
        )
        cons = _bool_cond("oem_authorization", True, True)
        req  = make_conditional_req(bad_cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW

    def test_consequence_sub_rule_missing_field_review(self):
        """Consequence missing 'field' in extra → REVIEW after condition passes."""
        cond = _bool_cond("bidder_type_is_oem", True, True)
        bad_cons = RuleDefinition(
            operator=Operator.EQUAL, required_value=True,
            extra={"rule_type": "BOOLEAN"},  # no "field"
        )
        req = make_conditional_req(cond, bad_cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW


# ===========================================================================
# Audit fields
# ===========================================================================

class TestAuditFields:

    def test_rule_type_is_conditional(self):
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = _bool_cond("oem_authorization",  True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.rule_type == RuleType.CONDITIONAL

    def test_not_applicable_is_pass_externally(self):
        cond = _bool_cond("bidder_type_is_oem", True, False)
        cons = _bool_cond("oem_authorization",  True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.NOT_APPLICABLE
        assert result.is_pass is True

    def test_pass_is_definitive(self):
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = _bool_cond("oem_authorization",  True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.PASS
        assert result.is_definitive is True

    def test_fail_is_definitive(self):
        cond = _bool_cond("bidder_type_is_oem", True, True)
        cons = _bool_cond("oem_authorization",  True, False)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.FAIL
        assert result.is_definitive is True

    def test_review_is_not_definitive(self):
        cond = _missing_sub("bidder_type_is_oem")
        cons = _bool_cond("oem_authorization", True, True)
        req  = make_conditional_req(cond, cons)
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW
        assert result.is_definitive is False
