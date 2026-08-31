import logging
import time
from typing import List, Optional

from app.models.enums import DocumentType
from app.schemas.classification import ClassificationResult
from app.schemas.entities import ExtractedEntity, StructuredDocumentOutput
from app.schemas.ocr import OCRDocumentResult
from app.schemas.processing import ExtractionResult, TableData
from app.services.document_classifier import RuleBasedDocumentClassifier, document_classifier
from app.services.document_processor import DocumentProcessor, document_processor
from app.services.entity_extractor import DocumentEntityExtractor, entity_extractor
from app.services.ocr_pipeline import OCRPipeline, ocr_pipeline

logger = logging.getLogger("app.services.document_processing_pipeline")


class DocumentProcessingPipeline:
    """
    End-to-End Processing Subsystem for the SIH-26100 AI Compliance Platform.
    Unifies:
    File -> Text Extraction (PyMuPDF) -> OCR (OpenCV + PaddleOCR if required)
         -> Classification (RuleBased) -> Structured Entity Extraction -> JSON Output
    """

    def __init__(
        self,
        doc_processor: Optional[DocumentProcessor] = None,
        ocr_pipe: Optional[OCRPipeline] = None,
        classifier: Optional[RuleBasedDocumentClassifier] = None,
        extractor: Optional[DocumentEntityExtractor] = None,
    ):
        self.doc_processor = doc_processor or document_processor
        self.ocr_pipeline = ocr_pipe or ocr_pipeline
        self.classifier = classifier or document_classifier
        self.entity_extractor = extractor or entity_extractor

    def process(
        self,
        file_bytes: bytes,
        filename: Optional[str] = None,
        mime_type: Optional[str] = None,
        declared_document_type: Optional[str] = None,
    ) -> StructuredDocumentOutput:
        """
        Executes the full pipeline on a raw document payload and returns
        complete structured JSON output.
        """
        start_time = time.perf_counter()

        if not file_bytes:
            return StructuredDocumentOutput(
                document_type=DocumentType.OTHER.value,
                confidence=0.0,
                classification=ClassificationResult(
                    document_type=DocumentType.OTHER.value,
                    confidence=0.0,
                    matched_signals=[],
                    explanation="Empty file content provided.",
                ),
                entities={},
                tables=[],
                page_count=0,
                raw_text="",
                is_scanned=False,
                processing_time_ms=0.0,
            )

        # 1. Text Extraction (PyMuPDF / pdfplumber)
        extract_res: ExtractionResult = self.doc_processor.process_document(
            file_bytes=file_bytes,
            mime_type=mime_type,
            filename=filename,
        )

        extracted_text = extract_res.text or ""
        pages_text: List[str] = [p.text for p in extract_res.pages] if extract_res.pages else []
        tables: List[TableData] = extract_res.tables or []
        page_count = extract_res.page_count
        is_scanned = False

        # 2. OCR Fallback if text is absent or insufficient
        if extract_res.requires_ocr or (page_count > 0 and len(extracted_text.strip()) < 15):
            logger.info(f"Document '{filename or 'unknown'}' requires OCR. Initiating OCR pipeline...")
            ocr_res: OCRDocumentResult = self.ocr_pipeline.process_document(
                file_bytes=file_bytes,
                mime_type=mime_type,
                filename=filename,
            )
            if ocr_res.is_success and ocr_res.full_text:
                extracted_text = ocr_res.full_text
                pages_text = [p.text for p in ocr_res.pages]
                page_count = ocr_res.page_count
                is_scanned = True

        # 3. Document Classification
        classification_res: ClassificationResult = self.classifier.classify(
            text=extracted_text,
            filename=filename,
        )

        # If caller passed an explicit/declared document type and classification was ambiguous, respect it
        effective_type = classification_res.document_type
        if effective_type == DocumentType.OTHER.value and declared_document_type:
            effective_type = declared_document_type

        # 4. Entity Extraction
        entities: dict[str, ExtractedEntity] = self.entity_extractor.extract(
            document_type=effective_type,
            text=extracted_text,
            pages=pages_text,
        )

        total_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return StructuredDocumentOutput(
            document_type=effective_type,
            confidence=classification_res.confidence,
            classification=classification_res,
            entities=entities,
            tables=tables,
            page_count=page_count,
            raw_text=extracted_text,
            is_scanned=is_scanned,
            processing_time_ms=total_time_ms,
        )


# Default singleton instance
processing_pipeline = DocumentProcessingPipeline()
