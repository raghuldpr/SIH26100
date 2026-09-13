"""
Test Suite: Phase 22.2 - Add Structured Evidence to Agent and Requirement Results
Verifies:
1. A passing requirement contains structured evidence when evidence exists.
2. A failed requirement contains requirement_id, status, reason, confidence, evidence.
3. A failed agent contains agent_id, status/normalized_status, confidence, reason, evidence.
4. An unresolved requirement has status = "UNRESOLVED" and is NOT represented as FAIL.
5. Source document references are preserved.
6. Page numbers are preserved when available.
7. Missing page numbers remain null (None) rather than fabricated.
8. Existing Phase 22.1 invariants still pass (agent vs requirement field separation).
9. Agent status normalization distinguishes VERIFIED, FAILED, UNRESOLVED, ERROR, NOT_APPLICABLE.
10. Fallback execution produces structured evidence with real values and null pages when missing.
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
    normalize_agent_status,
)
from app.services.verification_aggregator import verification_aggregator
from app.services.verification_service import VerificationService


class TestPhase22_2StructuredEvidence:

    def test_passing_requirement_contains_structured_evidence(self):
        """1. A passing requirement contains structured evidence when evidence exists."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-2-01",
            verification_id="VER-22-2-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Alpha Tech Infra",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-GST-01",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="GST_REGISTRATION",
                    mandatory=True,
                    description="Valid GSTIN certificate required",
                    required_value="ACTIVE",
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-GST-01",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="GST_Certificate.pdf",
                    page_number=1,
                    text_snippet="GSTIN: 29AAACB2929P1Z5 Active",
                ),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="GST_AGENT",
                agent_id="GST_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.99,
                evidence={
                    "gstin": "29AAACB2929P1Z5",
                    "status": "ACTIVE",
                    "source_document": "GST_Certificate.pdf",
                    "page_number": 1,
                },
                findings=["GST registration verified active"],
                reason="GSTIN is valid and active",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-2-01",
            request_id="REQ-22-2-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Alpha Tech Infra",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["All criteria passed"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # Verify passing requirement
        assert len(response.requirements) == 1
        req_eval = response.requirements[0]
        assert req_eval.requirement_id == "REQ-GST-01"
        assert req_eval.status == "PASS"
        assert req_eval.decision == "COMPLIANT"
        assert req_eval.confidence == 0.99

        # Structured evidence assertions
        assert len(req_eval.evidence) >= 1
        ev = req_eval.evidence[0]
        assert isinstance(ev, StructuredEvidenceItem)
        assert ev.source_document == "GST_Certificate.pdf"
        assert ev.page_number == 1
        assert ev.detected_value == "29AAACB2929P1Z5"
        assert ev.expected_value == "ACTIVE"

    def test_failed_requirement_contains_all_required_fields_and_evidence(self):
        """2. A failed requirement contains requirement_id, status, reason, confidence, and evidence."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-2-02",
            verification_id="VER-22-2-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Beta Build Corp",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-FIN-01",
                    category="FINANCIAL",
                    requirement_type="FINANCIAL",
                    rule="MINIMUM_TURNOVER",
                    mandatory=True,
                    description="Minimum average annual turnover >= Rs 50 Lakh",
                    required_value=5000000,
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-FIN-01",
                    bidder_id=b_id,
                    field="average_turnover",
                    value=4200000,
                    source_document="financial_statement.pdf",
                    page_number=4,
                    text_snippet="Average annual turnover: Rs 42 lakh",
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
                        detected_value=4200000,
                        expected_value=5000000,
                        evidence_text="Average annual turnover: Rs 42 lakh",
                    )
                ],
                findings=["Turnover ₹42 lakh below required ₹50 lakh"],
                reason="Average turnover is below the minimum requirement.",
                issues=["Deficit of 800,000 INR"],
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-2-02",
            request_id="REQ-22-2-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Beta Build Corp",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=85.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["MINIMUM_TURNOVER"],
            warnings=[],
            reasons=["Turnover insufficient"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # Requirement assertion
        assert len(response.requirements) == 1
        req_eval = response.requirements[0]
        assert req_eval.requirement_id == "REQ-FIN-01"
        assert req_eval.status == "FAIL"
        assert req_eval.decision == "NON_COMPLIANT"
        assert req_eval.confidence == 0.98
        assert req_eval.reason is not None and len(req_eval.reason) > 0
        assert len(req_eval.evidence) >= 1

        ev = req_eval.evidence[0]
        assert ev.source_document == "financial_statement.pdf"
        assert ev.page_number == 4
        assert ev.detected_value == 4200000
        assert ev.expected_value == 5000000
        assert "42 lakh" in (ev.evidence_text or "")

    def test_failed_agent_contains_structured_evidence(self):
        """3. A failed agent contains agent_id, status, confidence, reason, and structured evidence."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-2-03",
            verification_id="VER-22-2-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Gamma Supplies",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["EXPERIENCE_AGENT"],
        )

        ev_items = [
            StructuredEvidenceItem(
                source_document="experience_cert.pdf",
                page_number=2,
                field="similar_projects_completed",
                detected_value=1,
                expected_value=3,
                evidence_text="Completed only 1 similar road construction project",
            )
        ]

        agent_res = [
            N8nAgentResult(
                agent="EXPERIENCE_AGENT",
                agent_id="EXPERIENCE_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.95,
                evidence=ev_items,
                findings=["Insufficient project completion certificates"],
                reason="Bidder completed 1 project, required 3.",
                issues=["2 projects short"],
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-2-03",
            request_id="REQ-22-2-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Gamma Supplies",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=75.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["Experience criterion failed"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert len(response.agent_results) == 1
        agent = response.agent_results[0]
        assert agent.agent_id == "EXPERIENCE_AGENT"
        assert agent.status in ("FAILED", "FAIL")
        assert agent.normalized_status == "FAILED"
        assert agent.result == "NOT_QUALIFIED"
        assert agent.confidence == 0.95
        assert agent.reason == "Bidder completed 1 project, required 3."
        assert isinstance(agent.evidence, list)
        assert len(agent.evidence) == 1
        assert agent.evidence[0].source_document == "experience_cert.pdf"
        assert agent.evidence[0].page_number == 2
        assert agent.evidence[0].detected_value == 1
        assert agent.evidence[0].expected_value == 3

    def test_unresolved_requirement_remains_unresolved_not_fail(self):
        """4. An unresolved requirement remains status = UNRESOLVED and is NOT represented as FAIL."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-2-04",
            verification_id="VER-22-2-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Delta Services",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-UDYAM-01",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="MSME_UDYAM_REGISTRATION",
                    mandatory=False,
                    description="MSME Udyam Registration for preference",
                ),
            ],
            bidder_evidence=[],
            required_agents=["UDYAM_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="UDYAM_AGENT",
                agent_id="UDYAM_AGENT",
                status="UNVERIFIED",
                decision="MANUAL_REVIEW",
                confidence=0.5,
                evidence={},
                findings=["Document pending verification from MSME portal"],
                reason="MSME certificate portal was unreachable during scan",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-2-04",
            request_id="REQ-22-2-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Delta Services",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=35.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=["MSME portal offline"],
            reasons=["Pending verification"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # Requirement must be UNRESOLVED, not FAIL
        req = response.requirements[0]
        assert req.status == "UNRESOLVED"
        assert req.decision == "UNVERIFIED"
        assert req.status != "FAIL"
        assert req.decision != "NON_COMPLIANT"

        # Verification list assertions
        assert "MSME_UDYAM_REGISTRATION" not in response.failed_requirements
        assert "MSME_UDYAM_REGISTRATION" in response.review_requirements

    def test_source_document_and_page_number_preserved(self):
        """5 & 6. Source document and page numbers are preserved when available."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-2-05",
            verification_id="VER-22-2-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Epsilon Enterprises",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-PAN-01",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="PAN_CARD",
                    mandatory=True,
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-PAN-01",
                    bidder_id=b_id,
                    field="pan",
                    value="ABCDE1234F",
                    source_document="Annual_Report.pdf",
                    page_number=14,
                    text_snippet="Company PAN: ABCDE1234F",
                ),
            ],
            required_agents=["PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="PAN_AGENT",
                agent_id="PAN_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=1.0,
                evidence={
                    "pan": "ABCDE1234F",
                    "status": "VALID",
                    "source_document": "Annual_Report.pdf",
                    "page_number": 14,
                },
                findings=["PAN verified valid"],
                reason="PAN format and validity confirmed",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-2-05",
            request_id="REQ-22-2-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Epsilon Enterprises",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=0.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["All clear"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        req_eval = response.requirements[0]
        assert len(req_eval.evidence) >= 1
        ev = req_eval.evidence[0]
        assert ev.source_document == "Annual_Report.pdf"
        assert ev.page_number == 14

        ag = response.agent_results[0]
        assert len(ag.evidence) >= 1
        ag_ev = ag.evidence[0]
        assert ag_ev.source_document == "Annual_Report.pdf"
        assert ag_ev.page_number == 14

    def test_missing_page_numbers_remain_null_not_fabricated(self):
        """7. Missing page numbers remain null/None rather than fabricated."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-2-06",
            verification_id="VER-22-2-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Zeta Logistics",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-AFFIDAVIT-01",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="NON_BLACKLISTING_AFFIDAVIT",
                    mandatory=True,
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-AFF-01",
                    bidder_id=b_id,
                    field="affidavit",
                    value="True",
                    source_document="Affidavit.pdf",
                    page_number=None,  # Intentionally absent
                ),
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                agent_id="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.92,
                evidence={
                    "affidavit": "VALID",
                    "source_document": "Affidavit.pdf",
                    # No page number provided
                },
                findings=["Affidavit verified"],
                reason="Non-blacklisting affidavit clean",
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-2-06",
            request_id="REQ-22-2-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Zeta Logistics",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["Valid"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # Confirm requirement evidence page_number is None, NEVER 0 or 1
        req_eval = response.requirements[0]
        assert len(req_eval.evidence) >= 1
        ev = req_eval.evidence[0]
        assert ev.source_document == "Affidavit.pdf"
        assert ev.page_number is None

        # Confirm agent evidence page_number is None
        ag = response.agent_results[0]
        assert len(ag.evidence) >= 1
        assert ag.evidence[0].page_number is None

    def test_agent_status_normalization(self):
        """9. Agent status normalization distinguishes VERIFIED, FAILED, UNRESOLVED, ERROR, NOT_APPLICABLE."""
        assert normalize_agent_status("PASS") == "VERIFIED"
        assert normalize_agent_status("VERIFIED") == "VERIFIED"
        assert normalize_agent_status("QUALIFIED") == "VERIFIED"

        assert normalize_agent_status("FAIL") == "FAILED"
        assert normalize_agent_status("FAILED") == "FAILED"
        assert normalize_agent_status("NOT_QUALIFIED") == "FAILED"

        assert normalize_agent_status("UNVERIFIED") == "UNRESOLVED"
        assert normalize_agent_status("UNRESOLVED") == "UNRESOLVED"
        assert normalize_agent_status("REVIEW") == "UNRESOLVED"
        assert normalize_agent_status("MANUAL_REVIEW") == "UNRESOLVED"
        assert normalize_agent_status("INCONCLUSIVE") == "UNRESOLVED"
        assert normalize_agent_status("PENDING") == "UNRESOLVED"

        assert normalize_agent_status("ERROR") == "ERROR"
        assert normalize_agent_status("FAILED_EXECUTION") == "ERROR"

        assert normalize_agent_status("NOT_APPLICABLE") == "NOT_APPLICABLE"
        assert normalize_agent_status("SKIPPED") == "NOT_APPLICABLE"
        assert normalize_agent_status("NOT_EXECUTED") == "NOT_APPLICABLE"

    def test_fallback_execution_generates_structured_evidence(self):
        """10. VerificationService fallback execution produces structured evidence with real values and null pages when missing."""
        service = VerificationService()
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-FALLBACK-01",
            verification_id="VER-FALLBACK-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Omega Tech Systems",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-GST-F",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="GST_REGISTRATION",
                    mandatory=True,
                    required_value="ACTIVE",
                ),
                TenderRequirementItemInput(
                    requirement_id="REQ-FIN-F",
                    category="FINANCIAL",
                    requirement_type="FINANCIAL",
                    rule="MINIMUM_TURNOVER",
                    mandatory=True,
                    required_value=10000000,
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EVD-G-01",
                    bidder_id=b_id,
                    field="gstin",
                    value="29ABCDE1234F1Z5",
                    source_document="GST_Cert.pdf",
                    page_number=1,
                    text_snippet="GSTIN: 29ABCDE1234F1Z5",
                ),
                BidderEvidenceItemInput(
                    evidence_id="EVD-F-01",
                    bidder_id=b_id,
                    field="average_turnover",
                    value=4000000,  # Below 10,000,000 threshold
                    source_document="Turnover_Audited.pdf",
                    page_number=3,
                    text_snippet="Average turnover: 4,000,000",
                ),
            ],
            required_agents=["GST_AGENT", "FINANCIAL_AGENT"],
        )

        n8n_resp = service._execute_local_multi_agent_fallback(
            payload=payload,
            error_reason="n8n service unavailable for testing",
        )

        # Aggregate the fallback response
        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # Check GST_AGENT passed with structured evidence
        gst_agent = next(a for a in response.agent_results if a.agent == "GST_AGENT")
        assert gst_agent.status in ("PASS", "VERIFIED")
        assert gst_agent.normalized_status == "VERIFIED"
        assert len(gst_agent.evidence) >= 1
        assert gst_agent.evidence[0].source_document == "GST_Cert.pdf"
        assert gst_agent.evidence[0].page_number == 1
        assert gst_agent.evidence[0].detected_value == "29ABCDE1234F1Z5"

        # Check FINANCIAL_AGENT failed with structured evidence
        fin_agent = next(a for a in response.agent_results if a.agent == "FINANCIAL_AGENT")
        assert fin_agent.status in ("FAIL", "FAILED")
        assert fin_agent.normalized_status == "FAILED"
        assert len(fin_agent.evidence) >= 1
        assert fin_agent.evidence[0].source_document == "Turnover_Audited.pdf"
        assert fin_agent.evidence[0].page_number == 3
        assert fin_agent.evidence[0].detected_value == 4000000
        assert fin_agent.evidence[0].expected_value == 10000000

        # Check requirements
        gst_req = next(r for r in response.requirements if r.rule == "GST_REGISTRATION")
        assert gst_req.status == "PASS"
        assert len(gst_req.evidence) >= 1
        assert gst_req.evidence[0].source_document == "GST_Cert.pdf"

        fin_req = next(r for r in response.requirements if r.rule == "MINIMUM_TURNOVER")
        assert fin_req.status == "FAIL"
        assert len(fin_req.evidence) >= 1
        assert fin_req.evidence[0].detected_value == 4000000
        assert fin_req.evidence[0].expected_value == 10000000
