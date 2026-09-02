from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus


class DocumentResponse(BaseModel):
    """Public representation of an uploaded document artifact."""

    id: UUID = Field(..., description="Unique document record identifier")
    tender_id: Optional[UUID] = Field(None, description="Associated Tender ID if applicable")
    bidder_id: Optional[UUID] = Field(None, description="Associated Bidder ID if applicable")
    original_filename: str = Field(..., description="Original filename uploaded by client")
    document_type: DocumentType = Field(..., description="Document classification type")
    mime_type: Optional[str] = Field(None, description="Validated MIME type")
    file_size: Optional[int] = Field(None, description="File payload size in bytes")
    sha256: Optional[str] = Field(None, description="SHA-256 cryptographic digest of document payload")
    storage_path: str = Field(..., description="Canonical cloud storage path")
    status: DocumentStatus = Field(..., description="Document lifecycle status")
    processing_status: ProcessingStatus = Field(
        default=ProcessingStatus.NOT_PROCESSED,
        description="Document processing / OCR pipeline status",
    )
    processing_error: Optional[str] = Field(None, description="Processing error or failure message")
    extracted_data: Optional[dict] = Field(None, description="Structured extracted key-value data")
    uploaded_at: Optional[datetime] = Field(None, description="Upload timestamp")
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last record update timestamp")
    download_url: Optional[str] = Field(None, description="Temporary pre-signed download URL")

    model_config = ConfigDict(from_attributes=True)



class DocumentUploadResponse(BaseModel):
    """Response returned upon single document upload."""

    success: bool = Field(True, description="Indicates upload success")
    document: DocumentResponse = Field(..., description="Created document metadata")
    message: Optional[str] = Field(None, description="Informational message")


class MultiDocumentUploadResponse(BaseModel):
    """Response returned upon uploading multiple documents simultaneously."""

    success: bool = Field(True, description="Indicates upload success")
    documents: List[DocumentResponse] = Field(default_factory=list, description="List of created document records")
    count: int = Field(0, description="Total number of documents successfully processed")
    message: Optional[str] = Field(None, description="Informational message")
