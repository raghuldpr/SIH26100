"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_final_validation_scenarios.py: Validation of the 9 core engine contract scenarios.

Scenarios:
1. Minimum annual turnover = ₹15L; Bidder = ₹21L -> PASS
2. Minimum annual turnover = ₹15L; Bidder = ₹8L -> FAIL
3. Minimum annual turnover = ₹15L; Bidder evidence = missing -> REVIEW
4. Turnover >= ₹15L AND Experience >= 5 yrs; both PASS -> PASS
5. Turnover PASS, Experience FAIL -> FAIL
6. ISO 9001 OR ISO 14001; FAIL + PASS -> PASS
7. OEM bidder requires OEM authorization; OEM = true, Authorization = missing -> FAIL
8. Startup exemption explicitly supplied for turnover; Startup = true -> EXEMPT internally and excluded from turnover failure
9. Experience relevance cannot be deterministically established -> REVIEW
"""
from __future__ import annotations

import uuid
import pytest

from app.compliance.engine import ComplianceEngine
from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.models import BidderEvidence, Requirement, RuleDefinition

engine = ComplianceEngine()
BIDDER_ID = uuid.uuid4()
TENDER_ID = uuid.uuid4()


# ===========================================================================
# Test scenario 1: Min turnover ₹15L, Bidder ₹21L -> PASS
# ===========================================================================

def test_scenario_1_turnover_above_minimum_passes():
    req = Requirement(
        tender_id=TENDER_ID,
        category="FINANCIAL",
        field="annual_turnover",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=1500000,
            unit="INR",
        ),
        mandatory=True,
    )
    ev = BidderEvidence(
        bidder_id=BIDDER_ID,
        field="annual_turnover",
        value=2100000,
        source_document="balance_sheet_2025.pdf",
    )

    result = engine.evaluate(req, ev)
    assert result.status == ComplianceStatus.PASS
    assert result.is_pass is True
    assert "greater than or equal to" in result.reason
    assert result.actual_value == 2100000
    assert result.required_value == 1500000


# ===========================================================================
# Test scenario 2: Min turnover ₹15L, Bidder ₹8L -> FAIL
# ===========================================================================

def test_scenario_2_turnover_below_minimum_fails():
    req = Requirement(
        tender_id=TENDER_ID,
        category="FINANCIAL",
        field="annual_turnover",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=1500000,
            unit="INR",
        ),
        mandatory=True,
    )
    ev = BidderEvidence(
        bidder_id=BIDDER_ID,
        field="annual_turnover",
        value=800000,
        source_document="balance_sheet_2025.pdf",
    )

    result = engine.evaluate(req, ev)
    assert result.status == ComplianceStatus.FAIL
    assert result.is_pass is False
    assert "NOT greater than or equal to" in result.reason
    assert result.actual_value == 800000


# ===========================================================================
# Test scenario 3: Min turnover ₹15L, Bidder evidence missing -> REVIEW
# ===========================================================================

def test_scenario_3_turnover_missing_evidence_triggers_review():
    req = Requirement(
        tender_id=TENDER_ID,
        category="FINANCIAL",
        field="annual_turnover",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=1500000,
            unit="INR",
        ),
        mandatory=True,
    )

    result = engine.evaluate(req, None)
    assert result.status == ComplianceStatus.REVIEW
    assert result.is_pass is False
    assert "No numeric evidence provided" in result.reason


# ===========================================================================
# Test scenario 4: Turnover >= ₹15L AND Experience >= 5 yrs; both PASS -> PASS
# ===========================================================================

def test_scenario_4_logical_and_both_pass():
    req = Requirement(
        tender_id=TENDER_ID,
        category="COMPOSITE",
        field="turnover_and_experience",
        rule_type=RuleType.LOGICAL,
        rule_definition=RuleDefinition(
            operator=Operator.EQUAL,
            logical_operator="AND",
            sub_rules=[
                RuleDefinition(
                    operator=Operator.GREATER_THAN_OR_EQUAL,
                    required_value=1500000,
                    extra={"field": "annual_turnover", "rule_type": "NUMERIC"},
                ),
                RuleDefinition(
                    operator=Operator.GREATER_THAN_OR_EQUAL,
                    required_value=5,
                    extra={"field": "experience_years", "rule_type": "NUMERIC"},
                ),
            ],
        ),
    )
    ev_map = {
        "annual_turnover": BidderEvidence(bidder_id=BIDDER_ID, field="annual_turnover", value=2000000),
        "experience_years": BidderEvidence(bidder_id=BIDDER_ID, field="experience_years", value=7),
    }

    result = engine.evaluate(req, None, evidence_map=ev_map)
    assert result.status == ComplianceStatus.PASS
    assert result.is_pass is True
    assert "LOGICAL AND of 2 sub-rule(s) → PASS" in result.reason


# ===========================================================================
# Test scenario 5: Turnover PASS, Experience FAIL -> FAIL
# ===========================================================================

def test_scenario_5_logical_and_one_fail_fails():
    req = Requirement(
        tender_id=TENDER_ID,
        category="COMPOSITE",
        field="turnover_and_experience",
        rule_type=RuleType.LOGICAL,
        rule_definition=RuleDefinition(
            operator=Operator.EQUAL,
            logical_operator="AND",
            sub_rules=[
                RuleDefinition(
                    operator=Operator.GREATER_THAN_OR_EQUAL,
                    required_value=1500000,
                    extra={"field": "annual_turnover", "rule_type": "NUMERIC"},
                ),
                RuleDefinition(
                    operator=Operator.GREATER_THAN_OR_EQUAL,
                    required_value=5,
                    extra={"field": "experience_years", "rule_type": "NUMERIC"},
                ),
            ],
        ),
    )
    ev_map = {
        "annual_turnover": BidderEvidence(bidder_id=BIDDER_ID, field="annual_turnover", value=2000000),  # PASS
        "experience_years": BidderEvidence(bidder_id=BIDDER_ID, field="experience_years", value=3),     # FAIL (< 5)
    }

    result = engine.evaluate(req, None, evidence_map=ev_map)
    assert result.status == ComplianceStatus.FAIL
    assert result.is_pass is False
    assert "LOGICAL AND of 2 sub-rule(s) → FAIL" in result.reason


# ===========================================================================
# Test scenario 6: ISO 9001 OR ISO 14001; FAIL + PASS -> PASS
# ===========================================================================

def test_scenario_6_logical_or_fail_plus_pass_is_pass():
    req = Requirement(
        tender_id=TENDER_ID,
        category="STATUTORY",
        field="iso_certification",
        rule_type=RuleType.LOGICAL,
        rule_definition=RuleDefinition(
            operator=Operator.EQUAL,
            logical_operator="OR",
            sub_rules=[
                RuleDefinition(
                    operator=Operator.EQUAL,
                    required_value=True,
                    extra={"field": "iso_9001", "rule_type": "BOOLEAN"},
                ),
                RuleDefinition(
                    operator=Operator.EQUAL,
                    required_value=True,
                    extra={"field": "iso_14001", "rule_type": "BOOLEAN"},
                ),
            ],
        ),
    )
    ev_map = {
        "iso_9001": BidderEvidence(bidder_id=BIDDER_ID, field="iso_9001", value=False),  # FAIL
        "iso_14001": BidderEvidence(bidder_id=BIDDER_ID, field="iso_14001", value=True), # PASS
    }

    result = engine.evaluate(req, None, evidence_map=ev_map)
    assert result.status == ComplianceStatus.PASS
    assert result.is_pass is True
    assert "LOGICAL OR of 2 sub-rule(s) → PASS" in result.reason



# ===========================================================================
# Test scenario 7: OEM bidder requires OEM authorization. OEM = true, Auth = missing -> FAIL
# ===========================================================================

def test_scenario_7_conditional_oem_auth_missing_fails():
    req = Requirement(
        tender_id=TENDER_ID,
        category="TECHNICAL",
        field="oem_compliance",
        rule_type=RuleType.CONDITIONAL,
        rule_definition=RuleDefinition(
            operator=Operator.EQUAL,
            logical_operator="IF",
            sub_rules=[
                RuleDefinition(
                    operator=Operator.EQUAL,
                    required_value=True,
                    extra={"field": "bidder_is_oem", "rule_type": "BOOLEAN"},
                ),
                RuleDefinition(
                    operator=Operator.PRESENT,
                    required_value="OEM_AUTHORIZATION",
                    extra={
                        "field": "oem_authorization",
                        "rule_type": "DOCUMENT_PRESENCE",
                        "mandatory": True,
                    },
                ),
            ],
        ),
    )
    # OEM is true, but OEM authorization document is missing
    ev_map = {
        "bidder_is_oem": BidderEvidence(bidder_id=BIDDER_ID, field="bidder_is_oem", value=True),
        # "oem_authorization" not in ev_map -> None
    }

    result = engine.evaluate(req, None, evidence_map=ev_map)
    assert result.status == ComplianceStatus.FAIL
    assert result.is_pass is False
    assert "Condition 'bidder_is_oem' was PASS" in result.reason
    assert "definitely absent" in result.reason


# ===========================================================================
# Test scenario 8: Startup exemption explicitly supplied for turnover; Startup = true -> EXEMPT
# ===========================================================================

def test_scenario_8_startup_exemption_turnover_exempted():
    req = Requirement(
        tender_id=TENDER_ID,
        category="FINANCIAL",
        field="annual_turnover",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=1500000,
            extra={"requirement_code": "MINIMUM_TURNOVER"},
        ),
    )
    # Bidder only has 2L turnover, which would normally FAIL
    ev_turnover = BidderEvidence(bidder_id=BIDDER_ID, field="annual_turnover", value=200000)
    ev_map = {
        "annual_turnover": ev_turnover,
        "bidder_category": BidderEvidence(bidder_id=BIDDER_ID, field="bidder_category", value="STARTUP"),
    }

    exemption = {
        "type": "EXEMPTION",
        "name": "DPIIT_STARTUP_POLICY",
        "condition": {
            "field": "bidder_category",
            "operator": "EQUAL",
            "value": "STARTUP",
        },
        "exempts": ["MINIMUM_TURNOVER"],
    }

    result = engine.evaluate(req, ev_turnover, exemptions=[exemption], evidence_map=ev_map)
    assert result.status == ComplianceStatus.EXEMPT
    assert result.is_pass is True  # Exemptions map to passing externally
    assert "DPIIT_STARTUP_POLICY" in result.reason
    assert "exempted" in result.reason.lower()


# ===========================================================================
# Test scenario 9: Experience relevance cannot be deterministically established -> REVIEW
# ===========================================================================

def test_scenario_9_experience_uncertain_relevance_triggers_review():
    req = Requirement(
        tender_id=TENDER_ID,
        category="EXPERIENCE",
        field="solar_project_experience",
        rule_type=RuleType.EXPERIENCE,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=3,  # 3 years
            extra={
                "minimum_years": 3,
                "minimum_contracts": 1,
                "required_category": "SOLAR_INSTALLATION",
            },
        ),
    )
    # Evidence has ambiguous/uncertain category relevance
    contract_evidence = BidderEvidence(
        bidder_id=BIDDER_ID,
        field="solar_project_experience",
        value=[
            {
                "contract_id": "CNT-2023-99",
                "category": "ELECTRICAL_HYBRID_SOLAR",
                "relevance": "UNCERTAIN",  # Upstream flag indicating relevance cannot be confirmed
                "years": 4,
                "verification_status": "VERIFIED",
            }
        ],
    )

    result = engine.evaluate(req, contract_evidence)
    assert result.status == ComplianceStatus.REVIEW
    assert result.is_pass is False
    assert "uncertain" in result.reason.lower()
    assert "Manual review required" in result.reason
