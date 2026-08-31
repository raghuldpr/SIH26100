"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_models.py: Pydantic model validation tests.

Covers:
- Valid construction of all models
- Field normalisation (case, whitespace)
- Validation errors for invalid fields
- ComplianceResult properties (is_pass, is_fail, is_review, external_status)
- Factory classmethods
- EXEMPT / NOT_APPLICABLE → external PASS
- Frozen ComplianceResult cannot be mutated
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.compliance.enums import ComplianceStatus, EvidenceSource, Operator, RuleType
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.models.enums import RequirementType

TENDER_ID = uuid.uuid4()
BIDDER_ID = uuid.uuid4()
REQ_ID = uuid.uuid4()


# ============================================================
# RuleDefinition
# ============================================================

class TestRuleDefinition:

    def test_valid_construction(self):
        rd = RuleDefinition(operator=Operator.GREATER_THAN_OR_EQUAL, required_value=Decimal("1500000"))
        assert rd.operator == Operator.GREATER_THAN_OR_EQUAL
        assert rd.required_value == Decimal("1500000")

    def test_string_number_coerced_to_decimal(self):
        """String '1500000' should be coerced to Decimal by the validator."""
        rd = RuleDefinition(operator=Operator.MINIMUM, required_value="1500000")
        assert isinstance(rd.required_value, Decimal)
        assert rd.required_value == Decimal("1500000")

    def test_string_with_commas_coerced(self):
        rd = RuleDefinition(operator=Operator.MINIMUM, required_value="1,500,000")
        assert rd.required_value == Decimal("1500000")

    def test_non_numeric_string_preserved(self):
        """Non-numeric strings (e.g. document type names) should be left as-is."""
        rd = RuleDefinition(operator=Operator.EQUAL, required_value="PAN")
        assert rd.required_value == "PAN"

    def test_none_required_value_allowed(self):
        rd = RuleDefinition(operator=Operator.PRESENT, required_value=None)
        assert rd.required_value is None

    def test_list_required_value_preserved(self):
        rd = RuleDefinition(operator=Operator.BETWEEN, required_value=[1000000, 5000000])
        assert rd.required_value == [1000000, 5000000]

    def test_sub_rules_accepted(self):
        child = RuleDefinition(operator=Operator.EQUAL, required_value=True)
        parent = RuleDefinition(
            operator=Operator.EQUAL,
            required_value=None,
            sub_rules=[child],
            logical_operator="AND",
        )
        assert len(parent.sub_rules) == 1
        assert parent.sub_rules[0].operator == Operator.EQUAL


# ============================================================
# Requirement
# ============================================================

class TestRequirement:

    def test_valid_construction(self):
        req = Requirement(
            tender_id=TENDER_ID,
            category=RequirementType.FINANCIAL,
            field="annual_turnover",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(
                operator=Operator.GREATER_THAN_OR_EQUAL,
                required_value=Decimal("1500000"),
            ),
        )
        assert req.field == "annual_turnover"
        assert req.mandatory is True

    def test_field_normalised_to_lowercase_snake(self):
        req = Requirement(
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="Annual Turnover",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(operator=Operator.MINIMUM, required_value=100),
        )
        assert req.field == "annual_turnover"

    def test_category_normalised_to_uppercase(self):
        req = Requirement(
            tender_id=TENDER_ID,
            category="financial",
            field="annual_turnover",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(operator=Operator.MINIMUM, required_value=100),
        )
        assert req.category == "FINANCIAL"

    def test_missing_tender_id_raises(self):
        with pytest.raises(ValidationError):
            Requirement(
                category="FINANCIAL",
                field="annual_turnover",
                rule_type=RuleType.NUMERIC,
                rule_definition=RuleDefinition(operator=Operator.MINIMUM, required_value=100),
            )

    def test_empty_field_raises(self):
        with pytest.raises(ValidationError):
            Requirement(
                tender_id=TENDER_ID,
                category="FINANCIAL",
                field="",
                rule_type=RuleType.NUMERIC,
                rule_definition=RuleDefinition(operator=Operator.MINIMUM, required_value=100),
            )

    def test_requirement_id_auto_generated(self):
        req = Requirement(
            tender_id=TENDER_ID,
            category="FINANCIAL",
            field="net_worth",
            rule_type=RuleType.NUMERIC,
            rule_definition=RuleDefinition(operator=Operator.MINIMUM, required_value=500000),
        )
        assert isinstance(req.requirement_id, uuid.UUID)


# ============================================================
# BidderEvidence
# ============================================================

class TestBidderEvidence:

    def test_valid_construction(self):
        ev = BidderEvidence(bidder_id=BIDDER_ID, field="annual_turnover", value=Decimal("2100000"))
        assert ev.field == "annual_turnover"
        assert ev.value == Decimal("2100000")
        assert ev.confidence == 1.0

    def test_field_normalised(self):
        ev = BidderEvidence(bidder_id=BIDDER_ID, field="Annual Turnover", value=1000000)
        assert ev.field == "annual_turnover"

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            BidderEvidence(bidder_id=BIDDER_ID, field="annual_turnover", value=100, confidence=1.5)

    def test_confidence_negative_raises(self):
        with pytest.raises(ValidationError):
            BidderEvidence(bidder_id=BIDDER_ID, field="annual_turnover", value=100, confidence=-0.1)

    def test_none_value_allowed(self):
        ev = BidderEvidence(bidder_id=BIDDER_ID, field="gst_registered", value=None)
        assert ev.value is None

    def test_evidence_id_auto_generated(self):
        ev = BidderEvidence(bidder_id=BIDDER_ID, field="pan_number", value="ABCDE1234F")
        assert isinstance(ev.evidence_id, uuid.UUID)

    def test_missing_bidder_id_raises(self):
        with pytest.raises(ValidationError):
            BidderEvidence(field="annual_turnover", value=100)


# ============================================================
# ComplianceResult
# ============================================================

class TestComplianceResult:

    def test_pass_factory(self):
        result = ComplianceResult.pass_result(REQ_ID, BIDDER_ID, "Test pass reason")
        assert result.status == ComplianceStatus.PASS
        assert result.is_pass is True
        assert result.is_fail is False
        assert result.is_review is False

    def test_fail_factory(self):
        result = ComplianceResult.fail_result(REQ_ID, BIDDER_ID, "Test fail reason")
        assert result.status == ComplianceStatus.FAIL
        assert result.is_fail is True
        assert result.is_pass is False

    def test_review_factory(self):
        result = ComplianceResult.review_result(REQ_ID, BIDDER_ID, "Test review reason")
        assert result.status == ComplianceStatus.REVIEW
        assert result.is_review is True
        assert result.is_pass is False
        assert result.is_definitive is False

    def test_exempt_factory_is_pass_externally(self):
        result = ComplianceResult.exempt_result(REQ_ID, BIDDER_ID, "MSE exemption")
        assert result.status == ComplianceStatus.EXEMPT
        assert result.external_status == ComplianceStatus.PASS
        assert result.is_pass is True
        assert result.is_fail is False

    def test_not_applicable_is_pass_externally(self):
        result = ComplianceResult.not_applicable_result(REQ_ID, BIDDER_ID, "Not applicable")
        assert result.status == ComplianceStatus.NOT_APPLICABLE
        assert result.external_status == ComplianceStatus.PASS
        assert result.is_pass is True

    def test_result_is_immutable(self):
        """ComplianceResult is frozen=True — mutation should raise."""
        result = ComplianceResult.pass_result(REQ_ID, BIDDER_ID, "Immutable test")
        with pytest.raises(Exception):  # ValidationError or TypeError depending on pydantic version
            result.status = ComplianceStatus.FAIL  # type: ignore[misc]

    def test_reason_cannot_be_empty(self):
        with pytest.raises(ValidationError):
            ComplianceResult(
                requirement_id=REQ_ID,
                bidder_id=BIDDER_ID,
                status=ComplianceStatus.PASS,
                reason="",
            )

    def test_evaluated_at_auto_set(self):
        result = ComplianceResult.pass_result(REQ_ID, BIDDER_ID, "auto timestamp")
        assert result.evaluated_at is not None

    def test_is_definitive_pass(self):
        result = ComplianceResult.pass_result(REQ_ID, BIDDER_ID, "definitive pass")
        assert result.is_definitive is True

    def test_is_definitive_fail(self):
        result = ComplianceResult.fail_result(REQ_ID, BIDDER_ID, "definitive fail")
        assert result.is_definitive is True

    def test_is_not_definitive_review(self):
        result = ComplianceResult.review_result(REQ_ID, BIDDER_ID, "needs review")
        assert result.is_definitive is False


# ============================================================
# ComplianceStatus enum
# ============================================================

class TestComplianceStatusEnum:

    def test_pass_external_is_pass(self):
        assert ComplianceStatus.PASS.external_status == ComplianceStatus.PASS

    def test_fail_external_is_fail(self):
        assert ComplianceStatus.FAIL.external_status == ComplianceStatus.FAIL

    def test_review_external_is_review(self):
        assert ComplianceStatus.REVIEW.external_status == ComplianceStatus.REVIEW

    def test_exempt_external_is_pass(self):
        assert ComplianceStatus.EXEMPT.external_status == ComplianceStatus.PASS

    def test_not_applicable_external_is_pass(self):
        assert ComplianceStatus.NOT_APPLICABLE.external_status == ComplianceStatus.PASS

    def test_pass_is_passing(self):
        assert ComplianceStatus.PASS.is_passing is True

    def test_fail_not_passing(self):
        assert ComplianceStatus.FAIL.is_passing is False

    def test_review_not_passing(self):
        assert ComplianceStatus.REVIEW.is_passing is False

    def test_exempt_is_passing(self):
        assert ComplianceStatus.EXEMPT.is_passing is True
