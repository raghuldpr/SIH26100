"""
SIH-26100 — Phase 12.4 Test Suite
tests/test_phase12_verification_request.py

Verifies:
Tender
   ↓
Tender Requirements
   ↓
Compliance Profile
   +
Bidder
   ↓
Bidder Documents
   ↓
Structured Evidence
   ↓
Verification Request
   ↓
Existing FastAPI → n8n Client
"""
import io
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from uuid import UUID

import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.exceptions import AppException, BadRequestException, NotFoundException
from app.crud.crud_bidder import crud_bidder
from app.crud.crud_document import crud_document
from app.crud.crud_tender import crud_tender
from app.crud.crud_tender_requirement import crud_tender_requirement
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel
from app.models.document import Document
from app.models.enums import BidderStatus, DocumentStatus, DocumentType, ProcessingStatus, TenderStatus
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.schemas.bidder import BidderCreate
from app.schemas.verification import (
    DEFAULT_VERIFICATION_AGENTS,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    VerificationTriggerRequest,
)
from app.services.n8n_client import N8nClient
from app.services.verification_service import VerificationService, verification_service


class TestPhase12VerificationRequest(unittest.TestCase):
    """
    Phase 12.4 Test Suite.
    Tests 1 to 12 verifying the complete verification request construction,
    requirement mapping, evidence mapping, traceability, isolation, security,
    JSON serialization, and mock dispatch.
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

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

    def _create_tender(self, title: str = "Tender 2026 Procurement") -> Tender:
        tender = Tender(
            id=uuid.uuid4(),
            tender_number=f"GEM/2026/B/P12_{uuid.uuid4().hex[:8].upper()}",
            title=title,
            description="Procurement of IT and Networking Systems",
            organization="Department of Telecommunications",
            department="Network Infrastructure",
            category="IT Hardware",
            status=TenderStatus.OPEN,
        )
        self.db.add(tender)
        self.db.commit()
        self.db.refresh(tender)
        self.created_tender_ids.append(tender.id)
        return tender

    def _create_bidder(self, name: str = "Pinnacle Cloud Solutions") -> Bidder:
        bidder_in = BidderCreate(
            company_name=name,
            registration_number=f"U72200DL2026PTC{uuid.uuid4().hex[:6].upper()}",
            gst_number="07AAAAA0000A1Z5",
            pan_number="AAAAA0000A",
            udyam_number="UDYAM-DL-01-0012345",
            contact_person="Sunil Verma",
            email="sunil@pinnaclecloud.com",
            phone="+91-9988776655",
            address="Nehru Place, New Delhi",
            status=BidderStatus.ACTIVE,
        )
        bidder = crud_bidder.create(self.db, bidder_in=bidder_in)
        self.created_bidder_ids.append(bidder.id)
        return bidder

    def _create_standard_requirements(self, tender_id: UUID):
        r1 = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=tender_id,
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
            source_page=4,
            source_section="Financial Eligibility Criteria",
            source_text="The bidder must possess a minimum average annual turnover of Rs. 5 Crore during the last 3 financial years.",
        )
        r2 = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=tender_id,
            requirement_type="EXPERIENCE",
            rule="SIMILAR_WORK_EXPERIENCE",
            description="Experience of successfully completing at least 3 similar works of minimum value INR 2 Crore each",
            parameters={
                "minimum_similar_works": 3,
                "minimum_project_value": 20000000.0,
                "experience_period_years": 5,
                "require_completion_certificate": True,
            },
            mandatory=True,
            confidence=0.95,
            source_page=6,
            source_section="Past Performance Criteria",
            source_text="The bidder should have executed three similar projects of value not less than Rs 2.00 Crore each in last 5 years.",
        )
        self.db.add_all([r1, r2])
        self.db.commit()
        return [r1, r2]

    # -------------------------------------------------------------------------
    # Test 1 — Complete request construction
    # -------------------------------------------------------------------------
    def test_01_complete_request_construction(self):
        """Test 1: Tender + requirements + bidder + evidence produces a valid verification request."""
        tender = self._create_tender("Test 1 Complete Tender")
        bidder = self._create_bidder("Test 1 Alpha Corp")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        # Create bidder evidence
        ev = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="turnover",
            value={"amount": 60000000.0, "average": 60000000.0, "currency": "INR", "page": 1},
            source_document="audited_balance_sheet.pdf",
            confidence=0.95,
        )
        self.db.add(ev)
        self.db.commit()

        payload = verification_service.build_and_validate_verification_request(
            tender_id=tender.id,
            bidder_id=bidder.id,
            db=self.db,
        )

        self.assertIsInstance(payload, N8nVerificationPayload)
        self.assertEqual(payload.tender_id, str(tender.id))
        self.assertEqual(payload.bidder_id, str(bidder.id))
        self.assertEqual(payload.bidder_name, bidder.company_name)
        self.assertGreaterEqual(len(payload.tender_requirements), 2)
        self.assertGreaterEqual(len(payload.bidder_evidence), 1)
        self.assertEqual(payload.required_agents, DEFAULT_VERIFICATION_AGENTS)

    # -------------------------------------------------------------------------
    # Test 2 — Requirement mapping
    # -------------------------------------------------------------------------
    def test_02_requirement_mapping_preserves_parameters(self):
        """Test 2: Verify requirement parameters and traceability are preserved exactly."""
        tender = self._create_tender("Test 2 Requirement Mapping")
        bidder = self._create_bidder("Test 2 Bidder")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        payload = verification_service.build_and_validate_verification_request(
            tender_id=tender.id,
            bidder_id=bidder.id,
            db=self.db,
        )

        # Verify TenderRequirementItemInput items
        turnover_req = next((r for r in payload.tender_requirements if r.rule == "MINIMUM_TURNOVER"), None)
        self.assertIsNotNone(turnover_req)
        self.assertEqual(turnover_req.parameters["minimum"], 50000000.0)
        self.assertEqual(turnover_req.parameters["operator"], ">=")
        self.assertEqual(turnover_req.parameters["currency"], "INR")
        self.assertEqual(turnover_req.source_page, 4)
        self.assertEqual(turnover_req.source_section, "Financial Eligibility Criteria")
        self.assertIn("minimum average annual turnover", turnover_req.source_text)

        # Verify synthesized FinancialRequirementsInput
        self.assertIsNotNone(payload.financial_requirements)
        self.assertEqual(payload.financial_requirements.minimum_annual_turnover, 50000000.0)
        self.assertEqual(payload.financial_requirements.average_turnover, 50000000.0)

        # Verify Experience requirements
        self.assertIsNotNone(payload.experience_requirements)
        self.assertEqual(payload.experience_requirements.minimum_similar_works, 3)
        self.assertEqual(payload.experience_requirements.minimum_project_value, 20000000.0)

    # -------------------------------------------------------------------------
    # Test 3 — Evidence mapping
    # -------------------------------------------------------------------------
    def test_03_evidence_mapping_reaches_request(self):
        """Test 3: Verify bidder evidence (PAN, GSTIN, UDYAM, turnover, experience) reaches the request."""
        tender = self._create_tender("Test 3 Evidence Mapping")
        bidder = self._create_bidder("Test 3 Bidder Evidence")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        # Add PAN, GSTIN, Udyam, turnover, and experience evidence
        ev_gst = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="gstin",
            value={"gstin": "07AAAAA0000A1Z5", "page": 1, "source_text": "GSTIN: 07AAAAA0000A1Z5"},
            source_document="gst_cert.pdf",
            confidence=0.99,
        )
        ev_pan = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="pan",
            value={"pan": "AAAAA0000A", "page": 1, "source_text": "Permanent Account Number: AAAAA0000A"},
            source_document="pan_card.pdf",
            confidence=0.99,
        )
        ev_turnover = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="turnover",
            value={"average": 75000000.0, "amount": 75000000.0},
            source_document="ca_turnover.pdf",
            confidence=0.95,
        )
        ev_exp = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="projects",
            value=[
                {
                    "project_id": "WO-9988",
                    "project_name": "Optical Fiber Backbone",
                    "client_name": "BSNL",
                    "project_value": 35000000.0,
                    "completion_date": "2023-11-30",
                    "similarity": True,
                    "completion_certificate": True,
                }
            ],
            source_document="experience_cert.pdf",
            confidence=0.92,
        )
        self.db.add_all([ev_gst, ev_pan, ev_turnover, ev_exp])
        self.db.commit()

        payload = verification_service.build_and_validate_verification_request(
            tender_id=tender.id,
            bidder_id=bidder.id,
            db=self.db,
        )

        # Check evidence array
        fields = [e.field for e in payload.bidder_evidence]
        self.assertIn("gstin", fields)
        self.assertIn("pan", fields)
        self.assertIn("turnover", fields)
        self.assertIn("projects", fields)

        # Check synthesized financial evidence
        self.assertIsNotNone(payload.financial_evidence)
        self.assertIsNotNone(payload.financial_evidence.turnover)

        # Check synthesized experience evidence
        self.assertIsNotNone(payload.experience_evidence)
        self.assertEqual(len(payload.experience_evidence.projects), 1)
        self.assertEqual(payload.experience_evidence.projects[0].client_name, "BSNL")
        self.assertEqual(payload.experience_evidence.projects[0].project_value, 35000000.0)

    # -------------------------------------------------------------------------
    # Test 4 — Traceability preservation
    # -------------------------------------------------------------------------
    def test_04_traceability_preserves_document_and_page(self):
        """Test 4: Verify document -> page -> source text -> evidence is preserved."""
        tender = self._create_tender("Test 4 Traceability")
        bidder = self._create_bidder("Test 4 Trace Bidder")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        doc_id = uuid.uuid4()
        ev = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="udyam_number",
            value={
                "udyam_number": "UDYAM-DL-01-0012345",
                "document_id": str(doc_id),
                "document_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "page": 2,
                "source_text": "UDYAM REGISTRATION CERTIFICATE: UDYAM-DL-01-0012345",
                "extraction_method": "DETERMINISTIC",
            },
            source_document="udyam_cert.pdf",
            confidence=0.98,
        )
        self.db.add(ev)
        self.db.commit()

        payload = verification_service.build_and_validate_verification_request(
            tender_id=tender.id,
            bidder_id=bidder.id,
            db=self.db,
        )

        udyam_ev = next((e for e in payload.bidder_evidence if e.field == "udyam_number"), None)
        self.assertIsNotNone(udyam_ev)
        self.assertEqual(udyam_ev.document_id, str(doc_id))
        self.assertEqual(udyam_ev.source_page, 2)
        self.assertEqual(udyam_ev.source_text, "UDYAM REGISTRATION CERTIFICATE: UDYAM-DL-01-0012345")
        self.assertEqual(udyam_ev.document_hash, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(udyam_ev.extraction_method, "DETERMINISTIC")

    # -------------------------------------------------------------------------
    # Test 5 — Bidder isolation (Fails closed)
    # -------------------------------------------------------------------------
    def test_05_bidder_isolation_fails_closed(self):
        """Test 5: Evidence or unassociated bidder from another bidder must fail closed."""
        tender = self._create_tender("Test 5 Isolation Tender")
        bidder1 = self._create_bidder("Bidder 1 Associated")
        bidder2 = self._create_bidder("Bidder 2 Rogue")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder1.id)
        self._create_standard_requirements(tender.id)

        # Bidder 2 is NOT associated with tender
        with self.assertRaises(BadRequestException):
            verification_service.build_and_validate_verification_request(
                tender_id=tender.id,
                bidder_id=bidder2.id,
                db=self.db,
            )

    # -------------------------------------------------------------------------
    # Test 6 — Tender isolation (Fails closed)
    # -------------------------------------------------------------------------
    def test_06_tender_isolation_fails_closed(self):
        """Test 6: Evidence or requirements from another tender must be rejected."""
        tender1 = self._create_tender("Tender 1 Correct")
        tender2 = self._create_tender("Tender 2 Alien")
        bidder = self._create_bidder("Bidder Alien Test")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender1.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender1.id)

        # Inject evidence tagged with alien tender2 ID
        ev_alien = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="turnover",
            value={"amount": 50000000.0, "tender_id": str(tender2.id)},
            source_document="alien_doc.pdf",
            confidence=0.90,
        )
        self.db.add(ev_alien)
        self.db.commit()

        # Must fail closed due to cross-tender contamination
        with self.assertRaises(BadRequestException) as ctx:
            verification_service.build_and_validate_verification_request(
                tender_id=tender1.id,
                bidder_id=bidder.id,
                db=self.db,
            )
        self.assertIn("Evidence isolation violation", str(ctx.exception.message))

    # -------------------------------------------------------------------------
    # Test 7 — Missing bidder fails cleanly
    # -------------------------------------------------------------------------
    def test_07_missing_bidder_fails_cleanly(self):
        """Test 7: Request creation with non-existent bidder fails with NotFoundException."""
        tender = self._create_tender("Test 7 Missing Bidder")
        non_existent_bidder = uuid.uuid4()

        with self.assertRaises(NotFoundException):
            verification_service.build_and_validate_verification_request(
                tender_id=tender.id,
                bidder_id=non_existent_bidder,
                db=self.db,
            )

    # -------------------------------------------------------------------------
    # Test 8 — Missing requirements fails closed
    # -------------------------------------------------------------------------
    def test_08_missing_requirements_fails_closed(self):
        """Test 8: Request validation fails closed when a tender has 0 requirements configured."""
        tender = self._create_tender("Tender Without Requirements")
        bidder = self._create_bidder("Bidder With Empty Tender")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)

        # 0 requirements configured
        with self.assertRaises(BadRequestException) as ctx:
            verification_service.build_and_validate_verification_request(
                tender_id=tender.id,
                bidder_id=bidder.id,
                db=self.db,
            )
        self.assertIn("no compliance requirements configured", str(ctx.exception.message))

    # -------------------------------------------------------------------------
    # Test 9 — Invalid / malformed evidence rejected
    # -------------------------------------------------------------------------
    def test_09_invalid_evidence_rejected(self):
        """Test 9: Malformed evidence (e.g. missing / blank field name) is rejected."""
        tender = self._create_tender("Test 9 Invalid Evidence Tender")
        bidder = self._create_bidder("Test 9 Bidder")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        # Malformed: blank / whitespace field
        bad_ev = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="   ",
            value={"amount": 1000},
            source_document="bad_doc.pdf",
            confidence=0.95,
        )
        self.db.add(bad_ev)
        self.db.commit()

        with self.assertRaises(BadRequestException) as ctx:
            verification_service.build_and_validate_verification_request(
                tender_id=tender.id,
                bidder_id=bidder.id,
                db=self.db,
            )
        self.assertIn("missing required field name", str(ctx.exception.message).lower())


    # -------------------------------------------------------------------------
    # Test 10 — JSON serialization
    # -------------------------------------------------------------------------
    def test_10_json_serialization_succeeds_without_errors(self):
        """Test 10: Complete request serializes to JSON without UUID, datetime, or binary errors."""
        tender = self._create_tender("Test 10 Serialization Tender")
        bidder = self._create_bidder("Test 10 Bidder")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        payload = verification_service.build_and_validate_verification_request(
            tender_id=tender.id,
            bidder_id=bidder.id,
            db=self.db,
        )

        # Must serialize cleanly to JSON string
        json_str = payload.model_dump_json()
        self.assertIsInstance(json_str, str)

        # Must parse back cleanly into standard Python dict
        parsed = json.loads(json_str)
        self.assertEqual(parsed["tender_id"], str(tender.id))
        self.assertEqual(parsed["bidder_id"], str(bidder.id))
        self.assertIn("tender_requirements", parsed)
        self.assertIn("bidder_evidence", parsed)
        self.assertTrue(parsed["request_id"].startswith("REQ-VER-"))

    # -------------------------------------------------------------------------
    # Test 11 — Security validation (No credentials or internal paths)
    # -------------------------------------------------------------------------
    def test_11_security_sanitization_rejects_credentials(self):
        """Test 11: Secrets and internal paths are absent; injected secrets fail closed."""
        tender = self._create_tender("Test 11 Security Tender")
        bidder = self._create_bidder("Test 11 Security Bidder")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        # 1. Normal payload passes security scan
        payload = verification_service.build_and_validate_verification_request(
            tender_id=tender.id,
            bidder_id=bidder.id,
            db=self.db,
        )
        self.assertIsNotNone(payload)

        # 2. Inject forbidden credential into metadata
        trigger_with_leak = VerificationTriggerRequest(
            tender_id=tender.id,
            bidder_id=bidder.id,
            metadata={"db_uri": "postgresql://postgres:mysecretpassword@localhost:5432/sih_db"},
        )

        with self.assertRaises(AppException) as ctx:
            verification_service.build_and_validate_verification_request(
                tender_id=tender.id,
                bidder_id=bidder.id,
                db=self.db,
                trigger_request=trigger_with_leak,
            )
        self.assertIn("Security validation failed", str(ctx.exception.message))

    # -------------------------------------------------------------------------
    # Test 12 — n8n client dispatch mock (Zero real webhooks)
    # -------------------------------------------------------------------------
    def test_12_n8n_dispatch_with_mocked_client(self):
        """
        Test 12: Mocks existing N8nClient and verifies exact payload would be dispatched.
        Zero live webhooks, zero external government calls, zero live Groq calls.
        """
        tender = self._create_tender("Test 12 Dispatch Tender")
        bidder = self._create_bidder("Test 12 Dispatch Bidder")
        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)
        self._create_standard_requirements(tender.id)

        # Create corresponding evidence for the standard requirements
        ev1 = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="turnover",
            value={"amount": 100000000.0, "average": 100000000.0},
            source_document="balance_sheet.pdf",
            confidence=0.98,
        )
        ev2 = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="experience",
            value={"similar_works": 3},
            source_document="work_order.pdf",
            confidence=0.95,
        )
        self.db.add_all([ev1, ev2])
        self.db.commit()

        mock_n8n_client = MagicMock(spec=N8nClient)
        mock_response = N8nVerificationResponse(
            verification_id="VER-MOCK-999",
            request_id="REQ-MOCK-999",
            tender_id=str(tender.id),
            bidder_id=str(bidder.id),
            bidder_name=bidder.company_name,
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=12.5,
            risk_level="LOW",
            agent_results=[
                N8nAgentResult(
                    agent="FINANCIAL_AGENT",
                    status="VERIFIED",
                    confidence=0.98,
                    evidence={"average_turnover": 100000000.0},
                    issues=[],
                    risk_level="LOW",
                ),
                N8nAgentResult(
                    agent="EXPERIENCE_AGENT",
                    status="VERIFIED",
                    confidence=0.95,
                    evidence={"similar_works": 3},
                    issues=[],
                    risk_level="LOW",
                ),
                N8nAgentResult(
                    agent="GST_AGENT",
                    status="VERIFIED",
                    confidence=0.98,
                    evidence={"active": True},
                    issues=[],
                    risk_level="LOW",
                ),
            ],
            reasons=["All required criteria verified successfully"],
        )
        mock_n8n_client.trigger_verification = AsyncMock(return_value=mock_response)

        service_with_mock = VerificationService(client=mock_n8n_client)

        trigger_req = VerificationTriggerRequest(
            tender_id=tender.id,
            bidder_id=bidder.id,
            required_agents=["FINANCIAL_AGENT", "EXPERIENCE_AGENT", "GST_AGENT"],
        )


        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            api_resp = loop.run_until_complete(
                service_with_mock.execute_verification(
                    trigger_request=trigger_req,
                    db=self.db,
                )
            )
        finally:
            loop.close()

        # Verify n8n client was invoked once
        mock_n8n_client.trigger_verification.assert_called_once()
        dispatched_payload = mock_n8n_client.trigger_verification.call_args[1]["payload"]

        # Verify payload structure passed to n8n
        self.assertIsInstance(dispatched_payload, N8nVerificationPayload)
        self.assertEqual(dispatched_payload.tender_id, str(tender.id))
        self.assertEqual(dispatched_payload.bidder_id, str(bidder.id))
        self.assertEqual(dispatched_payload.bidder_name, bidder.company_name)
        self.assertEqual(api_resp.decision.value, "QUALIFIED")


if __name__ == "__main__":
    unittest.main()
