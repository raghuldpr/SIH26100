import io
import logging
from typing import Any, Dict, List, Optional

try:
    import fitz  # PyMuPDF
    import pdfplumber
except ImportError:
    fitz = None  # type: ignore
    pdfplumber = None  # type: ignore

from app.schemas.processing import ExtractionResult, PageExtractionResult, TableData

logger = logging.getLogger("app.services.pdf_extractor")

# Configuration thresholds for text vs OCR detection
MIN_PAGE_CHAR_THRESHOLD = 15
MIN_TOTAL_CHAR_THRESHOLD = 15


class PDFExtractor:

    """
    Robust PDF Text and Structure Extraction Engine using PyMuPDF and pdfplumber.
    Extracts text page-by-page, detects scanned/image-only PDFs requiring OCR,
    extracts tabular layouts, and handles corrupt or malformed files gracefully.
    """

    def __init__(
        self,
        min_page_chars: int = MIN_PAGE_CHAR_THRESHOLD,
        min_total_chars: int = MIN_TOTAL_CHAR_THRESHOLD,
    ):
        self.min_page_chars = min_page_chars
        self.min_total_chars = min_total_chars

    def extract(self, file_bytes: bytes, filename: Optional[str] = None) -> ExtractionResult:
        """
        Extracts structured text, tables, and metadata from PDF bytes.
        Never raises unhandled exceptions on corrupt documents.
        """
        if not file_bytes:
            return ExtractionResult(
                page_count=0,
                text="",
                requires_ocr=False,
                is_corrupted=True,
                error_message="Empty PDF byte stream provided.",
            )

        doc_fitz: Optional[fitz.Document] = None
        doc_plumber: Optional[pdfplumber.PDF] = None

        try:
            # 1. Open document with PyMuPDF
            try:
                doc_fitz = fitz.open(stream=file_bytes, filetype="pdf")
            except Exception as exc:
                logger.warning(f"PyMuPDF failed to open PDF '{filename or 'unknown'}': {exc}")
                return ExtractionResult(
                    page_count=0,
                    text="",
                    requires_ocr=False,
                    is_corrupted=True,
                    error_message=f"Failed to parse PDF document structure: {exc}",
                )

            page_count = len(doc_fitz)
            if page_count == 0:
                return ExtractionResult(
                    page_count=0,
                    text="",
                    requires_ocr=False,
                    is_corrupted=False,
                    error_message="PDF contains 0 pages.",
                )

            # 2. Extract Document Metadata
            doc_metadata: Dict[str, Any] = {}
            if doc_fitz.metadata:
                doc_metadata = {
                    k: v for k, v in doc_fitz.metadata.items() if v and isinstance(v, (str, int, float, bool))
                }

            # 3. Optional pdfplumber for table extraction
            try:
                doc_plumber = pdfplumber.open(io.BytesIO(file_bytes))
            except Exception as exc:
                logger.debug(f"pdfplumber failed to open PDF for table extraction (continuing with PyMuPDF): {exc}")
                doc_plumber = None

            pages: List[PageExtractionResult] = []
            all_tables: List[TableData] = []
            full_text_fragments: List[str] = []
            total_chars = 0
            total_words = 0
            scanned_pages_count = 0

            # 4. Page-by-page extraction
            for page_idx in range(page_count):
                page_num = page_idx + 1
                fitz_page = doc_fitz[page_idx]

                # Extract text with PyMuPDF
                page_raw_text = fitz_page.get_text("text") or ""
                cleaned_text = page_raw_text.strip()

                char_len = len(cleaned_text)
                word_count = len(cleaned_text.split())
                image_list = fitz_page.get_images()
                images_count = len(image_list)

                total_chars += char_len
                total_words += word_count

                if cleaned_text:
                    full_text_fragments.append(cleaned_text)

                # Page-level OCR necessity evaluation
                has_sufficient_text = char_len >= self.min_page_chars
                page_requires_ocr = False
                if not has_sufficient_text:
                    scanned_pages_count += 1
                    page_requires_ocr = True

                # Extract tables using pdfplumber if available
                page_tables_raw: List[List[Optional[str]]] = []
                if doc_plumber and page_idx < len(doc_plumber.pages):
                    try:
                        plumber_page = doc_plumber.pages[page_idx]
                        extracted_tables = plumber_page.extract_tables()
                        if extracted_tables:
                            for tbl in extracted_tables:
                                if tbl and len(tbl) > 0:
                                    # Clean table cells
                                    cleaned_tbl = [
                                        [cell.strip() if isinstance(cell, str) else cell for cell in row]
                                        for row in tbl
                                    ]
                                    page_tables_raw.append(cleaned_tbl)
                                    all_tables.append(
                                        TableData(
                                            page_number=page_num,
                                            rows=cleaned_tbl,
                                            row_count=len(cleaned_tbl),
                                            col_count=len(cleaned_tbl[0]) if cleaned_tbl else 0,
                                        )
                                    )
                    except Exception as exc:
                        logger.debug(f"Table extraction failed on page {page_num}: {exc}")

                pages.append(
                    PageExtractionResult(
                        page_number=page_num,
                        text=cleaned_text,
                        word_count=word_count,
                        char_count=char_len,
                        has_text=has_sufficient_text,
                        images_count=images_count,
                        requires_ocr=page_requires_ocr,
                        tables=page_tables_raw,
                    )
                )

            # 5. Determine if whole document or individual pages require OCR
            requires_ocr = False
            if total_chars < self.min_total_chars or scanned_pages_count == page_count:
                requires_ocr = True
                status_str = "OCR_REQUIRED"
            elif scanned_pages_count > 0:
                requires_ocr = True
                status_str = "PARTIALLY_EXTRACTED"
            else:
                requires_ocr = False
                status_str = "EXTRACTED"

            combined_full_text = "\n\n".join(full_text_fragments)

            return ExtractionResult(
                format="PDF",
                status=status_str,
                page_count=page_count,
                text=combined_full_text,
                pages=pages,
                requires_ocr=requires_ocr,
                tables=all_tables,
                is_corrupted=False,
                error_message=None,
                metadata=doc_metadata,
            )

        except Exception as exc:
            logger.error(f"Unexpected error during PDF extraction: {exc}", exc_info=True)
            return ExtractionResult(
                page_count=0,
                text="",
                requires_ocr=False,
                is_corrupted=True,
                error_message=f"Extraction failure: {str(exc)}",
            )
        finally:
            if doc_fitz:
                try:
                    doc_fitz.close()
                except Exception:
                    pass
            if doc_plumber:
                try:
                    doc_plumber.close()
                except Exception:
                    pass


# Default singleton instance
pdf_extractor = PDFExtractor()
