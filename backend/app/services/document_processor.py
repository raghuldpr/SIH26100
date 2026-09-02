import io
import logging
from typing import Optional

from app.schemas.processing import (
    DocxExtractionResult,
    ExtractionResult,
    PageExtractionResult,
    XlsxExtractionResult,
)
from app.services.docx_extractor import DOCXExtractor, docx_extractor
from app.services.ocr_pipeline import OCRPipeline, ocr_pipeline
from app.services.pdf_extractor import PDFExtractor, pdf_extractor
from app.services.xlsx_extractor import XLSXExtractor, xlsx_extractor

logger = logging.getLogger("app.services.document_processor")


class DocumentProcessor:
    """
    High-level Multi-Format Document Processing Subsystem for SIH-26100.
    Unifies deterministic text/table/metadata extraction across:
    - PDF (PyMuPDF + pdfplumber)
    - DOCX (OpenXML WordprocessingML)
    - XLSX (OpenXML SpreadsheetML)
    - OCR Fallback (OpenCV + PaddleOCR triggered ONLY when deterministic text is insufficient)
    """

    def __init__(
        self,
        pdf_ext: Optional[PDFExtractor] = None,
        docx_ext: Optional[DOCXExtractor] = None,
        xlsx_ext: Optional[XLSXExtractor] = None,
        ocr_pipe: Optional[OCRPipeline] = None,
    ):
        self.pdf_extractor = pdf_ext or pdf_extractor
        self.docx_extractor = docx_ext or docx_extractor
        self.xlsx_extractor = xlsx_ext or xlsx_extractor
        self.ocr_pipeline = ocr_pipe or ocr_pipeline

    def process_pdf(self, file_bytes: bytes, filename: Optional[str] = None) -> ExtractionResult:
        """Processes a PDF byte payload and returns structured extraction results."""
        return self.pdf_extractor.extract(file_bytes, filename=filename)

    def process_docx(self, file_bytes: bytes, filename: Optional[str] = None) -> ExtractionResult:
        """Processes a DOCX byte payload and returns structured extraction results."""
        res: DocxExtractionResult = self.docx_extractor.extract(file_bytes, filename=filename)
        # Wrap in unified ExtractionResult
        return ExtractionResult(
            format="DOCX",
            status=res.status,
            page_count=len(res.sections) if res.sections else 1,
            text=res.text,
            pages=[],
            requires_ocr=False,
            tables=[],  # tables are stored in docx_data and accessible via to_traceable_pages()
            docx_data=res,
            xlsx_data=None,
            is_corrupted=res.is_corrupted,
            error_message=res.error_message,
            metadata=res.metadata,
        )

    def process_xlsx(self, file_bytes: bytes, filename: Optional[str] = None) -> ExtractionResult:
        """Processes an XLSX byte payload and returns structured extraction results."""
        res: XlsxExtractionResult = self.xlsx_extractor.extract(file_bytes, filename=filename)
        # Wrap in unified ExtractionResult
        return ExtractionResult(
            format="XLSX",
            status=res.status,
            page_count=res.sheet_count,
            text=res.text,
            pages=[],
            requires_ocr=False,
            tables=res.tables,
            docx_data=None,
            xlsx_data=res,
            is_corrupted=res.is_corrupted,
            error_message=res.error_message,
            metadata=res.metadata,
        )

    def process_document(
        self,
        file_bytes: bytes,
        mime_type: Optional[str] = None,
        filename: Optional[str] = None,
        enable_ocr: bool = True,
        dpi: int = 200,
    ) -> ExtractionResult:
        """
        Unified multi-format router. Runs deterministic extraction first,
        and triggers OCR fallback ONLY when text extraction was insufficient.
        """
        if not file_bytes:
            return ExtractionResult(
                format="UNKNOWN",
                status="FAILED",
                page_count=0,
                text="",
                requires_ocr=False,
                is_corrupted=True,
                error_message="Empty file byte stream provided.",
            )

        extract_res: Optional[ExtractionResult] = None

        # 1. Detect PDF format
        is_pdf = (
            (mime_type and "pdf" in mime_type.lower())
            or (filename and filename.lower().endswith(".pdf"))
            or file_bytes.startswith(b"%PDF-")
        )
        if is_pdf:
            extract_res = self.process_pdf(file_bytes, filename=filename)

        # 2. Detect DOCX format
        elif (
            (mime_type and "wordprocessingml" in mime_type.lower())
            or (filename and filename.lower().endswith(".docx"))
        ):
            extract_res = self.process_docx(file_bytes, filename=filename)

        # 3. Detect XLSX format
        elif (
            (mime_type and "spreadsheetml" in mime_type.lower())
            or (filename and filename.lower().endswith(".xlsx"))
        ):
            extract_res = self.process_xlsx(file_bytes, filename=filename)

        # 4. Detect Image formats (JPEG, PNG) requiring OCR
        elif (
            (mime_type and any(img in mime_type.lower() for img in ["image/jpeg", "image/jpg", "image/png"]))
            or (filename and any(filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]))
            or file_bytes.startswith(b"\xff\xd8\xff")
            or file_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        ):
            extract_res = ExtractionResult(
                format="IMAGE",
                status="OCR_REQUIRED",
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

        # 5. Fallback for OpenXML ZIP payloads without explicit MIME
        elif file_bytes.startswith(b"PK\x03\x04"):
            import zipfile
            try:
                with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                    names = zf.namelist()
                    if any(n.startswith("word/") for n in names):
                        extract_res = self.process_docx(file_bytes, filename=filename)
                    elif any(n.startswith("xl/") for n in names):
                        extract_res = self.process_xlsx(file_bytes, filename=filename)
            except Exception:
                pass

        if extract_res is None:
            # Unsupported format
            return ExtractionResult(
                format="UNSUPPORTED",
                status="FAILED",
                page_count=0,
                text="",
                requires_ocr=False,
                is_corrupted=True,
                error_message=f"Unsupported document format for text extraction: '{mime_type or filename or 'unknown'}'",
            )

        # 6. Apply OCR Fallback ONLY if required and enabled
        if enable_ocr and extract_res.requires_ocr and not extract_res.is_corrupted:
            return self.ocr_pipeline.process_with_fallback(
                extract_res=extract_res,
                file_bytes=file_bytes,
                mime_type=mime_type,
                filename=filename,
                dpi=dpi,
            )

        return extract_res


# Default singleton instance
document_processor = DocumentProcessor()
