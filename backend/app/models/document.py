import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base
from app.models.enums import DocumentType

if TYPE_CHECKING:
    from app.models.bidder import Bidder
    from app.models.tender import Tender


class Document(Base):
    """Document metadata entity representing RFP notices, bids, and uploaded artifacts."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bidder_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bidders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False, length=50),
        nullable=False,
        default=DocumentType.OTHER,
        index=True,
    )
    file_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        doc="Storage URI or local file system path",
    )
    mime_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    file_size: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        doc="File size in bytes",
    )
    uploaded_at: Mapped[datetime] = mapped_column(
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
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="documents",
    )
    bidder: Mapped[Optional["Bidder"]] = relationship(
        "Bidder",
        back_populates="documents",
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} file_name={self.file_name} type={self.document_type}>"
