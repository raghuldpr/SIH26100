import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple, Union

import pdfplumber

from app.core.exceptions import (
    CorruptedPDFException,
    DocumentNotFoundException,
    EmptyPDFException,
    PasswordProtectedPDFException,
    UnsupportedDocumentException,
)
from app.schemas.table import ExtractedTable, TableExtractionResult

logger = logging.getLogger("document_engine.extractors.table")

PDF_MAGIC_BYTES = b"%PDF-"


class TableExtractor:
    """
    Extracts tabular data from digital PDF documents using pdfplumber.
    Normalizes rows and columns, pads missing cells, detects scanned documents,
    and returns comprehensive table metadata.
    """

    @classmethod
    def validate_pdf_file(cls, path: Path) -> None:
        """Validates that file exists, is non-empty, and has a valid %PDF- header."""
        if not path.exists():
            raise DocumentNotFoundException(message=f"PDF file not found: {path.name}")

        if not path.is_file():
            raise UnsupportedDocumentException(message=f"Path is not a regular file: {path.name}")

        if path.stat().st_size == 0:
            raise EmptyPDFException(message="PDF file is empty (0 bytes)")

        try:
            with open(path, "rb") as f:
                header = f.read(1024)
                if PDF_MAGIC_BYTES not in header:
                    raise UnsupportedDocumentException(
                        message=f"File '{path.name}' is not a valid PDF document (missing %PDF- header)"
                    )
        except (OSError, IOError) as e:
            logger.error(f"Failed to read file header for {path.name}: {e}")
            raise CorruptedPDFException(
                message=f"Unable to read file header: {path.name}", details=str(e)
            )

    @classmethod
    def clean_cell(cls, cell: Optional[Union[str, int, float]]) -> str:
        """Normalizes a table cell value by stripping whitespace and replacing None."""
        if cell is None:
            return ""
        text = str(cell).strip()
        # Collapse multiple horizontal whitespace characters while preserving newlines
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()

    @classmethod
    def normalize_table(cls, raw_rows: List[List[Optional[str]]]) -> Optional[Tuple[List[List[str]], int, int]]:
        """
        Normalizes a raw 2D list of cells:
        1. Cleans and strips each cell.
        2. Identifies maximum column count.
        3. Pads irregular rows so all rows have uniform length.
        4. Discards empty rows/degenerate tables.
        """
        if not raw_rows or len(raw_rows) == 0:
            return None

        cleaned_rows: List[List[str]] = []
        max_cols = 0
        has_content = False

        for row in raw_rows:
            if not row:
                continue
            cleaned_row = [cls.clean_cell(c) for c in row]
            if any(len(c) > 0 for c in cleaned_row):
                has_content = True
            max_cols = max(max_cols, len(cleaned_row))
            cleaned_rows.append(cleaned_row)

        if not has_content or max_cols == 0 or len(cleaned_rows) == 0:
            return None

        # Pad irregular rows with empty strings so matrix is rectangular
        normalized_rows: List[List[str]] = []
        for row in cleaned_rows:
            if len(row) < max_cols:
                row = row + [""] * (max_cols - len(row))
            normalized_rows.append(row)

        return normalized_rows, len(normalized_rows), max_cols

    @classmethod
    def is_scanned_document(cls, pdf: pdfplumber.PDF) -> bool:
        """
        Heuristic to detect if a PDF is a scanned image without native digital text.
        If total native text across all pages is negligible (< 25 alphanumeric chars)
        and pages contain raster images, flags as scanned document.
        """
        total_text_length = 0
        has_images = False

        for page in pdf.pages:
            page_text = page.extract_text() or ""
            alnum = re.findall(r"\w", page_text)
            total_text_length += len(alnum)
            if len(page.images) > 0:
                has_images = True

        # If negligible digital text and raster images are present, consider it scanned
        if total_text_length < 25 and has_images:
            return True

        # Also if there are zero alphanumeric characters across all pages
        if total_text_length == 0 and len(pdf.pages) > 0:
            return True

        return False

    @classmethod
    def extract(cls, file_path: Union[str, Path]) -> TableExtractionResult:
        """
        Safely extracts tables page-by-page from a digital PDF using pdfplumber.
        Never modifies the source document.
        """
        path = Path(file_path).resolve()
        cls.validate_pdf_file(path)

        pdf = None
        try:
            try:
                pdf = pdfplumber.open(str(path))
            except Exception as e:
                err_msg = str(e)
                if "password" in err_msg.lower() or "encrypt" in err_msg.lower():
                    raise PasswordProtectedPDFException(
                        message=f"PDF document is password protected: {path.name}"
                    )
                raise CorruptedPDFException(
                    message=f"Failed to open PDF with pdfplumber: {path.name}", details=err_msg
                )

            total_pages = len(pdf.pages)
            if total_pages == 0:
                return TableExtractionResult(
                    extraction_method="pdfplumber",
                    total_tables=0,
                    tables=[],
                    pages_with_tables=[],
                    is_scanned_pdf=False,
                    requires_ocr=False,
                )

            # Detect scanned PDF
            is_scanned = cls.is_scanned_document(pdf)
            if is_scanned:
                logger.info(
                    f"PDF '{path.name}' detected as scanned image. Native table extraction bypassed."
                )
                return TableExtractionResult(
                    extraction_method="pdfplumber",
                    total_tables=0,
                    tables=[],
                    pages_with_tables=[],
                    is_scanned_pdf=True,
                    requires_ocr=True,
                )

            extracted_tables: List[ExtractedTable] = []
            pages_with_tables: set[int] = set()

            for page_idx, page in enumerate(pdf.pages):
                page_number = page_idx + 1
                try:
                    raw_tables = page.extract_tables()
                except Exception as e:
                    logger.warning(f"Error extracting tables on page {page_number} of {path.name}: {e}")
                    raw_tables = []

                if not raw_tables:
                    continue

                for tbl_idx, raw_table in enumerate(raw_tables):
                    normalized = cls.normalize_table(raw_table)
                    if normalized is None:
                        continue

                    rows, num_rows, num_cols = normalized
                    extracted_tables.append(
                        ExtractedTable(
                            page=page_number,
                            table_index=tbl_idx,
                            rows=rows,
                            num_rows=num_rows,
                            num_cols=num_cols,
                        )
                    )
                    pages_with_tables.add(page_number)

            total_tables = len(extracted_tables)
            sorted_pages = sorted(list(pages_with_tables))

            logger.info(
                f"Extracted {total_tables} table(s) across pages {sorted_pages} from {path.name}"
            )

            return TableExtractionResult(
                extraction_method="pdfplumber",
                total_tables=total_tables,
                tables=extracted_tables,
                pages_with_tables=sorted_pages,
                is_scanned_pdf=False,
                requires_ocr=False,
            )

        finally:
            if pdf is not None:
                try:
                    pdf.close()
                except Exception as e:
                    logger.debug(f"Error closing pdfplumber PDF: {e}")


def extract_tables_from_pdf(file_path: Union[str, Path]) -> TableExtractionResult:
    """Convenience helper for extracting tables from a PDF."""
    return TableExtractor.extract(file_path)
