"""
Test Suite: Phase 22.4 - Explain Existing Verification Confidence
Verifies:
1. Qualified verification exposes confidence breakdown.
2. Not-qualified verification exposes confidence breakdown.
3. Manual-review/unresolved verification exposes unresolved confidence information.
4. Agent confidence values are preserved exactly.
5. Requirement confidence values are preserved exactly.
6. Existing overall confidence does not change:
   confidence_breakdown.overall_confidence == VerificationResponse.overall_confidence
7. Existing decision does not change.
8. Existing risk score does not change.
9. Existing Phase 22.1 invariants remain intact (passed/failed/review agents vs requirements).
10. Existing Phase 22.2 evidence remains intact (structured evidence items).
11. Existing Phase 22.3 explanation remains intact (deterministic decision explanation).
12. No additional LLM call occurs.
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
    VerificationConfidenceBreakdown,
)
from app.services.verification_aggregator import verification_aggregator
from app.services.verification_service import VerificationService


class TestPhase22_4ConfidenceBreakdown:

    def test_qualified_verification_exposes_confidence_breakdown(self):
        """1. Qualified verification exposes confidence breakdown with exact formula, inputs, and matching overall confidence."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-01",
            verification_id="VER-22-4-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Constructions Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
                TenderRequirementItemInput(requirement_id="R3", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="AAACB2929P"),
                BidderEvidenceItemInput(evidence_id="E3", bidder_id=b_id, field="annual_turnover", value=60000000),
            ],
            required_agents=["GST_AGENT", "PAN_AGENT", "FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={}),
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-4-01",
            request_id="REQ-22-4-01",
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

        # Invariants:
        assert resp.decision == VerificationDecisionEnum.QUALIFIED
        assert resp.confidence_breakdown is not None

        cb = resp.confidence_breakdown
        assert isinstance(cb, VerificationConfidenceBreakdown)
        assert cb.method == "arithmetic_mean"
        assert cb.formula == "round(sum(known_confidences) / len(known_confidences), 2)"
        assert cb.inputs == [0.99, 1.0, 0.98]

        # Consistency Invariant
        expected_confidence = round((0.99 + 1.0 + 0.98) / 3, 2)
        assert resp.overall_confidence == expected_confidence
        assert cb.overall_confidence == resp.overall_confidence
        assert cb.calculated_confidence == resp.overall_confidence

        # Contributing agents
        assert len(cb.agent_confidence) == 3
        agent_dict = {ag.agent_id: ag for ag in cb.agent_confidence}
        assert "GST_AGENT" in agent_dict
        assert agent_dict["GST_AGENT"].confidence == 0.99
        assert agent_dict["GST_AGENT"].status == "PASS"

        assert "PAN_AGENT" in agent_dict
        assert agent_dict["PAN_AGENT"].confidence == 1.0
        assert agent_dict["PAN_AGENT"].status == "PASS"

        assert "FINANCIAL_AGENT" in agent_dict
        assert agent_dict["FINANCIAL_AGENT"].confidence == 0.98
        assert agent_dict["FINANCIAL_AGENT"].status == "PASS"

        # Contributing requirements
        assert len(cb.requirement_confidence) == 3
        req_dict = {r.rule: r for r in cb.requirement_confidence}
        assert "GST_REGISTRATION" in req_dict
        assert req_dict["GST_REGISTRATION"].status == "PASS"
        assert "PAN_CARD" in req_dict
        assert req_dict["PAN_CARD"].status == "PASS"
        assert "AVERAGE_TURNOVER" in req_dict
        assert req_dict["AVERAGE_TURNOVER"].status == "PASS"

        # No unresolved items in qualified run
        assert len(cb.unresolved_items) == 0

    def test_not_qualified_verification_exposes_confidence_breakdown(self):
        """2. Not-qualified verification exposes confidence breakdown without changing numerical confidence."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-02",
            verification_id="VER-22-4-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Substandard Builders",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="annual_turnover", value=5000000),
            ],
            required_agents=["GST_AGENT", "FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="FAIL", decision="NOT_QUALIFIED", confidence=0.85, issues=["Turnover INR 5,000,000 below required minimum"], evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-4-02",
            request_id="REQ-22-4-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Substandard Builders",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=75.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["AVERAGE_TURNOVER"],
            warnings=[],
            reasons=["Turnover requirement failed"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.NOT_QUALIFIED
        expected_confidence = round((0.95 + 0.85) / 2, 2)
        assert resp.overall_confidence == expected_confidence

        cb = resp.confidence_breakdown
        assert cb is not None
        assert cb.overall_confidence == resp.overall_confidence
        assert cb.calculated_confidence == resp.overall_confidence
        assert cb.inputs == [0.95, 0.85]

        # Agent confidences
        fin_agent_cb = next(a for a in cb.agent_confidence if a.agent_id == "FINANCIAL_AGENT")
        assert fin_agent_cb.confidence == 0.85
        assert fin_agent_cb.status == "FAIL"

    def test_manual_review_unresolved_exposes_unresolved_confidence_items(self):
        """3. Manual-review/unresolved verification exposes unresolved confidence items without turning them into FAIL."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-03",
            verification_id="VER-22-4-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Pending Documents Corp",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="EXPERIENCE", requirement_type="EXPERIENCE", rule="EXPERIENCE_PERIOD", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
            ],
            required_agents=["GST_AGENT", "EXPERIENCE_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="UNRESOLVED", decision="MANUAL_REVIEW", confidence=0.50, issues=["Experience certificate partially illegible"], evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-4-03",
            request_id="REQ-22-4-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Pending Documents Corp",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=35.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=["Experience certificate partially illegible"],
            reasons=["Pending manual inspection of experience certificates"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.decision == VerificationDecisionEnum.MANUAL_REVIEW
        cb = resp.confidence_breakdown
        assert cb is not None

        # Check unresolved_items
        assert len(cb.unresolved_items) >= 1
        unres_types = [item.type for item in cb.unresolved_items]
        assert "REQUIREMENT" in unres_types or "AGENT" in unres_types

        # Verify status is NOT converted to FAIL
        for item in cb.unresolved_items:
            assert item.status != "FAIL"
            assert item.status != "FAILED"
            assert item.status in {"UNRESOLVED", "MANUAL_REVIEW", "UNVERIFIED", "PARTIALLY_COMPLIANT"}

    def test_agent_confidence_values_preserved_exactly(self):
        """4. Agent confidence values are preserved exactly, including nulls without fabrication."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-04",
            verification_id="VER-22-4-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Null Confidence Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="AAACB2929P"),
            ],
            required_agents=["GST_AGENT", "PAN_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.92, evidence={}),
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=None, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-4-04",
            request_id="REQ-22-4-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Null Confidence Bidder",
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

        cb = resp.confidence_breakdown
        assert cb is not None

        gst_item = next(a for a in cb.agent_confidence if a.agent_id == "GST_AGENT")
        assert gst_item.confidence == 0.92

        pan_item = next(a for a in cb.agent_confidence if a.agent_id == "PAN_AGENT")
        assert pan_item.confidence is None  # Never fabricated!

        # Arithmetic mean only includes non-null values
        assert cb.inputs == [0.92]
        assert cb.overall_confidence == 0.92
        assert resp.overall_confidence == 0.92

    def test_requirement_confidence_values_preserved_exactly(self):
        """5. Requirement confidence values are preserved exactly or null when unavailable."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-05",
            verification_id="VER-22-4-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Precision Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.975, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-4-05",
            request_id="REQ-22-4-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Precision Bidder",
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

        cb = resp.confidence_breakdown
        assert cb is not None
        assert len(cb.requirement_confidence) == 1
        rc = cb.requirement_confidence[0]
        assert rc.requirement_id == "R1"
        assert rc.rule == "GST_REGISTRATION"
        assert rc.confidence == 0.975
        assert rc.status == "PASS"

    def test_consistency_invariant_and_stability(self):
        """6, 7, 8. Consistency Invariant: confidence_breakdown.overall_confidence == resp.overall_confidence, and no alteration to decision or risk."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-06",
            verification_id="VER-22-4-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Stability Corp",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="annual_turnover", value=50000000),
            ],
            required_agents=["GST_AGENT", "FINANCIAL_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.96, evidence={}),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.88, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-4-06",
            request_id="REQ-22-4-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Stability Corp",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=8.5,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # 6. Strict overall confidence invariant
        assert resp.confidence_breakdown.overall_confidence == resp.overall_confidence
        assert resp.confidence_breakdown.calculated_confidence == resp.overall_confidence
        assert resp.overall_confidence == round((0.96 + 0.88) / 2, 2)

        # 7. Decision invariant
        assert resp.decision == VerificationDecisionEnum.QUALIFIED

        # 8. Risk score invariant
        assert resp.risk_score == 8.5
        assert resp.risk_level.value == "LOW"

    def test_phase22_1_phase22_2_phase22_3_invariants_preserved(self):
        """9, 10, 11. Preserves Phase 22.1 semantics, Phase 22.2 structured evidence, and Phase 22.3 explanations."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-07",
            verification_id="VER-22-4-07",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="MultiPhase Bidder",
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
                    source_page=1,
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
            verification_id="VER-22-4-07",
            request_id="REQ-22-4-07",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="MultiPhase Bidder",
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

        # Phase 22.1: Semantic separation
        assert "GST_AGENT" in resp.passed_agents
        assert "GST_REGISTRATION" in resp.passed_requirements
        assert not any(a.endswith("_AGENT") for a in resp.passed_requirements)

        # Phase 22.2: Structured evidence
        assert len(resp.requirements[0].evidence) > 0
        ev = resp.requirements[0].evidence[0]
        assert ev.source_document == "gst_cert.pdf"

        # Phase 22.3: Decision explanation
        assert resp.decision_explanation is not None
        assert "mandatory tender requirements were successfully verified" in resp.decision_explanation

        # Phase 22.4: Confidence breakdown
        assert resp.confidence_breakdown is not None
        assert resp.confidence_breakdown.overall_confidence == 0.99
        assert resp.confidence_breakdown.agent_confidence[0].agent_id == "GST_AGENT"

    def test_no_additional_llm_call_occurs(self):
        """12. Verifies that no LLM call (Groq, OpenAI, Claude, Gemini) occurs during confidence breakdown generation."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-4-08",
            verification_id="VER-22-4-08",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Deterministic Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
            ],
            required_agents=["GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-4-08",
            request_id="REQ-22-4-08",
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

        # Mock potential LLM clients to prove 0 calls
        with patch("app.services.ai_gateway.ai_gateway.analyze_ambiguous_clause") as mock_ai:
            resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
            mock_ai.assert_not_called()

        assert resp.confidence_breakdown is not None
        assert resp.confidence_breakdown.overall_confidence == 0.95
