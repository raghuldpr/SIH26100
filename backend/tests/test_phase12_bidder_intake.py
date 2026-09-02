"""
SIH-26100 — Phase 12.3 Test Suite
tests/test_phase12_bidder_intake.py

Verifies:
Tender
  ↓
Create / Register Bidder
  ↓
Associate Bidder with Tender
  ↓
Upload Bidder Documents
  ↓
Validate + SHA-256
  ↓
Store Document
  ↓
Classify Document
  ↓
Extract Evidence (Deterministic first)
  ↓
Persist Structured Evidence (Idempotent)
"""
import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import uuid
from uuid import UUID

import fitz

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.exceptions import BadRequestException
from app.core.validation import calculate_sha256
from app.crud.crud_bidder import crud_bidder
from app.crud.crud_document import crud_document
from app.crud.crud_tender import crud_tender
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel
from app.models.document import Document
from app.models.enums import BidderStatus, DocumentStatus, DocumentType, ProcessingStatus, TenderStatus
from app.models.tender import Tender
from app.schemas.ai_gateway import AmbiguousClauseRequest
from app.schemas.bidder import BidderCreate
from app.services.ai_gateway import AIGateway
from app.services.bidder_intake_service import BidderIntakeService, bidder_intake_service
from app.services.compliance_service import compliance_service


def make_pdf(text: str) -> bytes:
    """Helper to generate valid in-memory PDF bytes with text."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_mock_groq_completion(content_dict: dict, prompt_tokens: int = 100, completion_tokens: int = 50):
    """Helper to generate a mock Groq ChatCompletion object."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(content_dict)

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = prompt_tokens + completion_tokens

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage = mock_usage
    return mock_completion


class TestPhase12BidderIntake(unittest.TestCase):
    """
    Phase 12.3 Integration Test Suite.
    Verifies all 10 required steps of the bidder creation, association,
    document upload, validation, deterministic extraction, and structured evidence flow.
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
                # Delete associated evidence
                evidences = self.db.query(BidderEvidenceModel).filter(BidderEvidenceModel.bidder_id == bidder_id).all()
                for ev in evidences:
                    self.db.delete(ev)
                # Delete tender_bidders links
                assignments = self.db.query(TenderBidder).filter(TenderBidder.bidder_id == bidder_id).all()
                for a in assignments:
                    self.db.delete(a)
                bidder = crud_bidder.get_by_id(self.db, bidder_id)
                if bidder:
                    self.db.delete(bidder)
            for tender_id in self.created_tender_ids:
                tender = crud_tender.get_by_id(self.db, tender_id)
                if tender:
                    self.db.delete(tender)
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def _create_tender(self, title: str = "Tender Cloud Infrastructure 2026") -> Tender:
        tender_number = f"GEM/2026/B/P12_{uuid.uuid4().hex[:8].upper()}"
        tender = Tender(
            id=uuid.uuid4(),
            tender_number=tender_number,
            title=title,
            description="Procurement of Cloud Compute and High-Performance Storage",
            organization="Ministry of Electronics & IT",
            department="Cloud Infrastructure Division",
            category="IT Services",
            status=TenderStatus.OPEN,
        )
        self.db.add(tender)
        self.db.commit()
        self.db.refresh(tender)
        self.created_tender_ids.append(tender.id)
        return tender

    def _create_bidder_data(self, company_suffix: str = "1") -> BidderCreate:
        return BidderCreate(
            company_name=f"Alpha Infotech Solutions {company_suffix}",
            registration_number=f"U72200DL2026PTC{uuid.uuid4().hex[:6].upper()}",
            gst_number="27AAACS1234A1Z1",
            pan_number="AAACS1234A",
            udyam_number="UDYAM-MH-12-0012345",
            contact_person="Ramesh Sharma",
            email="ramesh@alphainfotech.com",
            phone="+91-9876543210",
            address="Level 4, IT Park, Pune, Maharashtra",
            status=BidderStatus.ACTIVE,
        )

    # -------------------------------------------------------------------------
    # Test 1 — Bidder creation and tender association
    # -------------------------------------------------------------------------
    def test_01_bidder_creation_and_tender_association(self):
        """Test 1: Verify a bidder can be created and associated with a specific tender."""
        tender = self._create_tender("Test 1 Tender")
        bidder_data = self._create_bidder_data("Test 1")

        bidder, assignment = bidder_intake_service.create_tender_bidder(
            db=self.db,
            tender_id=tender.id,
            bidder_in=bidder_data,
        )
        self.created_bidder_ids.append(bidder.id)

        self.assertIsNotNone(bidder.id)
        self.assertEqual(bidder.company_name, bidder_data.company_name)
        self.assertEqual(assignment.tender_id, tender.id)
        self.assertEqual(assignment.bidder_id, bidder.id)

        # Verify queryable through tender bidders
        bidders_list, count = crud_bidder.get_tender_bidders(self.db, tender_id=tender.id)
        self.assertEqual(count, 1)
        self.assertEqual(bidders_list[0].bidder_id, bidder.id)

    # -------------------------------------------------------------------------
    # Test 2 — Bidder isolation
    # -------------------------------------------------------------------------
    def test_02_bidder_isolation(self):
        """Test 2: Two bidders belonging to the same tender remain completely isolated."""
        tender = self._create_tender("Isolation Tender")
        b1, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("Bidder A"))
        b2, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("Bidder B"))
        self.created_bidder_ids.extend([b1.id, b2.id])

        # Upload PAN document for Bidder A
        pan_pdf = make_pdf("GOVERNMENT OF INDIA\nINCOME TAX DEPARTMENT\nPermanent Account Number: AAACS1111A\nALPHA INFOTECH A")
        doc_a, _ = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=b1.id,
            file_bytes=pan_pdf,
            filename="bidder_a_pan.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.PAN,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc_a.id)

        # Upload GST document for Bidder B
        gst_pdf = make_pdf("GOVERNMENT OF INDIA\nGST CERTIFICATE\nGSTIN: 27BBBCS2222B1Z2\nLegal Name: ALPHA INFOTECH B")
        doc_b, _ = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=b2.id,
            file_bytes=gst_pdf,
            filename="bidder_b_gst.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.GST,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc_b.id)

        # Verify Bidder A's evidence
        ev_a = bidder_intake_service.get_bidder_evidence(self.db, bidder_id=b1.id)
        ev_b = bidder_intake_service.get_bidder_evidence(self.db, bidder_id=b2.id)

        self.assertTrue(any(e.field == "pan" for e in ev_a))
        self.assertFalse(any(e.field == "gstin" for e in ev_a), "Bidder B's GST evidence leaked to Bidder A!")

        self.assertTrue(any(e.field == "gstin" for e in ev_b))
        self.assertFalse(any(e.field == "pan" for e in ev_b), "Bidder A's PAN evidence leaked to Bidder B!")

    # -------------------------------------------------------------------------
    # Test 3 — Document association
    # -------------------------------------------------------------------------
    def test_03_document_association(self):
        """Test 3: A bidder document is correctly associated with tender_id, bidder_id, and document_id."""
        tender = self._create_tender("Doc Association Tender")
        bidder, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("Doc Assoc"))
        self.created_bidder_ids.append(bidder.id)

        pdf_bytes = make_pdf("UDYAM REGISTRATION CERTIFICATE\nUDYAM-MH-01-0099887\nENTERPRISE NAME: DOC ASSOC CORP")
        doc, _ = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=pdf_bytes,
            filename="udyam_registration.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.UDYAM,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc.id)

        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.tender_id, tender.id)
        self.assertEqual(doc.bidder_id, bidder.id)
        self.assertEqual(doc.document_type, DocumentType.UDYAM)
        self.assertEqual(doc.processing_status, ProcessingStatus.PROCESSED)

    # -------------------------------------------------------------------------
    # Test 4 — Validation failure
    # -------------------------------------------------------------------------
    def test_04_validation_rejects_corrupted_files(self):
        """Test 4: Unsupported / corrupted files are rejected using existing validation system."""
        from unittest.mock import AsyncMock
        fake_upload = MagicMock()
        fake_upload.filename = "malicious_script.exe"
        fake_upload.content_type = "application/x-msdownload"
        fake_upload.read = AsyncMock(return_value=b"MZ\x90\x00not a valid pdf or docx")
        fake_upload.seek = AsyncMock()

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with self.assertRaises(BadRequestException):
                loop.run_until_complete(
                    bidder_intake_service.intake_bidder_document(
                        db=self.db,
                        bidder_id=uuid.uuid4(),
                        file=fake_upload,
                    )
                )
        finally:
            loop.close()


    # -------------------------------------------------------------------------
    # Test 5 — Deterministic SHA-256 calculation
    # -------------------------------------------------------------------------
    def test_05_sha256_deterministic_digest(self):
        """Test 5: Uploaded bidder documents receive a deterministic SHA-256 digest."""
        tender = self._create_tender("SHA256 Test Tender")
        bidder, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("SHA256"))
        self.created_bidder_ids.append(bidder.id)

        pdf_bytes = make_pdf("GST CERTIFICATE\nGSTIN: 07AAACH1234H1Z5\nLegal Name: HASH TEST CORP")
        expected_sha = calculate_sha256(pdf_bytes)

        doc, _ = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=pdf_bytes,
            filename="gst_certificate_sha.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.GST,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc.id)

        self.assertEqual(doc.sha256, expected_sha)

    # -------------------------------------------------------------------------
    # Test 6 — Classification reaches existing classification pipeline
    # -------------------------------------------------------------------------
    def test_06_classification_pipeline(self):
        """Test 6: A representative PAN/GST/financial/experience document reaches classification."""
        tender = self._create_tender("Classification Tender")
        bidder, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("Classify"))
        self.created_bidder_ids.append(bidder.id)

        # Upload as OTHER, classifier should detect GST_CERTIFICATE / GST
        gst_pdf = make_pdf("GOVERNMENT OF INDIA\nGOODS AND SERVICES TAX\nREGISTRATION CERTIFICATE\nGSTIN: 06AAACH5678H1Z8\nTrade Name: CLASS CORP")
        doc, _ = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=gst_pdf,
            filename="gst_upload.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.OTHER,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc.id)

        self.assertEqual(doc.processing_status, ProcessingStatus.PROCESSED)
        self.assertEqual(doc.document_type, DocumentType.GST)
        self.assertIsNotNone(doc.extracted_data)
        self.assertIn("classification", doc.extracted_data)

    # -------------------------------------------------------------------------
    # Test 7 — Structured evidence is persisted
    # -------------------------------------------------------------------------
    def test_07_structured_evidence_persisted(self):
        """Test 7: Structured evidence is persisted using the existing BidderEvidenceModel."""
        tender = self._create_tender("Evidence Persist Tender")
        bidder, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("Evidence"))
        self.created_bidder_ids.append(bidder.id)

        fin_pdf = make_pdf(
            "INDEPENDENT AUDITOR'S REPORT\n"
            "To the Members of Alpha Infotech Solutions\n"
            "UDIN: 24045678ABCD123456\n"
            "Financial Year: 2023-24\n"
            "Annual Turnover: Rs. 5 Crore\n"
        )
        doc, evidences = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=fin_pdf,
            filename="audited_financial_report_2024.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.FINANCIAL_STATEMENT,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc.id)

        self.assertGreaterEqual(len(evidences), 1)

        # Query persisted evidence from DB
        db_ev = compliance_service.get_bidder_evidence(self.db, bidder.id, "turnover")
        self.assertIsNotNone(db_ev)
        self.assertEqual(db_ev.bidder_id, bidder.id)
        self.assertIn("50000000", str(db_ev.value))

    # -------------------------------------------------------------------------
    # Test 8 — Traceability (document, page, source text, confidence)
    # -------------------------------------------------------------------------
    def test_08_evidence_traceability(self):
        """Test 8: Evidence retains document, page, source text, and confidence information."""
        tender = self._create_tender("Traceability Tender")
        bidder, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("Trace"))
        self.created_bidder_ids.append(bidder.id)

        pan_pdf = make_pdf("INCOME TAX DEPARTMENT\nPermanent Account Number: AAACA9999A\nName: TRACE CORP")
        doc, evidences = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=pan_pdf,
            filename="pan_card_traceable.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.PAN,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc.id)

        pan_ev = compliance_service.get_bidder_evidence(self.db, bidder.id, "pan")
        self.assertIsNotNone(pan_ev)
        self.assertIsInstance(pan_ev.value, dict)
        self.assertEqual(pan_ev.value.get("pan"), "AAACA9999A")
        self.assertEqual(pan_ev.value.get("document_id"), str(doc.id))
        self.assertEqual(pan_ev.value.get("document_hash"), doc.sha256)
        self.assertEqual(pan_ev.value.get("page"), 1)
        self.assertIn("AAACA9999A", pan_ev.value.get("source_text", ""))
        self.assertEqual(pan_ev.confidence, 0.99)
        self.assertEqual(pan_ev.value.get("extraction_method"), "DETERMINISTIC")

    # -------------------------------------------------------------------------
    # Test 9 — Repeated uploads / duplicate handling (Idempotency)
    # -------------------------------------------------------------------------
    def test_09_duplicate_document_handling_idempotent(self):
        """Test 9: Repeated identical uploads do not create uncontrolled duplicate evidence."""
        tender = self._create_tender("Deduplication Tender")
        bidder, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("Dedup"))
        self.created_bidder_ids.append(bidder.id)

        pdf_bytes = make_pdf("GST CERTIFICATE\nGSTIN: 09AAACB9876B1Z3\nTrade Name: DEDUP CORP")

        # First upload and intake
        doc1, ev1 = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=pdf_bytes,
            filename="gst_cert.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.GST,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc1.id)

        count_ev1 = len(self.db.query(BidderEvidenceModel).filter(BidderEvidenceModel.bidder_id == bidder.id).all())
        self.assertGreaterEqual(count_ev1, 1)

        # Second upload with exact same content & SHA-256
        doc2, ev2 = bidder_intake_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=pdf_bytes,
            filename="gst_cert.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.GST,
            tender_id=tender.id,
            process_document=True,
        )

        # Deduplication check: should return the existing document record
        self.assertEqual(doc1.id, doc2.id)

        # Evidence count must remain identical (no runaway duplicates)
        count_ev2 = len(self.db.query(BidderEvidenceModel).filter(BidderEvidenceModel.bidder_id == bidder.id).all())
        self.assertEqual(count_ev1, count_ev2, "Repeated identical upload created duplicate evidence rows!")

    # -------------------------------------------------------------------------
    # Test 10 — AI boundary & zero live Groq calls
    # -------------------------------------------------------------------------
    def test_10_ai_boundary_deterministic_bypasses_groq(self):
        """
        Test 10: Deterministic evidence extraction does not call Groq.
        Any semantic fallback must use the existing AIGateway abstraction.
        Mock Groq client. Zero live Groq calls.
        """
        mock_groq_client = MagicMock()
        mock_gateway = AIGateway(api_key="mock_groq_key", client=mock_groq_client)

        tender = self._create_tender("AI Boundary Tender")
        bidder, _ = bidder_intake_service.create_tender_bidder(self.db, tender.id, self._create_bidder_data("AIBoundary"))
        self.created_bidder_ids.append(bidder.id)

        custom_service = BidderIntakeService(ai_gw=mock_gateway)

        # 1. Deterministic PAN extraction
        pdf_bytes = make_pdf("INCOME TAX DEPARTMENT\nPermanent Account Number: AAACG1234G\nNAME: AI BOUNDARY CORP")
        doc, _ = custom_service.intake_bidder_document_content(
            db=self.db,
            bidder_id=bidder.id,
            file_bytes=pdf_bytes,
            filename="pan_deterministic.pdf",
            mime_type="application/pdf",
            document_type=DocumentType.PAN,
            tender_id=tender.id,
            process_document=True,
        )
        self.created_doc_ids.append(doc.id)

        # Assert Groq was NEVER called for deterministic extraction
        mock_groq_client.chat.completions.create.assert_not_called()

        # 2. Semantic fallback escalation via existing AIGateway
        mock_interpretation = {
            "requirement_type": "EXPERIENCE",
            "rule": "SIMILAR_WORK_EXPERIENCE",
            "description": "Bidder delivered cloud infrastructure projects with satisfactory performance",
            "parameters": {"minimum_projects": 2, "project_type": "cloud infrastructure"},
            "is_mandatory": True,
            "is_interpretable": True,
            "interpretation_confidence": 0.93,
            "rationale": "Extracted project experience from ambiguous qualitative testimonial",
        }
        mock_groq_client.chat.completions.create.return_value = create_mock_groq_completion(mock_interpretation)

        sem_req = AmbiguousClauseRequest(
            clause_text="The bidder has satisfactorily delivered at least 2 cloud infrastructure implementations in state projects.",
            reason_for_escalation="Qualitative performance testimonial requiring semantic interpretation",
            source_page=1,
            source_section="Work Experience",
        )
        ai_resp = mock_gateway.analyze_ambiguous_clause(sem_req)

        self.assertTrue(ai_resp.success)
        self.assertEqual(ai_resp.interpretation.rule, "SIMILAR_WORK_EXPERIENCE")
        mock_groq_client.chat.completions.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
