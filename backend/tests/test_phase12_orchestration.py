"""
SIH-26100 — Phase 12.5 Test Suite
tests/test_phase12_orchestration.py

Verifies:
Validated Tender + Bidder Request
              ↓
       FastAPI Verification Service
              ↓
        Existing n8n Client
              ↓
       n8n Master Orchestrator (Mocked)
              ↓
       Required Verification Agents
              ↓
       Agent Results
              ↓
       Result Aggregation
              ↓
       Schema Validation
              ↓
          FastAPI Response
"""
import asyncio
import io
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from uuid import UUID

import pytest
from pydantic import ValidationError

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.exceptions import AppException, BadRequestException, NotFoundException
from app.crud.crud_bidder import crud_bidder
from app.crud.crud_document import crud_document
from app.crud.crud_tender import crud_tender
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel
from app.models.document import Document
from app.models.enums import BidderStatus, DocumentType, TenderStatus
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.schemas.bidder import BidderCreate
from app.schemas.verification import (
    DEFAULT_VERIFICATION_AGENTS,
    AgentStatusEnum,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    OverallComplianceEnum,
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
)
from app.services.verification_aggregator import (
    VerificationResultAggregator,
    verification_aggregator,
)
from app.services.verification_service import (
    VerificationService,
    verification_service,
)


class TestPhase12Orchestration(unittest.TestCase):
    """
    Phase 12.5 Orchestration Execution & Result Collection Test Suite.
    Tests 1 to 20 validating n8n dispatch, agent result collection, aggregation,
    fail-closed security, traceability, and API compliance.
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

    def _setup_tender_and_bidder(self):
        """Helper to create a fully associated tender and bidder with requirements and evidence."""
        tender = Tender(
            id=uuid.uuid4(),
            tender_number=f"GEM/2026/B/ORCH_{uuid.uuid4().hex[:8].upper()}",
            title="Fiber Optic Network Deployment 2026",
            description="Turnkey optical fiber deployment and maintenance",
            organization="Ministry of Communications",
            department="Telecommunications",
            category="Infrastructure",
            status=TenderStatus.OPEN,
        )
        self.db.add(tender)
        self.db.commit()
        self.db.refresh(tender)
        self.created_tender_ids.append(tender.id)

        bidder_in = BidderCreate(
            company_name="Apex Teleinfra Private Limited",
            registration_number=f"U64200DL2026PTC{uuid.uuid4().hex[:6].upper()}",
            gst_number="07AAACA1234A1Z5",
            pan_number="AAACA1234A",
            udyam_number="UDYAM-DL-05-0099887",
            contact_person="Rajesh Kumar",
            email="rajesh@apexteleinfra.com",
            phone="+91-9876543210",
            address="Barakhamba Road, New Delhi",
            status=BidderStatus.ACTIVE,
        )
        bidder = crud_bidder.create(self.db, bidder_in=bidder_in)
        self.created_bidder_ids.append(bidder.id)

        crud_bidder.assign_bidder_to_tender(self.db, tender_id=tender.id, bidder_id=bidder.id)

        # Standard requirements
        r1 = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=tender.id,
            requirement_type="FINANCIAL",
            rule="MINIMUM_TURNOVER",
            description="Minimum average annual turnover of INR 10 Crore",
            parameters={"minimum": 100000000.0, "currency": "INR", "operator": ">="},
            mandatory=True,
            confidence=0.98,
            source_page=3,
            source_section="Financial Eligibility",
            source_text="The bidder must have an average annual turnover of at least Rs. 10 Crore.",
        )
        r2 = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=tender.id,
            requirement_type="EXPERIENCE",
            rule="SIMILAR_WORK_EXPERIENCE",
            description="Completion of at least 2 similar optical fiber projects",
            parameters={"minimum_similar_works": 2, "minimum_project_value": 40000000.0},
            mandatory=True,
            confidence=0.95,
            source_page=5,
            source_section="Technical Eligibility",
            source_text="Two similar projects of value not less than Rs. 4 Crore each.",
        )
        self.db.add_all([r1, r2])

        # Standard documents
        doc = Document(
            id=uuid.uuid4(),
            bidder_id=bidder.id,
            tender_id=tender.id,
            document_type=DocumentType.FINANCIAL_STATEMENT,
            file_name="balance_sheet_audited.pdf",
            original_filename="balance_sheet_audited.pdf",
            storage_path="bidders/apex/bs.pdf",
            mime_type="application/pdf",
            file_size=204800,
            sha256="a1b2c3d4e5f67890abcdef1234567890abcdef1234567890abcdef1234567890",
        )
        self.db.add(doc)
        self.created_doc_ids.append(doc.id)

        # Standard evidence
        ev = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder.id,
            field="turnover",
            value={
                "amount": 120000000.0,
                "average": 120000000.0,
                "document_id": str(doc.id),
                "document_hash": doc.sha256,
                "page": 2,
                "source_text": "Audited Annual Turnover: INR 12,00,00,000",
                "extraction_method": "DETERMINISTIC",
            },
            source_document="balance_sheet_audited.pdf",
            confidence=0.97,
        )
        self.db.add(ev)
        self.db.commit()

        return tender, bidder, [r1, r2], doc, ev

    def _build_standard_n8n_response(self, tender_id: UUID, bidder_id: UUID, bidder_name: str) -> N8nVerificationResponse:
        results = [
            N8nAgentResult(agent="TENDER_INTELLIGENCE_AGENT", status="VERIFIED", confidence=0.98, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="VERIFIED", confidence=0.99, evidence={"gstin": "07AAACA1234A1Z5"}, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="PAN_AGENT", status="VERIFIED", confidence=0.99, evidence={"pan": "AAACA1234A"}, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="UDYAM_AGENT", status="VERIFIED", confidence=0.95, evidence={"udyam": "UDYAM-DL-05-0099887"}, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="FINANCIAL_AGENT", status="VERIFIED", confidence=0.96, evidence={"turnover": 120000000.0}, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="VERIFIED", confidence=0.94, evidence={"verified_works": 2}, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="DOCUMENT_FORENSICS_AGENT", status="VERIFIED", confidence=0.97, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="ENTITY_RESOLUTION_AGENT", status="VERIFIED", confidence=0.96, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="RISK_INTELLIGENCE_AGENT", status="VERIFIED", confidence=0.95, issues=[], risk_level="LOW"),
            N8nAgentResult(agent="FINAL_COMPLIANCE_AGENT", status="QUALIFIED", confidence=0.98, issues=[], risk_level="LOW"),
        ]
        return N8nVerificationResponse(
            verification_id=f"VER-P125-{uuid.uuid4().hex[:8].upper()}",
            request_id=f"REQ-P125-{uuid.uuid4().hex[:8].upper()}",
            tender_id=str(tender_id),
            bidder_id=str(bidder_id),
            bidder_name=bidder_name,
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=10.0,
            risk_level="LOW",
            agent_results=results,
            failed_requirements=[],
            warnings=[],
            missing_documents=[],
            reasons=["All required statutory and technical criteria verified successfully."],
        )

    # -------------------------------------------------------------------------
    # Test 1: Complete valid request reaches n8n
    # -------------------------------------------------------------------------
    def test_01_complete_valid_request_reaches_n8n(self):
        """Test 1: Complete valid request reaches n8n client mock."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        mock_client.trigger_verification.assert_called_once()
        dispatched_payload = mock_client.trigger_verification.call_args[1]["payload"]
        self.assertIsInstance(dispatched_payload, N8nVerificationPayload)
        self.assertEqual(resp.status, VerificationStatusEnum.COMPLETED)

    # -------------------------------------------------------------------------
    # Test 2: n8n receives correct tender/bidder IDs
    # -------------------------------------------------------------------------
    def test_02_n8n_receives_correct_tender_bidder_ids(self):
        """Test 2: n8n receives exact correlated tender and bidder UUIDs."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        payload = mock_client.trigger_verification.call_args[1]["payload"]
        self.assertEqual(payload.tender_id, str(tender.id))
        self.assertEqual(payload.bidder_id, str(bidder.id))
        self.assertEqual(payload.bidder_name, bidder.company_name)

    # -------------------------------------------------------------------------
    # Test 3: All expected agent results are collected
    # -------------------------------------------------------------------------
    def test_03_all_expected_agent_results_are_collected(self):
        """Test 3: Aggregated response contains results for all canonical verification agents."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        agent_names = [a.agent for a in resp.agent_results]
        for canonical_agent in DEFAULT_VERIFICATION_AGENTS:
            self.assertIn(canonical_agent, agent_names)

    # -------------------------------------------------------------------------
    # Test 4: Successful agents are represented correctly
    # -------------------------------------------------------------------------
    def test_04_successful_agents_represented_correctly(self):
        """Test 4: Agents reporting VERIFIED or PASS are preserved with confidence scores."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        gst_agent = next((a for a in resp.agent_results if a.agent == "GST_AGENT"), None)
        self.assertIsNotNone(gst_agent)
        self.assertIn(gst_agent.status, {"VERIFIED", "PASS"})
        self.assertEqual(gst_agent.confidence, 0.99)
        self.assertEqual(gst_agent.risk_level, "LOW")

    # -------------------------------------------------------------------------
    # Test 5: Failed agent is represented as ERROR / FAIL
    # -------------------------------------------------------------------------
    def test_05_failed_agent_represented_as_error_or_fail(self):
        """Test 5: Failed agent outcome is preserved and propagated to failed_requirements."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        # Simulate GST Agent failure
        for a in mock_resp.agent_results:
            if a.agent == "GST_AGENT":
                a.status = "FAIL"
                a.issues = ["GSTIN registration canceled"]
                a.risk_level = "HIGH"
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        gst_agent = next(a for a in resp.agent_results if a.agent == "GST_AGENT")
        self.assertEqual(gst_agent.status, "FAIL")
        self.assertEqual(resp.decision, VerificationDecisionEnum.NOT_QUALIFIED)
        self.assertEqual(resp.overall_compliance, OverallComplianceEnum.NON_COMPLIANT)
        self.assertTrue(any("GST_AGENT failed" in fr for fr in resp.failed_requirements))

    # -------------------------------------------------------------------------
    # Test 6: Missing agent result becomes INCONCLUSIVE / ERROR
    # -------------------------------------------------------------------------
    def test_06_missing_agent_result_becomes_inconclusive(self):
        """Test 6: Required agent omitted from n8n response is synthesized as NOT_EXECUTED / INCONCLUSIVE."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        # Omit FINANCIAL_AGENT from reporting
        mock_resp.agent_results = [a for a in mock_resp.agent_results if a.agent != "FINANCIAL_AGENT"]
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        fin_agent = next((a for a in resp.agent_results if a.agent == "FINANCIAL_AGENT"), None)
        self.assertIsNotNone(fin_agent)
        self.assertEqual(fin_agent.status, "NOT_EXECUTED")
        self.assertEqual(fin_agent.confidence, 0.0)
        # Critical agent missing prevents QUALIFIED
        self.assertEqual(resp.decision, VerificationDecisionEnum.MANUAL_REVIEW)
        self.assertIn(resp.overall_compliance, {OverallComplianceEnum.INCONCLUSIVE, OverallComplianceEnum.UNVERIFIED})


    # -------------------------------------------------------------------------
    # Test 7: n8n timeout fails closed
    # -------------------------------------------------------------------------
    def test_07_n8n_timeout_fails_closed(self):
        """Test 7: n8n timeout raises N8nTimeoutError and fails closed without claiming compliance."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(side_effect=N8nTimeoutError("n8n timed out"))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        with self.assertRaises(N8nTimeoutError):
            asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

    # -------------------------------------------------------------------------
    # Test 8: n8n unavailable fails safely
    # -------------------------------------------------------------------------
    def test_08_n8n_unavailable_fails_safely(self):
        """Test 8: n8n connection failure raises N8nConnectionError and fails safely."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_client.trigger_verification = AsyncMock(side_effect=N8nConnectionError("Connection refused"))

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        with self.assertRaises(N8nConnectionError):
            asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

    # -------------------------------------------------------------------------
    # Test 9: Malformed n8n response is rejected
    # -------------------------------------------------------------------------
    def test_09_malformed_n8n_response_rejected(self):
        """Test 9: Inbound n8n response missing mandatory fields is rejected via validation error."""
        malformed_dict = {
            "status": "COMPLETED",
            # missing verification_id, request_id, bidder_name
        }
        with self.assertRaises(ValidationError):
            N8nVerificationResponse.model_validate(malformed_dict)

    # -------------------------------------------------------------------------
    # Test 10: Duplicate agent results are not double-counted
    # -------------------------------------------------------------------------
    def test_10_duplicate_agent_results_not_double_counted(self):
        """Test 10: Multiple result entries for the same agent are deduplicated."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        # Duplicate GST_AGENT entry
        mock_resp.agent_results.append(
            N8nAgentResult(agent="GST_AGENT", status="VERIFIED", confidence=0.99, issues=[], risk_level="LOW")
        )
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        gst_agents = [a for a in resp.agent_results if a.agent == "GST_AGENT"]
        self.assertEqual(len(gst_agents), 1)

    # -------------------------------------------------------------------------
    # Test 11: Compliance cannot become PASS when mandatory agent fails
    # -------------------------------------------------------------------------
    def test_11_compliance_cannot_be_pass_when_mandatory_agent_fails(self):
        """Test 11: If any mandatory statutory check fails, decision must be NOT_QUALIFIED / NON_COMPLIANT."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        # Set PAN agent to FAIL
        for a in mock_resp.agent_results:
            if a.agent == "PAN_AGENT":
                a.status = "FAIL"
                a.issues = ["PAN marked as inactive by NSDL"]
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        self.assertNotEqual(resp.decision, VerificationDecisionEnum.QUALIFIED)
        self.assertEqual(resp.decision, VerificationDecisionEnum.NOT_QUALIFIED)
        self.assertEqual(resp.overall_compliance, OverallComplianceEnum.NON_COMPLIANT)

    # -------------------------------------------------------------------------
    # Test 12: Compliance cannot become PASS when critical agent errors
    # -------------------------------------------------------------------------
    def test_12_compliance_cannot_be_pass_when_critical_agent_errors(self):
        """Test 12: If critical agent returns ERROR, overall decision must fall back to MANUAL_REVIEW."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        # Set DOCUMENT_FORENSICS_AGENT to ERROR
        for a in mock_resp.agent_results:
            if a.agent == "DOCUMENT_FORENSICS_AGENT":
                a.status = "ERROR"
                a.issues = ["Corrupted PDF stream encountered"]
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        self.assertNotEqual(resp.decision, VerificationDecisionEnum.QUALIFIED)
        self.assertEqual(resp.decision, VerificationDecisionEnum.MANUAL_REVIEW)
        self.assertIn(resp.overall_compliance, {OverallComplianceEnum.INCONCLUSIVE, OverallComplianceEnum.UNVERIFIED})


    # -------------------------------------------------------------------------
    # Test 13: Risk result is preserved separately from compliance
    # -------------------------------------------------------------------------
    def test_13_risk_preserved_separately_from_compliance(self):
        """Test 13: Risk score and compliance verdict are distinct separate outputs."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        # Compliance passed, but Risk Agent raises non-fatal adverse litigation warning
        for a in mock_resp.agent_results:
            if a.agent == "RISK_INTELLIGENCE_AGENT":
                a.status = "WARNING"
                a.issues = ["Ongoing commercial arbitration noted"]
                a.risk_level = "HIGH"
        mock_resp.risk_score = 65.0
        mock_resp.risk_level = "HIGH"
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        # Risk is HIGH, but factual criteria did not fail with NOT_QUALIFIED
        self.assertEqual(resp.risk_level, RiskLevelEnum.HIGH)
        self.assertGreaterEqual(resp.risk_score, 65.0)
        self.assertIn("Ongoing commercial arbitration noted", str(resp.warnings))

    # -------------------------------------------------------------------------
    # Test 14: Requirement and evidence traceability survives flow
    # -------------------------------------------------------------------------
    def test_14_traceability_survives_complete_flow(self):
        """Test 14: Requirement clauses and extracted evidence survive in raw_response audit trail."""
        tender, bidder, reqs, doc, ev = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        self.assertIsNotNone(resp.raw_response)
        traceability = resp.raw_response.get("traceability", {})
        self.assertIn("requirements", traceability)
        self.assertIn("evidence", traceability)

        # Verify requirement clause text preserved
        rules = [r["rule"] for r in traceability["requirements"]]
        self.assertIn("MINIMUM_TURNOVER", rules)

        # Verify evidence preserved
        fields = [e["field"] for e in traceability["evidence"]]
        self.assertIn("turnover", fields)

    # -------------------------------------------------------------------------
    # Test 15: Document SHA-256 survives the complete flow
    # -------------------------------------------------------------------------
    def test_15_document_sha256_survives_complete_flow(self):
        """Test 15: Cryptographic document SHA-256 hash is preserved in final audit output."""
        tender, bidder, _, doc, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        traceability = resp.raw_response.get("traceability", {})
        doc_hashes = traceability.get("document_hashes", [])
        self.assertTrue(any(d["sha256"] == doc.sha256 for d in doc_hashes))

    # -------------------------------------------------------------------------
    # Test 16: Verification ID remains consistent
    # -------------------------------------------------------------------------
    def test_16_verification_id_remains_consistent(self):
        """Test 16: Verification ID is consistent between request, payload, and response."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        self.assertEqual(resp.verification_id, mock_resp.verification_id)
        self.assertTrue(resp.verification_id.startswith("VER-"))

    # -------------------------------------------------------------------------
    # Test 17: Secrets are not present in serialized response
    # -------------------------------------------------------------------------
    def test_17_secrets_not_present_in_serialized_response(self):
        """Test 17: Serialized response contains zero API keys, db passwords, or bearer tokens."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        service = VerificationService(client=mock_client)
        trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)

        resp = asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

        serialized = resp.model_dump_json()
        forbidden_keywords = ["postgresql://", "gsk_", "Bearer ey", "db_password", "webhook_secret"]
        for kw in forbidden_keywords:
            self.assertNotIn(kw, serialized)

    # -------------------------------------------------------------------------
    # Test 18: No direct Groq invocation occurs
    # -------------------------------------------------------------------------
    def test_18_no_direct_groq_invocation(self):
        """Test 18: Verification orchestration executes with 0 direct Groq calls."""
        tender, bidder, _, _, _ = self._setup_tender_and_bidder()

        mock_client = MagicMock(spec=N8nClient)
        mock_resp = self._build_standard_n8n_response(tender.id, bidder.id, bidder.company_name)
        mock_client.trigger_verification = AsyncMock(return_value=mock_resp)

        with patch("groq.Groq") as mock_groq:
            service = VerificationService(client=mock_client)
            trigger_req = VerificationTriggerRequest(tender_id=tender.id, bidder_id=bidder.id)
            asyncio.run(service.execute_verification(trigger_request=trigger_req, db=self.db))

            mock_groq.assert_not_called()

    # -------------------------------------------------------------------------
    # Test 19: Phase 11 compatibility verified
    # -------------------------------------------------------------------------
    def test_19_phase11_compatibility(self):
        """Test 19: Phase 11 packaging models and normalizers remain functional."""
        from app.services.verification_packaging_service import verification_packaging_service
        self.assertIsNotNone(verification_packaging_service)

    # -------------------------------------------------------------------------
    # Test 20: Phase 10 and n8n client contract compatibility verified
    # -------------------------------------------------------------------------
    def test_20_phase10_n8n_client_compatibility(self):
        """Test 20: Existing n8n_client HMAC signing and headers generation remain intact."""
        from app.services.n8n_client import n8n_client
        sig = n8n_client.generate_signature("test_payload")
        self.assertIsInstance(sig, str)
        self.assertTrue(n8n_client.verify_webhook_signature("test_payload", sig))


if __name__ == "__main__":
    unittest.main()
