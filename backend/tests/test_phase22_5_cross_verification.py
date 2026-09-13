"""
Test Suite: Phase 22.5 - Deterministic Cross-Verification of Existing Evidence
Verifies:
1. Matching GSTIN across two documents -> CONSISTENT.
2. Different GSTIN across two documents -> INCONSISTENT.
3. Matching PAN across two documents -> CONSISTENT.
4. Different PAN across two documents -> INCONSISTENT.
5. Matching legal entity name -> CONSISTENT.
6. Conflicting legal entity names -> INCONSISTENT.
7. Matching turnover values -> CONSISTENT.
8. Conflicting turnover values -> INCONSISTENT.
9. Missing second value -> UNRESOLVED, NOT INCONSISTENT.
10. Page/source provenance is preserved.
11. Existing Phase 22.1 semantic invariants remain unchanged.
12. Existing Phase 22.2 evidence remains unchanged.
13. Existing Phase 22.3 decision explanation remains unchanged.
14. Existing Phase 22.4 confidence remains unchanged.
15. No LLM/Groq call is introduced.
"""
from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import patch

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
    VerificationCrossVerification,
)
from app.services.verification_aggregator import verification_aggregator


class TestPhase22_5CrossVerification:

    def test_matching_gstin_across_two_documents_is_consistent(self):
        """1. Matching GSTIN across two documents -> CONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-01",
            verification_id="VER-22-5-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="GST_Certificate.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="Company_Profile.pdf",
                    page_number=2,
                ),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-01",
            request_id="REQ-22-5-01",
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
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.cross_verification is not None
        cv = resp.cross_verification
        assert isinstance(cv, VerificationCrossVerification)
        assert cv.overall_status == "CONSISTENT"

        gst_check = next((c for c in cv.checks if c.field == "gstin"), None)
        assert gst_check is not None
        assert gst_check.check_id == "GSTIN_CROSS_DOCUMENT"
        assert gst_check.status == "CONSISTENT"
        assert len(gst_check.values) == 2
        assert "matches" in gst_check.reason.lower()

    def test_different_gstin_across_two_documents_is_inconsistent(self):
        """2. Different GSTIN across two documents -> INCONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-02",
            verification_id="VER-22-5-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="GST_Certificate.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="gstin",
                    value="27XYZCB9999P1Z1",
                    source_document="Company_Profile.pdf",
                    page_number=3,
                ),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-02",
            request_id="REQ-22-5-02",
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
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.cross_verification is not None
        cv = resp.cross_verification
        assert cv.overall_status == "INCONSISTENT"

        gst_check = next((c for c in cv.checks if c.field == "gstin"), None)
        assert gst_check is not None
        assert gst_check.status == "INCONSISTENT"
        assert len(gst_check.values) == 2
        assert "differ" in gst_check.reason.lower()

    def test_matching_pan_is_consistent(self):
        """3. Matching PAN across two documents -> CONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-03",
            verification_id="VER-22-5-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="pan",
                    value="AAACB2929P",
                    source_document="PAN_Card.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="pan",
                    value="AAACB2929P",
                    source_document="Bank_Certificate.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-03",
            request_id="REQ-22-5-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
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

        pan_check = next((c for c in resp.cross_verification.checks if c.field == "pan"), None)
        assert pan_check is not None
        assert pan_check.status == "CONSISTENT"
        assert pan_check.values[0].value == "AAACB2929P"
        assert pan_check.values[1].value == "AAACB2929P"

    def test_different_pan_is_inconsistent(self):
        """4. Different PAN across two documents -> INCONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-04",
            verification_id="VER-22-5-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="pan",
                    value="AAACB2929P",
                    source_document="PAN.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="pan",
                    value="AAACB9999P",
                    source_document="GST.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-04",
            request_id="REQ-22-5-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
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

        pan_check = next((c for c in resp.cross_verification.checks if c.field == "pan"), None)
        assert pan_check is not None
        assert pan_check.status == "INCONSISTENT"
        assert resp.cross_verification.overall_status == "INCONSISTENT"

    def test_matching_legal_entity_name_is_consistent(self):
        """5. Matching legal entity name -> CONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-05",
            verification_id="VER-22-5-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="legal_name",
                    value="Apex Constructions Ltd",
                    source_document="Incorporation.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="company_name",
                    value="Apex Constructions Ltd.",
                    source_document="Tax_Return.pdf",
                    page_number=2,
                ),
            ],
            required_agents=[],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-05",
            request_id="REQ-22-5-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=[],
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        name_check = next((c for c in resp.cross_verification.checks if c.field == "bidder_name"), None)
        assert name_check is not None
        assert name_check.status == "CONSISTENT"

    def test_conflicting_legal_entity_names_is_inconsistent(self):
        """6. Conflicting legal entity names -> INCONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-06",
            verification_id="VER-22-5-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="legal_name",
                    value="Apex Constructions Ltd",
                    source_document="DocA.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="legal_name",
                    value="Zenith Infrastructure Pvt Ltd",
                    source_document="DocB.pdf",
                    page_number=1,
                ),
            ],
            required_agents=[],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-06",
            request_id="REQ-22-5-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=[],
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        name_check = next((c for c in resp.cross_verification.checks if c.field == "bidder_name"), None)
        assert name_check is not None
        assert name_check.status == "INCONSISTENT"
        assert resp.cross_verification.overall_status == "INCONSISTENT"

    def test_matching_turnover_values_is_consistent(self):
        """7. Matching turnover values -> CONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-07",
            verification_id="VER-22-5-07",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="annual_turnover",
                    value="₹42 lakh",
                    source_document="Financial_Report_A.pdf",
                    page_number=4,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="annual_turnover",
                    value="4200000",
                    source_document="CA_Certificate.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-07",
            request_id="REQ-22-5-07",
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
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        to_check = next((c for c in resp.cross_verification.checks if c.field == "annual_turnover"), None)
        assert to_check is not None
        assert to_check.status == "CONSISTENT"

    def test_conflicting_turnover_values_is_inconsistent(self):
        """8. Conflicting turnover values -> INCONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-08",
            verification_id="VER-22-5-08",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="annual_turnover",
                    value="₹42 lakh",
                    source_document="Financial_Report_A.pdf",
                    page_number=4,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="annual_turnover",
                    value="₹60 lakh",
                    source_document="CA_Certificate.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-08",
            request_id="REQ-22-5-08",
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
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        to_check = next((c for c in resp.cross_verification.checks if c.field == "annual_turnover"), None)
        assert to_check is not None
        assert to_check.status == "INCONSISTENT"
        assert "Turnover discrepancy detected" in to_check.reason
        assert resp.cross_verification.overall_status == "INCONSISTENT"

    def test_missing_second_value_is_unresolved_not_inconsistent(self):
        """9. Missing second value -> UNRESOLVED, NOT INCONSISTENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-09",
            verification_id="VER-22-5-09",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Single Doc Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="GST_Only.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-09",
            request_id="REQ-22-5-09",
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

        gst_check = next((c for c in resp.cross_verification.checks if c.field == "gstin"), None)
        assert gst_check is not None
        assert gst_check.status == "UNRESOLVED"
        assert gst_check.status != "INCONSISTENT"
        assert len(gst_check.values) == 1
        assert resp.cross_verification.overall_status == "UNRESOLVED"

    def test_page_and_source_provenance_preserved(self):
        """10. Page and source document provenance is preserved without fabrication."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-10",
            verification_id="VER-22-5-10",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Provenance Bidder",
            tender_requirements=[],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E10",
                    bidder_id=b_id,
                    field="pan",
                    value="ABCDE1234F",
                    source_document="PAN_Official.pdf",
                    page_number=3,
                ),
            ],
            required_agents=[],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-10",
            request_id="REQ-22-5-10",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Provenance Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=[],
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        pan_check = next((c for c in resp.cross_verification.checks if c.field == "pan"), None)
        assert pan_check is not None
        v = pan_check.values[0]
        assert v.source_document == "PAN_Official.pdf"
        assert v.page_number == 3
        assert v.evidence_id == "E10"
        assert v.value == "ABCDE1234F"

    def test_all_existing_phase_invariants_preserved(self):
        """11, 12, 13, 14. Phase 22.1 semantics, 22.2 evidence, 22.3 explanation, and 22.4 confidence remain unchanged."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-11",
            verification_id="VER-22-5-11",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Invariant Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="gst_cert.pdf",
                    page_number=1,
                    source_section="Taxpayer Details",
                ),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="GST_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.99,
                evidence={"gstin": "29AAACB2929P1Z5", "source_document": "gst_cert.pdf", "page_number": 1},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-11",
            request_id="REQ-22-5-11",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Invariant Bidder",
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

        # 11. Phase 22.1: Semantic separation
        assert "GST_AGENT" in resp.passed_agents
        assert "GST_REGISTRATION" in resp.passed_requirements
        assert not any(a.endswith("_AGENT") for a in resp.passed_requirements)

        # 12. Phase 22.2: Structured evidence
        assert len(resp.requirements[0].evidence) > 0
        assert resp.requirements[0].evidence[0].source_document == "gst_cert.pdf"

        # 13. Phase 22.3: Decision explanation
        assert resp.decision_explanation is not None
        assert "mandatory tender requirements were successfully verified" in resp.decision_explanation

        # 14. Phase 22.4: Confidence breakdown
        assert resp.confidence_breakdown is not None
        assert resp.confidence_breakdown.overall_confidence == 0.99
        assert resp.confidence_breakdown.overall_confidence == resp.overall_confidence

        # Phase 22.5: Cross-verification
        assert resp.cross_verification is not None

        # Decision & Risk score unchanged:
        assert resp.decision == VerificationDecisionEnum.QUALIFIED
        assert resp.risk_score == 2.0

    def test_no_additional_llm_call_occurs(self):
        """15. Verifies that zero LLM / Groq calls occur during cross-verification."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-5-15",
            verification_id="VER-22-5-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Deterministic Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="doc1.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="doc2.pdf",
                    page_number=2,
                ),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-5-15",
            request_id="REQ-22-5-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Deterministic Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        with patch("app.services.ai_gateway.ai_gateway.analyze_ambiguous_clause") as mock_ai:
            resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
            mock_ai.assert_not_called()

        assert resp.cross_verification is not None
        assert resp.cross_verification.overall_status == "CONSISTENT"
