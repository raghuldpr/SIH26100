import logging
from typing import Optional, Union
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.core.storage import storage_service
from app.crud.crud_document import crud_document
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus
from app.schemas.entities import StructuredDocumentOutput
from app.services.document_processing_pipeline import DocumentProcessingPipeline, processing_pipeline

logger = logging.getLogger("app.services.document_processing")


class DocumentProcessingService:
    """
    Service orchestrating document lifecycle transitions and AI/OCR processing.
    Ensures safe retry semantics, non-destructive failure handling,
    and PostgreSQL persistence of structured extracted data.
    """

    def __init__(self, pipeline: Optional[DocumentProcessingPipeline] = None):
        self.pipeline = pipeline or processing_pipeline

    def process_document(
        self,
        db: Session,
        document_id: Union[UUID, str],
        file_bytes: Optional[bytes] = None,
    ) -> Document:
        """
        Executes the full extraction & classification pipeline for a document record.
        Persists structured JSON data and updates processing status in PostgreSQL.
        """
        doc = crud_document.get_by_id(db, document_id=document_id)
        if not doc:
            raise NotFoundException(message=f"Document with ID '{document_id}' not found.")

        # 1. Update state to PROCESSING
        crud_document.update_processing(
            db=db,
            document_id=doc.id,
            processing_status=ProcessingStatus.PROCESSING,
            processing_error=None,
        )

        try:
            # 2. Fetch file content from Supabase Storage if not provided in memory
            content = file_bytes
            if content is None:
                content = storage_service.download(doc.storage_path)

            # 3. Run Pipeline (Text extraction -> OCR if required -> Classification -> Entity extraction)
            declared_type = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)
            result: StructuredDocumentOutput = self.pipeline.process(
                file_bytes=content,
                filename=doc.original_filename,
                mime_type=doc.mime_type,
                declared_document_type=declared_type,
            )

            # 4. Map classified type to DocumentType enum safely
            resolved_doc_type = doc.document_type
            if result.document_type and result.document_type != DocumentType.OTHER.value:
                try:
                    resolved_doc_type = DocumentType(result.document_type)
                except ValueError:
                    pass

            # 5. Persist success state and structured JSON in DB
            updated_doc = crud_document.update_processing(
                db=db,
                document_id=doc.id,
                processing_status=ProcessingStatus.PROCESSED,
                extracted_data=result.model_dump(),
                processing_error=None,
                document_type=resolved_doc_type,
            )
            logger.info(
                f"Successfully processed document [id={doc.id}, file={doc.original_filename}, "
                f"type={resolved_doc_type}, time={result.processing_time_ms}ms]"
            )
            return updated_doc or doc

        except Exception as exc:
            # 6. Failure handling (Non-destructive: preserves original file in storage & metadata in DB)
            err_msg = str(exc)[:500]
            logger.error(f"Document processing failed for [id={doc.id}, file={doc.original_filename}]: {err_msg}")
            updated_doc = crud_document.update_processing(
                db=db,
                document_id=doc.id,
                processing_status=ProcessingStatus.FAILED,
                processing_error=err_msg,
            )
            return updated_doc or doc

    def retry_processing(
        self,
        db: Session,
        document_id: Union[UUID, str],
    ) -> Document:
        """
        Retry helper that safely resets state and reruns the document processing pipeline.
        """
        logger.info(f"Retrying processing for document ID: {document_id}")
        return self.process_document(db=db, document_id=document_id)


# Default singleton instance
document_processing_service = DocumentProcessingService()
