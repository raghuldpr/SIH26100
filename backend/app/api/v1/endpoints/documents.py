from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.dependencies.auth import get_current_user, require_role
from app.dependencies.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import StandardResponse
from app.schemas.document import DocumentResponse

from app.services.document_processing_service import document_processing_service
from app.services.document_service import (
    check_document_access,
    delete_document,
    enrich_document_response,
    get_document,
)

documents_router = APIRouter(
    prefix="/documents",
    tags=["documents"],
)


@documents_router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Metadata & Access URL",
    description="Retrieves metadata and a secure pre-signed download URL for a document by ID.",
)
def get_document_endpoint(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Fetches document metadata and temporary signed URL."""
    return get_document(db=db, document_id=document_id, current_user=current_user)


@documents_router.post(
    "/{document_id}/process",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Document OCR & Structured Processing",
    description="Triggers the OCR, classification, and structured entity extraction pipeline for a document.",
)
def process_document_endpoint(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Processes document and stores extracted structured data in PostgreSQL."""
    doc = get_document(db=db, document_id=document_id, current_user=current_user)
    processed_doc = document_processing_service.process_document(db=db, document_id=document_id)
    return enrich_document_response(processed_doc)


@documents_router.post(
    "/{document_id}/retry",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retry Document Processing",
    description="Retries document OCR and extraction after a previous failure.",
)
def retry_document_endpoint(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Retries processing on a document."""
    doc = get_document(db=db, document_id=document_id, current_user=current_user)
    retried_doc = document_processing_service.retry_processing(db=db, document_id=document_id)
    return enrich_document_response(retried_doc)


@documents_router.delete(
    "/{document_id}",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Delete Document",
    description="Permanently removes a document from both cloud storage and PostgreSQL metadata.",
)
def delete_document_endpoint(
    document_id: UUID,
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN, UserRole.BUYER, UserRole.BIDDER)
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[dict]:
    """Deletes document metadata and cloud storage payload with authorization checks."""
    delete_document(db=db, document_id=document_id, current_user=current_user)
    return StandardResponse[dict](
        success=True,
        data={"document_id": str(document_id)},
        message="Document successfully deleted from storage and metadata.",
    )


