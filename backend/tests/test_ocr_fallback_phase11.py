"""
Phase 11.4 — OCR Fallback Test Suite
Tests OCR requirement detection, conditional OCR fallback triggering, selective page OCR,
explicit OCR failure handling, status preservation, and non-mutation of original documents.
"""
import io
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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
        sys.modules[mod] = MagicMock()

from app.schemas.ocr import OCRDocumentResult, OCRPageResult, OCRTextBox
from app.schemas.processing import ExtractionResult, PageExtractionResult, TableData
from app.services.document_processor import DocumentProcessor
from app.services.ocr_pipeline import OCRPipeline
from app.services.pdf_extractor import PDFExtractor


class TestOCRFallbackPhase11(unittest.TestCase):
    """Unit tests for Phase 11.4 OCR fallback subsystem."""

    def setUp(self):
        self.mock_pdf_extractor = MagicMock(spec=PDFExtractor)
        self.mock_ocr_pipeline = MagicMock(spec=OCRPipeline)
        self.doc_processor = DocumentProcessor(
            pdf_ext=self.mock_pdf_extractor,
            ocr_pipe=self.mock_ocr_pipeline,
        )

    # -------------------------------------------------------------------------
    # 1. TEXT PDF -> OCR NOT TRIGGERED
    # -------------------------------------------------------------------------
    def test_text_pdf_ocr_not_triggered(self):
        """
        Verifies that when a PDF has sufficient deterministic text,
        OCR fallback is NOT triggered and deterministic text is returned directly.
        """
        text_payload = b"%PDF-1.5 test document with plenty of searchable text..."
        deterministic_result = ExtractionResult(
            format="PDF",
            status="EXTRACTED",
            page_count=1,
            text="This is a valid procurement notice with ample searchable digital text.",
            pages=[
                PageExtractionResult(
                    page_number=1,
                    text="This is a valid procurement notice with ample searchable digital text.",
                    word_count=10,
                    char_count=68,
                    has_text=True,
                    images_count=0,
                    requires_ocr=False,
                )
            ],
            requires_ocr=False,
            tables=[],
            is_corrupted=False,
        )
        self.mock_pdf_extractor.extract.return_value = deterministic_result

        # Process document with OCR enabled
        res = self.doc_processor.process_document(
            file_bytes=text_payload,
            filename="tender_notice.pdf",
            mime_type="application/pdf",
            enable_ocr=True,
        )

        # Ensure PDFExtractor was called, but OCRPipeline was NOT invoked
        self.mock_pdf_extractor.extract.assert_called_once_with(text_payload, filename="tender_notice.pdf")
        self.mock_ocr_pipeline.process_with_fallback.assert_not_called()
        self.assertEqual(res.status, "EXTRACTED")
        self.assertEqual(res.text, "This is a valid procurement notice with ample searchable digital text.")
        self.assertFalse(res.requires_ocr)

    # -------------------------------------------------------------------------
    # 2. SCANNED PDF -> OCR TRIGGERED
    # -------------------------------------------------------------------------
    def test_scanned_pdf_ocr_triggered(self):
        """
        Verifies that a scanned PDF with 0 extractable text triggers the OCR pipeline
        and successfully returns OCR-extracted text and status OCR_COMPLETED.
        """
        scanned_payload = b"%PDF-1.5 scanned image-only PDF bytes..."
        deterministic_result = ExtractionResult(
            format="PDF",
            status="OCR_REQUIRED",
            page_count=1,
            text="",
            pages=[
                PageExtractionResult(
                    page_number=1,
                    text="",
                    word_count=0,
                    char_count=0,
                    has_text=False,
                    images_count=1,
                    requires_ocr=True,
                )
            ],
            requires_ocr=True,
            tables=[],
            is_corrupted=False,
        )
        self.mock_pdf_extractor.extract.return_value = deterministic_result

        # Real OCR fallback runner testing
        real_ocr_pipeline = OCRPipeline()
        mock_ocr_doc = OCRDocumentResult(
            page_count=1,
            full_text="ANNUAL TURNOVER CERTIFICATE\nAudited Revenue: INR 2.50 Crores",
            pages=[
                OCRPageResult(
                    page_number=1,
                    text="ANNUAL TURNOVER CERTIFICATE\nAudited Revenue: INR 2.50 Crores",
                    word_count=7,
                    line_count=2,
                    avg_confidence=0.96,
                    is_blank=False,
                    rotation_angle=0.0,
                    processing_time_ms=120.0,
                )
            ],
            overall_confidence=0.96,
            engine_used="PaddleOCR",
            is_success=True,
            execution_time_ms=150.0,
        )

        with patch.object(real_ocr_pipeline, "process_scanned_pdf", return_value=mock_ocr_doc) as mock_scan:
            res = real_ocr_pipeline.process_with_fallback(
                extract_res=deterministic_result,
                file_bytes=scanned_payload,
                filename="scanned_cert.pdf",
            )
            mock_scan.assert_called_once()
            self.assertEqual(res.status, "OCR_COMPLETED")
            self.assertIn("Audited Revenue: INR 2.50 Crores", res.text)
            self.assertEqual(len(res.pages), 1)
            self.assertEqual(res.pages[0].page_number, 1)
            self.assertFalse(res.requires_ocr)
            self.assertIsNotNone(res.ocr_data)

    # -------------------------------------------------------------------------
    # 3. OCR FAILURE -> EXPLICIT ERROR REPORTING
    # -------------------------------------------------------------------------
    def test_ocr_failure_explicit_handling(self):
        """
        Verifies that when the OCR engine fails, the pipeline explicitly marks
        status="FAILED", is_success=False, and returns the error without silent suppression.
        """
        scanned_payload = b"%PDF-1.5 scanned corrupted render stream"
        deterministic_result = ExtractionResult(
            format="PDF",
            status="OCR_REQUIRED",
            page_count=1,
            text="",
            pages=[
                PageExtractionResult(
                    page_number=1,
                    text="",
                    requires_ocr=True,
                )
            ],
            requires_ocr=True,
            tables=[],
            is_corrupted=False,
        )

        real_ocr_pipeline = OCRPipeline()
        failed_ocr_doc = OCRDocumentResult(
            page_count=0,
            full_text="",
            pages=[],
            overall_confidence=0.0,
            engine_used="PaddleOCR",
            is_success=False,
            error_message="OpenCV memory allocation failed during deskew rotation.",
            execution_time_ms=25.0,
        )

        with patch.object(real_ocr_pipeline, "process_scanned_pdf", return_value=failed_ocr_doc):
            res = real_ocr_pipeline.process_with_fallback(
                extract_res=deterministic_result,
                file_bytes=scanned_payload,
                filename="bad_scan.pdf",
            )
            # Verify explicit failure status
            self.assertEqual(res.status, "FAILED")
            self.assertIn("OCR execution failure", res.error_message)
            self.assertIn("OpenCV memory allocation failed", res.error_message)
            self.assertTrue(res.requires_ocr)

    # -------------------------------------------------------------------------
    # 4. MIXED TEXT / IMAGE DOCUMENT (SELECTIVE PAGE OCR)
    # -------------------------------------------------------------------------
    def test_mixed_document_selective_ocr(self):
        """
        Verifies that in a 2-page document (Page 1 has text, Page 2 is scanned image):
        - OCR is ONLY executed on Page 2 (pages_to_ocr=[2])
        - Page 1 preserves its original crisp deterministic text
        - Page 2 gets OCR-extracted text
        - Combined text contains both pages in proper 1-indexed order.
        """
        mixed_payload = b"%PDF-1.5 mixed text and scanned image document"
        deterministic_result = ExtractionResult(
            format="PDF",
            status="PARTIALLY_EXTRACTED",
            page_count=2,
            text="TENDER INSTRUCTIONS:\nAll bidders must submit genuine tax certificates.",
            pages=[
                PageExtractionResult(
                    page_number=1,
                    text="TENDER INSTRUCTIONS:\nAll bidders must submit genuine tax certificates.",
                    word_count=8,
                    char_count=65,
                    has_text=True,
                    images_count=0,
                    requires_ocr=False,
                ),
                PageExtractionResult(
                    page_number=2,
                    text="",
                    word_count=0,
                    char_count=0,
                    has_text=False,
                    images_count=1,
                    requires_ocr=True,
                ),
            ],
            requires_ocr=True,
            tables=[],
            is_corrupted=False,
        )

        real_ocr_pipeline = OCRPipeline()
        ocr_page_2_doc = OCRDocumentResult(
            page_count=2,
            full_text="GOVERNMENT OF INDIA - GST CERTIFICATE\nGSTIN: 07AAAAA0000A1Z5",
            pages=[
                OCRPageResult(
                    page_number=2,
                    text="GOVERNMENT OF INDIA - GST CERTIFICATE\nGSTIN: 07AAAAA0000A1Z5",
                    word_count=7,
                    line_count=2,
                    avg_confidence=0.98,
                    is_blank=False,
                    rotation_angle=0.0,
                    processing_time_ms=100.0,
                )
            ],
            overall_confidence=0.98,
            engine_used="PaddleOCR",
            is_success=True,
            execution_time_ms=130.0,
        )

        with patch.object(real_ocr_pipeline, "process_scanned_pdf", return_value=ocr_page_2_doc) as mock_selective_scan:
            res = real_ocr_pipeline.process_with_fallback(
                extract_res=deterministic_result,
                file_bytes=mixed_payload,
                filename="mixed_doc.pdf",
            )
            # Verify only Page 2 was requested for OCR
            mock_selective_scan.assert_called_once_with(
                pdf_bytes=mixed_payload,
                dpi=200,
                filename="mixed_doc.pdf",
                pages_to_ocr=[2],
            )

            # Verify Page 1 retained original deterministic text
            self.assertEqual(res.pages[0].page_number, 1)
            self.assertIn("TENDER INSTRUCTIONS", res.pages[0].text)

            # Verify Page 2 received OCR text
            self.assertEqual(res.pages[1].page_number, 2)
            self.assertIn("GSTIN: 07AAAAA0000A1Z5", res.pages[1].text)

            # Verify combined text and final status
            self.assertEqual(res.status, "OCR_COMPLETED")
            self.assertIn("TENDER INSTRUCTIONS", res.text)
            self.assertIn("GSTIN: 07AAAAA0000A1Z5", res.text)

    # -------------------------------------------------------------------------
    # 5. ORIGINAL DOCUMENT UNCHANGED & TRACEABILITY
    # -------------------------------------------------------------------------
    def test_original_document_preserved_unchanged(self):
        """Verifies that processing a document leaves original byte buffers untouched."""
        original_bytes = b"%PDF-1.5 immutable byte stream check"
        copy_bytes = bytes(original_bytes)

        deterministic_result = ExtractionResult(
            format="PDF",
            status="EXTRACTED",
            page_count=1,
            text="Sample immutable content",
            pages=[
                PageExtractionResult(
                    page_number=1,
                    text="Sample immutable content",
                    has_text=True,
                )
            ],
            requires_ocr=False,
        )
        self.mock_pdf_extractor.extract.return_value = deterministic_result

        res = self.doc_processor.process_document(
            file_bytes=original_bytes,
            filename="immutable.pdf",
        )

        # Assert byte buffer was never modified in place
        self.assertEqual(original_bytes, copy_bytes)

        # Test traceability output for downstream normalization
        traceable = res.to_traceable_pages()
        self.assertEqual(len(traceable), 1)
        self.assertEqual(traceable[0]["page_number"], 1)
        self.assertEqual(traceable[0]["text"], "Sample immutable content")


if __name__ == "__main__":
    unittest.main()
