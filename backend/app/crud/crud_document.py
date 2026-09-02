import logging
from typing import List, Optional, Tuple, Union
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus

logger = logging.getLogger("app.crud.document")


def get_document_by_id(db: Session, document_id: Union[UUID, str]) -> Optional[Document]:
    """
    Fetch a single document by primary key UUID.
    Returns None if not found or format is invalid.
    """
    if isinstance(document_id, str):
        try:
            document_id = UUID(document_id.strip())
        except (ValueError, AttributeError):
            return None
    stmt = select(Document).where(Document.id == document_id)
    return db.scalars(stmt).first()


def list_tender_documents(
    db: Session,
    tender_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[Document], int]:
    """
    Retrieves paginated list of documents uploaded for a specific Tender.
    """
    safe_skip = max(0, skip)
    safe_limit = max(1, min(limit, 100))

    query = select(Document).where(Document.tender_id == tender_id)
    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = db.scalar(count_stmt) or 0

    items_stmt = query.order_by(Document.created_at.desc()).offset(safe_skip).limit(safe_limit)
    items = list(db.scalars(items_stmt).all())

    return items, total_count


def list_bidder_documents(
    db: Session,
    bidder_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[Document], int]:
    """
    Retrieves paginated list of documents uploaded for a specific Bidder.
    """
    safe_skip = max(0, skip)
    safe_limit = max(1, min(limit, 100))

    query = select(Document).where(Document.bidder_id == bidder_id)
    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = db.scalar(count_stmt) or 0

    items_stmt = query.order_by(Document.created_at.desc()).offset(safe_skip).limit(safe_limit)
    items = list(db.scalars(items_stmt).all())

    return items, total_count


def create_document_metadata(
    db: Session,
    original_filename: str,
    storage_path: str,
    document_type: DocumentType,
    mime_type: Optional[str] = None,
    file_size: Optional[int] = None,
    sha256: Optional[str] = None,
    tender_id: Optional[UUID] = None,
    bidder_id: Optional[UUID] = None,
    status: DocumentStatus = DocumentStatus.ACTIVE,
    processing_status: ProcessingStatus = ProcessingStatus.NOT_PROCESSED,
    processing_error: Optional[str] = None,
    extracted_data: Optional[dict] = None,
) -> Document:
    """
    Persists document record in PostgreSQL.
    """
    db_doc = Document(
        original_filename=original_filename,
        storage_path=storage_path,
        document_type=document_type,
        mime_type=mime_type,
        file_size=file_size,
        sha256=sha256,
        tender_id=tender_id,
        bidder_id=bidder_id,
        status=status,
        processing_status=processing_status,
        processing_error=processing_error,
        extracted_data=extracted_data,
    )
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    logger.info(f"Document record created in DB [id={db_doc.id}, file={original_filename}]")
    return db_doc



def delete_document_record(db: Session, db_doc: Union[Document, UUID, str]) -> Document:
    """
    Deletes a document record from PostgreSQL.
    """
    if isinstance(db_doc, (UUID, str)):
        target_doc = get_document_by_id(db, db_doc)
        if not target_doc:
            raise NotFoundException(message=f"Document with ID '{db_doc}' not found.")
        db_doc = target_doc

    db.delete(db_doc)
    db.commit()
    logger.info(f"Document record deleted from DB [id={db_doc.id}]")
    return db_doc


def update_document_processing(

    db: Session,
    document_id: Union[UUID, str],
    processing_status: ProcessingStatus,
    extracted_data: Optional[dict] = None,
    processing_error: Optional[str] = None,
    document_type: Optional[DocumentType] = None,
) -> Optional[Document]:
    """
    Updates document processing status, extracted structured data,
    and optional error message in PostgreSQL.
    """
    doc = get_document_by_id(db, document_id)
    if not doc:
        return None

    doc.processing_status = processing_status
    if extracted_data is not None:
        doc.extracted_data = extracted_data
    doc.processing_error = processing_error

    if document_type is not None:
        doc.document_type = document_type

    db.add(doc)
    db.commit()
    db.refresh(doc)
    logger.info(
        f"Updated document processing state [id={doc.id}, status={processing_status}, type={doc.document_type}]"
    )
    return doc


class CRUDDocument:
    """Data layer operations for Document entities."""

    get_by_id = staticmethod(get_document_by_id)
    list_tender_documents = staticmethod(list_tender_documents)
    list_bidder_documents = staticmethod(list_bidder_documents)
    create_metadata = staticmethod(create_document_metadata)
    update_processing = staticmethod(update_document_processing)
    delete = staticmethod(delete_document_record)


crud_document = CRUDDocument()

