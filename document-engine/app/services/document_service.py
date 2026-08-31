import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pymupdf

from app.classifiers.document_classifier import DocumentClassifier
from app.core.config import settings
from app.core.exceptions import DocumentEngineException
from app.extractors.pdf_extractor import PDFExtractor
from app.extractors.table_extractor import TableExtractor
from app.ocr.ocr_engine import OCREngine
from app.preprocessing.image_processor import ImageProcessor, SUPPORTED_IMAGE_EXTENSIONS
from app.schemas.unified import (
    ExtractionSummary,
    ProcessingMetadata,
    UnifiedDocumentResponse,
    UnifiedPageExtraction,
)
from app.services.structured_extractor import StructuredExtractor

logger = logging.getLogger("document_engine.service")


class DocumentService:
    """
    Unified document processing pipeline orchestrator.
    Combines validation, format routing, native/OCR extraction, table parsing,
    document classification, and structured attribute extraction.
    """

    @classmethod
    def render_pdf_page_to_image(cls, page: pymupdf.Page, temp_dir: Path) -> Path:
        """Renders a PDF page to a temporary raster image file for preprocessing and OCR."""
        temp_dir.mkdir(parents=True, exist_ok=True)
        img_path = temp_dir / f"rendered_{uuid.uuid4().hex}.png"
        pix = page.get_pixmap(dpi=200)
        pix.save(str(img_path))
        return img_path

    @classmethod
    def process_document(
        cls, file_path: Union[str, Path], filename: Optional[str] = None
    ) -> UnifiedDocumentResponse:
        """
        Executes the end-to-end processing pipeline on a single document.
        Measures processing duration and returns a consolidated JSON response.
        Never modifies the original source file.
        """
        start_time = time.perf_counter()
        doc_id = str(uuid.uuid4())
        path = Path(file_path).resolve()
        doc_filename = filename or path.name

        temp_scratch_files: List[Path] = []

        try:
            if not path.exists():
                raise FileNotFoundError(f"Document file not found: {path.name}")

            is_pdf = path.suffix.lower() == ".pdf"
            is_image = path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS

            if not is_pdf and not is_image:
                raise ValueError(
                    f"Unsupported file format '{path.suffix}'. Expected PDF or image."
                )

            extracted_text = ""
            pages_summary: List[UnifiedPageExtraction] = []
            extracted_tables: List[Dict[str, Any]] = []
            method_used = "native_pdf"
            ocr_performed = False
            total_pages = 0

            # -------------------------------------------------------------
            # PDF Processing Branch
            # -------------------------------------------------------------
            if is_pdf:
                # 1. Attempt native text extraction
                pdf_result = PDFExtractor.extract(path)
                total_pages = pdf_result.total_pages

                # 2. Extract tables via pdfplumber
                try:
                    table_result = TableExtractor.extract(path)
                    extracted_tables = [t.model_dump() for t in table_result.tables]
                except Exception as e:
                    logger.warning(f"Table extraction bypassed on {path.name}: {e}")
                    extracted_tables = []

                if pdf_result.has_meaningful_text and total_pages > 0:
                    method_used = "native_pdf"
                    ocr_performed = False
                    extracted_text = "\n\n".join(p.text for p in pdf_result.pages)
                    pages_summary = [
                        UnifiedPageExtraction(
                            page_number=p.page_number,
                            text=p.text,
                            character_count=p.character_count,
                        )
                        for p in pdf_result.pages
                    ]
                else:
                    # 3. Insufficient or zero text: fallback to render + preprocess + OCR
                    logger.info(f"Insufficient native text in {path.name}. Initiating OCR pipeline.")
                    method_used = "ocr"
                    ocr_performed = True

                    doc = pymupdf.open(str(path))
                    page_texts = []

                    try:
                        for page_idx in range(len(doc)):
                            page = doc[page_idx]
                            page_num = page_idx + 1

                            # Render page to raster image
                            rendered_img = cls.render_pdf_page_to_image(page, settings.temp_path)
                            temp_scratch_files.append(rendered_img)

                            # OpenCV preprocessing
                            proc_res = ImageProcessor.process(rendered_img)
                            if proc_res.processed_image_path:
                                temp_scratch_files.append(Path(proc_res.processed_image_path))
                                ocr_target = proc_res.processed_image_path
                            else:
                                ocr_target = str(rendered_img)

                            # OCR Engine
                            p_text = OCREngine.extract_text(ocr_target)
                            page_texts.append(p_text)
                            pages_summary.append(
                                UnifiedPageExtraction(
                                    page_number=page_num,
                                    text=p_text,
                                    character_count=len(p_text),
                                )
                            )
                    finally:
                        doc.close()

                    extracted_text = "\n\n".join(page_texts)

            # -------------------------------------------------------------
            # Image Processing Branch
            # -------------------------------------------------------------
            else:
                total_pages = 1
                method_used = "ocr"
                ocr_performed = True

                # OpenCV preprocessing
                proc_res = ImageProcessor.process(path)
                if proc_res.processed_image_path:
                    temp_scratch_files.append(Path(proc_res.processed_image_path))
                    ocr_target = proc_res.processed_image_path
                else:
                    ocr_target = str(path)

                # OCR text extraction
                extracted_text = OCREngine.extract_text(ocr_target)
                pages_summary = [
                    UnifiedPageExtraction(
                        page_number=1,
                        text=extracted_text,
                        character_count=len(extracted_text),
                    )
                ]
                extracted_tables = []

            # -------------------------------------------------------------
            # Classification
            # -------------------------------------------------------------
            classification = DocumentClassifier.classify_text(extracted_text)
            doc_type = classification.document_type
            confidence = classification.confidence

            # -------------------------------------------------------------
            # Structured Information Extraction
            # -------------------------------------------------------------
            structured = StructuredExtractor.extract_structured_data(
                extracted_text, doc_type=doc_type
            )

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            return UnifiedDocumentResponse(
                document_id=doc_id,
                filename=doc_filename,
                document_type=doc_type,
                classification_confidence=confidence,
                pages=total_pages,
                extraction=ExtractionSummary(
                    method=method_used,
                    ocr_used=ocr_performed,
                    text=extracted_text,
                    pages=pages_summary,
                ),
                tables=extracted_tables,
                data=structured.data,
                processing=ProcessingMetadata(
                    status="completed",
                    processing_time_ms=elapsed_ms,
                    message="Document successfully processed.",
                ),
            )

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            err_code = getattr(e, "code", type(e).__name__)
            err_msg = str(e)
            logger.error(f"Processing failed for {doc_filename}: [{err_code}] {err_msg}")

            return UnifiedDocumentResponse(
                document_id=doc_id,
                filename=doc_filename,
                document_type="UNKNOWN",
                classification_confidence=0.0,
                pages=0,
                extraction=ExtractionSummary(
                    method="unknown",
                    ocr_used=False,
                    text="",
                    pages=[],
                ),
                tables=[],
                data={},
                processing=ProcessingMetadata(
                    status="failed",
                    processing_time_ms=elapsed_ms,
                    error_code=err_code,
                    message=err_msg,
                ),
            )

        finally:
            # Safely clean up intermediate rendered/preprocessed scratch files
            for scratch_file in temp_scratch_files:
                if scratch_file.exists():
                    try:
                        scratch_file.unlink()
                    except OSError as e:
                        logger.debug(f"Failed cleaning intermediate file {scratch_file}: {e}")


def process_document(
    file_path: Union[str, Path], filename: Optional[str] = None
) -> UnifiedDocumentResponse:
    """Convenience helper for unified document pipeline execution."""
    return DocumentService.process_document(file_path, filename=filename)
