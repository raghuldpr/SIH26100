import logging
import re
from pathlib import Path
from typing import Union

import pymupdf

from app.core.exceptions import (
    CorruptedPDFException,
    DocumentNotFoundException,
    EmptyPDFException,
    PasswordProtectedPDFException,
    UnsupportedDocumentException,
)
from app.schemas.extractor import PageExtractionResult, PDFExtractionResult

logger = logging.getLogger("document_engine.extractors.pdf")

# Standard PDF header signature
PDF_MAGIC_BYTES = b"%PDF-"
# Minimum alphanumeric characters to consider text meaningful
MIN_MEANINGFUL_CHARACTERS = 20


class PDFExtractor:
    """
    Robust native text extractor for PDF documents using PyMuPDF.
    Extracts text page-by-page, preserves metadata, and validates PDF integrity.
    """

    @classmethod
    def validate_pdf_file(cls, path: Path) -> None:
        """
        Validates file existence, non-emptiness, and PDF header signature.
        Raises appropriate exceptions if the file fails validation.
        """
        if not path.exists():
            raise DocumentNotFoundException(message=f"File not found: {path.name}")

        if not path.is_file():
            raise UnsupportedDocumentException(message=f"Path is not a regular file: {path.name}")

        file_size = path.stat().st_size
        if file_size == 0:
            raise EmptyPDFException(message="PDF file is empty (0 bytes)")

        # Inspect initial bytes for valid PDF header signature
        try:
            with open(path, "rb") as f:
                header = f.read(1024)
                if PDF_MAGIC_BYTES not in header:
                    raise UnsupportedDocumentException(
                        message=f"File '{path.name}' is not a valid PDF document (missing %PDF- header)"
                    )
        except (OSError, IOError) as e:
            logger.error(f"Failed reading file header for {path.name}: {e}")
            raise CorruptedPDFException(
                message=f"Unable to read file header: {path.name}", details=str(e)
            )

    @classmethod
    def is_meaningful_text(cls, pages: list[PageExtractionResult]) -> bool:
        """
        Evaluates whether the extracted text represents meaningful human-readable content
        rather than empty space, unreadable artifacts, or sparse punctuation.
        """
        combined_text = "".join(p.text for p in pages)
        # Filter for alphanumeric characters
        alphanumeric_chars = re.findall(r"\w", combined_text)
        return len(alphanumeric_chars) >= MIN_MEANINGFUL_CHARACTERS

    @classmethod
    def extract(cls, file_path: Union[str, Path]) -> PDFExtractionResult:
        """
        Safely opens and extracts text page-by-page from the provided PDF file.
        Never modifies the source file.
        """
        path = Path(file_path).resolve()
        cls.validate_pdf_file(path)

        doc = None
        try:
            try:
                doc = pymupdf.open(str(path))
            except pymupdf.FileDataError as e:
                logger.warning(f"PyMuPDF FileDataError opening {path.name}: {e}")
                raise CorruptedPDFException(
                    message=f"Corrupted or invalid PDF structure: {path.name}", details=str(e)
                )
            except Exception as e:
                logger.error(f"Unexpected error opening PDF {path.name}: {e}")
                raise CorruptedPDFException(
                    message=f"Failed to open PDF document: {path.name}", details=str(e)
                )

            # Check for encryption / password protection
            if getattr(doc, "is_encrypted", False) or getattr(doc, "needs_pass", False):
                logger.warning(f"Encrypted or password-protected PDF detected: {path.name}")
                raise PasswordProtectedPDFException(
                    message=f"PDF document is encrypted or password protected: {path.name}"
                )

            total_pages = doc.page_count
            if total_pages == 0:
                logger.warning(f"PDF has 0 pages: {path.name}")
                return PDFExtractionResult(
                    extraction_method="native_pdf",
                    pages=[],
                    total_pages=0,
                    total_characters=0,
                    has_meaningful_text=False,
                )

            pages_result: list[PageExtractionResult] = []
            total_characters = 0

            for page_idx in range(total_pages):
                page_number = page_idx + 1
                try:
                    page = doc.load_page(page_idx)
                    page_text = page.get_text("text") or ""
                except Exception as e:
                    logger.warning(f"Error extracting page {page_number} in {path.name}: {e}")
                    page_text = ""

                char_count = len(page_text)
                total_characters += char_count

                pages_result.append(
                    PageExtractionResult(
                        page_number=page_number,
                        text=page_text,
                        character_count=char_count,
                    )
                )

            has_meaningful = cls.is_meaningful_text(pages_result)

            logger.info(
                f"Successfully extracted {total_pages} page(s) ({total_characters} chars) "
                f"from {path.name}. Meaningful text: {has_meaningful}"
            )

            return PDFExtractionResult(
                extraction_method="native_pdf",
                pages=pages_result,
                total_pages=total_pages,
                total_characters=total_characters,
                has_meaningful_text=has_meaningful,
            )

        finally:
            if doc is not None:
                try:
                    doc.close()
                except Exception as e:
                    logger.debug(f"Error closing PDF document: {e}")


def extract_pdf_text(file_path: Union[str, Path]) -> PDFExtractionResult:
    """Convenience helper function for PDF extraction."""
    return PDFExtractor.extract(file_path)
