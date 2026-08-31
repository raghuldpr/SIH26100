"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_experience.py: Comprehensive ExperienceEvaluator tests.

Test matrix
-----------
1. Sufficient experience (4 years >= 3 required) → PASS
2. Insufficient experience (2 years < 3 required) → FAIL
3. Exact boundary (3 years == 3 required) → PASS
4. Insufficient contracts (1 contract < 2 required) → FAIL
5. Wrong category (ROAD_CONSTRUCTION instead of SOLAR_EQUIPMENT) → FAIL
6. Uncertain category relevance (relevance="UNCERTAIN") → REVIEW
7. Invalid dates (start_date > end_date, unparseable) → REVIEW
8. Incomplete / missing evidence → REVIEW
9. Structured requirement dictionary specification:
   {"minimum_years": 3, "minimum_contracts": 2, "required_category": "SOLAR_EQUIPMENT"}
10. Scalar evidence values (e.g. similar_work_count = 5)
11. Completion status filtering (completed vs ongoing)
12. Audit fields preservation
"""
from __future__ import annotations

from decimal import Decimal
import uuid
import pytest

from app.compliance.experience import ExperienceEvaluator
from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID, make_evidence

evaluator = ExperienceEvaluator()
S = ComplianceStatus


def make_exp_req(
    minimum_years: Optional[int] = 3,
    minimum_contracts: Optional[int] = 2,
    required_category: Optional[str] = "SOLAR_EQUIPMENT",
    field: str = "similar_work_experience",
) -> Requirement:
    req_spec = {}
    if minimum_years is not None:
        req_spec["minimum_years"] = minimum_years
    if minimum_contracts is not None:
        req_spec["minimum_contracts"] = minimum_contracts
    if required_category is not None:
        req_spec["required_category"] = required_category

    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.EXPERIENCE,
        field=field,
        rule_type=RuleType.EXPERIENCE,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=req_spec,
            extra=req_spec,
        ),
    )


# ===========================================================================
# 1. Sufficient Experience & Contracts
# ===========================================================================

class TestSufficientExperience:

    def test_sufficient_experience_pass(self):
        """3 years required, 2 contracts required, SOLAR_EQUIPMENT; verified 4 years, 2 contracts -> PASS."""
        req = make_exp_req(minimum_years=3, minimum_contracts=2, required_category="SOLAR_EQUIPMENT")
        contracts = [
            {
                "contract_id": "CNT-001",
                "category": "SOLAR_EQUIPMENT",
                "start_date": "2020-01-01",
                "end_date": "2022-01-01",
                "duration_years": 2.0,
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
                "relevance": "RELEVANT",
            },
            {
                "contract_id": "CNT-002",
                "category": "SOLAR_EQUIPMENT",
                "start_date": "2022-02-01",
                "end_date": "2024-02-01",
                "duration_years": 2.0,
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
                "relevance": "RELEVANT",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.PASS
        assert result.is_pass is True
        assert "satisfied" in result.reason.lower()

    def test_exact_boundary_pass(self):
        """3 years required, 3 years verified -> PASS (boundary)."""
        req = make_exp_req(minimum_years=3, minimum_contracts=1, required_category="SOLAR_EQUIPMENT")
        contracts = [
            {
                "contract_id": "CNT-001",
                "category": "SOLAR_EQUIPMENT",
                "duration_years": 3.0,
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
                "relevance": "RELEVANT",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.PASS


# ===========================================================================
# 2. Insufficient Experience
# ===========================================================================

class TestInsufficientExperience:

    def test_insufficient_years_fail(self):
        """3 years required, 2 years verified -> FAIL."""
        req = make_exp_req(minimum_years=3, minimum_contracts=1, required_category="SOLAR_EQUIPMENT")
        contracts = [
            {
                "contract_id": "CNT-001",
                "category": "SOLAR_EQUIPMENT",
                "duration_years": 2.0,
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL
        assert result.is_fail is True
        assert "insufficient experience" in result.reason.lower()

    def test_insufficient_contracts_fail(self):
        """2 contracts required, 1 verified -> FAIL."""
        req = make_exp_req(minimum_years=2, minimum_contracts=2, required_category="SOLAR_EQUIPMENT")
        contracts = [
            {
                "contract_id": "CNT-001",
                "category": "SOLAR_EQUIPMENT",
                "duration_years": 5.0,  # Plenty of years, but only 1 contract
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL
        assert "insufficient qualifying contracts" in result.reason.lower()


# ===========================================================================
# 3. Category & Semantic Relevance
# ===========================================================================

class TestCategoryAndRelevance:

    def test_wrong_category_fail(self):
        """Required SOLAR_EQUIPMENT, submitted ROAD_CONSTRUCTION -> FAIL."""
        req = make_exp_req(minimum_years=2, minimum_contracts=1, required_category="SOLAR_EQUIPMENT")
        contracts = [
            {
                "contract_id": "CNT-001",
                "category": "ROAD_CONSTRUCTION",
                "duration_years": 5.0,
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL
        assert "matched the required category" in result.reason

    def test_uncertain_category_relevance_review(self):
        """Relevance uncertain -> REVIEW (Do not guess!)."""
        req = make_exp_req(minimum_years=2, minimum_contracts=1, required_category="SOLAR_EQUIPMENT")
        contracts = [
            {
                "contract_id": "CNT-001",
                "category": "ELECTRICAL_WORKS",
                "duration_years": 3.0,
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
                "relevance": "UNCERTAIN",  # Upstream marked uncertain
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW
        assert result.is_review is True
        assert "cannot be determined confidently" in result.reason or "uncertain" in result.reason.lower()


# ===========================================================================
# 4. Date Validity
# ===========================================================================

class TestDateValidity:

    def test_reversed_dates_review(self):
        """start_date > end_date -> REVIEW."""
        req = make_exp_req(minimum_years=1, minimum_contracts=1, required_category=None)
        contracts = [
            {
                "contract_id": "CNT-001",
                "start_date": "2024-01-01",
                "end_date": "2020-01-01",  # Reversed!
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW
        assert "date validity error" in result.reason.lower()

    def test_unparseable_dates_review(self):
        """Malformed date strings -> REVIEW."""
        req = make_exp_req(minimum_years=1, minimum_contracts=1, required_category=None)
        contracts = [
            {
                "contract_id": "CNT-001",
                "start_date": "invalid-start-date",
                "end_date": "2022-01-01",
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW
        assert "unparseable" in result.reason.lower() or "date" in result.reason.lower()


# ===========================================================================
# 5. Incomplete / Missing Evidence
# ===========================================================================

class TestIncompleteEvidence:

    def test_none_evidence_review(self):
        req = make_exp_req(minimum_years=3, minimum_contracts=2)
        result = evaluator.evaluate(req, None)
        assert result.status == S.REVIEW
        assert "no experience evidence provided" in result.reason.lower()

    def test_empty_contract_list_review(self):
        req = make_exp_req(minimum_years=3, minimum_contracts=2)
        ev = make_evidence("similar_work_experience", [])
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW

    def test_low_confidence_evidence_review(self):
        req = make_exp_req(minimum_years=2, minimum_contracts=1, required_category=None)
        contracts = [
            {
                "contract_id": "CNT-001",
                "duration_years": 4.0,
                "completion_status": "COMPLETED",
                "verification_status": "VERIFIED",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts, confidence=0.3)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.REVIEW
        assert "low extraction confidence" in result.reason.lower()


# ===========================================================================
# 6. Completion Status Filtering
# ===========================================================================

class TestCompletionStatus:

    def test_ongoing_contract_disqualified(self):
        """Contract marked ONGOING cannot qualify when completion is required."""
        req = make_exp_req(minimum_years=2, minimum_contracts=1, required_category=None)
        contracts = [
            {
                "contract_id": "CNT-001",
                "duration_years": 4.0,
                "completion_status": "ONGOING",  # Not completed!
                "verification_status": "VERIFIED",
            },
        ]
        ev = make_evidence("similar_work_experience", contracts)
        result = evaluator.evaluate(req, ev)
        # Found 0 completed contracts
        assert result.status == S.FAIL


# ===========================================================================
# 7. Scalar Evidence Values (e.g. simple similar_work_count)
# ===========================================================================

class TestScalarExperience:

    def test_scalar_count_pass(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category=RequirementType.EXPERIENCE,
            field="similar_work_count",
            rule_type=RuleType.EXPERIENCE,
            rule_definition=RuleDefinition(operator=Operator.MINIMUM, required_value=3),
        )
        ev = make_evidence("similar_work_count", 5)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.PASS
        assert "verified 5 >= required 3" in result.reason

    def test_scalar_count_fail(self):
        req = Requirement(
            requirement_id=REQUIREMENT_ID,
            tender_id=TENDER_ID,
            category=RequirementType.EXPERIENCE,
            field="similar_work_count",
            rule_type=RuleType.EXPERIENCE,
            rule_definition=RuleDefinition(operator=Operator.MINIMUM, required_value=3),
        )
        ev = make_evidence("similar_work_count", 2)
        result = evaluator.evaluate(req, ev)
        assert result.status == S.FAIL
        assert "verified 2 < required 3" in result.reason


# ===========================================================================
# 8. Audit Fields
# ===========================================================================

class TestExperienceAuditFields:

    def test_rule_type_stored(self):
        req = make_exp_req(minimum_years=2, minimum_contracts=1, required_category=None)
        ev = make_evidence("similar_work_experience", [{"duration_years": 3, "completion_status": "COMPLETED"}])
        result = evaluator.evaluate(req, ev)
        assert result.rule_type == RuleType.EXPERIENCE

    def test_actual_and_required_values_populated(self):
        req = make_exp_req(minimum_years=3, minimum_contracts=2, required_category="SOLAR")
        ev = make_evidence("similar_work_experience", [{"duration_years": 4, "category": "SOLAR", "completion_status": "COMPLETED"}])
        result = evaluator.evaluate(req, ev)
        assert result.actual_value is not None
        assert result.required_value is not None
