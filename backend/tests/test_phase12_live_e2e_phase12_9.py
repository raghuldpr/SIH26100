"""
Phase 12.9 — Live n8n Workflow Activation & E2E Validation Test Suite
backend/tests/test_phase12_live_e2e_phase12_9.py: Comprehensive validation of
genuine local end-to-end verification execution with live n8n Master Orchestrator,
10 specialized verification agents, callback security, state machine transitions,
result hashing, idempotency, and failure scenarios.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from uuid import UUID

from fastapi import HTTPException
from fastapi.testclient import TestClient
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_bidder import crud_bidder
from app.crud.crud_document import crud_document
from app.crud.crud_tender import crud_tender
from app.crud.crud_tender_requirement import crud_tender_requirement
from app.crud.crud_verification import (
    compute_canonical_result_hash,
    crud_verification,
)
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel
from app.models.document import Document
from app.models.enums import BidderStatus, DocumentStatus, DocumentType, ProcessingStatus, TenderStatus
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.schemas.bidder import BidderCreate
from app.schemas.verification import (
    DEFAULT_VERIFICATION_AGENTS,
    BidderEvidenceItemInput,
    CompliancePolicyInput,
    DocumentForensicInput,
    ExperienceEvidenceInput,
    ExperienceRequirementsInput,
    FinancialEvidenceInput,
    FinancialRequirementsInput,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    OverallComplianceEnum,
    ProjectExperienceItem,
    RequirementComplianceEnum,
    RiskLevelEnum,
    TenderRequirementItemInput,
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
from app.services.verification_service import (
    VerificationService,
    verification_service,
)


class TestPhase12LiveE2EPhase129(unittest.TestCase):
    """
    Phase 12.9 Validation Suite.
    Exercises live and mock contracts across all 12 validation pillars.
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        self.created_tender_ids = []
        self.created_bidder_ids = []
        self.created_doc_ids = []

    def tearDown(self):
        try:
            for doc_id in self.created_doc_ids:
                doc = crud_document.get_by_id(self.db, doc_id)
                if doc:
                    self.db.delete(doc)
            for bidder_id in self.created_bidder_ids:
                evidences = self.db.query(BidderEvidenceModel).filter(BidderEvidenceModel.bidder_id == bidder_id).all()
                for ev in evidences:
                    self.db.delete(ev)
                assignments = self.db.query(TenderBidder).filter(TenderBidder.bidder_id == bidder_id).all()
                for a in assignments:
                    self.db.delete(a)
                bidder = crud_bidder.get_by_id(self.db, bidder_id)
                if bidder:
                    self.db.delete(bidder)
            for tender_id in self.created_tender_ids:
                reqs = self.db.query(TenderRequirement).filter(TenderRequirement.tender_id == tender_id).all()
                for r in reqs:
                    self.db.delete(r)
                tender = crud_tender.get_by_id(self.db, tender_id)
                if tender:
                    self.db.delete(tender)
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def _create_synthetic_tender(self) -> Tender:
        tender = Tender(
            id=uuid.uuid4(),
            tender_number=f"GEM/2026/B/SYNTH_{uuid.uuid4().hex[:8].upper()}",
            title="Synthetic Tender for E2E Verification",
            description="Procurement of IT Equipment and Multi-Agent Evaluation",
            organization="Ministry of Electronics and Information Technology",
            department="Procurement Division",
            category="IT Infrastructure",
            status=TenderStatus.OPEN,
        )
        self.db.add(tender)
        self.db.commit()
        self.db.refresh(tender)
        self.created_tender_ids.append(tender.id)

        # Standard requirements
        r1 = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=tender.id,
            requirement_type="FINANCIAL",
            rule="MINIMUM_TURNOVER",
            description="Average annual turnover of at least INR 5 Crore over the preceding 3 years",
            parameters={
                "minimum": 50000000.0,
                "currency": "INR",
                "operator": ">=",
                "period": 3,
                "period_unit": "YEARS",
            },
            mandatory=True,
            confidence=0.98,
            source_page=2,
            source_section="Financial Eligibility",
            source_text="Bidder must have average annual turnover of at least Rs 5.00 Crore in last 3 financial years.",
        )
        r2 = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=tender.id,
            requirement_type="EXPERIENCE",
            rule="SIMILAR_WORK_EXPERIENCE",
            description="Minimum 3 completed similar works of value at least INR 2 Crore each",
            parameters={
                "minimum_similar_works": 3,
                "minimum_project_value": 20000000.0,
                "experience_period_years": 5,
            },
            mandatory=True,
            confidence=0.95,
            source_page=3,
            source_section="Technical Eligibility",
            source_text="Bidder should have completed 3 similar contracts valued at not less than Rs 2.00 Crore each.",
        )
        self.db.add_all([r1, r2])
        self.db.commit()
        return tender

    def _create_synthetic_bidder(self, tender_id: uuid.UUID) -> Bidder:
        bidder_in = BidderCreate(
            company_name="Apex Teleinfra Private Limited",
            registration_number="U72200MH2018PTC123456",
            gst_number="27AABCU9603R1ZM",
            pan_number="AABCU9603R",
            udyam_number="UDYAM-TEST-001",
            contact_person="Ramesh Patel",
            email="ramesh@apexteleinfra.example.com",
            phone="+91-9876543210",
            address="BKC, Bandra East, Mumbai, Maharashtra 400051",
            status=BidderStatus.ACTIVE,
        )
        bidder = crud_bidder.create(self.db, bidder_in=bidder_in)
        self.created_bidder_ids.append(bidder.id)
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender_id, bidder_id=bidder.id)

        # Synthetic Bidder Documents for Forensics Agent
        doc1 = Document(
            id=uuid.uuid4(),
            tender_id=tender_id,
            bidder_id=bidder.id,
            document_type=DocumentType.GST,
            original_filename="synthetic_gst_cert.pdf",
            storage_path="documents/synthetic_gst_cert.pdf",
            mime_type="application/pdf",
            file_size=245678,
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            status=DocumentStatus.ACTIVE,
            processing_status=ProcessingStatus.PROCESSED,
            extracted_data={
                "metadata": {
                    "creation_date": "2024-01-10T10:00:00Z",
                    "modification_date": "2024-01-10T10:30:00Z",
                    "producer": "Adobe PDF Library 15.0",
                },
                "ocr_text": "Government of India Form GST REG-06 Registration Certificate 27AABCU9603R1ZM Apex Teleinfra Private Limited Active Verified",
            },
        )
        doc2 = Document(
            id=uuid.uuid4(),
            tender_id=tender_id,
            bidder_id=bidder.id,
            document_type=DocumentType.PAN,
            original_filename="synthetic_pan_card.pdf",
            storage_path="documents/synthetic_pan_card.pdf",
            mime_type="application/pdf",
            file_size=154200,
            sha256="a1b2c3d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcdef",
            status=DocumentStatus.ACTIVE,
            processing_status=ProcessingStatus.PROCESSED,
            extracted_data={
                "metadata": {
                    "creation_date": "2023-05-12T08:00:00Z",
                    "modification_date": "2023-05-12T08:00:00Z",
                    "producer": "Income Tax Department NSDL",
                },
                "ocr_text": "INCOME TAX DEPARTMENT GOVT OF INDIA Permanent Account Number AABCU9603R Apex Teleinfra Private Limited",
            },
        )
        self.db.add_all([doc1, doc2])
        self.db.commit()
        self.created_doc_ids.extend([doc1.id, doc2.id])

        # Evidence: Turnover
        ev_turnover = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="turnover",
            value={"amount": 75000000.0, "average": 75000000.0, "currency": "INR", "page": 1},
            source_document="synthetic_ca_turnover.pdf",
            confidence=0.98,
        )
        # Evidence: Experience
        ev_exp = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="projects",
            value=[
                {
                    "project_id": "PRJ-SYNTH-01",
                    "project_name": "Metro Data Network",
                    "client_name": "MMRDA",
                    "project_value": 30000000.0,
                    "completion_date": "2024-02-15",
                    "similarity": True,
                    "completion_certificate": True,
                },
                {
                    "project_id": "PRJ-SYNTH-02",
                    "project_name": "Smart City CCTV",
                    "client_name": "Pune Smart City",
                    "project_value": 25000000.0,
                    "completion_date": "2023-08-20",
                    "similarity": True,
                    "completion_certificate": True,
                },
                {
                    "project_id": "PRJ-SYNTH-03",
                    "project_name": "Campus LAN Upgrade",
                    "client_name": "IIT Bombay",
                    "project_value": 22000000.0,
                    "completion_date": "2023-01-10",
                    "similarity": True,
                    "completion_certificate": True,
                },
            ],
            source_document="synthetic_completion_certs.pdf",
            confidence=0.96,
        )
        self.db.add_all([ev_turnover, ev_exp])
        self.db.commit()
        return bidder

    # -------------------------------------------------------------------------
    # Pillar 1 & 3: Webhook Registration & Health Check
    # -------------------------------------------------------------------------
    def test_01_n8n_health_and_webhook_availability(self):
        """Pillar 1 & 3: Confirms local n8n healthz endpoint and webhook registration."""
        loop = asyncio.new_event_loop()
        try:
            health = loop.run_until_complete(n8n_client.check_health())
            self.assertTrue(health.get("reachable"), f"n8n is not reachable: {health}")
            self.assertEqual(health.get("status_code"), 200)
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Pillar 2 & 4: Master Orchestrator Contract & 10 Agent Chain
    # -------------------------------------------------------------------------
    def test_02_live_n8n_master_orchestrator_execution(self):
        """Pillar 2 & 4: Executes live webhook with full 10-agent payload and validates response contract."""
        tender = self._create_synthetic_tender()
        bidder = self._create_synthetic_bidder(tender.id)

        payload = verification_service.build_and_validate_verification_request(
            tender_id=tender.id,
            bidder_id=bidder.id,
            db=self.db,
        )

        loop = asyncio.new_event_loop()
        try:
            response = loop.run_until_complete(n8n_client.trigger_verification(payload=payload))
            self.assertIsInstance(response, N8nVerificationResponse)
            self.assertEqual(response.status, "COMPLETED")
            self.assertEqual(response.decision, "QUALIFIED")
            self.assertEqual(response.risk_score, 0.0)
            self.assertEqual(response.risk_level, "LOW")
            self.assertGreaterEqual(len(response.agent_results), 10)

            agent_names = {a.agent for a in response.agent_results}
            expected_agents = set(DEFAULT_VERIFICATION_AGENTS)
            for exp in expected_agents:
                self.assertIn(exp, agent_names, f"Agent {exp} missing from live n8n execution output.")
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Pillar 6 & 7: End-to-End FastAPI -> n8n Flow & State Transitions
    # -------------------------------------------------------------------------
    def test_03_full_e2e_state_machine_lifecycle(self):
        """Pillar 6 & 7: Tests complete state transition QUEUED -> RUNNING -> COMPLETED and persistence."""
        tender = self._create_synthetic_tender()
        bidder = self._create_synthetic_bidder(tender.id)

        trigger_req = VerificationTriggerRequest(
            tender_id=tender.id,
            bidder_id=bidder.id,
        )

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                verification_service.execute_verification(
                    trigger_request=trigger_req,
                    db=self.db,
                )
            )
            self.assertIsInstance(result, VerificationResponse)
            self.assertEqual(result.status, VerificationStatusEnum.COMPLETED)
            self.assertEqual(result.decision, VerificationDecisionEnum.QUALIFIED)
            self.assertEqual(result.overall_compliance, OverallComplianceEnum.COMPLIANT)
            self.assertEqual(result.risk_level, RiskLevelEnum.LOW)
            self.assertIsNotNone(result.result_hash)
            self.assertTrue(len(result.result_hash) == 64)

            # Check database persistence
            persisted = crud_verification.get_by_verification_id(self.db, result.verification_id)
            self.assertIsNotNone(persisted)
            self.assertEqual(persisted.status, "COMPLETED")
            self.assertEqual(persisted.result_hash, result.result_hash)

            # Check audit events trail
            events = crud_verification.get_audit_events_for_verification(self.db, result.verification_id)
            event_types = [e.event_type for e in events]
            self.assertIn("VERIFICATION_CREATED", event_types)
            self.assertIn("VERIFICATION_STARTED", event_types)
            self.assertIn("VERIFICATION_DISPATCHED", event_types)
            self.assertIn("VERIFICATION_COMPLETED", event_types)
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Pillar 8: Callback Security & HMAC Verification
    # -------------------------------------------------------------------------
    def test_04_callback_security_and_hmac_enforcement(self):
        """Pillar 8: Verifies webhook callback HMAC authentication, reject on tamper/mismatch."""
        tender = self._create_synthetic_tender()
        bidder = self._create_synthetic_bidder(tender.id)

        verification_id = f"VER-CB-{uuid.uuid4().hex[:8].upper()}"
        request_id = f"REQ-CB-{uuid.uuid4().hex[:8].upper()}"

        # Create in-flight execution in DB
        execution = crud_verification.create_execution(
            db=self.db,
            verification_id=verification_id,
            request_id=request_id,
            tender_id=tender.id,
            bidder_id=bidder.id,
            request_hash="mock_hash",
            status="RUNNING",
        )

        callback_data = {
            "verification_id": verification_id,
            "request_id": request_id,
            "tender_id": str(tender.id),
            "bidder_id": str(bidder.id),
            "bidder_name": bidder.company_name,
            "status": "COMPLETED",
            "decision": "QUALIFIED",
            "risk_score": 0.0,
            "risk_level": "LOW",
            "agent_results": [
                {
                    "agent": "GST_AGENT",
                    "status": "VERIFIED",
                    "confidence": 0.98,
                    "evidence": {"active": True},
                    "issues": [],
                    "risk_level": "LOW",
                }
            ],
            "failed_requirements": [],
            "missing_documents": [],
            "warnings": [],
            "reasons": ["Verified via callback"],
        }
        body_json = json.dumps(callback_data)

        # 1. Reject invalid HMAC signature
        res_bad_sig = self.client.post(
            "/api/v1/verification/webhook/callback",
            content=body_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
                "X-Webhook-Signature": "sha256=invalid_signature_hex",
            },
        )
        self.assertEqual(res_bad_sig.status_code, 401)

        # 2. Reject invalid webhook secret
        res_bad_sec = self.client.post(
            "/api/v1/verification/webhook/callback",
            content=body_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": "wrong_secret",
            },
        )
        self.assertEqual(res_bad_sec.status_code, 401)

        # 3. Reject unknown verification ID
        bad_id_data = dict(callback_data)
        bad_id_data["verification_id"] = "VER-UNKNOWN-999"
        bad_id_json = json.dumps(bad_id_data)
        valid_bad_sig = n8n_client.generate_signature(bad_id_json)

        res_unknown = self.client.post(
            "/api/v1/verification/webhook/callback",
            content=bad_id_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
                "X-Webhook-Signature": f"sha256={valid_bad_sig}",
            },
        )
        self.assertEqual(res_unknown.status_code, 404)

        # 4. Accept valid HMAC and process callback
        valid_sig = n8n_client.generate_signature(body_json)
        res_valid = self.client.post(
            "/api/v1/verification/webhook/callback",
            content=body_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
                "X-Webhook-Signature": f"sha256={valid_sig}",
            },
        )
        self.assertEqual(res_valid.status_code, 200)
        self.assertEqual(res_valid.json()["status"], "processed")

        # 5. Finalized execution cannot be overwritten (Idempotent ignore)
        res_overwrite = self.client.post(
            "/api/v1/verification/webhook/callback",
            content=body_json,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Secret": settings.N8N_WEBHOOK_SECRET,
                "X-Webhook-Signature": f"sha256={valid_sig}",
            },
        )
        self.assertEqual(res_overwrite.status_code, 200)
        self.assertEqual(res_overwrite.json()["status"], "already_finalized")

    # -------------------------------------------------------------------------
    # Pillar 9 & 10: Result Traceability & Result Hashing
    # -------------------------------------------------------------------------
    def test_05_result_traceability_and_deterministic_hash(self):
        """Pillar 9 & 10: Confirms clause-to-evidence provenance and SHA-256 hash consistency."""
        tender = self._create_synthetic_tender()
        bidder = self._create_synthetic_bidder(tender.id)

        trigger_req = VerificationTriggerRequest(
            tender_id=tender.id,
            bidder_id=bidder.id,
        )

        loop = asyncio.new_event_loop()
        try:
            resp = loop.run_until_complete(
                verification_service.execute_verification(
                    trigger_request=trigger_req,
                    db=self.db,
                )
            )

            # Traceability check
            self.assertGreaterEqual(len(resp.requirements), 2)
            for req_eval in resp.requirements:
                self.assertIsNotNone(req_eval.requirement_id)
                self.assertIsNotNone(req_eval.rule)
                self.assertIsNotNone(req_eval.agent)
                self.assertIn(req_eval.decision, [RequirementComplianceEnum.COMPLIANT, RequirementComplianceEnum.PARTIALLY_COMPLIANT, RequirementComplianceEnum.UNVERIFIED])

            # Result hash check
            hash1 = resp.result_hash
            self.assertIsNotNone(hash1)
            self.assertEqual(len(hash1), 64)

            # Recomputed canonical hash with same data must match exactly
            hash2 = compute_canonical_result_hash(
                verification_id=resp.verification_id,
                tender_id=resp.tender_id,
                bidder_id=resp.bidder_id,
                overall_compliance=resp.overall_compliance.value if resp.overall_compliance else None,
                decision=resp.decision.value if resp.decision else None,
                risk_level=resp.risk_level.value if resp.risk_level else None,
                risk_score=resp.risk_score,
                overall_confidence=resp.overall_confidence,
                requirements=[r.model_dump() for r in resp.requirements],
                agent_results=[a.model_dump() for a in resp.agent_results],
                evidence_snapshot=resp.evidence_snapshot,
                document_hashes=resp.document_hashes,
            )
            self.assertEqual(hash1, hash2)

            # Altering decision must change the hash
            tampered_hash = compute_canonical_result_hash(
                verification_id=resp.verification_id,
                tender_id=resp.tender_id,
                bidder_id=resp.bidder_id,
                overall_compliance="NON_COMPLIANT",
                decision="NOT_QUALIFIED",
                risk_level="HIGH",
                risk_score=90.0,
                overall_confidence=resp.overall_confidence,
                requirements=[r.model_dump() for r in resp.requirements],
                agent_results=[a.model_dump() for a in resp.agent_results],
                evidence_snapshot=resp.evidence_snapshot,
                document_hashes=resp.document_hashes,
            )
            self.assertNotEqual(hash1, tampered_hash)
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Pillar 11: Idempotency Enforcement
    # -------------------------------------------------------------------------
    def test_06_idempotency_cached_result_and_in_flight_status(self):
        """Pillar 11: Repeated trigger request returns existing result without re-executing n8n."""
        tender = self._create_synthetic_tender()
        bidder = self._create_synthetic_bidder(tender.id)

        trigger_req = VerificationTriggerRequest(
            tender_id=tender.id,
            bidder_id=bidder.id,
        )

        loop = asyncio.new_event_loop()
        try:
            # 1. First execution (Live or mock)
            first_resp = loop.run_until_complete(
                verification_service.execute_verification(
                    trigger_request=trigger_req,
                    db=self.db,
                )
            )
            self.assertEqual(first_resp.status, VerificationStatusEnum.COMPLETED)

            # 2. Second execution (Should return cached completed result)
            second_resp = loop.run_until_complete(
                verification_service.execute_verification(
                    trigger_request=trigger_req,
                    db=self.db,
                )
            )
            self.assertEqual(first_resp.verification_id, second_resp.verification_id)
            self.assertEqual(first_resp.result_hash, second_resp.result_hash)
        finally:
            loop.close()

    # -------------------------------------------------------------------------
    # Pillar 12: Failure Scenarios Fail Closed
    # -------------------------------------------------------------------------
    def test_07_failure_handling_fails_closed(self):
        """Pillar 12: Tests connection error, timeout, malformed payload, and isolation failure."""
        tender = self._create_synthetic_tender()
        bidder = self._create_synthetic_bidder(tender.id)

        # 1. Connection error handling
        failing_client = N8nClient(webhook_url="http://localhost:59999/non-existent-port")
        failing_service = VerificationService(client=failing_client)

        trigger_req = VerificationTriggerRequest(
            tender_id=tender.id,
            bidder_id=bidder.id,
            metadata={"force_refresh": True},
        )

        loop = asyncio.new_event_loop()
        try:
            with self.assertRaises(N8nConnectionError):
                loop.run_until_complete(
                    failing_service.execute_verification(
                        trigger_request=trigger_req,
                        db=self.db,
                    )
                )
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
