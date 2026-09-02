"""
SIH-26100 — Phase 12.7 Test Suite
tests/test_phase12_verification_persistence.py

Verifies:
Verification Request
        ↓
Execution
        ↓
Agent Results
        ↓
Final Compliance + Risk
        ↓
Persist Verification
        ↓
Persist Audit Information
        ↓
Return Verification ID
        ↓
Retrieve Result Later
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from typing import Any, Dict, List, Optional, Union
from uuid import UUID


from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.security import create_access_token
from app.crud.crud_bidder import crud_bidder
from app.crud.crud_tender import crud_tender
from app.crud.crud_user import crud_user
from app.crud.crud_verification import (
    compute_canonical_result_hash,
    crud_verification,
    sanitize_error_details,
    sanitize_text,
)
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
    UserRole,
)

from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.models.user import User
from app.models.verification import VerificationAuditEvent, VerificationExecution
from app.schemas.bidder import BidderCreate
from app.schemas.tender import TenderCreate
from app.schemas.user import UserCreate
from app.schemas.verification import (
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    OverallComplianceEnum,
    RequirementComplianceEnum,
    RequirementEvaluation,
    RiskLevelEnum,
    VerificationComplianceSummary,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationRiskAssessment,
    VerificationStatusEnum,
    VerificationTriggerRequest,
)
from app.services.n8n_client import N8nClient, N8nTimeoutError
from app.services.verification_service import VerificationService


class TestPhase12VerificationPersistence(unittest.TestCase):
    """
    Comprehensive test suite covering Phase 12.7 verification execution persistence,
    tamper-evident result hashing, request idempotency, audit trail recording,
    traceability snapshots, security sanitization, and isolation boundaries.
    """

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db: Session = self.SessionLocal()

        # App TestClient with get_db override
        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    # -------------------------------------------------------------------------
    # Test Helpers
    # -------------------------------------------------------------------------

    def _create_user(self, email: str = "officer@gem.gov.in", role: UserRole = UserRole.PROCUREMENT_OFFICER) -> User:
        user_in = UserCreate(
            email=email,
            password="SecurePassword123!",
            name="Verification Officer",
            role=role,
        )
        return crud_user.create(self.db, user_in=user_in)

    def _create_tender_and_bidder(self, created_by: Optional[UUID] = None):
        tender = Tender(
            id=uuid.uuid4(),
            tender_number=f"GEM/2026/B/P12_{uuid.uuid4().hex[:8].upper()}",
            title="Telecommunications Optical Backbone",
            description="Optical fiber deployment for railway signaling",
            organization="Indian Railways",
            department="Signal & Telecom",
            category="Infrastructure",
            status=TenderStatus.OPEN,
            created_by=created_by,
        )
        self.db.add(tender)
        self.db.commit()
        self.db.refresh(tender)

        bidder = Bidder(
            id=uuid.uuid4(),
            company_name="Apex Teleinfra Private Limited",
            registration_number=f"U72200DL2026PTC{uuid.uuid4().hex[:6].upper()}",
            gst_number="07AAAAA0000A1Z5",
            pan_number="AAAAA0000A",
            udyam_number="UDYAM-DL-01-0012345",
            status=BidderStatus.ACTIVE,
        )
        self.db.add(bidder)
        self.db.commit()
        self.db.refresh(bidder)

        assoc = TenderBidder(
            id=uuid.uuid4(),
            tender_id=tender.id,
            bidder_id=bidder.id,
        )
        self.db.add(assoc)
        self.db.commit()

        # Add standard requirement
        req = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=tender.id,
            requirement_type="FINANCIAL",
            rule="MINIMUM_TURNOVER",
            description="Minimum turnover of ₹10 Cr",
            parameters={"minimum": 100000000.0},
            mandatory=True,
            confidence=0.98,
            source_page=2,
            source_section="Financial Eligibility",
            source_text="Average annual turnover of Rs 10 Crore",
        )
        self.db.add(req)

        # Add standard evidence
        doc_id = uuid.uuid4()
        doc_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        doc = Document(
            id=doc_id,
            tender_id=tender.id,
            original_filename="balance_sheet.pdf",
            storage_path="documents/balance_sheet.pdf",
            sha256=doc_hash,

            document_type=DocumentType.FINANCIAL_STATEMENT,
            processing_status=ProcessingStatus.PROCESSED,
        )
        self.db.add(doc)


        ev = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="turnover",
            value={"amount": 150000000.0},
            source_document="balance_sheet.pdf",
            confidence=0.96,
        )
        self.db.add(ev)
        self.db.commit()

        return tender, bidder, req, ev, doc

    def _build_mock_n8n_response(self, tender_id: UUID, bidder_id: UUID) -> N8nVerificationResponse:
        return N8nVerificationResponse(
            verification_id=f"VER-{uuid.uuid4().hex[:8].upper()}",
            request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
            tender_id=str(tender_id),
            bidder_id=str(bidder_id),
            bidder_name="Apex Teleinfra Private Limited",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=10.0,
            risk_level="LOW",
            agent_results=[
                N8nAgentResult(
                    agent="FINANCIAL_AGENT",
                    status="PASS",
                    confidence=0.96,
                    issues=[],
                    risk_level="LOW",
                ),
                N8nAgentResult(
                    agent="GST_AGENT",
                    status="PASS",
                    confidence=0.98,
                    issues=[],
                    risk_level="LOW",
                ),
            ],
            failed_requirements=[],
            warnings=[],
            missing_documents=[],
            reasons=["All required criteria verified successfully"],
        )

    # -------------------------------------------------------------------------
    # Test 1: Verification record creation
    # -------------------------------------------------------------------------
    def test_01_verification_record_creation(self):
        """Test 1: Verification execution row is created with correct initial state."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        v_id = f"VER-{uuid.uuid4().hex[:8].upper()}"
        r_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"

        execution = crud_verification.create_execution(
            db=self.db,
            verification_id=v_id,
            request_id=r_id,
            tender_id=tender.id,
            bidder_id=bidder.id,
            request_hash="a" * 64,
            status="RUNNING",
        )

        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.verification_id, v_id)
        self.assertEqual(execution.status, "RUNNING")
        self.assertIsNotNone(execution.started_at)
        self.assertIsNone(execution.completed_at)

    # -------------------------------------------------------------------------
    # Test 2: Successful result persistence
    # -------------------------------------------------------------------------
    def test_02_successful_result_persistence(self):
        """Test 2: End-to-end verification run persists COMPLETED execution in database."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(
            tender_id=tender.id,
            bidder_id=bidder.id,
            required_agents=["FINANCIAL_AGENT", "GST_AGENT"],
        )

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, "COMPLETED")
        self.assertEqual(execution.decision, "QUALIFIED")
        self.assertIsNotNone(execution.completed_at)
        self.assertIsNotNone(execution.result_hash)

    # -------------------------------------------------------------------------
    # Test 3: Compliance result persistence
    # -------------------------------------------------------------------------
    def test_03_compliance_result_persistence(self):
        """Test 3: Overall compliance and requirement compliance breakdown are persisted."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        self.assertEqual(execution.overall_compliance, "COMPLIANT")
        self.assertIsNotNone(execution.compliance_summary)
        self.assertEqual(execution.compliance_summary["compliant"], 1)

    # -------------------------------------------------------------------------
    # Test 4: Risk result persistence
    # -------------------------------------------------------------------------
    def test_04_risk_result_persistence(self):
        """Test 4: Risk level, score, signals, and critical condition breakdown are persisted."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        self.assertEqual(execution.risk_level, "LOW")
        self.assertIsNotNone(execution.risk_assessment)
        self.assertIn("signals", execution.risk_assessment)

    # -------------------------------------------------------------------------
    # Test 5: Agent result persistence
    # -------------------------------------------------------------------------
    def test_05_agent_result_persistence(self):
        """Test 5: Individual normalized agent outcomes survive into persistent storage."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        self.assertIsNotNone(execution.agent_results)
        agents = [a["agent"] for a in execution.agent_results]
        self.assertIn("FINANCIAL_AGENT", agents)
        self.assertIn("GST_AGENT", agents)

    # -------------------------------------------------------------------------
    # Test 6: Requirement traceability persistence
    # -------------------------------------------------------------------------
    def test_06_requirement_traceability_persistence(self):
        """Test 6: Requirement evaluations retain source text, page, section, and linked evidence IDs."""
        tender, bidder, req, ev, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        req_record = execution.requirements[0]
        self.assertEqual(req_record["rule"], "MINIMUM_TURNOVER")
        self.assertEqual(req_record["source_page"], 2)
        self.assertIn("Average annual turnover", req_record["source_text"])
        self.assertIn(str(ev.evidence_id), [str(e) for e in req_record["evidence_ids"]])

    # -------------------------------------------------------------------------
    # Test 7: Evidence snapshot persistence
    # -------------------------------------------------------------------------
    def test_07_evidence_snapshot_persistence(self):
        """Test 7: Safe evidence snapshot is retained without storing raw files or entire documents."""
        tender, bidder, _, ev, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        self.assertIsNotNone(execution.evidence_snapshot)
        self.assertTrue(len(execution.evidence_snapshot) > 0)
        snap = execution.evidence_snapshot[0]
        self.assertEqual(snap["field"], "turnover")
        self.assertNotIn("raw_file_bytes", snap)

    # -------------------------------------------------------------------------
    # Test 8: Document hash preservation
    # -------------------------------------------------------------------------
    def test_08_document_hash_preservation(self):
        """Test 8: Evaluated document SHA-256 hashes are recorded with the verification."""
        tender, bidder, _, _, doc = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        self.assertIsNotNone(execution.document_hashes)
        self.assertEqual(execution.document_hashes.get(str(doc.id)), doc.sha256)

    # -------------------------------------------------------------------------
    # Test 9: Result hash generation
    # -------------------------------------------------------------------------
    def test_09_result_hash_generation(self):
        """Test 9: Completed verification receives a 64-character SHA-256 result hash."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        self.assertIsNotNone(resp.result_hash)
        self.assertEqual(len(resp.result_hash), 64)
        execution = crud_verification.get_by_verification_id(self.db, resp.verification_id)
        self.assertEqual(execution.result_hash, resp.result_hash)

    # -------------------------------------------------------------------------
    # Test 10: Deterministic result hashing
    # -------------------------------------------------------------------------
    def test_10_deterministic_result_hashing(self):
        """Test 10: Repeated hashing of identical logical output yields identical SHA-256 digest."""
        h1 = compute_canonical_result_hash(
            verification_id="VER-TEST-100",
            tender_id="t-1",
            bidder_id="b-1",
            overall_compliance="COMPLIANT",
            decision="QUALIFIED",
            risk_level="LOW",
            risk_score=15.0,
            overall_confidence=0.95,
            requirements=[{"requirement_id": "r1", "rule": "MIN_TURNOVER", "mandatory": True, "decision": "COMPLIANT"}],
            agent_results=[{"agent": "FINANCIAL_AGENT", "status": "PASS", "confidence": 0.95, "issues": []}],
        )
        h2 = compute_canonical_result_hash(
            verification_id="VER-TEST-100",
            tender_id="t-1",
            bidder_id="b-1",
            overall_compliance="COMPLIANT",
            decision="QUALIFIED",
            risk_level="LOW",
            risk_score=15.0,
            overall_confidence=0.95,
            requirements=[{"requirement_id": "r1", "rule": "MIN_TURNOVER", "mandatory": True, "decision": "COMPLIANT"}],
            agent_results=[{"agent": "FINANCIAL_AGENT", "status": "PASS", "confidence": 0.95, "issues": []}],
        )
        self.assertEqual(h1, h2)

    # -------------------------------------------------------------------------
    # Test 11: Duplicate request / idempotency behavior
    # -------------------------------------------------------------------------
    def test_11_duplicate_request_idempotency_behavior(self):
        """Test 11: Duplicate verification trigger returns cached completed result without re-dispatching."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        # First execution
        resp1 = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))
        self.assertEqual(mock_client.trigger_verification.call_count, 1)

        # Second execution with exact same payload
        resp2 = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        # Must reuse without calling n8n client a second time
        self.assertEqual(mock_client.trigger_verification.call_count, 1)
        self.assertEqual(resp1.verification_id, resp2.verification_id)
        self.assertEqual(resp1.result_hash, resp2.result_hash)

    # -------------------------------------------------------------------------
    # Test 12: Running verification behavior
    # -------------------------------------------------------------------------
    def test_12_running_verification_idempotency_behavior(self):
        """Test 12: Duplicate request while verification is in-flight returns current execution status."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        v_id = f"VER-{uuid.uuid4().hex[:8].upper()}"

        # Insert RUNNING execution
        execution = crud_verification.create_execution(
            db=self.db,
            verification_id=v_id,
            request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
            tender_id=tender.id,
            bidder_id=bidder.id,
            request_hash="mock_hash_123",
            status="RUNNING",
        )

        # Mock find_existing_execution to return the running execution
        mock_client = MagicMock(spec=N8nClient)
        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        with patch.object(crud_verification, "find_existing_execution", return_value=execution):
            resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        self.assertEqual(resp.status, VerificationStatusEnum.RUNNING)
        self.assertEqual(mock_client.trigger_verification.call_count, 0)

    # -------------------------------------------------------------------------
    # Test 13: Failed verification persistence
    # -------------------------------------------------------------------------
    def test_13_failed_verification_persistence(self):
        """Test 13: n8n timeout or failure records FAILED state and failure audit event."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(side_effect=N8nTimeoutError("Workflow timeout after 60s"))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        with self.assertRaises(N8nTimeoutError):
            asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        failed_exec = (
            self.db.query(VerificationExecution)
            .filter(VerificationExecution.tender_id == tender.id, VerificationExecution.status == "FAILED")
            .first()
        )
        self.assertIsNotNone(failed_exec)
        self.assertEqual(failed_exec.status, "FAILED")
        self.assertIn("timeout", failed_exec.error["message"].lower())

    # -------------------------------------------------------------------------
    # Test 14: Verification retrieval
    # -------------------------------------------------------------------------
    def test_14_verification_retrieval_endpoint(self):
        """Test 14: GET /api/v1/verification/{verification_id} retrieves persisted result."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])
        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        http_resp = self.client.get(f"/api/v1/verification/{resp.verification_id}")
        self.assertEqual(http_resp.status_code, 200)
        data = http_resp.json()
        self.assertEqual(data["verification_id"], resp.verification_id)
        self.assertEqual(data["decision"], "QUALIFIED")
        self.assertEqual(data["overall_compliance"], "COMPLIANT")
        self.assertIsNotNone(data["result_hash"])

    # -------------------------------------------------------------------------
    # Test 15: Tender/bidder isolation
    # -------------------------------------------------------------------------
    def test_15_tender_bidder_isolation(self):
        """Test 15: Verification history listing only returns records for the designated tender/bidder."""
        tender1, bidder1, _, _, _ = self._create_tender_and_bidder()
        tender2, bidder2, _, _, _ = self._create_tender_and_bidder()

        # Create executions for both pairs
        crud_verification.create_execution(
            self.db, "VER-PAIR-1", "REQ-1", tender1.id, bidder1.id, "hash1", "COMPLETED"
        )
        crud_verification.create_execution(
            self.db, "VER-PAIR-2", "REQ-2", tender2.id, bidder2.id, "hash2", "COMPLETED"
        )

        http_resp = self.client.get(f"/api/v1/verification/tender/{tender1.id}/bidder/{bidder1.id}")
        self.assertEqual(http_resp.status_code, 200)
        history = http_resp.json()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["verification_id"], "VER-PAIR-1")

    # -------------------------------------------------------------------------
    # Test 16: Unauthorized retrieval rejection
    # -------------------------------------------------------------------------
    def test_16_unauthorized_retrieval_rejection(self):
        """Test 16: User without permission to tender cannot retrieve verification result."""
        owner = self._create_user(email="owner@gem.gov.in", role=UserRole.PROCUREMENT_OFFICER)
        other_user = self._create_user(email="other@gem.gov.in", role=UserRole.PROCUREMENT_OFFICER)
        tender, bidder, _, _, _ = self._create_tender_and_bidder(created_by=owner.id)

        v_exec = crud_verification.create_execution(
            self.db, "VER-AUTH-TEST", "REQ-AUTH", tender.id, bidder.id, "hashauth", "COMPLETED"
        )

        other_token = create_access_token(subject=str(other_user.id), claims={"role": other_user.role.value})
        headers = {"Authorization": f"Bearer {other_token}"}


        resp = self.client.get(f"/api/v1/verification/{v_exec.verification_id}", headers=headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("forbidden", resp.text.lower())


    # -------------------------------------------------------------------------
    # Test 17: Verification history
    # -------------------------------------------------------------------------
    def test_17_verification_history_endpoint(self):
        """Test 17: GET /api/v1/verification/tender/{tender_id}/bidder/{bidder_id} returns safe history."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        crud_verification.create_execution(
            self.db, "VER-HIST-1", "REQ-1", tender.id, bidder.id, "hash1", "COMPLETED"
        )
        crud_verification.create_execution(
            self.db, "VER-HIST-2", "REQ-2", tender.id, bidder.id, "hash2", "FAILED"
        )

        resp = self.client.get(f"/api/v1/verification/tender/{tender.id}/bidder/{bidder.id}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data), 2)
        v_ids = [item["verification_id"] for item in data]
        self.assertIn("VER-HIST-1", v_ids)
        self.assertIn("VER-HIST-2", v_ids)

    # -------------------------------------------------------------------------
    # Test 18: Audit event creation
    # -------------------------------------------------------------------------
    def test_18_audit_event_creation(self):
        """Test 18: Lifecycle events VERIFICATION_CREATED, DISPATCHED, COMPLETED are logged in audit."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(return_value=self._build_mock_n8n_response(tender.id, bidder.id))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id, required_agents=["FINANCIAL_AGENT", "GST_AGENT"])

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        events = crud_verification.get_audit_events_for_verification(self.db, resp.verification_id)
        event_types = [e.event_type for e in events]
        self.assertIn("VERIFICATION_CREATED", event_types)
        self.assertIn("VERIFICATION_STARTED", event_types)
        self.assertIn("VERIFICATION_DISPATCHED", event_types)
        self.assertIn("VERIFICATION_COMPLETED", event_types)

    # -------------------------------------------------------------------------
    # Test 19: Secret sanitization
    # -------------------------------------------------------------------------
    def test_19_secret_sanitization(self):
        """Test 19: Error details containing API keys, database URLs, or paths are scrubbed."""
        err_with_secrets = {
            "db_error": "Connection failed to postgresql://admin:SuperSecretPassword123@db.internal:5432/sih",
            "api_key": "gsk_1234567890abcdef1234567890",
            "auth_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-ID",
            "path": "C:\\Users\\admin\\Desktop\\secrets\\app.key",
        }
        clean = sanitize_error_details(err_with_secrets)
        clean_str = json.dumps(clean)

        self.assertNotIn("SuperSecretPassword123", clean_str)
        self.assertNotIn("gsk_1234567890abcdef1234567890", clean_str)
        self.assertNotIn("app.key", clean_str)
        self.assertIn("[REDACTED", clean_str)

    # -------------------------------------------------------------------------
    # Test 20: No raw exception leakage
    # -------------------------------------------------------------------------
    def test_20_no_raw_exception_leakage(self):
        """Test 20: API returns sanitized error response without raw traceback on failures."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()

        # Request with invalid verification ID to trigger 404
        resp = self.client.get("/api/v1/verification/NON_EXISTENT_VERIFICATION_ID")
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("Traceback", resp.text)
        self.assertNotIn("File \"", resp.text)

    # -------------------------------------------------------------------------
    # Test 21: Missing verification → 404
    # -------------------------------------------------------------------------
    def test_21_missing_verification_returns_404(self):
        """Test 21: GET for non-existent verification ID returns 404 with standard error format."""
        resp = self.client.get(f"/api/v1/verification/VER-{uuid.uuid4().hex[:8].upper()}")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.text.lower())


    # -------------------------------------------------------------------------
    # Test 22: Malformed persisted data handling
    # -------------------------------------------------------------------------
    def test_22_malformed_persisted_data_handling(self):
        """Test 22: Reconstituting corrupted/malformed DB fields falls back gracefully without crashing."""
        tender, bidder, _, _, _ = self._create_tender_and_bidder()
        v_id = f"VER-{uuid.uuid4().hex[:8].upper()}"

        corrupt_exec = VerificationExecution(
            id=uuid.uuid4(),
            verification_id=v_id,
            request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
            tender_id=tender.id,
            bidder_id=bidder.id,
            status="UNKNOWN_STATUS_STRING",
            request_hash="hash",
            decision="UNKNOWN_DECISION_STRING",
            overall_compliance="UNKNOWN_COMPLIANCE",
            risk_level="UNKNOWN_RISK",
            requirements=[{"invalid_key": "missing_required_fields"}],
            agent_results=[{"invalid_agent": "missing_status"}],
            compliance_summary={"corrupt": "data"},
        )
        self.db.add(corrupt_exec)
        self.db.commit()

        # Reconstitution should not raise an exception
        reconstructed = crud_verification.to_verification_response(corrupt_exec)
        self.assertIsNotNone(reconstructed)
        self.assertEqual(reconstructed.verification_id, v_id)
        self.assertEqual(reconstructed.status, VerificationStatusEnum.UNVERIFIED)


if __name__ == "__main__":
    unittest.main()
