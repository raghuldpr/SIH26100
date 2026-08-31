"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_logical.py: Comprehensive LogicalEvaluator tests.

Test matrix
-----------
AND combos : PASS+PASS, PASS+FAIL, PASS+REVIEW, FAIL+FAIL, FAIL+REVIEW, REVIEW+REVIEW
OR combos  : same 6 pairs
Arity      : 2-sub-rule, 3-sub-rule combinations
Nesting    : A AND (B OR C), (A AND B) OR (C AND D)
Error paths: missing logical_operator, unknown logical_operator, no sub_rules,
             misconfigured sub-rule (missing field/rule_type in extra)
Engine     : integration tests through ComplianceEngine singleton
Three-valued logic property tests
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import List

import pytest

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.logical import LogicalEvaluator, _and_reduce, _or_reduce
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.compliance.engine import ComplianceEngine
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID

S = ComplianceStatus

# ---------------------------------------------------------------------------
# Helpers — build sub-rule definitions that carry inline evidence
# ---------------------------------------------------------------------------

def _numeric_sub(
    field: str,
    operator: Operator,
    required_value,
    evidence_value,
    confidence: float = 1.0,
) -> RuleDefinition:
    """Build a NUMERIC sub-rule RuleDefinition with inline evidence."""
    return RuleDefinition(
        operator=operator,
        required_value=required_value,
        extra={
            "field": field,
            "rule_type": "NUMERIC",
            "evidence_value": evidence_value,
            "evidence_confidence": confidence,
        },
    )


def _bool_sub(
    field: str,
    required_value: bool,
    evidence_value,
    confidence: float = 1.0,
) -> RuleDefinition:
    """Build a BOOLEAN sub-rule RuleDefinition with inline evidence."""
    return RuleDefinition(
        operator=Operator.EQUAL,
        required_value=required_value,
        extra={
            "field": field,
            "rule_type": "BOOLEAN",
            "evidence_value": evidence_value,
            "evidence_confidence": confidence,
        },
    )


def _missing_sub(field: str) -> RuleDefinition:
    """A sub-rule with no inline evidence — will produce REVIEW."""
    return RuleDefinition(
        operator=Operator.MINIMUM,
        required_value=1,
        extra={
            "field": field,
            "rule_type": "NUMERIC",
            # no evidence_value → evaluator sees None → REVIEW
        },
    )


def make_logical_req(
    logical_op: str,
    sub_rules: List[RuleDefinition],
    field: str = "composite_check",
) -> Requirement:
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.FINANCIAL,
        field=field,
        rule_type=RuleType.LOGICAL,
        rule_definition=RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator=logical_op,
            sub_rules=sub_rules,
        ),
    )


# ---------------------------------------------------------------------------
# Engine with wired evaluate_fn
# ---------------------------------------------------------------------------
local_engine = ComplianceEngine()


# ===========================================================================
# Unit tests: _and_reduce / _or_reduce (pure logic, no engine)
# ===========================================================================

class TestThreeValuedLogicTables:

    # AND ------------------------------------------------------------------

    def test_and_pass_pass(self):
        assert _and_reduce([S.PASS, S.PASS]) == S.PASS

    def test_and_pass_fail(self):
        assert _and_reduce([S.PASS, S.FAIL]) == S.FAIL

    def test_and_fail_pass(self):
        assert _and_reduce([S.FAIL, S.PASS]) == S.FAIL

    def test_and_pass_review(self):
        assert _and_reduce([S.PASS, S.REVIEW]) == S.REVIEW

    def test_and_review_pass(self):
        assert _and_reduce([S.REVIEW, S.PASS]) == S.REVIEW

    def test_and_fail_review(self):
        """FAIL beats REVIEW in AND — already definitively impossible."""
        assert _and_reduce([S.FAIL, S.REVIEW]) == S.FAIL

    def test_and_review_fail(self):
        assert _and_reduce([S.REVIEW, S.FAIL]) == S.FAIL

    def test_and_fail_fail(self):
        assert _and_reduce([S.FAIL, S.FAIL]) == S.FAIL

    def test_and_review_review(self):
        assert _and_reduce([S.REVIEW, S.REVIEW]) == S.REVIEW

    def test_and_three_all_pass(self):
        assert _and_reduce([S.PASS, S.PASS, S.PASS]) == S.PASS

    def test_and_three_one_fail(self):
        assert _and_reduce([S.PASS, S.FAIL, S.PASS]) == S.FAIL

    def test_and_three_fail_and_review(self):
        assert _and_reduce([S.PASS, S.FAIL, S.REVIEW]) == S.FAIL

    def test_and_empty_review(self):
        assert _and_reduce([]) == S.REVIEW

    # OR -------------------------------------------------------------------

    def test_or_pass_pass(self):
        assert _or_reduce([S.PASS, S.PASS]) == S.PASS

    def test_or_pass_fail(self):
        assert _or_reduce([S.PASS, S.FAIL]) == S.PASS

    def test_or_fail_pass(self):
        assert _or_reduce([S.FAIL, S.PASS]) == S.PASS

    def test_or_pass_review(self):
        """PASS beats REVIEW in OR — already satisfied."""
        assert _or_reduce([S.PASS, S.REVIEW]) == S.PASS

    def test_or_review_pass(self):
        assert _or_reduce([S.REVIEW, S.PASS]) == S.PASS

    def test_or_fail_review(self):
        """REVIEW beats FAIL in OR — might still be satisfied."""
        assert _or_reduce([S.FAIL, S.REVIEW]) == S.REVIEW

    def test_or_review_fail(self):
        assert _or_reduce([S.REVIEW, S.FAIL]) == S.REVIEW

    def test_or_fail_fail(self):
        assert _or_reduce([S.FAIL, S.FAIL]) == S.FAIL

    def test_or_review_review(self):
        assert _or_reduce([S.REVIEW, S.REVIEW]) == S.REVIEW

    def test_or_three_all_fail(self):
        assert _or_reduce([S.FAIL, S.FAIL, S.FAIL]) == S.FAIL

    def test_or_three_one_pass(self):
        assert _or_reduce([S.FAIL, S.FAIL, S.PASS]) == S.PASS

    def test_or_empty_review(self):
        assert _or_reduce([]) == S.REVIEW


# ===========================================================================
# AND — integration tests through the engine
# ===========================================================================

class TestAND:

    def test_and_pass_pass_is_pass(self):
        """Turnover ≥ 15L AND gst_registered == True → both PASS → PASS."""
        req = make_logical_req("AND", [
            _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2100000")),
            _bool_sub("gst_registered", True, True),
        ])
        result = local_engine.evaluate(req, None)
        assert result.status == S.PASS
        assert "PASS" in result.reason

    def test_and_pass_fail_is_fail(self):
        """Turnover ≥ 15L PASS, experience ≥ 5 years FAIL → FAIL."""
        req = make_logical_req("AND", [
            _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2100000")),
            _numeric_sub("experience_years", Operator.MINIMUM, Decimal("5"), Decimal("3")),
        ])
        result = local_engine.evaluate(req, None)
        assert result.status == S.FAIL
        assert "FAIL" in result.reason

    def test_and_fail_pass_is_fail(self):
        req = make_logical_req("AND", [
            _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("800000")),
            _bool_sub("gst_registered", True, True),
        ])
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_and_fail_fail_is_fail(self):
        req = make_logical_req("AND", [
            _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("100000")),
            _numeric_sub("experience_years", Operator.MINIMUM, Decimal("5"), Decimal("1")),
        ])
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_and_pass_review_is_review(self):
        """PASS AND REVIEW → REVIEW (uncertain)."""
        req = make_logical_req("AND", [
            _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2100000")),
            _missing_sub("experience_years"),  # no evidence → REVIEW
        ])
        assert local_engine.evaluate(req, None).status == S.REVIEW

    def test_and_fail_review_is_fail(self):
        """FAIL AND REVIEW → FAIL (definitively impossible)."""
        req = make_logical_req("AND", [
            _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("500000")),
            _missing_sub("experience_years"),
        ])
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_and_review_review_is_review(self):
        req = make_logical_req("AND", [
            _missing_sub("annual_turnover"),
            _missing_sub("experience_years"),
        ])
        assert local_engine.evaluate(req, None).status == S.REVIEW

    def test_and_three_all_pass(self):
        req = make_logical_req("AND", [
            _numeric_sub("turnover",    Operator.MINIMUM, Decimal("1500000"), Decimal("2000000")),
            _numeric_sub("experience",  Operator.MINIMUM, Decimal("5"),       Decimal("7")),
            _bool_sub("gst_registered", True, True),
        ])
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_and_three_one_fail_others_pass(self):
        req = make_logical_req("AND", [
            _numeric_sub("turnover",    Operator.MINIMUM, Decimal("1500000"), Decimal("2000000")),
            _numeric_sub("experience",  Operator.MINIMUM, Decimal("5"),       Decimal("3")),  # FAIL
            _bool_sub("gst_registered", True, True),
        ])
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_and_three_fail_and_review(self):
        """When both FAIL and REVIEW present, FAIL must win."""
        req = make_logical_req("AND", [
            _numeric_sub("turnover",   Operator.MINIMUM, Decimal("1500000"), Decimal("500000")),  # FAIL
            _missing_sub("experience"),  # REVIEW
            _bool_sub("gst_registered", True, True),  # PASS
        ])
        assert local_engine.evaluate(req, None).status == S.FAIL


# ===========================================================================
# OR — integration tests through the engine
# ===========================================================================

class TestOR:

    def test_or_pass_pass_is_pass(self):
        """ISO 9001 PASS OR ISO 14001 PASS → PASS."""
        req = make_logical_req("OR", [
            _bool_sub("iso_9001_certified", True, True),
            _bool_sub("iso_14001_certified", True, True),
        ])
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_or_pass_fail_is_pass(self):
        """One satisfied alternative is enough."""
        req = make_logical_req("OR", [
            _bool_sub("iso_9001_certified", True, True),
            _bool_sub("iso_14001_certified", True, False),
        ])
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_or_fail_pass_is_pass(self):
        req = make_logical_req("OR", [
            _bool_sub("iso_9001_certified", True, False),
            _bool_sub("iso_14001_certified", True, True),
        ])
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_or_fail_fail_is_fail(self):
        req = make_logical_req("OR", [
            _bool_sub("iso_9001_certified", True, False),
            _bool_sub("iso_14001_certified", True, False),
        ])
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_or_fail_review_is_review(self):
        """FAIL OR REVIEW → REVIEW (might still be satisfied)."""
        req = make_logical_req("OR", [
            _bool_sub("iso_9001_certified", True, False),
            _missing_sub("iso_14001_certified"),
        ])
        assert local_engine.evaluate(req, None).status == S.REVIEW

    def test_or_pass_review_is_pass(self):
        """PASS OR REVIEW → PASS (already satisfied)."""
        req = make_logical_req("OR", [
            _bool_sub("iso_9001_certified", True, True),
            _missing_sub("iso_14001_certified"),
        ])
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_or_review_review_is_review(self):
        req = make_logical_req("OR", [
            _missing_sub("iso_9001_certified"),
            _missing_sub("iso_14001_certified"),
        ])
        assert local_engine.evaluate(req, None).status == S.REVIEW

    def test_or_three_all_fail(self):
        req = make_logical_req("OR", [
            _bool_sub("cert_a", True, False),
            _bool_sub("cert_b", True, False),
            _bool_sub("cert_c", True, False),
        ])
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_or_three_last_pass(self):
        req = make_logical_req("OR", [
            _bool_sub("cert_a", True, False),
            _bool_sub("cert_b", True, False),
            _bool_sub("cert_c", True, True),
        ])
        assert local_engine.evaluate(req, None).status == S.PASS


# ===========================================================================
# Reason strings
# ===========================================================================

class TestReasonStrings:

    def test_and_reason_contains_and(self):
        req = make_logical_req("AND", [
            _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2000000")),
        ])
        result = local_engine.evaluate(req, None)
        assert "AND" in result.reason

    def test_or_reason_contains_or(self):
        req = make_logical_req("OR", [
            _bool_sub("iso_9001_certified", True, True),
        ])
        result = local_engine.evaluate(req, None)
        assert "OR" in result.reason

    def test_reason_contains_sub_rule_count(self):
        req = make_logical_req("AND", [
            _numeric_sub("a", Operator.MINIMUM, Decimal("1"), Decimal("2")),
            _numeric_sub("b", Operator.MINIMUM, Decimal("1"), Decimal("2")),
            _numeric_sub("c", Operator.MINIMUM, Decimal("1"), Decimal("2")),
        ])
        result = local_engine.evaluate(req, None)
        assert "3" in result.reason


# ===========================================================================
# Nested rules: A AND (B OR C)
# ===========================================================================

class TestNestedANDOR:

    def _build_nested_b_or_c(
        self,
        b_passes: bool,
        c_passes: bool,
    ) -> Requirement:
        """
        Build:  A AND (B OR C)
        A  = annual_turnover >= 15L   (always PASS — 20L supplied)
        B  = iso_9001_certified == True
        C  = iso_14001_certified == True
        """
        # Inner (B OR C) as a nested LOGICAL sub-rule
        b_or_c_def = RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator="OR",
            sub_rules=[
                _bool_sub("iso_9001_certified",  True, b_passes),
                _bool_sub("iso_14001_certified", True, c_passes),
            ],
            extra={
                "field": "cert_check",
                "rule_type": "LOGICAL",
            },
        )
        a_def = _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2000000"))

        return Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="nested_composite",
            rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL,
                required_value=None,
                logical_operator="AND",
                sub_rules=[a_def, b_or_c_def],
            ),
        )

    def test_nested_a_and_b_or_c_all_pass(self):
        """A=PASS, B=PASS, C=PASS → (B OR C)=PASS → AND → PASS."""
        req = self._build_nested_b_or_c(b_passes=True, c_passes=True)
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_nested_a_and_b_or_c_b_pass_c_fail(self):
        """A=PASS, B=PASS, C=FAIL → (B OR C)=PASS → AND → PASS."""
        req = self._build_nested_b_or_c(b_passes=True, c_passes=False)
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_nested_a_and_b_or_c_both_fail(self):
        """A=PASS, B=FAIL, C=FAIL → (B OR C)=FAIL → AND → FAIL."""
        req = self._build_nested_b_or_c(b_passes=False, c_passes=False)
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_nested_a_and_b_or_c_b_fail_c_missing(self):
        """A=PASS, B=FAIL, C=REVIEW → (B OR C)=REVIEW → AND → REVIEW."""
        b_or_c_def = RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            logical_operator="OR",
            sub_rules=[
                _bool_sub("iso_9001_certified", True, False),  # FAIL
                _missing_sub("iso_14001_certified"),           # REVIEW
            ],
            extra={"field": "cert_check", "rule_type": "LOGICAL"},
        )
        a_def = _numeric_sub("annual_turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2000000"))
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="nested_composite", rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None, logical_operator="AND",
                sub_rules=[a_def, b_or_c_def],
            ),
        )
        assert local_engine.evaluate(req, None).status == S.REVIEW


class TestNestedABorCD:
    """(A AND B) OR (C AND D)"""

    def _build_ab_or_cd(
        self,
        a_pass: bool, b_pass: bool,
        c_pass: bool, d_pass: bool,
    ) -> Requirement:
        ab_def = RuleDefinition(
            operator=Operator.EQUAL, required_value=None, logical_operator="AND",
            sub_rules=[
                _bool_sub("a", True, a_pass),
                _bool_sub("b", True, b_pass),
            ],
            extra={"field": "ab_check", "rule_type": "LOGICAL"},
        )
        cd_def = RuleDefinition(
            operator=Operator.EQUAL, required_value=None, logical_operator="AND",
            sub_rules=[
                _bool_sub("c", True, c_pass),
                _bool_sub("d", True, d_pass),
            ],
            extra={"field": "cd_check", "rule_type": "LOGICAL"},
        )
        return Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="ab_or_cd", rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None, logical_operator="OR",
                sub_rules=[ab_def, cd_def],
            ),
        )

    def test_ab_pass_cd_fail(self):
        """A&B pass, C|D fail → overall PASS."""
        req = self._build_ab_or_cd(True, True, True, False)
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_ab_fail_cd_pass(self):
        req = self._build_ab_or_cd(True, False, True, True)
        assert local_engine.evaluate(req, None).status == S.PASS

    def test_both_fail(self):
        req = self._build_ab_or_cd(True, False, True, False)
        assert local_engine.evaluate(req, None).status == S.FAIL

    def test_both_pass(self):
        req = self._build_ab_or_cd(True, True, True, True)
        assert local_engine.evaluate(req, None).status == S.PASS


# ===========================================================================
# Error / misconfiguration paths
# ===========================================================================

class TestMisconfiguredLogical:

    def test_missing_logical_operator_review(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="bad_rule", rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None,
                logical_operator=None,  # missing
                sub_rules=[_bool_sub("gst_registered", True, True)],
            ),
        )
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW
        assert "misconfigured" in result.reason.lower()

    def test_invalid_logical_operator_review(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="bad_rule", rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None,
                logical_operator="XOR",  # not supported
                sub_rules=[_bool_sub("gst_registered", True, True)],
            ),
        )
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW

    def test_empty_sub_rules_review(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID, tender_id=TENDER_ID, category="FINANCIAL",
            field="bad_rule", rule_type=RuleType.LOGICAL,
            rule_definition=RuleDefinition(
                operator=Operator.EQUAL, required_value=None,
                logical_operator="AND",
                sub_rules=[],  # empty
            ),
        )
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW
        assert "no sub_rules" in result.reason.lower()

    def test_sub_rule_missing_field_treated_as_review(self):
        """A sub-rule missing 'field' in extra → that sub-rule is REVIEW."""
        bad_sub = RuleDefinition(
            operator=Operator.MINIMUM, required_value=1,
            extra={"rule_type": "NUMERIC"},  # no "field"
        )
        req = make_logical_req("AND", [
            bad_sub,
            _numeric_sub("turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2000000")),
        ])
        result = local_engine.evaluate(req, None)
        # PASS AND REVIEW → REVIEW
        assert result.status == S.REVIEW

    def test_sub_rule_missing_rule_type_treated_as_review(self):
        bad_sub = RuleDefinition(
            operator=Operator.MINIMUM, required_value=1,
            extra={"field": "some_field"},  # no "rule_type"
        )
        req = make_logical_req("AND", [
            bad_sub,
            _numeric_sub("turnover", Operator.MINIMUM, Decimal("1500000"), Decimal("2000000")),
        ])
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW

    def test_unknown_rule_type_in_sub_rule(self):
        bad_sub = RuleDefinition(
            operator=Operator.MINIMUM, required_value=1,
            extra={"field": "some_field", "rule_type": "MADE_UP_TYPE"},
        )
        req = make_logical_req("AND", [bad_sub])
        result = local_engine.evaluate(req, None)
        assert result.status == S.REVIEW


# ===========================================================================
# Result audit fields
# ===========================================================================

class TestAuditFields:

    def test_rule_type_is_logical(self):
        req = make_logical_req("AND", [
            _numeric_sub("a", Operator.MINIMUM, Decimal("1"), Decimal("2")),
        ])
        result = local_engine.evaluate(req, None)
        assert result.rule_type == RuleType.LOGICAL

    def test_pass_result_is_definitive(self):
        req = make_logical_req("AND", [
            _numeric_sub("a", Operator.MINIMUM, Decimal("1"), Decimal("2")),
        ])
        result = local_engine.evaluate(req, None)
        if result.status == S.PASS:
            assert result.is_definitive is True

    def test_fail_result_is_definitive(self):
        req = make_logical_req("AND", [
            _numeric_sub("a", Operator.MINIMUM, Decimal("5"), Decimal("1")),
        ])
        result = local_engine.evaluate(req, None)
        assert result.status == S.FAIL
        assert result.is_definitive is True
