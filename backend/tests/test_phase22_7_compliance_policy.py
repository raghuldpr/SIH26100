"""
Test Suite: Phase 22.7 - Deterministic Compliance Policy for Cross-Verification and Forensics
Verifies:
1. Mandatory requirement FAIL -> NOT_QUALIFIED.
2. Mandatory requirement UNRESOLVED -> MANUAL_REVIEW.
3. Cross-verification INCONSISTENT -> MANUAL_REVIEW.
4. Cross-verification UNRESOLVED -> does not automatically disqualify.
5. HIGH/CRITICAL existing forensic anomaly -> MANUAL_REVIEW.
6. LOW/MEDIUM forensic warning -> warning only unless existing policy says otherwise.
7. Multiple findings follow deterministic precedence.
8. Mandatory FAIL takes precedence over cross-verification review.
9. Policy does not change existing confidence.
10. Policy does not arbitrarily change risk score.
11. Decision explanation remains consistent with policy.
12. Phase 22.1 invariants remain intact.
13. Phase 22.2 evidence remains intact.
14. Phase 22.3 explanation remains intact.
15. Phase 22.4 confidence breakdown remains intact.
16. Phase 22.5 cross-verification remains intact.
17. Phase 22.6 forensics remains intact.
18. No LLM/Groq call is introduced.
19. Persistence/reconstruction preserves compliance_policy.
"""
from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import patch

from app.schemas.verification import (
    AppliedPolicyRule,
    BidderEvidenceItemInput,
    CrossVerificationCheckItem,
    ForensicAnomalyItem,
    ForensicDocumentResult,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    PolicyFindingItem,
    RequirementComplianceEnum,
    RequirementEvaluation,
    StructuredEvidenceItem,
    TenderRequirementItemInput,
    VerificationCompliancePolicy,
    VerificationConfidenceBreakdown,
    VerificationCrossVerification,
    VerificationDecisionEnum,
    VerificationDocumentForensics,
    VerificationResponse,
)
from app.services.verification_aggregator import verification_aggregator
from app.models.verification import VerificationExecution
from app.crud.crud_verification import crud_verification


class TestPhase22_7CompliancePolicy:

    def test_mandatory_requirement_fail_yields_not_qualified(self):
        """1. Mandatory requirement with status=FAIL must yield NOT_QUALIFIED blocking finding."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-01",
            verification_id="VER-22-7-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Failing Bidder Ltd",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-MIN-TURNOVER",
                    category="FINANCIAL",
                    requirement_type="FINANCIAL",
                    rule="MINIMUM_TURNOVER",
                    mandatory=True,
                    required_value="₹50 lakh",
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="annual_turnover",
                    value="₹30 lakh",
                    source_document="turnover_cert.pdf",
                    page_number=1,
                )
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.98,
                evidence=[
                    StructuredEvidenceItem(
                        source_document="turnover_cert.pdf",
                        page_number=1,
                        field="annual_turnover",
                        detected_value="₹30 lakh",
                        expected_value="₹50 lakh",
                    )
                ],
                reason="Turnover is below mandatory minimum.",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-01",
            request_id="REQ-22-7-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Failing Bidder Ltd",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=85.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["MINIMUM_TURNOVER"],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        assert cp.final_status == "NOT_QUALIFIED"
        assert resp.decision == VerificationDecisionEnum.NOT_QUALIFIED
        assert len(cp.blocking_findings) >= 1
        blocking = cp.blocking_findings[0]
        assert blocking.finding_type == "MANDATORY_REQUIREMENT_FAILURE"
        assert blocking.severity == "CRITICAL"
        assert "MINIMUM_TURNOVER" in blocking.source or "REQ-MIN-TURNOVER" in blocking.source

        applied = next((r for r in cp.applied_rules if r.rule_id == "MANDATORY_REQUIREMENT_FAILURE"), None)
        assert applied is not None
        assert applied.action == "NOT_QUALIFIED"

    def test_mandatory_requirement_unresolved_yields_manual_review(self):
        """2. Mandatory requirement with status=UNRESOLVED must NOT be treated as FAIL; yields MANUAL_REVIEW."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-02",
            verification_id="VER-22-7-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Incomplete Evidence Bidder",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-EXP",
                    category="EXPERIENCE",
                    requirement_type="EXPERIENCE",
                    rule="EXPERIENCE_PERIOD",
                    mandatory=True,
                ),
            ],
            bidder_evidence=[],
            required_agents=["EXPERIENCE_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="EXPERIENCE_AGENT",
                status="UNVERIFIED",
                decision="MANUAL_REVIEW",
                confidence=None,
                evidence=[],
                reason="Verification evidence was insufficient.",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-02",
            request_id="REQ-22-7-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Incomplete Evidence Bidder",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=35.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        assert cp.final_status == "MANUAL_REVIEW"
        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW
        assert len(cp.blocking_findings) == 0  # Crucial: Unresolved is never blocking fail
        assert len(cp.review_findings) >= 1
        review_item = cp.review_findings[0]
        assert review_item.finding_type in ("MANDATORY_REQUIREMENT_UNRESOLVED", "AGENT_REVIEW_REQUIRED")
        assert "EXPERIENCE_PERIOD" in review_item.source or "REQ-EXP" in review_item.source

    def test_cross_verification_inconsistent_yields_manual_review(self):
        """3. Cross-verification INCONSISTENT triggers MANUAL_REVIEW."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-03",
            verification_id="VER-22-7-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Mismatch Bidder Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_VERIFICATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="pan", value="AAACB2929P", source_document="Pan_Card.pdf", page_number=1),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="ZZZCB9999P", source_document="Tender_Form.pdf", page_number=2),
            ],
            required_agents=["PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=0.96, evidence={"pan": "AAACB2929P"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-03",
            request_id="REQ-22-7-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Mismatch Bidder Ltd",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        assert cp.final_status == "MANUAL_REVIEW"
        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW

        cross_findings = [f for f in cp.review_findings if f.finding_type == "CROSS_VERIFICATION_INCONSISTENCY"]
        assert len(cross_findings) >= 1
        assert cross_findings[0].source == "pan"
        assert "differ" in cross_findings[0].description.lower() or "discrepancy" in cross_findings[0].description.lower()

        applied = next((r for r in cp.applied_rules if r.rule_id == "CROSS_VERIFICATION_INCONSISTENCY"), None)
        assert applied is not None
        assert applied.action == "MANUAL_REVIEW"

    def test_cross_verification_unresolved_does_not_automatically_disqualify(self):
        """4. Cross-verification UNRESOLVED remains informational warning and does not disqualify."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-04",
            verification_id="VER-22-7-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Single Doc Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="GST_Certificate.pdf", page_number=1),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={"gstin": "29AAACB2929P1Z5"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-04",
            request_id="REQ-22-7-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Single Doc Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        assert cp.final_status == "QUALIFIED"
        assert resp.decision == VerificationDecisionEnum.QUALIFIED
        assert len(cp.blocking_findings) == 0

    def test_high_critical_forensic_anomaly_yields_manual_review(self):
        """5. Existing HIGH/CRITICAL forensic anomaly triggers MANUAL_REVIEW."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-05",
            verification_id="VER-22-7-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Suspicious Bidder Corp",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="GST_Cert.pdf", page_number=1),
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT", "GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.88,
                evidence={
                    "source_document": "GST_Cert.pdf",
                    "anomalies": [
                        {
                            "anomaly_id": "ANO-TAMPER-01",
                            "type": "TAMPERING_INDICATOR",
                            "severity": "HIGH",
                            "description": "Inconsistent font rendering and glyph displacement detected.",
                        }
                    ],
                },
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={"gstin": "29AAACB2929P1Z5"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-05",
            request_id="REQ-22-7-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Suspicious Bidder Corp",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=25.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        assert cp.final_status == "MANUAL_REVIEW"
        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW

        forensic_reviews = [f for f in cp.review_findings if f.finding_type == "FORENSIC_ANOMALY"]
        assert len(forensic_reviews) >= 1
        assert forensic_reviews[0].severity == "HIGH"
        # Language must state suspicious indicator, not criminal/fraud claim
        assert "Suspicious document indicator requires manual review" in forensic_reviews[0].description
        assert "criminal" not in forensic_reviews[0].description.lower()
        assert "fraudulent" not in forensic_reviews[0].description.lower()

    def test_low_medium_forensic_warning_is_warning_only(self):
        """6. LOW/MEDIUM forensic anomaly produces advisory warning only and remains QUALIFIED if clean."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-06",
            verification_id="VER-22-7-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Low Warning Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="GST_Cert.pdf", page_number=1),
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT", "GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.90,
                evidence={
                    "source_document": "GST_Cert.pdf",
                    "anomalies": [
                        {
                            "anomaly_id": "ANO-LOW-01",
                            "type": "TEXT_DENSITY_ANOMALY",
                            "severity": "LOW",
                            "description": "Low text density observed on header region.",
                        }
                    ],
                },
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={"gstin": "29AAACB2929P1Z5"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-06",
            request_id="REQ-22-7-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Low Warning Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        assert cp.final_status == "QUALIFIED"
        assert resp.decision == VerificationDecisionEnum.QUALIFIED
        assert len(cp.blocking_findings) == 0
        assert len(cp.review_findings) == 0
        assert any("LOW" in w for w in cp.warnings)

    def test_multiple_findings_follow_deterministic_precedence(self):
        """7. Multiple findings adhere to exact precedence rules."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        # An unresolved requirement AND a cross-verification inconsistency both yield MANUAL_REVIEW
        payload = N8nVerificationPayload(
            request_id="REQ-22-7-07",
            verification_id="VER-22-7-07",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Multi Finding Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="EXPERIENCE", requirement_type="EXPERIENCE", rule="EXPERIENCE_PERIOD", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="pan", value="AAACB2929P", source_document="Pan1.pdf"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="BBBCB2929P", source_document="Pan2.pdf"),
            ],
            required_agents=["EXPERIENCE_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="EXPERIENCE_AGENT",
                status="UNVERIFIED",
                decision="MANUAL_REVIEW",
                confidence=None,
                evidence=[],
                reason="Verification evidence insufficient.",
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-07",
            request_id="REQ-22-7-07",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Multi Finding Bidder",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=40.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        assert cp.final_status == "MANUAL_REVIEW"
        types = [f.finding_type for f in cp.review_findings]
        assert "MANDATORY_REQUIREMENT_UNRESOLVED" in types or "AGENT_REVIEW_REQUIRED" in types
        assert "CROSS_VERIFICATION_INCONSISTENCY" in types

    def test_mandatory_fail_takes_precedence_over_cross_verification_review(self):
        """8. Mandatory FAIL unconditionally determines NOT_QUALIFIED despite cross-verification review."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-08",
            verification_id="VER-22-7-08",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Fail Overrides Review Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="FINANCIAL", requirement_type="FINANCIAL", rule="MINIMUM_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="Doc1.pdf"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="gstin", value="27XYZCB9999P1Z1", source_document="Doc2.pdf"),
            ],
            required_agents=["FINANCIAL_AGENT", "GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.95,
                evidence=[],
                reason="Turnover criteria failed.",
            ),
            N8nAgentResult(
                agent="GST_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.90,
                evidence={"gstin": "29AAACB2929P1Z5"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-08",
            request_id="REQ-22-7-08",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Fail Overrides Review Ltd",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=85.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["MINIMUM_TURNOVER"],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.compliance_policy is not None
        cp = resp.compliance_policy
        # Mandatory FAIL takes precedence!
        assert cp.final_status == "NOT_QUALIFIED"
        assert resp.decision == VerificationDecisionEnum.NOT_QUALIFIED
        assert len(cp.blocking_findings) >= 1
        assert len(cp.review_findings) >= 1  # Cross verification is still transparently captured in review_findings

    def test_policy_does_not_change_existing_confidence(self):
        """9. Policy status and confidence are independent; overall_confidence formula is unchanged."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-09",
            verification_id="VER-22-7-09",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="High Confidence Review Bidder",
            tender_requirements=[],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="pan", value="AAACB2929P", source_document="Pan1.pdf"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="ZZZCB9999P", source_document="Pan2.pdf"),
            ],
            required_agents=["PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=0.94, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-09",
            request_id="REQ-22-7-09",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="High Confidence Review Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # Policy triggers MANUAL_REVIEW
        assert resp.compliance_policy.final_status == "MANUAL_REVIEW"
        # But confidence is purely preserved from agent results (0.94)
        assert resp.overall_confidence == 0.94
        assert resp.confidence_breakdown.overall_confidence == 0.94

    def test_policy_does_not_arbitrarily_change_risk_score(self):
        """10. Policy does not arbitrarily change existing risk score."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-10",
            verification_id="VER-22-7-10",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Risk Preserved Bidder",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-10",
            request_id="REQ-22-7-10",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Risk Preserved Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=14.5,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.risk_score == 14.5

    def test_decision_explanation_consistent_with_policy(self):
        """11. Decision explanation accurately and deterministically reflects the applied compliance policy."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-11",
            verification_id="VER-22-7-11",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Explanation Check Corp",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_VERIFICATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="pan", value="AAACB2929P", source_document="DocA.pdf"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="DIFFB2929P", source_document="DocB.pdf"),
            ],
            required_agents=["PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=0.96, evidence={"pan": "AAACB2929P"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-11",
            request_id="REQ-22-7-11",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Explanation Check Corp",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW
        assert resp.decision_explanation is not None
        # Must specifically state PAN values differ across submitted documents
        assert "Manual review is required because PAN values differ across submitted documents" in resp.decision_explanation

    def test_phase22_1_semantic_invariants_preserved(self):
        """12. Phase 22.1 semantic separation invariants remain intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-12",
            verification_id="VER-22-7-12",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Semantic Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="gst.pdf"),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={"gstin": "29AAACB2929P1Z5"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-12",
            request_id="REQ-22-7-12",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Semantic Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert "GST_AGENT" in resp.passed_agents
        assert "GST_REGISTRATION" in resp.passed_requirements
        assert not any(a.endswith("_AGENT") for a in resp.passed_requirements)

    def test_phase22_2_evidence_preserved(self):
        """13. Phase 22.2 structured evidence remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-13",
            verification_id="VER-22-7-13",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Evidence Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="certificate.pdf", page_number=3),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={"gstin": "29AAACB2929P1Z5"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-13",
            request_id="REQ-22-7-13",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Evidence Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert len(resp.requirements[0].evidence) > 0
        assert resp.requirements[0].evidence[0].source_document == "certificate.pdf"
        assert resp.requirements[0].evidence[0].page_number == 3

    def test_phase22_3_explanation_preserved(self):
        """14. Phase 22.3 explanation remains intact for clean qualification."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-14",
            verification_id="VER-22-7-14",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Explanation Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="doc.pdf"),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={"gstin": "29AAACB2929P1Z5"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-14",
            request_id="REQ-22-7-14",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Explanation Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert "all 1 mandatory tender requirements were successfully verified" in resp.decision_explanation

    def test_phase22_4_confidence_breakdown_preserved(self):
        """15. Phase 22.4 confidence breakdown remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-15",
            verification_id="VER-22-7-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Confidence Bidder",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-15",
            request_id="REQ-22-7-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Confidence Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.confidence_breakdown is not None
        assert resp.confidence_breakdown.overall_confidence == 0.95

    def test_phase22_5_cross_verification_preserved(self):
        """16. Phase 22.5 cross-verification remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-16",
            verification_id="VER-22-7-16",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Cross Bidder",
            tender_requirements=[],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="doc1.pdf"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="doc2.pdf"),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-16",
            request_id="REQ-22-7-16",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Cross Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.cross_verification is not None
        assert resp.cross_verification.overall_status == "CONSISTENT"

    def test_phase22_6_forensics_preserved(self):
        """17. Phase 22.6 document forensics remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-17",
            verification_id="VER-22-7-17",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Forensic Bidder",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.97,
                evidence={"source_document": "clean_doc.pdf"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-17",
            request_id="REQ-22-7-17",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Forensic Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        assert resp.document_forensics.overall_status == "CLEAN"

    def test_no_llm_groq_call_introduced(self):
        """18. Verifies zero LLM or Groq calls occur during policy evaluation."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-7-18",
            verification_id="VER-22-7-18",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="No LLM Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="doc.pdf"),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={"gstin": "29AAACB2929P1Z5"}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-7-18",
            request_id="REQ-22-7-18",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="No LLM Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        with patch("app.services.ai_gateway.ai_gateway.analyze_ambiguous_clause") as mock_ai:
            resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
            mock_ai.assert_not_called()
            assert resp.compliance_policy is not None

    def test_persistence_reconstruction_survives(self):
        """19. Verifies compliance_policy survives aggregation -> persistence -> API reconstruction."""
        b_id = uuid.uuid4()
        t_id = uuid.uuid4()
        exec_id = uuid.uuid4()

        policy = VerificationCompliancePolicy(
            final_status="MANUAL_REVIEW",
            blocking_findings=[],
            review_findings=[
                PolicyFindingItem(
                    finding_id="REVIEW-CROSS-01",
                    finding_type="CROSS_VERIFICATION_INCONSISTENCY",
                    severity="HIGH",
                    source="pan",
                    description="Cross-document discrepancy detected for pan: PAN values differ.",
                )
            ],
            warnings=["Advisory warning flag"],
            applied_rules=[
                AppliedPolicyRule(
                    rule_id="CROSS_VERIFICATION_INCONSISTENCY",
                    trigger="pan",
                    action="MANUAL_REVIEW",
                    reason="PAN values differ across submitted documents.",
                )
            ],
        )

        raw_resp = {
            "compliance_policy": policy.model_dump(),
            "decision_explanation": "Manual review is required because PAN values differ across submitted documents.",
        }

        execution = VerificationExecution(
            id=exec_id,
            verification_id="VER-22-7-19",
            request_id="REQ-22-7-19",
            tender_id=t_id,
            bidder_id=b_id,
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            overall_compliance="UNVERIFIED",
            risk_level="MEDIUM",
            risk_score=30.0,
            overall_confidence=0.91,
            compliance_summary={"compliance_policy": policy.model_dump(), "raw_response": raw_resp},
            requirements=[],
            agent_results=[],
            failed_requirements=[],
            warnings=["Advisory warning flag"],
            reasons=["Pending review"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        reconstructed = crud_verification.to_verification_response(execution)

        assert reconstructed.compliance_policy is not None
        rcp = reconstructed.compliance_policy
        assert isinstance(rcp, VerificationCompliancePolicy)
        assert rcp.final_status == "MANUAL_REVIEW"
        assert len(rcp.review_findings) == 1
        assert rcp.review_findings[0].finding_type == "CROSS_VERIFICATION_INCONSISTENCY"
        assert len(rcp.applied_rules) == 1
        assert rcp.applied_rules[0].rule_id == "CROSS_VERIFICATION_INCONSISTENCY"
