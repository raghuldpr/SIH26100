"""
Test Suite: Phase 22.1 - Correct Agent vs Requirement Result Semantics
Verifies strict separation of Agent identifiers vs Requirement/Rule identifiers:
- passed_agents, failed_agents, review_agents contain ONLY agent IDs
- passed_requirements, failed_requirements, review_requirements contain ONLY requirement rule IDs
- QUALIFIED verification has zero failed or review requirements
- Unresolved requirement is classified as review/unresolved and NOT failed
"""
import uuid
import pytest
from app.schemas.verification import (
    N8nVerificationResponse,
    N8nVerificationPayload,
    TenderRequirementItemInput,
    BidderEvidenceItemInput,
    N8nAgentResult,
    VerificationResponse,
    VerificationDecisionEnum,
    RequirementComplianceEnum,
    DEFAULT_VERIFICATION_AGENTS,
)
from app.services.verification_aggregator import verification_aggregator
from app.services.verification_service import VerificationService


def _is_agent_id(item: str) -> bool:
    s = str(item).strip().upper()
    return s.endswith("_AGENT") or s in DEFAULT_VERIFICATION_AGENTS


def _is_requirement_id(item: str) -> bool:
    # A requirement ID must not be an agent ID
    return not _is_agent_id(item)


class TestPhase22_1AgentVsRequirementSemantics:

    def test_semantics_passed_agents_contains_agent_ids_only(self):
        """1. Verify passed_agents contains agent IDs only, never requirement IDs."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-SEM-01",
            request_id="REQ-SEM-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Semantics Test Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["All criteria passed"],
        )
        payload = N8nVerificationPayload(
            request_id="REQ-SEM-01",
            verification_id="VER-SEM-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Semantics Test Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
                TenderRequirementItemInput(requirement_id="R3", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="AAACB2929P"),
                BidderEvidenceItemInput(evidence_id="E3", bidder_id=b_id, field="annual_turnover", value=50000000),
            ],
            required_agents=["GST_AGENT", "PAN_AGENT", "FINANCIAL_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert len(response.passed_agents) > 0
        for ag in response.passed_agents:
            assert _is_agent_id(ag), f"Expected agent ID, got requirement ID: {ag}"
            assert not ag.startswith("GST_REGISTRATION")
            assert not ag.startswith("PAN_CARD")
            assert not ag.startswith("AVERAGE_TURNOVER")

    def test_semantics_failed_agents_contains_agent_ids_only(self):
        """2. Verify failed_agents contains agent IDs only, never requirement IDs."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="FAIL", decision="NOT_QUALIFIED", confidence=0.0, evidence={}, findings=[], issues=["Turnover inadequate"]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-SEM-02",
            request_id="REQ-SEM-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Fail Agent Bidder",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=80.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["AVERAGE_TURNOVER"],
            warnings=[],
            reasons=["Turnover inadequate"],
        )
        payload = N8nVerificationPayload(
            request_id="REQ-SEM-02",
            verification_id="VER-SEM-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Fail Agent Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="annual_turnover", value=1000),
            ],
            required_agents=["GST_AGENT", "FINANCIAL_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert "FINANCIAL_AGENT" in response.failed_agents
        for ag in response.failed_agents:
            assert _is_agent_id(ag), f"Expected agent ID, got: {ag}"
            assert ag != "AVERAGE_TURNOVER"

    def test_semantics_review_agents_contains_agent_ids_only(self):
        """3. Verify review_agents contains agent IDs only."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="REVIEW", decision="MANUAL_REVIEW", confidence=0.5, evidence={}, findings=[], issues=["Subjective clause"]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-SEM-03",
            request_id="REQ-SEM-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Review Agent Bidder",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=35.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=["Experience needs manual review"],
            reasons=["Review required"],
        )
        response = verification_aggregator.aggregate(n8n_resp=n8n_resp)

        assert "EXPERIENCE_AGENT" in response.review_agents
        for ag in response.review_agents:
            assert _is_agent_id(ag), f"Expected agent ID in review_agents, got: {ag}"

    def test_semantics_passed_requirements_contains_requirement_ids_only(self):
        """4. Verify passed_requirements contains requirement rule IDs only, never agent IDs."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-SEM-04",
            request_id="REQ-SEM-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Pass Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=0.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )
        payload = N8nVerificationPayload(
            request_id="REQ-SEM-04",
            verification_id="VER-SEM-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Pass Bidder",
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

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert "GST_REGISTRATION" in response.passed_requirements
        assert "PAN_CARD" in response.passed_requirements
        for req in response.passed_requirements:
            assert _is_requirement_id(req), f"Expected requirement ID, but got agent ID: {req}"
            assert not req.endswith("_AGENT")

    def test_semantics_failed_requirements_contains_requirement_ids_only(self):
        """5. Verify failed_requirements contains requirement rule IDs only, never agent IDs."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="FAIL", decision="NOT_QUALIFIED", confidence=0.0, evidence={}, findings=[], issues=["Turnover inadequate"]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-SEM-05",
            request_id="REQ-SEM-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Fail Bidder",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=75.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )
        payload = N8nVerificationPayload(
            request_id="REQ-SEM-05",
            verification_id="VER-SEM-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Fail Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R-FIN", category="FINANCIAL", requirement_type="FINANCIAL", rule="AVERAGE_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="annual_turnover", value=100),
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert "AVERAGE_TURNOVER" in response.failed_requirements
        for req in response.failed_requirements:
            assert _is_requirement_id(req), f"Expected requirement rule ID, got agent ID: {req}"
            assert not req.endswith("_AGENT")

    def test_semantics_review_requirements_contains_requirement_ids_only(self):
        """6. Verify review_requirements contains requirement rule IDs only, never agent IDs."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="REVIEW", decision="MANUAL_REVIEW", confidence=0.5, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-SEM-06",
            request_id="REQ-SEM-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Review Bidder",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=30.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )
        payload = N8nVerificationPayload(
            request_id="REQ-SEM-06",
            verification_id="VER-SEM-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Req Review Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R-EXP", category="EXPERIENCE", requirement_type="EXPERIENCE", rule="SIMILAR_WORK_EXPERIENCE", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="years_of_experience", value=5),
            ],
            required_agents=["EXPERIENCE_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert "SIMILAR_WORK_EXPERIENCE" in response.review_requirements
        for req in response.review_requirements:
            assert _is_requirement_id(req), f"Expected requirement ID, got agent ID: {req}"
            assert not req.endswith("_AGENT")

    def test_semantics_qualified_verification_has_no_failed_or_review_requirements(self):
        """7. Verify a QUALIFIED verification has no failed/review requirements and no failed/review agents."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={}, findings=[]),
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95, evidence={}, findings=[]),
            N8nAgentResult(agent="DOCUMENT_FORENSICS_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-QUAL-01",
            request_id="REQ-QUAL-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Qualified Perfect Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=0.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["All requirements passed"],
        )
        payload = N8nVerificationPayload(
            request_id="REQ-QUAL-01",
            verification_id="VER-QUAL-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Qualified Perfect Bidder",
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
                BidderEvidenceItemInput(evidence_id="E3", bidder_id=b_id, field="annual_turnover", value=50000000),
                BidderEvidenceItemInput(evidence_id="E4", bidder_id=b_id, field="years_of_experience", value=8),
                BidderEvidenceItemInput(evidence_id="E5", bidder_id=b_id, field="document", value="doc_hash_123"),
            ],
            required_agents=["GST_AGENT", "PAN_AGENT", "FINANCIAL_AGENT", "EXPERIENCE_AGENT", "DOCUMENT_FORENSICS_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert response.decision == VerificationDecisionEnum.QUALIFIED
        # Requirement checks
        assert len(response.failed_requirements) == 0
        assert len(response.review_requirements) == 0
        assert len(response.passed_requirements) == 5
        # Agent checks
        assert len(response.failed_agents) == 0
        assert len(response.review_agents) == 0
        assert len(response.passed_agents) >= 5

    def test_semantics_unresolved_requirement_is_review_and_not_failed(self):
        """8. Verify an unresolved requirement is represented as review/unresolved and NOT as a failed requirement."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
            N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED", confidence=1.0, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-UNRES-01",
            request_id="REQ-UNRES-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Ambiguous Bidder",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=25.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=["Subjective local presence clause requires human discretion"],
            reasons=["Subjective criteria present"],
        )
        payload = N8nVerificationPayload(
            request_id="REQ-UNRES-01",
            verification_id="VER-UNRES-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Ambiguous Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
                TenderRequirementItemInput(
                    requirement_id="R3",
                    category="SUBJECTIVE",
                    requirement_type="CUSTOM",
                    rule="LOCAL_SERVICE_CENTER",
                    description="Bidder should preferably maintain a local service station in the state",
                    status="UNRESOLVED",
                    mandatory=False,
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="AAACB2929P"),
            ],
            required_agents=["GST_AGENT", "PAN_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # The unresolved clause must be in review_requirements
        assert "LOCAL_SERVICE_CENTER" in response.review_requirements
        # It must NOT be in failed_requirements
        assert "LOCAL_SERVICE_CENTER" not in response.failed_requirements
        assert len(response.failed_requirements) == 0
        # Decision must NOT be disqualified
        assert response.decision in (VerificationDecisionEnum.MANUAL_REVIEW, VerificationDecisionEnum.CONDITIONALLY_QUALIFIED)

    def test_semantics_fallback_service_execution(self):
        """9. Verify fallback execution populates all 6 semantic fields properly."""
        service = VerificationService()
        t_id = str(uuid.uuid4())
        b_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-FALLBACK-01",
            verification_id="VER-FALLBACK-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Solutions",
            gstin="29AAACB2929P1Z5",
            pan="AAACB2929P",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_CARD", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="AAACB2929P"),
                BidderEvidenceItemInput(evidence_id="E3", bidder_id=b_id, field="annual_turnover", value=30000000),
                BidderEvidenceItemInput(evidence_id="E4", bidder_id=b_id, field="years_of_experience", value=6),
            ],
            required_agents=["GST_AGENT", "PAN_AGENT", "FINANCIAL_AGENT", "EXPERIENCE_AGENT"],
        )

        n8n_resp = service._execute_local_multi_agent_fallback(payload=payload)

        # Check agent fields
        assert isinstance(n8n_resp.passed_agents, list)
        assert isinstance(n8n_resp.failed_agents, list)
        assert isinstance(n8n_resp.review_agents, list)
        for a in n8n_resp.passed_agents:
            assert _is_agent_id(a)
        for a in n8n_resp.failed_agents:
            assert _is_agent_id(a)

        # Check requirement fields
        assert isinstance(n8n_resp.passed_requirements, list)
        assert isinstance(n8n_resp.failed_requirements, list)
        assert isinstance(n8n_resp.review_requirements, list)
        for r in n8n_resp.passed_requirements:
            assert _is_requirement_id(r)
        for r in n8n_resp.failed_requirements:
            assert _is_requirement_id(r)

        # Aggregate and verify client response
        client_resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert client_resp.passed_agents == n8n_resp.passed_agents
        assert len(client_resp.passed_requirements) > 0
        assert len(client_resp.failed_requirements) == 0
