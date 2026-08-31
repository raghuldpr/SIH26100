import logging
from typing import List, Optional, Tuple, Union
from uuid import UUID
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AppException,
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)

from app.core.storage import (
    generate_bidder_storage_path,
    generate_tender_storage_path,
    storage_service,
)
from app.core.validation import (
    ValidatedFile,
    validate_multiple_upload_files,
    validate_single_upload_file,
)
from app.crud.crud_bidder import get_bidder_by_id
from app.crud.crud_document import crud_document
from app.crud.crud_tender import get_tender_by_id
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus, UserRole
from app.models.user import User
from app.schemas.document import DocumentResponse

logger = logging.getLogger("app.services.document")


def enrich_document_response(doc: Document) -> DocumentResponse:
    """Enriches Document model instance with a pre-signed URL into DocumentResponse."""
    doc_resp = DocumentResponse.model_validate(doc)
    doc_resp.download_url = storage_service.get_signed_url(doc.storage_path)
    return doc_resp


def check_document_access(doc: Document, user: Optional[User], is_delete: bool = False) -> bool:
    """
    Evaluates whether the user is authorized to view or delete the document.
    - ADMIN: Full access.
    - PROCUREMENT_OFFICER, BUYER: Can view all and delete tender/bidder documents.
    - REVIEWER: Read-only access to documents.
    - BIDDER: Can view tender docs & own bidder docs; can only delete own bidder docs.
    """
    if user is None:
        return False

    if user.role == UserRole.ADMIN:
        return True

    if user.role in (UserRole.PROCUREMENT_OFFICER, UserRole.BUYER):
        return True

    if user.role == UserRole.REVIEWER:
        return not is_delete

    if user.role == UserRole.BIDDER:
        if not is_delete:
            # Can view tender documents
            if doc.tender_id is not None:
                return True
            # Can view own bidder documents
            if doc.bidder and doc.bidder.user_id == user.id:
                return True
            if getattr(user, "bidders", None) and doc.bidder_id in [b.id for b in user.bidders]:
                return True
            return False
        else:
            # Cannot delete tender documents
            if doc.tender_id is not None and doc.bidder_id is None:
                return False
            # Can only delete own bidder documents
            if doc.bidder and doc.bidder.user_id == user.id:
                return True
            if getattr(user, "bidders", None) and doc.bidder_id in [b.id for b in user.bidders]:
                return True
            return False

    return False



async def upload_tender_document(
    db: Session,
    tender_id: UUID,
    file: UploadFile,
    document_type: DocumentType = DocumentType.TENDER_PDF,
) -> DocumentResponse:
    """
    Validates, uploads, and persists a document for a specific Tender.
    Guarantees storage/database consistency via compensating rollback.
    """
    tender = get_tender_by_id(db, tender_id=tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    # 1. Validate file format, signature, size, and extension
    val_file: ValidatedFile = await validate_single_upload_file(file)

    # 2. Generate canonical, safe server-side storage path: tenders/{tender_id}/{filename}
    storage_path = generate_tender_storage_path(tender_id, val_file.filename)

    # 3. Upload binary content to Supabase Storage
    uploaded_path = storage_service.upload(
        storage_path=storage_path,
        file_content=val_file.content,
        mime_type=val_file.mime_type,
    )

    # 4. Save metadata in PostgreSQL
    try:
        doc = crud_document.create_metadata(
            db=db,
            original_filename=val_file.original_filename,
            storage_path=uploaded_path,
            document_type=document_type,
            mime_type=val_file.mime_type,
            file_size=val_file.file_size,
            tender_id=tender_id,
            status=DocumentStatus.UPLOADED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )
    except Exception as exc:
        # Compensating rollback: Delete orphaned object from storage
        logger.error(f"Database error during document record creation. Cleaning up storage: {exc}")
        storage_service.delete(uploaded_path)
        raise AppException(message="Failed to record document metadata in database.")

    return enrich_document_response(doc)


async def upload_multiple_tender_documents(
    db: Session,
    tender_id: UUID,
    files: List[UploadFile],
    document_type: DocumentType = DocumentType.TENDER_PDF,
) -> List[DocumentResponse]:
    """
    Validates, uploads, and persists multiple documents for a Tender.
    Supports partial failure safely with compensating rollback for failed items.
    """
    tender = get_tender_by_id(db, tender_id=tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    if not files:
        raise BadRequestException(message="No files provided for upload.")

    # Validate batch
    validated_files = await validate_multiple_upload_files(files)

    results: List[DocumentResponse] = []
    for val_file in validated_files:
        storage_path = generate_tender_storage_path(tender_id, val_file.filename)
        uploaded_path = storage_service.upload(
            storage_path=storage_path,
            file_content=val_file.content,
            mime_type=val_file.mime_type,
        )
        try:
            doc = crud_document.create_metadata(
                db=db,
                original_filename=val_file.original_filename,
                storage_path=uploaded_path,
                document_type=document_type,
                mime_type=val_file.mime_type,
                file_size=val_file.file_size,
                tender_id=tender_id,
                status=DocumentStatus.UPLOADED,
                processing_status=ProcessingStatus.NOT_PROCESSED,
            )
            results.append(enrich_document_response(doc))
        except Exception as exc:
            logger.error(f"Database error during batch document creation. Cleaning up storage: {exc}")
            storage_service.delete(uploaded_path)
            raise AppException(message=f"Failed to persist metadata for '{val_file.original_filename}'.")

    return results


async def upload_bidder_document(
    db: Session,
    bidder_id: UUID,
    file: UploadFile,
    document_type: DocumentType = DocumentType.OTHER,
) -> DocumentResponse:
    """
    Validates, uploads, and persists a compliance document for a Bidder.
    Guarantees storage/database consistency via compensating rollback.
    """
    bidder = get_bidder_by_id(db, bidder_id=bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    # 1. Validate file
    val_file: ValidatedFile = await validate_single_upload_file(file)

    # 2. Generate safe storage path: bidders/{bidder_id}/{document_type}/{filename}
    storage_path = generate_bidder_storage_path(
        bidder_id=bidder_id,
        document_type=document_type,
        filename=val_file.filename,
    )

    # 3. Upload to storage
    uploaded_path = storage_service.upload(
        storage_path=storage_path,
        file_content=val_file.content,
        mime_type=val_file.mime_type,
    )

    # 4. Save metadata in DB
    try:
        doc = crud_document.create_metadata(
            db=db,
            original_filename=val_file.original_filename,
            storage_path=uploaded_path,
            document_type=document_type,
            mime_type=val_file.mime_type,
            file_size=val_file.file_size,
            bidder_id=bidder_id,
            status=DocumentStatus.UPLOADED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )
    except Exception as exc:
        logger.error(f"Database error during document record creation. Cleaning up storage: {exc}")
        storage_service.delete(uploaded_path)
        raise AppException(message="Failed to record document metadata in database.")

    return enrich_document_response(doc)


async def upload_multiple_bidder_documents(
    db: Session,
    bidder_id: UUID,
    files: List[UploadFile],
    document_type: DocumentType = DocumentType.OTHER,
) -> List[DocumentResponse]:
    """
    Uploads multiple documents for a Bidder. Validates all files and persists records.
    """
    bidder = get_bidder_by_id(db, bidder_id=bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    if not files:
        raise BadRequestException(message="No files provided for upload.")

    validated_files = await validate_multiple_upload_files(files)

    results: List[DocumentResponse] = []
    for val_file in validated_files:
        storage_path = generate_bidder_storage_path(
            bidder_id=bidder_id,
            document_type=document_type,
            filename=val_file.filename,
        )
        uploaded_path = storage_service.upload(
            storage_path=storage_path,
            file_content=val_file.content,
            mime_type=val_file.mime_type,
        )
        try:
            doc = crud_document.create_metadata(
                db=db,
                original_filename=val_file.original_filename,
                storage_path=uploaded_path,
                document_type=document_type,
                mime_type=val_file.mime_type,
                file_size=val_file.file_size,
                bidder_id=bidder_id,
                status=DocumentStatus.UPLOADED,
                processing_status=ProcessingStatus.NOT_PROCESSED,
            )
            results.append(enrich_document_response(doc))
        except Exception as exc:
            logger.error(f"Database error during batch document creation. Cleaning up storage: {exc}")
            storage_service.delete(uploaded_path)
            raise AppException(message=f"Failed to persist metadata for '{val_file.original_filename}'.")

    return results


def list_tender_documents(
    db: Session,
    tender_id: UUID,
    skip: int = 0,
    limit: int = 50,
    current_user: Optional[User] = None,
) -> Tuple[List[DocumentResponse], int]:
    """Lists documents uploaded for a Tender."""
    tender = get_tender_by_id(db, tender_id=tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    docs, total = crud_document.list_tender_documents(db, tender_id=tender_id, skip=skip, limit=limit)
    return [enrich_document_response(d) for d in docs], total


def list_bidder_documents(
    db: Session,
    bidder_id: UUID,
    skip: int = 0,
    limit: int = 50,
    current_user: Optional[User] = None,
) -> Tuple[List[DocumentResponse], int]:
    """Lists documents uploaded for a Bidder."""
    bidder = get_bidder_by_id(db, bidder_id=bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    # If current_user is a BIDDER, verify they own this bidder record
    if current_user and current_user.role == UserRole.BIDDER:
        is_owner = (bidder.user_id == current_user.id) or (
            getattr(current_user, "bidders", None)
            and bidder_id in [b.id for b in current_user.bidders]
        )
        if not is_owner:
            raise ForbiddenException(message="You do not have permission to view this bidder's documents.")

    docs, total = crud_document.list_bidder_documents(db, bidder_id=bidder_id, skip=skip, limit=limit)
    return [enrich_document_response(d) for d in docs], total


def get_document(
    db: Session,
    document_id: UUID,
    current_user: Optional[User] = None,
) -> DocumentResponse:
    """Retrieves document metadata and pre-signed URL with authorization check."""
    doc = crud_document.get_by_id(db, document_id=document_id)
    if not doc:
        raise NotFoundException(message=f"Document with id '{document_id}' not found.")

    if current_user and not check_document_access(doc, current_user, is_delete=False):
        raise ForbiddenException(message="You do not have permission to view this document.")

    return enrich_document_response(doc)


def delete_document(
    db: Session,
    document_id: UUID,
    current_user: Optional[User] = None,
) -> bool:
    """
    Deletes a document from both cloud storage and PostgreSQL metadata
    with strict authorization enforcement.
    """
    doc = crud_document.get_by_id(db, document_id=document_id)
    if not doc:
        raise NotFoundException(message=f"Document with id '{document_id}' not found.")

    if current_user and not check_document_access(doc, current_user, is_delete=True):
        raise ForbiddenException(message="You do not have permission to delete this document.")

    storage_path = doc.storage_path

    # 1. Delete from database
    crud_document.delete(db, db_doc=doc)

    # 2. Delete from cloud storage
    storage_service.delete(storage_path)

    logger.info(f"Document successfully purged [id={document_id}, path={storage_path}]")
    return True

