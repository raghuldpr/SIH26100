"""
Phase 10 — Verification Schemas Unit Test Suite
tests/test_verification_schemas_phase10.py: Validates strongly-typed Pydantic models
for FastAPI ↔ n8n Master Orchestrator verification integration.
"""
from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError

from app.schemas.verification import (
    AgentStatusEnum,
    CompliancePolicyInput,
    DEFAULT_VERIFICATION_AGENTS,
    DocumentForensicInput,
    ExperienceEvidenceInput,
    ExperienceRequirementsInput,
    FinalComplianceResult,
    FinancialEvidenceInput,
    FinancialRequirementsInput,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    ProjectExperienceItem,
    RiskLevelEnum,
    VerificationAgentEnum,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationStatusEnum,
    VerificationSummaryItem,
    VerificationTriggerRequest,
)


class TestVerificationTriggerRequest:
    """Tests for client-facing verification trigger schema."""

    def test_valid_minimal_trigger_request(self):
        t_id = uuid.uuid4()
        b_id = uuid.uuid4()
        req = VerificationTriggerRequest(
            tender_id=t_id,
            bidder_id=b_id,
        )
        assert req.tender_id == t_id
        assert req.bidder_id == b_id
        assert req.required_agents is None
        assert req.financial_overrides is None
        assert req.experience_overrides is None

    def test_trigger_request_with_full_overrides(self):
        t_id = uuid.uuid4()
        b_id = uuid.uuid4()
        req = VerificationTriggerRequest(
            tender_id=t_id,
            bidder_id=b_id,
            required_agents=["GST_AGENT", "PAN_AGENT", "FINAL_COMPLIANCE_AGENT"],
            financial_overrides=FinancialRequirementsInput(
                average_turnover=2500000.0,
                turnover_period_years=3,
            ),
            experience_overrides=ExperienceRequirementsInput(
                minimum_similar_works=2,
                minimum_project_value=1500000.0,
            ),
            compliance_policy=CompliancePolicyInput(
                mandatory_agents=["GST_AGENT", "PAN_AGENT"],
                allow_review_status=True,
                maximum_review_risk_score=35.0,
            ),
            metadata={"source": "react_portal_trigger", "user_id": "user-123"},
        )
        assert len(req.required_agents) == 3
        assert req.financial_overrides.average_turnover == 2500000.0
        assert req.compliance_policy.allow_review_status is True
        assert req.metadata["source"] == "react_portal_trigger"

    def test_invalid_trigger_request_missing_ids(self):
        with pytest.raises(ValidationError):
            VerificationTriggerRequest(tender_id=uuid.uuid4())  # Missing bidder_id


class TestN8nVerificationPayload:
    """Tests for structured payload dispatched to n8n webhook."""

    def test_valid_n8n_payload_minimal(self):
        payload = N8nVerificationPayload(
            request_id="REQ-TEST-001",
            tender_id="TENDER-GEM-2026-001",
            bidder_id="BIDDER-ABC-001",
            bidder_name="ABC Technologies Pvt Ltd",
        )
        assert payload.request_id == "REQ-TEST-001"
        assert payload.bidder_name == "ABC Technologies Pvt Ltd"
        assert len(payload.required_agents) == len(DEFAULT_VERIFICATION_AGENTS)
        assert payload.required_agents == DEFAULT_VERIFICATION_AGENTS
        assert payload.timestamp is not None

    def test_n8n_payload_custom_agents_normalization(self):
        payload = N8nVerificationPayload(
            request_id="REQ-TEST-002",
            tender_id="TENDER-002",
            bidder_id="BIDDER-002",
            bidder_name="XYZ Infra Ltd",
            required_agents=["gst_agent", " pan_agent ", "FINANCIAL_AGENT"],
        )
        assert payload.required_agents == ["GST_AGENT", "PAN_AGENT", "FINANCIAL_AGENT"]

    def test_n8n_payload_comprehensive(self):
        payload = N8nVerificationPayload(
            request_id="REQ-FULL-001",
            verification_id="VER-FULL-001",
            tender_id="TENDER-001",
            tender_number="GEM/2026/B/9999",
            tender_title="IT Infrastructure Procurement",
            bidder_id="BIDDER-001",
            bidder_name="ABC Technologies Pvt Ltd",
            gstin="27AABCU9603R1ZM",
            pan="AABCU9603R",
            udyam="UDYAM-MH-01-0012345",
            cin="U72900MH2018PTC123456",
            documents=[
                DocumentForensicInput(
                    document_id="DOC-GST-001",
                    document_type="GST_CERTIFICATE",
                    file_name="gst_certificate.pdf",
                    file_size=102400,
                    sha256="abc123hash",
                )
            ],
            financial_requirements=FinancialRequirementsInput(
                average_turnover=2000000.0,
                minimum_net_worth=1000000.0,
            ),
            financial_evidence=FinancialEvidenceInput(
                turnover={"2023-24": 1800000, "2024-25": 2200000, "2025-26": 2500000},
                net_worth=1200000,
                udin="2409603R1ZMCA8812",
            ),
            experience_requirements=ExperienceRequirementsInput(
                minimum_similar_works=3,
                minimum_project_value=1000000.0,
            ),
            experience_evidence=ExperienceEvidenceInput(
                projects=[
                    ProjectExperienceItem(
                        project_id="PROJ-001",
                        project_name="Smart City Portal",
                        project_value=1500000.0,
                        completion_date="2024-06-15",
                        similarity=True,
                        completion_certificate=True,
                    )
                ]
            ),
        )
        assert payload.gstin == "27AABCU9603R1ZM"
        assert len(payload.documents) == 1
        assert payload.financial_evidence.udin == "2409603R1ZMCA8812"
        assert len(payload.experience_evidence.projects) == 1

    def test_invalid_n8n_payload_empty_bidder_name(self):
        with pytest.raises(ValidationError):
            N8nVerificationPayload(
                request_id="REQ-001",
                tender_id="T-001",
                bidder_id="B-001",
                bidder_name="",  # Must have length >= 1
            )


class TestN8nAgentResult:
    """Tests for child agent outcome records."""

    def test_valid_agent_result_verified(self):
        res = N8nAgentResult(
            agent="GST_AGENT",
            status="VERIFIED",
            confidence=0.98,
            evidence={"legal_name": "ABC Tech", "gstin": "27AABCU9603R1ZM", "status": "ACTIVE"},
            issues=[],
            risk_level="LOW",
        )
        assert res.agent == "GST_AGENT"
        assert res.status == "VERIFIED"
        assert res.risk_level == "LOW"

    def test_valid_agent_result_with_issues(self):
        res = N8nAgentResult(
            agent="FINANCIAL_AGENT",
            status="NOT_VERIFIED",
            confidence=0.95,
            evidence={"average_turnover": 800000, "required": 1500000},
            issues=["Average turnover ₹8,00,000 is below required minimum ₹15,00,000"],
            risk_level="HIGH",
        )
        assert res.status == "NOT_VERIFIED"
        assert len(res.issues) == 1
        assert res.risk_level == "HIGH"


class TestN8nVerificationResponse:
    """Tests for incoming n8n Master Orchestrator response."""

    def test_parse_live_n8n_orchestrator_response(self):
        raw_json = {
            "verification_id": "VER-M9XYZ-789",
            "request_id": "REQ-FULL-001",
            "tender_id": "TENDER-GEM-2026-001",
            "bidder_id": "BIDDER-ABC-001",
            "bidder_name": "ABC Technologies Pvt Ltd",
            "status": "COMPLETED",
            "decision": "QUALIFIED",
            "risk_score": 0.0,
            "risk_level": "LOW",
            "agent_results": [
                {
                    "agent": "GST_AGENT",
                    "status": "VERIFIED",
                    "confidence": 0.99,
                    "evidence": {"status": "ACTIVE"},
                    "issues": [],
                    "risk_level": "LOW",
                },
                {
                    "agent": "PAN_AGENT",
                    "status": "VERIFIED",
                    "confidence": 0.99,
                    "evidence": {"status": "VALID"},
                    "issues": [],
                    "risk_level": "LOW",
                },
            ],
            "failed_requirements": [],
            "missing_documents": [],
            "warnings": [],
            "reasons": ["All mandatory statutory and eligibility criteria successfully verified"],
            "timestamp": "2026-09-01T22:30:00Z",
        }
        resp = N8nVerificationResponse.model_validate(raw_json)
        assert resp.verification_id == "VER-M9XYZ-789"
        assert resp.decision == "QUALIFIED"
        assert resp.risk_score == 0.0
        assert len(resp.agent_results) == 2
        assert len(resp.reasons) == 1

    def test_parse_n8n_failure_response(self):
        raw_json = {
            "verification_id": "VER-FAIL-001",
            "request_id": "REQ-FINFAIL-004",
            "bidder_name": "ABC Technologies Pvt Ltd",
            "status": "COMPLETED",
            "decision": "NOT_QUALIFIED",
            "risk_score": 80.0,
            "risk_level": "HIGH",
            "agent_results": [
                {
                    "agent": "FINANCIAL_AGENT",
                    "status": "ERROR",
                    "confidence": 0.0,
                    "evidence": {},
                    "issues": ["Invalid financial data encountered"],
                    "risk_level": "HIGH",
                }
            ],
            "failed_requirements": ["FINANCIAL_AGENT failed verification (ERROR)"],
            "missing_documents": [],
            "warnings": [],
            "reasons": ["Financial child workflow encountered invalid data"],
        }
        resp = N8nVerificationResponse.model_validate(raw_json)
        assert resp.decision == "NOT_QUALIFIED"
        assert resp.risk_score == 80.0
        assert resp.risk_level == "HIGH"


class TestVerificationResponseClientModel:
    """Tests for client-facing FastAPI verification response."""

    def test_verification_response_creation(self):
        rec_id = uuid.uuid4()
        t_id = uuid.uuid4()
        b_id = uuid.uuid4()

        api_resp = VerificationResponse(
            id=rec_id,
            verification_id="VER-2026-001",
            request_id="REQ-001",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="ABC Technologies Pvt Ltd",
            status=VerificationStatusEnum.COMPLETED,
            decision=VerificationDecisionEnum.QUALIFIED,
            risk_score=5.0,
            risk_level=RiskLevelEnum.LOW,
            reasons=["All criteria passed"],
            failed_requirements=[],
            warnings=[],
            missing_documents=[],
            agent_results=[
                N8nAgentResult(
                    agent="GST_AGENT",
                    status="VERIFIED",
                    confidence=0.99,
                    risk_level="LOW",
                )
            ],
            created_at=datetime.now(timezone.utc),
        )
        assert api_resp.id == rec_id
        assert api_resp.status == VerificationStatusEnum.COMPLETED
        assert api_resp.decision == VerificationDecisionEnum.QUALIFIED
        assert api_resp.risk_score == 5.0

    def test_verification_summary_item(self):
        rec_id = uuid.uuid4()
        t_id = uuid.uuid4()
        b_id = uuid.uuid4()

        summary = VerificationSummaryItem(
            id=rec_id,
            verification_id="VER-SUM-001",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="ABC Tech",
            status=VerificationStatusEnum.COMPLETED,
            decision=VerificationDecisionEnum.QUALIFIED,
            risk_score=10.0,
            risk_level=RiskLevelEnum.LOW,
            agents_executed_count=10,
            created_at=datetime.now(timezone.utc),
        )
        assert summary.agents_executed_count == 10
        assert summary.decision == VerificationDecisionEnum.QUALIFIED
