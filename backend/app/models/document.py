import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base
from app.models.enums import DocumentProcessingStatus, DocumentStatus, DocumentType, ProcessingStatus

if TYPE_CHECKING:
    from app.models.bidder import Bidder
    from app.models.tender import Tender


class Document(Base):
    """
    Document metadata entity representing uploaded artifacts for Tenders and Bidders.
    Actual binary payloads are persisted in Supabase Storage.
    """

    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "tender_id IS NOT NULL OR bidder_id IS NOT NULL",
            name="check_document_has_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    bidder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bidders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False, length=50),
        nullable=False,
        default=DocumentType.OTHER,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Original client-supplied file name before server-side path generation",
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        doc="Canonical Supabase Storage object path",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Validated MIME type (e.g., application/pdf)",
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        doc="File payload size in bytes",
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=50),
        nullable=False,
        default=DocumentStatus.ACTIVE,
        index=True,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, native_enum=False, length=50),
        nullable=False,
        default=ProcessingStatus.NOT_PROCESSED,
        index=True,
    )
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Error message or exception details if document processing/OCR fails",
    )
    extracted_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Structured OCR extractions and parsed compliance key-value payload",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tender: Mapped[Optional["Tender"]] = relationship(
        "Tender",
        back_populates="documents",
    )
    bidder: Mapped[Optional["Bidder"]] = relationship(
        "Bidder",
        back_populates="documents",
    )

    def __init__(self, **kwargs):
        # Support backward-compatible file_name and file_path parameters
        if "file_name" in kwargs and "original_filename" not in kwargs:
            kwargs["original_filename"] = kwargs.pop("file_name")
        if "file_path" in kwargs and "storage_path" not in kwargs:
            kwargs["storage_path"] = kwargs.pop("file_path")
        super().__init__(**kwargs)

    @property
    def file_name(self) -> str:
        """Backward compatibility alias for original_filename."""
        return self.original_filename

    @file_name.setter
    def file_name(self, value: str) -> None:
        self.original_filename = value

    @property
    def file_path(self) -> str:
        """Backward compatibility alias for storage_path."""
        return self.storage_path

    @file_path.setter
    def file_path(self, value: str) -> None:
        self.storage_path = value

    def __repr__(self) -> str:
        return (
            f"<Document id={self.id} file={self.original_filename} "
            f"type={self.document_type} status={self.status} "
            f"proc_status={self.processing_status}>"
        )
