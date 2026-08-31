import logging
from typing import Optional
from app.schemas.processing import ExtractionResult, PageExtractionResult
from app.services.pdf_extractor import PDFExtractor, pdf_extractor

logger = logging.getLogger("app.services.document_processor")


class DocumentProcessor:
    """
    High-level Document Processing Subsystem for SIH-26100.
    Unifies PDF text/table extraction, image preprocessing, and OCR-need classification.
    """

    def __init__(self, extractor: Optional[PDFExtractor] = None):
        self.pdf_extractor = extractor or pdf_extractor

    def process_pdf(self, file_bytes: bytes, filename: Optional[str] = None) -> ExtractionResult:
        """Processes a PDF byte payload and returns structured extraction results."""
        return self.pdf_extractor.extract(file_bytes, filename=filename)

    def process_document(
        self,
        file_bytes: bytes,
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Processes any supported document format (PDF, JPEG, PNG).
        Routes PDFs to PyMuPDF/pdfplumber text extraction and marks scanned/image files for OCR.
        """
        if not file_bytes:
            return ExtractionResult(
                page_count=0,
                text="",
                requires_ocr=False,
                is_corrupted=True,
                error_message="Empty file byte stream provided.",
            )

        # Detect or match MIME type
        is_pdf = (
            (mime_type and "pdf" in mime_type.lower())
            or (filename and filename.lower().endswith(".pdf"))
            or file_bytes.startswith(b"%PDF-")
        )

        if is_pdf:
            return self.process_pdf(file_bytes, filename=filename)

        # Handle Image formats (JPEG, PNG)
        is_image = (
            (mime_type and any(img in mime_type.lower() for img in ["image/jpeg", "image/jpg", "image/png"]))
            or (filename and any(filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]))
            or file_bytes.startswith(b"\xff\xd8\xff")
            or file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        )

        if is_image:
            # Standalone images inherently require OCR for text recognition
            return ExtractionResult(
                document_type=None,
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
                        tables=[],
                    )
                ],
                requires_ocr=True,
                tables=[],
                is_corrupted=False,
                error_message=None,
            )

        # Unsupported or unrecognized format
        return ExtractionResult(
            page_count=0,
            text="",
            requires_ocr=False,
            is_corrupted=True,
            error_message=f"Unsupported document format for text extraction: '{mime_type or filename or 'unknown'}'",
        )


# Default singleton instance
document_processor = DocumentProcessor()
