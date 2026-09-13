"""
Test Suite: Phase 22.3 - Deterministic Final Decision Explanation
Verifies:
1. QUALIFIED result produces a qualified explanation with accurate mandatory requirement count.
2. NOT_QUALIFIED result identifies the failed mandatory requirement.
3. NOT_QUALIFIED explanation includes actual detected and expected values when available.
4. Evidence source document/page is included when available.
5. MANUAL_REVIEW identifies unresolved requirements and explains why human review is required.
6. UNRESOLVED is never described as FAILED (strict vocabulary invariant).
7. Multiple failed mandatory requirements are all represented in the explanation.
8. Critical document-forensics anomaly triggers an authenticity explanation.
9. decision_factors structured list is cleanly populated.
10. Fallback execution path deterministically provides decision_explanation.
"""
import uuid
import pytest
from app.schemas.verification import (
    N8nVerificationResponse,
    N8nVerificationPayload,
    TenderRequirementItemInput,
    BidderEvidenceItemInput,
    N8nAgentResult,
    StructuredEvidenceItem,
    RequirementEvaluation,
    VerificationResponse,
    VerificationDecisionEnum,
    RequirementComplianceEnum,
)
from app.services.verification_aggregator import verification_aggregator
from app.services.verification_service import VerificationService


class TestPhase22_3DecisionExplanation:

    def test_qualified_explanation_with_mandatory_count(self):
        """1. QUALIFIED result produces a qualified explanation with accurate mandatory requirement count."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-3-01",
            verification_id="VER-22-3-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
                TenderRequirementItemInput(requirement_id="R3", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
                TenderRequirementItemInput(requirement_id="R4", category="EXPERIENCE", requirement_type="EXPERIENCE", rule="EXPERIENCE_PERIOD", mandatory=True),
                TenderRequirementItemInput(requirement_id="R5", category="DOCUMENT", requirement_type="DOCUMENT", rule="REQUIRED_DOCUMENT", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="AAACB2929P"),
                BidderEvidenceItemInput(evidence_id="E3", bidder_id=b_id, field="annual_turnover", value=60000000),
                BidderEvidenceItemInput(evidence_id="E4", bidder_id=b_id, field="years_of_experience", value=7),
                BidderEvidenceItemInput(evidence_id="E5", bidder_id=b_id, field="document", value="doc_hash_valid"),
            ],
            required_agents=["GST_AGENT", "PAN_AGENT", "FINANCIAL_AGENT", "EXPERIENCE_AGENT", "DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}),
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}),
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
            N8nAgentResult(agent="DOCUMENT_FORENSICS_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-3-01",
            request_id="REQ-22-3-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["All verification criteria met"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.QUALIFIED
        assert resp.decision_explanation is not None
        assert "all 5 mandatory tender requirements were successfully verified" in resp.decision_explanation
        assert "No mandatory requirements failed or remain unresolved" in resp.decision_explanation
        assert len(resp.decision_factors) == 5
        assert all(f["type"] == "PASSED_REQUIREMENT" for f in resp.decision_factors)

    def test_not_qualified_identifies_failed_mandatory_requirement_with_values_and_evidence(self):
        """2, 3, 4. NOT_QUALIFIED explanation identifies failed mandatory requirement, detected/expected values, and source doc/page."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-3-02",
            verification_id="VER-22-3-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Sigma Infra Pvt Ltd",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-FIN-TURNOVER",
                    category="FINANCIAL",
                    requirement_type="FINANCIAL",
                    rule="MINIMUM_TURNOVER",
                    mandatory=True,
                    required_value="₹50 lakh",
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-FIN-01",
                    bidder_id=b_id,
                    field="average_turnover",
                    value="₹42 lakh",
                    source_document="financial_statement.pdf",
                    page_number=4,
                    text_snippet="Average annual turnover: ₹42 lakh",
                ),
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                agent_id="FINANCIAL_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.98,
                evidence=[
                    StructuredEvidenceItem(
                        source_document="financial_statement.pdf",
                        page_number=4,
                        field="average_turnover",
                        detected_value="₹42 lakh",
                        expected_value="₹50 lakh",
                        evidence_text="Average annual turnover: ₹42 lakh",
                    )
                ],
                findings=["Turnover below required threshold"],
                reason="Turnover is below minimum threshold.",
                issues=["Turnover is below minimum threshold."],
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-3-02",
            request_id="REQ-22-3-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Sigma Infra Pvt Ltd",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=85.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["MINIMUM_TURNOVER"],
            warnings=[],
            reasons=["Turnover insufficient"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.NOT_QUALIFIED
        assert resp.decision_explanation is not None
        exp = resp.decision_explanation

        # Verifies the exact required components
        assert "Bidder is not qualified because the mandatory MINIMUM_TURNOVER requirement failed" in exp
        assert "₹42 lakh" in exp
        assert "₹50 lakh" in exp
        assert "financial_statement.pdf" in exp
        assert "page 4" in exp

        # Verifies structured decision factors
        assert len(resp.decision_factors) >= 1
        factor = resp.decision_factors[0]
        assert factor["type"] == "FAILED_REQUIREMENT"
        assert factor["rule"] == "MINIMUM_TURNOVER"
        assert factor["status"] == "FAIL"

    def test_manual_review_identifies_unresolved_requirement_and_never_calls_it_fail(self):
        """5 & 6. MANUAL_REVIEW identifies unresolved requirements, explains human review, and never describes them as FAILED."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-3-03",
            verification_id="VER-22-3-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Nova Services",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-EXP-01",
                    category="EXPERIENCE",
                    requirement_type="EXPERIENCE",
                    rule="EXPERIENCE_PERIOD",
                    mandatory=True,
                ),
            ],
            bidder_evidence=[],  # Insufficient evidence submitted
            required_agents=["EXPERIENCE_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="EXPERIENCE_AGENT",
                agent_id="EXPERIENCE_AGENT",
                status="UNVERIFIED",
                decision="MANUAL_REVIEW",
                confidence=None,
                evidence={},
                findings=["Experience documents inconclusive"],
                reason="Verification evidence was insufficient.",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-3-03",
            request_id="REQ-22-3-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Nova Services",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=40.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["Pending review"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW
        exp = resp.decision_explanation
        assert exp is not None

        # Must mention manual review and the unresolved requirement
        assert "Manual review is required because" in exp
        assert "EXPERIENCE_PERIOD" in exp
        assert "could not be conclusively verified" in exp
        assert "verification evidence was insufficient" in exp

        # Invariant: UNRESOLVED is NEVER described as FAIL or failed in the explanation
        assert "requirement failed" not in exp.lower()
        assert "status: fail" not in exp.lower()

        # Decision factors
        assert len(resp.decision_factors) >= 1
        factor = resp.decision_factors[0]
        assert factor["type"] == "UNRESOLVED_REQUIREMENT"
        assert factor["status"] == "UNRESOLVED"

    def test_manual_review_with_submitted_evidence_document_and_page(self):
        """4 & 5. MANUAL_REVIEW includes source document and page number when evidence was submitted but inconclusive."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-3-04",
            verification_id="VER-22-3-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Delta Engineering",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-EXP-02",
                    category="EXPERIENCE",
                    requirement_type="EXPERIENCE",
                    rule="EXPERIENCE_PERIOD",
                    mandatory=True,
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-EXP-01",
                    bidder_id=b_id,
                    field="years_of_experience",
                    value=4,
                    source_document="experience_cert.pdf",
                    page_number=2,
                ),
            ],
            required_agents=["EXPERIENCE_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="EXPERIENCE_AGENT",
                agent_id="EXPERIENCE_AGENT",
                status="UNVERIFIED",
                decision="MANUAL_REVIEW",
                confidence=None,  # Not low partial, genuinely unverified
                evidence=[
                    StructuredEvidenceItem(
                        source_document="experience_cert.pdf",
                        page_number=2,
                        field="years_of_experience",
                        detected_value=4,
                    )
                ],
                findings=["Certificate scope ambiguous"],
                reason="Scope of previous project requires human review.",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-3-04",
            request_id="REQ-22-3-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Delta Engineering",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=35.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["Scope ambiguous"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW
        exp = resp.decision_explanation
        assert "Manual review is required because" in exp
        assert "EXPERIENCE_PERIOD" in exp
        assert "experience_cert.pdf" in exp
        assert "page 2" in exp

    def test_multiple_failed_mandatory_requirements_all_represented(self):
        """7. Multiple failed mandatory requirements are all represented in the explanation."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-3-05",
            verification_id="VER-22-3-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Multi-Fail Bidder Ltd",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-GST-01",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="GST_REGISTRATION",
                    mandatory=True,
                    required_value="ACTIVE",
                ),
                TenderRequirementItemInput(
                    requirement_id="REQ-FIN-01",
                    category="FINANCIAL",
                    requirement_type="FINANCIAL",
                    rule="MINIMUM_TURNOVER",
                    mandatory=True,
                    required_value="50000000",
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-GST",
                    bidder_id=b_id,
                    field="gstin",
                    value="CANCELLED",
                    source_document="gst_notice.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="EVD-FIN",
                    bidder_id=b_id,
                    field="average_turnover",
                    value="20000000",
                    source_document="audited_accounts.pdf",
                    page_number=3,
                ),
            ],
            required_agents=["GST_AGENT", "FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="GST_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.99,
                evidence=[
                    StructuredEvidenceItem(
                        source_document="gst_notice.pdf",
                        page_number=1,
                        field="gstin",
                        detected_value="CANCELLED",
                        expected_value="ACTIVE",
                    )
                ],
                issues=["GST registration is cancelled"],
            ),
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.98,
                evidence=[
                    StructuredEvidenceItem(
                        source_document="audited_accounts.pdf",
                        page_number=3,
                        field="average_turnover",
                        detected_value="20000000",
                        expected_value="50000000",
                    )
                ],
                issues=["Turnover is 20,000,000 against required 50,000,000"],
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-3-05",
            request_id="REQ-22-3-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Multi-Fail Bidder Ltd",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=95.0,
            risk_level="CRITICAL",
            agent_results=agent_res,
            failed_requirements=["GST_REGISTRATION", "MINIMUM_TURNOVER"],
            warnings=[],
            reasons=["Multiple criteria failed"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.NOT_QUALIFIED
        exp = resp.decision_explanation
        assert "multiple mandatory requirements failed" in exp
        assert "GST_REGISTRATION" in exp
        assert "MINIMUM_TURNOVER" in exp
        assert "gst_notice.pdf" in exp
        assert "audited_accounts.pdf" in exp
        assert len(resp.decision_factors) == 2

    def test_document_forensics_anomaly_explanation(self):
        """8. Critical document-forensics anomaly triggers an authenticity explanation."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-3-06",
            verification_id="VER-22-3-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Suspect Bidder Corp",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="R-DOC",
                    category="DOCUMENT",
                    requirement_type="DOCUMENT",
                    rule="REQUIRED_DOCUMENT",
                    mandatory=True,
                )
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E-DOC",
                    bidder_id=b_id,
                    field="document",
                    value="anomaly_doc_hash",
                    source_document="suspicious.pdf",
                    page_number=1,
                )
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                agent_id="DOCUMENT_FORENSICS_AGENT",
                status="UNVERIFIED",
                decision="MANUAL_REVIEW",
                confidence=None,
                issues=["Font inconsistency and unresolved document authenticity anomaly"],
                evidence={},
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-3-06",
            request_id="REQ-22-3-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Suspect Bidder Corp",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=70.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["Document anomaly"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW
        exp = resp.decision_explanation
        assert "DOCUMENT_FORENSICS_AGENT" in exp or "REQUIRED_DOCUMENT" in exp
        assert "document authenticity anomaly" in exp or "could not be conclusively verified" in exp

    def test_fallback_execution_generates_explanation_deterministically(self):
        """10. Fallback execution path deterministically provides decision_explanation."""
        service = VerificationService()
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-FALLBACK-22-3",
            verification_id="VER-FALLBACK-22-3",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Fallback Bidder Inc",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-GST-FB",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="GST_REGISTRATION",
                    mandatory=True,
                    required_value="ACTIVE",
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-G-FB",
                    bidder_id=b_id,
                    field="gstin",
                    value="29ABCDE1234F1Z5",
                    source_document="GST_Cert.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="EVD-P-FB",
                    bidder_id=b_id,
                    field="pan",
                    value="ABCDE1234F",
                    source_document="PAN_Cert.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["GST_AGENT"],
        )

        n8n_resp = service._execute_local_multi_agent_fallback(
            payload=payload,
            error_reason="n8n service offline",
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision_explanation is not None
        assert len(resp.decision_explanation) > 0
        assert "Bidder is" in resp.decision_explanation
