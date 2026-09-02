"""
SIH-26100 — Phase 12.2 Test Suite
tests/test_phase12_tender_flow.py

End-to-End Verification of the Tender-Side Pipeline:
Create Tender
    ↓
Upload / Associate Tender Document
    ↓
Document Processing & Layout Extraction
    ↓
Tender Section Detection
    ↓
Deterministic Requirement Extraction
    ↓
Selective Groq Fallback for Ambiguous Clauses (Mocked)
    ↓
Canonical Verification Packaging
    ↓
Persist Tender Requirements (Idempotent)
    ↓
Tender Compliance Profile Generation
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import uuid

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus, RequirementType, TenderStatus
from app.models.document import Document
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.schemas.ai_gateway import AmbiguousClauseRequest
from app.schemas.packaged_output import CanonicalDocumentOutput
from app.schemas.processing import ExtractionResult, PageExtractionResult
from app.schemas.tender_clause import ClauseCandidate
from app.schemas.tender_intelligence import TenderAnalysisRequest, TenderComplianceProfileResponse
from app.schemas.tender_requirement_normalizer import NormalizationStatus, NormalizedRequirement
from app.services.ai_gateway import AIGateway
from app.crud.crud_tender import crud_tender
from app.services.document_processor import document_processor
from app.services.tender_clause_extractor import tender_clause_extractor, extract_clauses_from_text
from app.services.tender_intelligence_service import TenderIntelligenceService, tender_intelligence_service
from app.services.tender_requirement_normalizer import normalize_clause, tender_requirement_normalizer
from app.services.tender_section_detector import tender_section_detector
from app.services.verification_packaging_service import package_verification_output
from app.crud.crud_document import crud_document
from app.crud.crud_tender_requirement import crud_tender_requirement


def create_mock_groq_completion(content_dict: dict, prompt_tokens: int = 150, completion_tokens: int = 60):
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


class TestPhase12TenderFlow(unittest.TestCase):
    """
    Phase 12.2 Integration Test Suite.
    Verifies all 8 required steps of the tender intelligence and compliance profile pipeline.
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    def setUp(self):
        self.db = SessionLocal()
        self.created_tender_ids = []
        self.created_doc_ids = []

    def tearDown(self):
        # Clean up created database records
        try:
            for doc_id in self.created_doc_ids:
                doc = crud_document.get_by_id(self.db, doc_id)
                if doc:
                    self.db.delete(doc)
            for tender_id in self.created_tender_ids:
                crud_tender_requirement.delete_by_tender(self.db, tender_id)
                tender = crud_tender.get_by_id(self.db, tender_id)
                if tender:
                    self.db.delete(tender)
            self.db.commit()
        except Exception:
            self.db.rollback()
        finally:
            self.db.close()

    def _create_test_tender(self, title: str = "Procurement of High-Capacity Server Hardware") -> Tender:
        """Helper to create a test tender record."""
        tender_number = f"GEM/2026/B/P12_{uuid.uuid4().hex[:8].upper()}"
        tender = Tender(
            id=uuid.uuid4(),
            tender_number=tender_number,
            title=title,
            description="GeM standard procurement for servers, storage, and networking equipment.",
            organization="National Informatics Centre",
            department="Cloud Services Division",
            category="Hardware",
            status=TenderStatus.OPEN,
        )
        self.db.add(tender)
        self.db.commit()
        self.db.refresh(tender)
        self.created_tender_ids.append(tender.id)
        return tender

    # -------------------------------------------------------------------------
    # Test 1: Tender can be created
    # -------------------------------------------------------------------------
    def test_01_tender_can_be_created(self):
        """Test 1: Verify that a tender record can be successfully created and queried."""
        tender = self._create_test_tender(title="Tender Creation Test 01")
        self.assertIsNotNone(tender.id)
        self.assertTrue(str(tender.tender_number).startswith("GEM/2026/B/"))

        fetched = crud_tender.get_by_id(self.db, tender.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.title, "Tender Creation Test 01")
        self.assertEqual(fetched.status, TenderStatus.OPEN)

    # -------------------------------------------------------------------------
    # Test 2: Tender document can be associated with the tender
    # -------------------------------------------------------------------------
    def test_02_tender_document_association(self):
        """Test 2: Verify that a document can be created and associated with a tender."""
        tender = self._create_test_tender(title="Document Association Test 02")
        doc_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        doc = crud_document.create_metadata(
            db=self.db,
            original_filename="gem_bid_document_servers_2026.pdf",
            storage_path=f"tenders/{tender.id}/gem_bid_document_servers_2026.pdf",
            document_type=DocumentType.TENDER_PDF,
            mime_type="application/pdf",
            file_size=1048576,
            sha256=doc_hash,
            tender_id=tender.id,
            status=DocumentStatus.UPLOADED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )
        self.created_doc_ids.append(doc.id)

        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.tender_id, tender.id)
        self.assertEqual(doc.sha256, doc_hash)

        # Retrieve documents associated with the tender
        docs, count = crud_document.list_tender_documents(self.db, tender.id)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(any(d.id == doc.id for d in docs))

    # -------------------------------------------------------------------------
    # Test 3: A deterministic tender requirement is extracted
    # -------------------------------------------------------------------------
    def test_03_deterministic_tender_requirement_extraction(self):
        """
        Test 3: Verify deterministic extraction of average annual turnover.
        Clause: 'Minimum average annual turnover of Rs. 5 Crore'
        Expected structured result:
        minimum = 50000000, currency = INR, period = 3, operator = >=
        """
        raw_clause = "The minimum average annual turnover of the bidder shall not be less than Rs. 5 Crore across the last 3 financial years."
        res = extract_clauses_from_text(raw_clause, page=3)
        self.assertGreaterEqual(res.total_candidates, 1)

        norm = normalize_clause(res.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.FINANCIAL.value)
        self.assertEqual(norm.rule, "AVERAGE_TURNOVER")
        self.assertEqual(norm.parameters.get("minimum"), 50000000.0)
        self.assertEqual(norm.parameters.get("currency"), "INR")
        self.assertEqual(norm.parameters.get("period"), 3)
        self.assertEqual(norm.parameters.get("operator"), ">=")
        self.assertTrue(norm.mandatory)
        self.assertEqual(norm.resolution_method, "DETERMINISTIC")

    # -------------------------------------------------------------------------
    # Test 4: Ambiguous clause is routed through existing AI Gateway abstraction
    # -------------------------------------------------------------------------
    def test_04_ambiguous_clause_routed_through_ai_gateway(self):
        """
        Test 4: Verify that an ambiguous clause is routed through AIGateway with a mocked Groq client.
        Never makes a real Groq call.
        """
        mock_groq_client = MagicMock()
        mock_interpretation = {
            "requirement_type": "FINANCIAL",
            "rule": "AVERAGE_TURNOVER",
            "description": "Bidder should maintain average financial turnover of 20000000 INR over past 3 years",
            "parameters": {
                "minimum": 20000000,
                "currency": "INR",
                "period": 3,
                "period_unit": "YEARS",
                "operator": ">=",
            },
            "is_mandatory": True,
            "is_interpretable": True,
            "interpretation_confidence": 0.94,
            "rationale": "Standard turnover qualification extracted from ambiguous formulation",
        }
        mock_groq_client.chat.completions.create.return_value = create_mock_groq_completion(mock_interpretation)

        gateway = AIGateway(api_key="mock_groq_api_key", client=mock_groq_client)

        req = AmbiguousClauseRequest(
            clause_text="The bidder's financial standing should reflect adequate turnover averaging roughly Rs. 2 Crore over previous three years.",
            reason_for_escalation="Ambiguous qualitative wording ('roughly', 'adequate turnover')",
            source_page=4,
            source_section="Financial Evaluation",
        )

        response = gateway.analyze_ambiguous_clause(req)
        self.assertTrue(response.success)
        self.assertIsNotNone(response.interpretation)
        self.assertEqual(response.interpretation.rule, "AVERAGE_TURNOVER")
        self.assertEqual(response.interpretation.parameters.get("minimum"), 20000000)
        mock_groq_client.chat.completions.create.assert_called_once()

    # -------------------------------------------------------------------------
    # Test 5: An unresolved ambiguous clause remains AMBIGUOUS with confidence=null
    # -------------------------------------------------------------------------
    def test_05_unresolved_ambiguous_clause_remains_ambiguous(self):
        """
        Test 5: Verify that a contradictory or unresolvable ambiguous clause remains AMBIGUOUS with confidence = null.
        """
        ambiguous_text = "Bidder should possess sound financial standing and credit rating from RBI approved agencies."
        req = normalize_clause(ambiguous_text, page=5, section="Financial Evaluation")
        self.assertEqual(req.status, NormalizationStatus.AMBIGUOUS)
        self.assertTrue(req.requires_semantic_interpretation)
        self.assertIsNone(req.confidence)

        # Mock AI gateway to simulate refusal / network timeout
        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create.side_effect = Exception("Groq API Timeout / Refusal")
        failing_gateway = AIGateway(api_key="mock_key", client=mock_groq_client)

        from app.services.tender_requirement_normalizer import resolve_ambiguous_requirements
        resolved = resolve_ambiguous_requirements([req], gateway=failing_gateway)

        # Unresolved clause must remain AMBIGUOUS with confidence = null
        self.assertEqual(resolved[0].status, NormalizationStatus.AMBIGUOUS)
        self.assertTrue(resolved[0].requires_semantic_interpretation)
        self.assertIsNone(resolved[0].confidence)



    # -------------------------------------------------------------------------
    # Test 6: Requirement provenance is preserved (document, page, section, text)
    # -------------------------------------------------------------------------
    def test_06_requirement_provenance_preservation(self):
        """
        Test 6: Verify that requirement provenance (page, section, source text) is fully preserved in DB.
        """
        tender = self._create_test_tender(title="Provenance Test 06")

        pages = [
            {
                "page_number": 7,
                "section": "Financial Criteria",
                "text": "SECTION 3: FINANCIAL CRITERIA\nThe bidder must have a minimum turnover of Rs. 3 Crore in the preceding financial year.",
            }
        ]

        batch = tender_intelligence_service.process_tender_pages(
            pages=pages,
            tender_id=tender.id,
            db=self.db,
            persist=True,
        )

        self.assertGreaterEqual(batch.normalized_count, 1)

        # Query persisted requirement from PostgreSQL
        persisted = crud_tender_requirement.get_by_tender(self.db, tender.id)
        self.assertGreaterEqual(len(persisted), 1)

        req = persisted[0]
        self.assertEqual(req.source_page, 7)
        self.assertIn("Financial", req.source_section)
        self.assertIn("3 Crore", req.source_text)
        self.assertGreaterEqual(req.confidence, 0.90)

    # -------------------------------------------------------------------------
    # Test 7: Repeated processing does not create uncontrolled duplicate requirements
    # -------------------------------------------------------------------------
    def test_07_repeated_processing_idempotency(self):
        """
        Test 7: Verify idempotency: re-running processing on the same tender does not create duplicate requirements.
        """
        tender = self._create_test_tender(title="Idempotency Test 07")

        pages = [
            {
                "page_number": 2,
                "section": "Eligibility Criteria",
                "text": "The minimum average annual turnover of the bidder shall be Rs. 5 Crore in the last 3 financial years.\n"
                        "The bidder must have successfully completed at least 3 similar projects in the last 5 years.",
            }
        ]

        # First run
        tender_intelligence_service.process_tender_pages(
            pages=pages,
            tender_id=tender.id,
            db=self.db,
            persist=True,
        )
        count_run_1 = len(crud_tender_requirement.get_by_tender(self.db, tender.id))
        self.assertGreaterEqual(count_run_1, 1)

        # Second run with exact same content
        tender_intelligence_service.process_tender_pages(
            pages=pages,
            tender_id=tender.id,
            db=self.db,
            persist=True,
        )
        count_run_2 = len(crud_tender_requirement.get_by_tender(self.db, tender.id))

        # Idempotency guarantee: count must remain identical
        self.assertEqual(count_run_1, count_run_2, "Repeated processing created duplicate requirement rows!")

    # -------------------------------------------------------------------------
    # Test 8: Canonical packaged output is generated successfully
    # -------------------------------------------------------------------------
    def test_08_canonical_packaged_output_generation(self):
        """
        Test 8: Verify that CanonicalDocumentOutput (Phase 11.9) is generated and attached to the compliance profile.
        """
        tender = self._create_test_tender(title="Canonical Packaging Test 08")
        doc_hash = "4a5b6c7d8e9f0123456789abcdef0123456789abcdef0123456789abcdef0123"

        doc = crud_document.create_metadata(
            db=self.db,
            original_filename="Tender_NIT_2026.pdf",
            storage_path=f"tenders/{tender.id}/Tender_NIT_2026.pdf",
            document_type=DocumentType.TENDER_PDF,
            mime_type="application/pdf",
            file_size=2097152,
            sha256=doc_hash,
            tender_id=tender.id,
            status=DocumentStatus.ACTIVE,
            processing_status=ProcessingStatus.PROCESSED,
        )
        self.created_doc_ids.append(doc.id)

        raw_text = (
            "SECTION 1: NOTICE INVITING TENDER\nTender for Supply and Installation of Servers.\n\n"
            "SECTION 2: ELIGIBILITY CRITERIA\n"
            "1. The bidder must have a minimum average annual turnover of Rs. 10 Crore in the last 3 financial years.\n"
            "2. EMD: Rs. 2,00,000 must be deposited online.\n"
        )

        # Run analyze_tender with raw_text
        profile = tender_intelligence_service.analyze_tender(
            db=self.db,
            tender_id=tender.id,
            request=TenderAnalysisRequest(raw_text=raw_text, force_reanalyze=True),
        )

        self.assertIsInstance(profile, TenderComplianceProfileResponse)
        self.assertEqual(profile.status, "COMPLETED")
        self.assertGreaterEqual(profile.requirement_count, 1)
        self.assertIsNotNone(profile.canonical_output)
        self.assertIsInstance(profile.canonical_output, CanonicalDocumentOutput)

        # Inspect canonical packaging elements
        pkg = profile.canonical_output
        self.assertGreaterEqual(len(pkg.sections), 1)
        self.assertGreaterEqual(len(pkg.requirements), 1)
        self.assertIsNotNone(pkg.extraction_summary)
        self.assertGreaterEqual(pkg.extraction_summary.deterministic_requirements, 1)
        self.assertEqual(pkg.extraction_summary.ai_resolved_requirements, 0)
        self.assertIsNotNone(pkg.traceability)


if __name__ == "__main__":
    unittest.main()
