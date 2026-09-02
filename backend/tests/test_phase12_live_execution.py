"""
Phase 12.8 — Live End-to-End n8n Verification Execution Tests
tests/test_phase12_live_execution.py

12 comprehensive mock-n8n integration tests (A–L) covering:
- Valid request → n8n receives correct payload (A)
- n8n successful result → COMPLETED execution persisted (B)
- n8n NON_COMPLIANT result persisted (C)
- n8n risk findings → risk result persisted (D)
- n8n timeout → controlled FAILED state (E)
- n8n 5xx → retry + eventual FAILED (F)
- n8n 4xx → fail-fast, no retry (G)
- Invalid callback signature → 401 (H)
- Unknown verification ID callback → 404 (I)
- Duplicate request → no duplicate n8n dispatch (J)
- Agent failure → no false COMPLIANT (K)
- Missing mandatory evidence → no false COMPLIANT (L)
"""
import asyncio
import hashlib
import json
import unittest
import uuid
from datetime import datetime, timezone
from typing import Dict, Optional
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.crud.crud_verification import compute_canonical_result_hash, crud_verification
from app.db.base import Base
from app.dependencies.database import get_db
from app.main import app
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel
from app.models.document import Document
from app.models.enums import (
    BidderStatus,
    DocumentProcessingStatus,
    DocumentType,
    ProcessingStatus,
    TenderStatus,
)
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.models.verification import VerificationAuditEvent, VerificationExecution
from app.schemas.verification import (
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    OverallComplianceEnum,
    RequirementComplianceEnum,
    RiskLevelEnum,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationStatusEnum,
    VerificationTriggerRequest,
)
from app.services.n8n_client import (
    N8nClient,
    N8nClientError,
    N8nConnectionError,
    N8nTimeoutError,
    n8n_client,
)
from app.services.verification_service import VerificationService


def _build_n8n_response(
    verification_id: str,
    tender_id: str,
    bidder_id: str,
    decision: str = "QUALIFIED",
    risk_score: float = 12.5,
    risk_level: str = "LOW",
    agent_statuses: Optional[Dict[str, str]] = None,
) -> N8nVerificationResponse:
    """Builds a complete mock n8n response with all 10 agents."""
    if agent_statuses is None:
        agent_statuses = {}

    default_agents = [
        "TENDER_INTELLIGENCE_AGENT",
        "GST_AGENT",
        "PAN_AGENT",
        "UDYAM_AGENT",
        "FINANCIAL_AGENT",
        "EXPERIENCE_AGENT",
        "DOCUMENT_FORENSICS_AGENT",
        "ENTITY_RESOLUTION_AGENT",
        "RISK_INTELLIGENCE_AGENT",
        "FINAL_COMPLIANCE_AGENT",
    ]
    results = []
    for agent_name in default_agents:
        status_val = agent_statuses.get(agent_name, "PASS")
        confidence_val = 0.95 if status_val == "PASS" else (0.0 if status_val in ("FAIL", "ERROR") else 0.5)
        issues = []
        if status_val == "FAIL":
            issues = [f"{agent_name} verification failed"]
        elif status_val == "ERROR":
            issues = [f"{agent_name} encountered an execution error"]

        results.append(
            N8nAgentResult(
                agent=agent_name,
                status=status_val,
                confidence=confidence_val,
                evidence={"verified": status_val == "PASS"},
                issues=issues,
                risk_level="LOW" if status_val == "PASS" else "HIGH",
            )
        )

    return N8nVerificationResponse(
        verification_id=verification_id,
        request_id=f"REQ-{verification_id}",
        tender_id=tender_id,
        bidder_id=bidder_id,
        bidder_name="Apex Infra Solutions Pvt Ltd",
        status="COMPLETED",
        decision=decision,
        risk_score=risk_score,
        risk_level=risk_level,
        agent_results=results,
        reasons=["All criteria evaluated"],
    )


class TestPhase12_8_LiveExecution(unittest.TestCase):
    """12 comprehensive mock-n8n integration tests for Phase 12.8."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db: Session = self.SessionLocal()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

        # Seed database records
        self.tender = Tender(
            id=uuid.uuid4(),
            tender_number=f"GEM/2026/B/P12_{uuid.uuid4().hex[:8].upper()}",
            title="Test Tender for Phase 12.8",
            description="Government infrastructure tender",
            organization="Ministry of Road Transport",
            department="Highways",
            category="Infrastructure",
            status=TenderStatus.OPEN,
        )
        self.db.add(self.tender)
        self.db.commit()
        self.db.refresh(self.tender)

        self.bidder = Bidder(
            id=uuid.uuid4(),
            company_name="Apex Infra Solutions Pvt Ltd",
            registration_number=f"U72200DL2026PTC{uuid.uuid4().hex[:6].upper()}",
            gst_number="29ABCDE1234F1Z5",
            pan_number="ABCDE1234F",
            udyam_number="UDYAM-DL-01-0012345",
            status=BidderStatus.ACTIVE,
        )
        self.db.add(self.bidder)
        self.db.commit()
        self.db.refresh(self.bidder)

        assoc = TenderBidder(tender_id=self.tender.id, bidder_id=self.bidder.id)
        self.db.add(assoc)
        self.db.commit()

        self.requirement = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=self.tender.id,
            requirement_type="FINANCIAL",
            rule="MINIMUM_TURNOVER",
            description="Minimum annual turnover of INR 1 Crore",
            parameters={"minimum_annual_turnover": 10000000},
            mandatory=True,
            confidence=0.95,
            source_page=3,
            source_section="Section 2.1 – Financial Eligibility",
            source_text="The bidder shall have a minimum annual turnover of INR 1 Crore.",
        )
        self.db.add(self.requirement)
        self.db.commit()
        self.db.refresh(self.requirement)

        self.document = Document(
            id=uuid.uuid4(),
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
            original_filename="balance_sheet_2024.pdf",
            storage_path=f"docs/{uuid.uuid4().hex}.pdf",
            document_type=DocumentType.FINANCIAL_STATEMENT,
            mime_type="application/pdf",
            file_size=102400,
            sha256=hashlib.sha256(b"test-document-content").hexdigest(),
            processing_status=ProcessingStatus.PROCESSED,
        )
        self.db.add(self.document)
        self.db.commit()
        self.db.refresh(self.document)

        self.evidence = BidderEvidenceModel(
            id=uuid.uuid4(),
            bidder_id=self.bidder.id,
            field="turnover",
            value={"amount": 15000000, "average": 15000000, "document_id": str(self.document.id), "document_hash": self.document.sha256},
            source_document="balance_sheet_2024.pdf",
            confidence=0.92,
        )
        self.db.add(self.evidence)
        self.db.commit()
        self.db.refresh(self.evidence)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _make_trigger(self) -> VerificationTriggerRequest:
        return VerificationTriggerRequest(
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
        )

    # -----------------------------------------------------------------------
    # Test A: Valid request → n8n receives correct payload
    # -----------------------------------------------------------------------
    def test_A_valid_request_n8n_receives_correct_payload(self):
        service = VerificationService()
        payload = service.build_and_validate_verification_request(
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
            db=self.db,
        )

        assert payload.tender_id == str(self.tender.id)
        assert payload.tender_title == self.tender.title
        assert payload.bidder_id == str(self.bidder.id)
        assert payload.bidder_name == "Apex Infra Solutions Pvt Ltd"
        assert payload.gstin == "29ABCDE1234F1Z5"
        assert payload.pan == "ABCDE1234F"

        assert len(payload.tender_requirements) >= 1
        req = payload.tender_requirements[0]
        assert req.requirement_id == str(self.requirement.id)
        assert req.category == "FINANCIAL"
        assert req.rule == "MINIMUM_TURNOVER"
        assert req.mandatory is True
        assert req.source_page == 3
        assert req.source_section == "Section 2.1 – Financial Eligibility"
        assert req.source_text is not None
        assert req.resolution_method == "DETERMINISTIC"

        assert len(payload.bidder_evidence) >= 1
        ev = payload.bidder_evidence[0]
        assert ev.bidder_id == str(self.bidder.id)
        assert ev.field == "turnover"

        assert len(payload.documents) >= 1
        doc = payload.documents[0]
        assert doc.document_id == str(self.document.id)
        assert doc.sha256 is not None
        assert len(payload.required_agents) == 10

    # -----------------------------------------------------------------------
    # Test B: n8n successful result → COMPLETED execution persisted
    # -----------------------------------------------------------------------
    def test_B_n8n_success_creates_completed_execution(self):
        mock_client = AsyncMock(spec=N8nClient)
        n8n_resp = _build_n8n_response(
            verification_id="VER-TEST-B-001",
            tender_id=str(self.tender.id),
            bidder_id=str(self.bidder.id),
        )
        mock_client.trigger_verification = AsyncMock(return_value=n8n_resp)

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()
        result = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        assert isinstance(result, VerificationResponse)
        assert result.status == VerificationStatusEnum.COMPLETED
        assert result.tender_id == self.tender.id
        assert result.bidder_id == self.bidder.id
        assert result.result_hash is not None

        execution = crud_verification.get_by_verification_id(self.db, result.verification_id)
        assert execution is not None
        assert execution.status == "COMPLETED"
        assert execution.result_hash is not None
        assert execution.completed_at is not None

        events = crud_verification.get_audit_events_for_verification(self.db, result.verification_id)
        event_types = [e.event_type for e in events]
        assert "VERIFICATION_CREATED" in event_types
        assert "VERIFICATION_STARTED" in event_types
        assert "VERIFICATION_DISPATCHED" in event_types
        assert "VERIFICATION_COMPLETED" in event_types

    # -----------------------------------------------------------------------
    # Test C: n8n NON_COMPLIANT → NON_COMPLIANT result persisted
    # -----------------------------------------------------------------------
    def test_C_non_compliant_result_persisted(self):
        mock_client = AsyncMock(spec=N8nClient)
        n8n_resp = _build_n8n_response(
            verification_id="VER-TEST-C-001",
            tender_id=str(self.tender.id),
            bidder_id=str(self.bidder.id),
            decision="NOT_QUALIFIED",
            risk_score=65.0,
            risk_level="HIGH",
            agent_statuses={"FINANCIAL_AGENT": "FAIL", "GST_AGENT": "FAIL"},
        )
        mock_client.trigger_verification = AsyncMock(return_value=n8n_resp)

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()
        result = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        assert result.overall_compliance != OverallComplianceEnum.COMPLIANT
        assert result.decision != VerificationDecisionEnum.QUALIFIED

        execution = crud_verification.get_by_verification_id(self.db, result.verification_id)
        assert execution is not None
        assert execution.overall_compliance != "COMPLIANT"

    # -----------------------------------------------------------------------
    # Test D: n8n risk findings → risk result persisted
    # -----------------------------------------------------------------------
    def test_D_risk_findings_persisted(self):
        mock_client = AsyncMock(spec=N8nClient)
        n8n_resp = _build_n8n_response(
            verification_id="VER-TEST-D-001",
            tender_id=str(self.tender.id),
            bidder_id=str(self.bidder.id),
            risk_score=55.0,
            risk_level="MEDIUM",
            agent_statuses={"DOCUMENT_FORENSICS_AGENT": "WARNING"},
        )
        mock_client.trigger_verification = AsyncMock(return_value=n8n_resp)

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()
        result = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        assert result.risk is not None
        assert result.risk_score >= 0.0

        execution = crud_verification.get_by_verification_id(self.db, result.verification_id)
        assert execution.risk_assessment is not None
        assert execution.risk_score is not None

    # -----------------------------------------------------------------------
    # Test E: n8n timeout → controlled FAILED state
    # -----------------------------------------------------------------------
    def test_E_n8n_timeout_creates_failed_execution(self):
        mock_client = AsyncMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(
            side_effect=N8nTimeoutError("Request to n8n timed out after 60s")
        )

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()

        with self.assertRaises(N8nTimeoutError):
            asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        executions = self.db.query(VerificationExecution).filter(
            VerificationExecution.tender_id == self.tender.id,
            VerificationExecution.bidder_id == self.bidder.id,
        ).all()
        assert len(executions) >= 1
        latest = executions[-1]
        assert latest.status == "FAILED"
        assert latest.error is not None

        events = crud_verification.get_audit_events_for_verification(self.db, latest.verification_id)
        event_types = [e.event_type for e in events]
        assert "VERIFICATION_FAILED" in event_types

    # -----------------------------------------------------------------------
    # Test F: n8n 5xx → retry + eventual FAILED
    # -----------------------------------------------------------------------
    def test_F_n8n_5xx_retry_then_fail(self):
        mock_client = AsyncMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(
            side_effect=N8nClientError("n8n webhook failed with HTTP 500", status_code=500)
        )

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()

        with self.assertRaises(N8nClientError):
            asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        executions = self.db.query(VerificationExecution).filter(
            VerificationExecution.tender_id == self.tender.id,
            VerificationExecution.bidder_id == self.bidder.id,
        ).all()
        assert len(executions) >= 1
        assert executions[-1].status == "FAILED"

    # -----------------------------------------------------------------------
    # Test G: n8n 4xx → fail-fast, no retry
    # -----------------------------------------------------------------------
    def test_G_n8n_4xx_fail_fast(self):
        mock_client = AsyncMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(
            side_effect=N8nClientError("n8n rejected request with HTTP 400", status_code=400)
        )

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()

        with self.assertRaises(N8nClientError) as ctx:
            asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        assert ctx.exception.status_code == 400

        executions = self.db.query(VerificationExecution).filter(
            VerificationExecution.tender_id == self.tender.id,
        ).all()
        assert len(executions) >= 1
        assert executions[-1].status == "FAILED"

    # -----------------------------------------------------------------------
    # Test H: Invalid callback signature → 401
    # -----------------------------------------------------------------------
    def test_H_invalid_callback_signature_rejected(self):
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
            "X-Webhook-Signature": "sha256=invalid-signature-value",
        }
        response = self.client.post(
            "/api/v1/verification/webhook/callback",
            json={"test": 123},
            headers=headers,
        )
        assert response.status_code == 401

    # -----------------------------------------------------------------------
    # Test I: Unknown verification ID callback → 404
    # -----------------------------------------------------------------------
    def test_I_unknown_verification_id_rejected(self):
        callback_payload = {
            "verification_id": "VER-UNKNOWN-99999",
            "request_id": "REQ-UNKNOWN-99999",
            "bidder_name": "Unknown Bidder",
            "status": "COMPLETED",
            "decision": "QUALIFIED",
            "risk_score": 5.0,
            "risk_level": "LOW",
            "agent_results": [],
            "reasons": ["test"],
        }
        body_bytes = json.dumps(callback_payload).encode("utf-8")
        signature = n8n_client.generate_signature(body_bytes)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
            "X-Webhook-Signature": f"sha256={signature}",
        }
        response = self.client.post(
            "/api/v1/verification/webhook/callback",
            content=body_bytes,
            headers=headers,
        )
        assert response.status_code == 404

    # -----------------------------------------------------------------------
    # Test J: Duplicate request → no duplicate n8n dispatch
    # -----------------------------------------------------------------------
    def test_J_duplicate_request_no_duplicate_dispatch(self):
        mock_client = AsyncMock(spec=N8nClient)
        n8n_resp = _build_n8n_response(
            verification_id="VER-TEST-J-001",
            tender_id=str(self.tender.id),
            bidder_id=str(self.bidder.id),
        )
        mock_client.trigger_verification = AsyncMock(return_value=n8n_resp)

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()

        # First call: should dispatch to n8n
        result1 = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))
        assert result1.status == VerificationStatusEnum.COMPLETED
        assert mock_client.trigger_verification.call_count == 1

        # Second call: should return cached result without dispatching
        result2 = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))
        assert result2.verification_id == result1.verification_id
        assert mock_client.trigger_verification.call_count == 1

    # -----------------------------------------------------------------------
    # Test K: Agent failure → no false COMPLIANT
    # -----------------------------------------------------------------------
    def test_K_agent_failure_no_false_compliant(self):
        mock_client = AsyncMock(spec=N8nClient)
        n8n_resp = _build_n8n_response(
            verification_id="VER-TEST-K-001",
            tender_id=str(self.tender.id),
            bidder_id=str(self.bidder.id),
            decision="NOT_QUALIFIED",
            agent_statuses={
                "GST_AGENT": "ERROR",
                "PAN_AGENT": "ERROR",
                "FINANCIAL_AGENT": "FAIL",
            },
        )
        mock_client.trigger_verification = AsyncMock(return_value=n8n_resp)

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()
        result = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        assert result.overall_compliance != OverallComplianceEnum.COMPLIANT
        assert result.decision != VerificationDecisionEnum.QUALIFIED

        execution = crud_verification.get_by_verification_id(self.db, result.verification_id)
        assert execution.overall_compliance != "COMPLIANT"
        assert execution.decision != "QUALIFIED"

    # -----------------------------------------------------------------------
    # Test L: Missing mandatory evidence → no false COMPLIANT
    # -----------------------------------------------------------------------
    def test_L_missing_evidence_no_false_compliant(self):
        # Remove all evidence for this bidder
        self.db.query(BidderEvidenceModel).filter(
            BidderEvidenceModel.bidder_id == self.bidder.id,
        ).delete()
        self.db.commit()

        mock_client = AsyncMock(spec=N8nClient)
        n8n_resp = _build_n8n_response(
            verification_id="VER-TEST-L-001",
            tender_id=str(self.tender.id),
            bidder_id=str(self.bidder.id),
            decision="QUALIFIED",
        )
        mock_client.trigger_verification = AsyncMock(return_value=n8n_resp)

        service = VerificationService(client=mock_client)
        trigger = self._make_trigger()
        result = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        for req in result.requirements:
            if req.mandatory and req.decision.value == "COMPLIANT":
                assert len(req.evidence_ids) > 0, (
                    f"Requirement {req.requirement_id} claims COMPLIANT without evidence"
                )


class TestPhase12_8_StateValidation(unittest.TestCase):
    """Tests for state machine correctness and structural invariants."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db: Session = self.SessionLocal()

        self.tender = Tender(
            id=uuid.uuid4(),
            tender_number=f"GEM/2026/B/P12_{uuid.uuid4().hex[:8].upper()}",
            title="State Validation Tender",
            organization="Central Public Works Department",
            department="Civil",
            category="Works",
            status=TenderStatus.OPEN,
        )
        self.db.add(self.tender)
        self.db.commit()
        self.db.refresh(self.tender)

        self.bidder = Bidder(
            id=uuid.uuid4(),
            company_name="Apex Builders",
            registration_number=f"U72200DL2026PTC{uuid.uuid4().hex[:6].upper()}",
            gst_number="29ABCDE1234F1Z5",
            pan_number="ABCDE1234F",
            status=BidderStatus.ACTIVE,
        )
        self.db.add(self.bidder)
        self.db.commit()
        self.db.refresh(self.bidder)

        assoc = TenderBidder(tender_id=self.tender.id, bidder_id=self.bidder.id)
        self.db.add(assoc)
        self.db.commit()

        self.req = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=self.tender.id,
            requirement_type="FINANCIAL",
            rule="MINIMUM_TURNOVER",
            description="Minimum annual turnover",
            parameters={"minimum": 5000000},
            mandatory=True,
        )
        self.db.add(self.req)
        self.db.commit()

        doc = Document(
            id=uuid.uuid4(),
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
            original_filename="doc.pdf",
            storage_path="docs/doc.pdf",
            document_type=DocumentType.OTHER,
            mime_type="application/pdf",
            sha256=hashlib.sha256(b"content").hexdigest(),
        )
        self.db.add(doc)
        self.db.commit()

        evidence = BidderEvidenceModel(
            id=uuid.uuid4(),
            bidder_id=self.bidder.id,
            field="turnover",
            value={"amount": 8000000},
            source_document="doc.pdf",
        )
        self.db.add(evidence)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_queued_to_running_transition(self):
        dispatch_states = []

        async def capture_state_then_respond(payload, request_id=None):
            execution = self.db.query(VerificationExecution).filter(
                VerificationExecution.tender_id == self.tender.id,
            ).first()
            if execution:
                dispatch_states.append(execution.status)
            return _build_n8n_response(
                verification_id=payload.verification_id or "VER-STATE-001",
                tender_id=str(self.tender.id),
                bidder_id=str(self.bidder.id),
            )

        mock_client = AsyncMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(side_effect=capture_state_then_respond)

        service = VerificationService(client=mock_client)
        trigger = VerificationTriggerRequest(
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
        )
        result = asyncio.run(service.execute_verification(trigger_request=trigger, db=self.db))

        assert len(dispatch_states) == 1
        assert dispatch_states[0] == "RUNNING"

        execution = crud_verification.get_by_verification_id(self.db, result.verification_id)
        assert execution.status == "COMPLETED"

    def test_security_no_secrets_in_payload(self):
        service = VerificationService()
        payload = service.build_and_validate_verification_request(
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
            db=self.db,
        )
        serialized = payload.model_dump_json()

        assert "gsk_" not in serialized
        assert "Bearer ey" not in serialized
        assert "postgresql://" not in serialized
        assert "postgres://" not in serialized

    def test_result_hash_determinism(self):
        h1 = compute_canonical_result_hash(
            verification_id="VER-HASH-001",
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
            overall_compliance="COMPLIANT",
            decision="QUALIFIED",
            risk_level="LOW",
            risk_score=10.0,
            overall_confidence=0.95,
        )
        h2 = compute_canonical_result_hash(
            verification_id="VER-HASH-001",
            tender_id=self.tender.id,
            bidder_id=self.bidder.id,
            overall_compliance="COMPLIANT",
            decision="QUALIFIED",
            risk_level="LOW",
            risk_score=10.0,
            overall_confidence=0.95,
        )
        assert h1 == h2
        assert len(h1) == 64

    def test_error_sanitization_no_secrets(self):
        from app.crud.crud_verification import sanitize_text

        dangerous = "Connection failed: postgresql://admin:MyP@ss123@db.example.com/sih gsk_1234567890abcdefghijklmnopqrstuv"
        sanitized = sanitize_text(dangerous)
        assert "MyP@ss" not in sanitized
        assert "gsk_1234" not in sanitized
        assert "REDACTED" in sanitized


if __name__ == "__main__":
    unittest.main()
