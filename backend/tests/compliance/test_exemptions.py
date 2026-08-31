"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_exemptions.py: Comprehensive tests for generic deterministic EXEMPTION mechanism.

Test Matrix
-----------
1. Exemption triggered:
   - Condition is definitively True (e.g. bidder_category == "STARTUP")
   - Result is EXEMPT (external_status == PASS)
   - Audit reason records exemption rule, condition, and affected requirement.
2. Exemption not triggered:
   - Condition is False (e.g. bidder_category == "LARGE_ENTERPRISE")
   - Fallback: Original requirement evaluated (turnover threshold passes or fails based on evidence).
3. Uncertain exemption condition:
   - Condition evidence missing or low confidence (< 0.5)
   - Result is REVIEW ("Exemption applicability is uncertain...").
4. Multiple exemptions:
   - Rule A: MSE exempts EMD
   - Rule B: STARTUP exempts MINIMUM_TURNOVER
   - Single bidder satisfying one rule, both rules, or neither.
5. Exemption affecting multiple requirements:
   - Single rule exempts ["MINIMUM_TURNOVER", "PRIOR_EXPERIENCE"]
   - Affects turnover evaluation -> EXEMPT
   - Affects experience evaluation -> EXEMPT
6. Invalid exemption definitions:
   - Missing condition
   - Missing exempts
   - Unknown operator
   - Malformed data structure (gracefully produces REVIEW, never crashes)
7. Auditability:
   - Check all audit fields: rule_type, reason, evidence_reference.
"""
from __future__ import annotations

from decimal import Decimal
import uuid
import pytest

from app.compliance.engine import ComplianceEngine
from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.exemptions import (
    ExemptionCondition,
    ExemptionEvaluator,
    ExemptionRule,
    matches_exemption_target,
)
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.models.enums import RequirementType

from tests.compliance.conftest import BIDDER_ID, REQUIREMENT_ID, TENDER_ID, make_evidence

S = ComplianceStatus
evaluator = ExemptionEvaluator()
engine = ComplianceEngine()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_turnover_req(threshold: int = 1500000) -> Requirement:
    """Standard annual turnover requirement: turnover >= ₹15,00,000."""
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.FINANCIAL,
        field="annual_turnover",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=Decimal(str(threshold)),
            unit="INR",
            extra={"requirement_code": "MINIMUM_TURNOVER"},
        ),
        description="Minimum annual turnover requirement",
    )


def make_emd_req(amount: int = 100000) -> Requirement:
    """EMD payment requirement."""
    return Requirement(
        requirement_id=uuid.uuid4(),
        tender_id=TENDER_ID,
        category=RequirementType.FINANCIAL,
        field="emd_amount",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=Decimal(str(amount)),
            unit="INR",
            extra={"requirement_code": "EMD_DEPOSIT"},
        ),
        description="Earnest Money Deposit (EMD)",
    )


def make_exp_req(years: int = 3) -> Requirement:
    """Experience requirement."""
    return Requirement(
        requirement_id=uuid.uuid4(),
        tender_id=TENDER_ID,
        category=RequirementType.EXPERIENCE,
        field="experience_years",
        rule_type=RuleType.EXPERIENCE,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=years,
            extra={"requirement_code": "PRIOR_EXPERIENCE"},
        ),
        description="Prior experience requirement",
    )


# ===========================================================================
# 1. Exemption Triggered
# ===========================================================================

class TestExemptionTriggered:

    def test_startup_turnover_exemption_triggered(self):
        """Bidder is STARTUP -> MINIMUM_TURNOVER requirement is EXEMPT."""
        req = make_turnover_req(1500000)
        # Even if turnover evidence is below threshold or absent:
        turnover_ev = make_evidence("annual_turnover", Decimal("500000"))
        startup_ev = make_evidence("bidder_category", "STARTUP")

        exemption_rule = {
            "type": "EXEMPTION",
            "name": "STARTUP_TURNOVER_EXEMPTION",
            "condition": {
                "field": "bidder_category",
                "operator": "EQUAL",
                "value": "STARTUP",
            },
            "exempts": ["MINIMUM_TURNOVER"],
        }

        result = engine.evaluate(
            req,
            turnover_ev,
            exemptions=[exemption_rule],
            evidence_map={"bidder_category": startup_ev, "annual_turnover": turnover_ev},
        )

        assert result.status == S.EXEMPT
        assert result.external_status == S.PASS
        assert result.is_pass is True
        assert "exempted because" in result.reason
        assert "STARTUP" in result.reason

    def test_pydantic_exemption_rule_triggered(self):
        """Using ExemptionRule model instance directly."""
        req = make_turnover_req(1500000)
        turnover_ev = make_evidence("annual_turnover", Decimal("200000"))
        mse_ev = make_evidence("is_mse_registered", True)

        rule = ExemptionRule(
            name="MSE_GENERAL_EXEMPTION",
            condition=ExemptionCondition(
                field="is_mse_registered",
                operator=Operator.EQUAL,
                value=True,
            ),
            exempts=["annual_turnover"],
            description="Micro and Small Enterprise waiver",
        )

        result = engine.evaluate(
            req,
            turnover_ev,
            exemptions=[rule],
            evidence_map={"is_mse_registered": mse_ev},
        )

        assert result.status == S.EXEMPT
        assert result.is_pass is True


# ===========================================================================
# 2. Exemption Not Triggered (Condition False)
# ===========================================================================

class TestExemptionNotTriggered:

    def test_non_exempt_bidder_evaluates_original_pass(self):
        """Condition is false -> original requirement evaluates and passes."""
        req = make_turnover_req(1500000)
        # Bidder is not a startup, but has 25L turnover (>= 15L required)
        turnover_ev = make_evidence("annual_turnover", Decimal("2500000"))
        category_ev = make_evidence("bidder_category", "LARGE_ENTERPRISE")

        exemption_rule = {
            "type": "EXEMPTION",
            "name": "STARTUP_EXEMPTION",
            "condition": {
                "field": "bidder_category",
                "operator": "EQUAL",
                "value": "STARTUP",
            },
            "exempts": ["MINIMUM_TURNOVER"],
        }

        result = engine.evaluate(
            req,
            turnover_ev,
            exemptions=[exemption_rule],
            evidence_map={"bidder_category": category_ev, "annual_turnover": turnover_ev},
        )

        assert result.status == S.PASS
        # Original rule reason
        assert "₹25,00,000 is greater than or equal to the required ₹15,00,000" in result.reason

    def test_non_exempt_bidder_evaluates_original_fail(self):
        """Condition is false -> original requirement evaluates and fails."""
        req = make_turnover_req(1500000)
        # Bidder is not a startup, and only has 8L turnover (< 15L required)
        turnover_ev = make_evidence("annual_turnover", Decimal("800000"))
        category_ev = make_evidence("bidder_category", "LARGE_ENTERPRISE")

        exemption_rule = {
            "type": "EXEMPTION",
            "name": "STARTUP_EXEMPTION",
            "condition": {
                "field": "bidder_category",
                "operator": "EQUAL",
                "value": "STARTUP",
            },
            "exempts": ["MINIMUM_TURNOVER"],
        }

        result = engine.evaluate(
            req,
            turnover_ev,
            exemptions=[exemption_rule],
            evidence_map={"bidder_category": category_ev, "annual_turnover": turnover_ev},
        )

        assert result.status == S.FAIL
        assert result.is_fail is True
        assert "₹8,00,000 is NOT greater than or equal to the required ₹15,00,000" in result.reason



# ===========================================================================
# 3. Uncertain Exemption Condition
# ===========================================================================

class TestUncertainExemptionCondition:

    def test_missing_condition_evidence_gives_review(self):
        """When evidence for the exemption condition is absent -> REVIEW."""
        req = make_turnover_req(1500000)
        turnover_ev = make_evidence("annual_turnover", Decimal("500000"))
        # bidder_category evidence is NOT provided in evidence_map

        exemption_rule = {
            "type": "EXEMPTION",
            "name": "STARTUP_EXEMPTION",
            "condition": {
                "field": "bidder_category",
                "operator": "EQUAL",
                "value": "STARTUP",
            },
            "exempts": ["MINIMUM_TURNOVER"],
        }

        result = engine.evaluate(
            req,
            turnover_ev,
            exemptions=[exemption_rule],
            evidence_map={"annual_turnover": turnover_ev},
        )

        assert result.status == S.REVIEW
        assert result.is_review is True
        assert "Exemption applicability for 'annual_turnover' is uncertain" in result.reason

    def test_low_confidence_condition_evidence_gives_review(self):
        """Condition evidence has low confidence (< 0.5) -> REVIEW."""
        req = make_turnover_req(1500000)
        turnover_ev = make_evidence("annual_turnover", Decimal("500000"))
        startup_ev = make_evidence("bidder_category", "STARTUP", confidence=0.35)

        exemption_rule = {
            "type": "EXEMPTION",
            "condition": {
                "field": "bidder_category",
                "operator": "EQUAL",
                "value": "STARTUP",
            },
            "exempts": ["MINIMUM_TURNOVER"],
        }

        result = engine.evaluate(
            req,
            turnover_ev,
            exemptions=[exemption_rule],
            evidence_map={"bidder_category": startup_ev, "annual_turnover": turnover_ev},
        )

        assert result.status == S.REVIEW


# ===========================================================================
# 4. Multiple Exemptions
# ===========================================================================

class TestMultipleExemptions:

    def test_multiple_exemptions_one_triggers_for_target(self):
        """
        Rule 1: MSE exempts EMD
        Rule 2: STARTUP exempts MINIMUM_TURNOVER
        Bidder is STARTUP but not MSE.
        - Turnover -> EXEMPT
        - EMD -> Evaluates original (e.g. 50k < 100k -> FAIL)
        """
        turnover_req = make_turnover_req(1500000)
        emd_req = make_emd_req(100000)

        rules = [
            {
                "type": "EXEMPTION",
                "name": "MSE_EMD_EXEMPTION",
                "condition": {"field": "is_mse", "operator": "EQUAL", "value": True},
                "exempts": ["EMD_DEPOSIT", "emd_amount"],
            },
            {
                "type": "EXEMPTION",
                "name": "STARTUP_TURNOVER_EXEMPTION",
                "condition": {"field": "bidder_category", "operator": "EQUAL", "value": "STARTUP"},
                "exempts": ["MINIMUM_TURNOVER"],
            },
        ]

        ev_map = {
            "is_mse": make_evidence("is_mse", False),
            "bidder_category": make_evidence("bidder_category", "STARTUP"),
            "annual_turnover": make_evidence("annual_turnover", Decimal("100000")),
            "emd_amount": make_evidence("emd_amount", Decimal("50000")),
        }

        # Evaluate turnover
        res_turnover = engine.evaluate(turnover_req, ev_map["annual_turnover"], exemptions=rules, evidence_map=ev_map)
        assert res_turnover.status == S.EXEMPT

        # Evaluate EMD
        res_emd = engine.evaluate(emd_req, ev_map["emd_amount"], exemptions=rules, evidence_map=ev_map)
        assert res_emd.status == S.FAIL  # 50,000 < 100,000

    def test_multiple_exemptions_batch_evaluation(self):
        """evaluate_batch with multiple requirements and exemptions."""
        reqs = [make_turnover_req(1500000), make_emd_req(100000)]

        rules = [
            {
                "type": "EXEMPTION",
                "name": "STARTUP_FULL_WAIVER",
                "condition": {"field": "bidder_category", "operator": "EQUAL", "value": "STARTUP"},
                "exempts": ["MINIMUM_TURNOVER", "EMD_DEPOSIT"],
            },
        ]

        ev_map = {
            "bidder_category": make_evidence("bidder_category", "STARTUP"),
            "annual_turnover": make_evidence("annual_turnover", Decimal("0")),
            "emd_amount": make_evidence("emd_amount", Decimal("0")),
        }

        results = engine.evaluate_batch(reqs, ev_map, exemptions=rules)
        assert len(results) == 2
        assert results[0].status == S.EXEMPT
        assert results[1].status == S.EXEMPT


# ===========================================================================
# 5. Exemption Affecting Multiple Requirements
# ===========================================================================

class TestExemptionAffectingMultipleRequirements:

    def test_single_rule_exempts_turnover_and_experience(self):
        """One rule exempts both turnover and experience for STARTUP."""
        turnover_req = make_turnover_req(1500000)
        exp_req = make_exp_req(3)

        rule = {
            "type": "EXEMPTION",
            "name": "DPIIT_STARTUP_POLICY_EXEMPTION",
            "condition": {"field": "is_dpiit_recognized", "operator": "EQUAL", "value": True},
            "exempts": ["MINIMUM_TURNOVER", "PRIOR_EXPERIENCE"],
            "description": "Public Procurement Policy for Startups (Prior Turnover & Experience Exemption)",
        }

        ev_map = {
            "is_dpiit_recognized": make_evidence("is_dpiit_recognized", True),
            "annual_turnover": make_evidence("annual_turnover", Decimal("0")),
            "experience_years": make_evidence("experience_years", 0),
        }

        res1 = engine.evaluate(turnover_req, ev_map["annual_turnover"], exemptions=[rule], evidence_map=ev_map)
        res2 = engine.evaluate(exp_req, ev_map["experience_years"], exemptions=[rule], evidence_map=ev_map)

        assert res1.status == S.EXEMPT
        assert res2.status == S.EXEMPT
        assert "DPIIT_STARTUP_POLICY_EXEMPTION" in res1.reason
        assert "DPIIT_STARTUP_POLICY_EXEMPTION" in res2.reason


# ===========================================================================
# 6. Invalid Exemption Definitions
# ===========================================================================

class TestInvalidExemptionDefinitions:

    def test_missing_condition_returns_review(self):
        req = make_turnover_req(1500000)
        bad_rule = {
            "type": "EXEMPTION",
            # missing "condition"
            "exempts": ["MINIMUM_TURNOVER"],
        }
        result = engine.evaluate(req, make_evidence("annual_turnover", Decimal("2000000")), exemptions=[bad_rule])
        assert result.status == S.REVIEW
        assert "invalid exemption definition" in result.reason.lower()

    def test_missing_exempts_returns_review(self):
        req = make_turnover_req(1500000)
        bad_rule = {
            "type": "EXEMPTION",
            "condition": {"field": "bidder_category", "operator": "EQUAL", "value": "STARTUP"},
            # missing "exempts"
        }
        result = engine.evaluate(req, make_evidence("annual_turnover", Decimal("2000000")), exemptions=[bad_rule])
        assert result.status == S.REVIEW

    def test_unknown_operator_returns_review(self):
        req = make_turnover_req(1500000)
        bad_rule = {
            "type": "EXEMPTION",
            "condition": {"field": "bidder_category", "operator": "UNKNOWN_OP", "value": "STARTUP"},
            "exempts": ["MINIMUM_TURNOVER"],
        }
        result = engine.evaluate(req, make_evidence("annual_turnover", Decimal("2000000")), exemptions=[bad_rule])
        assert result.status == S.REVIEW


# ===========================================================================
# 7. Auditability
# ===========================================================================

class TestExemptionAuditability:

    def test_audit_fields_populated_on_exemption(self):
        req = make_turnover_req(1500000)
        startup_ev = make_evidence("bidder_category", "STARTUP")

        rule = {
            "type": "EXEMPTION",
            "name": "RULE_001",
            "condition": {"field": "bidder_category", "operator": "EQUAL", "value": "STARTUP"},
            "exempts": ["MINIMUM_TURNOVER"],
        }

        result = engine.evaluate(
            req,
            None,
            exemptions=[rule],
            evidence_map={"bidder_category": startup_ev},
        )

        assert result.status == S.EXEMPT
        assert result.rule_type == RuleType.EXEMPTION
        assert result.evidence_reference == startup_ev.source_document
        assert result.is_pass is True
        assert "STARTUP" in result.reason
        assert "RULE_001" in result.reason
