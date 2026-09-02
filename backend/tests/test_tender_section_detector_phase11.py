"""
Phase 11.6 — Tender Section Detection Test Suite
Tests deterministic detection, bounding, and classification of procurement tender sections
(Eligibility, Financial, Technical, Experience, Statutory, Required Documents, EMD, PBG,
Terms and Conditions, Scope of Work, Evaluation Criteria, Tender Info) across normalized documents.
"""
import os
import sys
import unittest

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# If running in environment where heavy DB/OCR libraries are not installed in global site-packages, provide typed mock stubs
if "sqlalchemy" not in sys.modules:
    import types

    class DummyType(type):
        def __getitem__(cls, item):
            return cls
        def __getattr__(cls, item):
            return DummyClass()
        def __call__(cls, *args, **kwargs):
            return super().__call__(*args, **kwargs)
            
    class DummyClass(metaclass=DummyType):
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return self
        def __getattr__(self, item):
            return self

    class AutoModule(types.ModuleType):
        def __init__(self, name):
            super().__init__(name)
            self.__path__ = []
        def __getattr__(self, name):
            if name == "create_engine":
                return lambda *a, **kw: DummyClass()
            if name == "text":
                return lambda *a, **kw: DummyClass()
            if name == "mapped_column":
                return lambda *a, **kw: None
            if name == "relationship":
                return lambda *a, **kw: None
            if name == "declarative_base":
                return lambda *a, **kw: DummyClass
            if name == "sessionmaker":
                return lambda *a, **kw: DummyClass
            return DummyClass

    sa_mod = AutoModule("sqlalchemy")
    sa_orm = AutoModule("sqlalchemy.orm")
    sa_dialects = AutoModule("sqlalchemy.dialects")
    sa_pg = AutoModule("sqlalchemy.dialects.postgresql")
    sa_types = AutoModule("sqlalchemy.types")
    
    sa_mod.orm = sa_orm
    sa_mod.dialects = sa_dialects
    sa_mod.types = sa_types
    
    sys.modules["sqlalchemy"] = sa_mod
    sys.modules["sqlalchemy.orm"] = sa_orm
    sys.modules["sqlalchemy.dialects"] = sa_dialects
    sys.modules["sqlalchemy.dialects.postgresql"] = sa_pg
    sys.modules["sqlalchemy.types"] = sa_types

for mod in ["supabase", "fitz", "pdfplumber", "cv2", "numpy"]:
    if mod not in sys.modules:
        from unittest.mock import MagicMock
        sys.modules[mod] = MagicMock()

from app.schemas.normalized_content import (
    NormalizedCurrency,
    NormalizedDate,
    NormalizedDocument,
    NormalizedPage,
    NormalizedTable,
)
from app.schemas.processing import ExtractionResult, PageExtractionResult, TableData
from app.schemas.tender_section import (
    DetectedTenderSection,
    SectionType,
    TenderSectionDetectionResult,
)
from app.services.tender_section_detector import (
    TenderSectionDetector,
    tender_section_detector,
)


class TestTenderSectionDetectorPhase11(unittest.TestCase):
    """Unit tests for Phase 11.6 Tender Section Detection subsystem."""

    def setUp(self):
        self.detector = TenderSectionDetector()

    # -------------------------------------------------------------------------
    # 1. CANONICAL HEADING CLASSIFICATION TEST
    # -------------------------------------------------------------------------
    def test_heading_classification_all_categories(self):
        """Verifies heading strings map accurately to canonical SectionType."""
        test_cases = [
            ("NOTICE INVITING TENDER (NIT)", SectionType.TENDER_INFORMATION),
            ("SECTION 1: TENDER INFORMATION AND KEY DATES", SectionType.TENDER_INFORMATION),
            ("SECTION II: MINIMUM ELIGIBILITY CRITERIA", SectionType.ELIGIBILITY_CRITERIA),
            ("PRE-QUALIFICATION CRITERIA FOR BIDDERS", SectionType.ELIGIBILITY_CRITERIA),
            ("TECHNICAL SPECIFICATIONS AND COMPLIANCE SCHEDULE", SectionType.TECHNICAL_REQUIREMENTS),
            ("BILL OF MATERIALS (BOM)", SectionType.TECHNICAL_REQUIREMENTS),
            ("FINANCIAL CRITERIA & ANNUAL TURNOVER", SectionType.FINANCIAL_REQUIREMENTS),
            ("TURNOVER REQUIREMENTS", SectionType.FINANCIAL_REQUIREMENTS),
            ("PAST EXPERIENCE AND SIMILAR WORK EXECUTION", SectionType.EXPERIENCE),
            ("TRACK RECORD OF SIMILAR WORKS", SectionType.EXPERIENCE),
            ("STATUTORY REQUIREMENTS & TAX COMPLIANCE", SectionType.STATUTORY_REQUIREMENTS),
            ("GST AND STATUTORY REGISTRATIONS", SectionType.STATUTORY_REQUIREMENTS),
            ("CHECKLIST OF MANDATORY DOCUMENTS TO BE SUBMITTED", SectionType.REQUIRED_DOCUMENTS),
            ("ANNEXURE-A: REQUIRED DOCUMENTS", SectionType.REQUIRED_DOCUMENTS),
            ("EARNEST MONEY DEPOSIT (EMD) CLAUSE", SectionType.EMD),
            ("BID SECURITY DECLARATION", SectionType.EMD),
            ("PERFORMANCE SECURITY BANK GUARANTEE (PBG)", SectionType.PERFORMANCE_SECURITY),
            ("CONTRACT PERFORMANCE GUARANTEE", SectionType.PERFORMANCE_SECURITY),
            ("GENERAL CONDITIONS OF CONTRACT (GCC)", SectionType.TERMS_AND_CONDITIONS),
            ("SPECIAL TERMS AND CONDITIONS", SectionType.TERMS_AND_CONDITIONS),
            ("SCOPE OF WORK AND DELIVERABLES", SectionType.SCOPE_OF_WORK),
            ("PROJECT SCOPE AND WORK DESCRIPTION", SectionType.SCOPE_OF_WORK),
            ("EVALUATION CRITERIA AND SELECTION METHODOLOGY", SectionType.EVALUATION_CRITERIA),
            ("QCBS EVALUATION MATRIX", SectionType.EVALUATION_CRITERIA),
        ]

        for heading, expected_type in test_cases:
            classif = self.detector.classify_heading(heading)
            self.assertIsNotNone(classif, f"Failed to classify heading: '{heading}'")
            s_type, s_name, conf = classif
            self.assertEqual(s_type, expected_type, f"Mismatch for '{heading}': got {s_type}")
            self.assertGreater(conf, 0.8)

    # -------------------------------------------------------------------------
    # 2. MULTI-SECTION DOCUMENT BOUNDING & TRACEABILITY
    # -------------------------------------------------------------------------
    def test_multi_section_document_segmentation(self):
        """
        Verifies that a multi-page document with multiple sections is accurately bounded
        with page_start, page_end, source_reference, and child entities.
        """
        p1_text = (
            "NOTICE INVITING TENDER\n"
            "Tender Ref: GEM/2026/B/1001. Estimated Value: INR 5,00,00,000.\n"
            "Pre-bid meeting on 15/08/2026.\n\n"
            "SECTION 1: ELIGIBILITY CRITERIA\n"
            "The bidder must be a registered Indian entity operating for past 3 financial years.\n"
            "Annual turnover must be at least ₹2.5 crore in each of the last 3 years.\n"
        )
        p2_text = (
            "SECTION 2: TECHNICAL REQUIREMENTS\n"
            "All supplied enterprise servers must have minimum 64-core processors.\n"
            "Compliance certificate from OEM is required.\n\n"
            "SECTION 3: EARNEST MONEY DEPOSIT (EMD)\n"
            "Bidder must submit EMD of ₹5,00,000 via Bank Guarantee.\n"
        )
        p3_text = (
            "SECTION 4: MANDATORY DOCUMENTS CHECKLIST\n"
            "1. GST Registration Certificate\n"
            "2. Audited Balance Sheets for last 3 years\n"
            "3. OEM Authorization Form\n"
        )

        norm_doc = NormalizedDocument(
            document_id="doc-tender-999",
            format="PDF",
            raw_text=f"{p1_text}\n\n{p2_text}\n\n{p3_text}",
            normalized_text=f"{p1_text}\n\n{p2_text}\n\n{p3_text}",
            page_count=3,
            pages=[
                NormalizedPage(
                    page_number=1,
                    raw_text=p1_text,
                    normalized_text=p1_text,
                ),
                NormalizedPage(
                    page_number=2,
                    raw_text=p2_text,
                    normalized_text=p2_text,
                ),
                NormalizedPage(
                    page_number=3,
                    raw_text=p3_text,
                    normalized_text=p3_text,
                ),
            ],
        )

        res: TenderSectionDetectionResult = self.detector.detect_sections_from_normalized(norm_doc)

        self.assertEqual(res.document_id, "doc-tender-999")
        self.assertGreaterEqual(res.total_sections, 4)

        # Check section types detected
        sec_types = [s.section_type for s in res.sections]
        self.assertIn(SectionType.TENDER_INFORMATION, sec_types)
        self.assertIn(SectionType.ELIGIBILITY_CRITERIA, sec_types)
        self.assertIn(SectionType.TECHNICAL_REQUIREMENTS, sec_types)
        self.assertIn(SectionType.EMD, sec_types)
        self.assertIn(SectionType.REQUIRED_DOCUMENTS, sec_types)

        # Verify Eligibility Section details
        elig_sec = next(s for s in res.sections if s.section_type == SectionType.ELIGIBILITY_CRITERIA)
        self.assertEqual(elig_sec.page_start, 1)
        self.assertIn("₹2.5 crore", elig_sec.text)
        self.assertGreaterEqual(len(elig_sec.currencies), 1)
        self.assertEqual(elig_sec.currencies[0].amount, 25000000.0)
        self.assertEqual(elig_sec.source_reference, "Page 1 - SECTION 1: ELIGIBILITY CRITERIA")

        # Verify EMD Section details
        emd_sec = next(s for s in res.sections if s.section_type == SectionType.EMD)
        self.assertEqual(emd_sec.page_start, 2)
        self.assertIn("₹5,00,000", emd_sec.text)
        self.assertGreaterEqual(len(emd_sec.currencies), 1)
        self.assertEqual(emd_sec.currencies[0].amount, 500000.0)

    # -------------------------------------------------------------------------
    # 3. MULTI-PAGE SPANNING SECTION TEST
    # -------------------------------------------------------------------------
    def test_multi_page_spanning_section(self):
        """Verifies sections spanning across multiple consecutive pages are tracked properly."""
        p1 = (
            "SECTION 1: SCOPE OF WORK\n"
            "Phase 1 includes civil construction and site preparation in District A.\n"
        )
        p2 = (
            "Phase 2 includes electrical cabling, HVAC installation and transformer testing.\n"
            "Phase 3 includes commissioning and safety handover.\n"
        )
        norm_doc = NormalizedDocument(
            document_id="doc-span-123",
            format="PDF",
            raw_text=f"{p1}\n{p2}",
            normalized_text=f"{p1}\n{p2}",
            page_count=2,
            pages=[
                NormalizedPage(page_number=1, raw_text=p1, normalized_text=p1),
                NormalizedPage(page_number=2, raw_text=p2, normalized_text=p2),
            ],
        )

        res: TenderSectionDetectionResult = self.detector.detect_sections_from_normalized(norm_doc)
        self.assertGreaterEqual(res.total_sections, 1)

        sow_sec = res.sections[0]
        self.assertEqual(sow_sec.section_type, SectionType.SCOPE_OF_WORK)
        self.assertEqual(sow_sec.page_start, 1)
        self.assertEqual(sow_sec.page_end, 2)
        self.assertEqual(sow_sec.source_reference, "Pages 1-2 - SECTION 1: SCOPE OF WORK")
        self.assertIn("Phase 1", sow_sec.text)
        self.assertIn("Phase 3", sow_sec.text)

    # -------------------------------------------------------------------------
    # 4. END-TO-END CONVENIENCE EXTRACTION WRAPPER
    # -------------------------------------------------------------------------
    def test_detect_sections_from_raw_extraction_result(self):
        """Verifies detect_sections accepts raw ExtractionResult directly."""
        ext_res = ExtractionResult(
            document_id="ext-doc-456",
            format="DOCX",
            status="EXTRACTED",
            page_count=1,
            text=(
                "GENERAL CONDITIONS OF CONTRACT\n"
                "Liquidated damages shall be 0.5% per week of delay up to a maximum of 10%.\n"
                "Termination clause applicable after 30 days default notice."
            ),
            pages=[
                PageExtractionResult(
                    page_number=1,
                    text=(
                        "GENERAL CONDITIONS OF CONTRACT\n"
                        "Liquidated damages shall be 0.5% per week of delay up to a maximum of 10%.\n"
                        "Termination clause applicable after 30 days default notice."
                    ),
                    has_text=True,
                )
            ],
            requires_ocr=False,
            tables=[],
        )

        res: TenderSectionDetectionResult = self.detector.detect_sections(ext_res, document_id="ext-doc-456")
        self.assertEqual(res.document_id, "ext-doc-456")
        self.assertEqual(len(res.sections), 1)
        self.assertEqual(res.sections[0].section_type, SectionType.TERMS_AND_CONDITIONS)
        self.assertIn("Liquidated damages", res.sections[0].text)


if __name__ == "__main__":
    unittest.main()
