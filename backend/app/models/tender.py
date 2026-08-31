import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base
from app.models.enums import TenderStatus

if TYPE_CHECKING:
    from app.models.document import Document


class Tender(Base):
    """Tender procurement entity representing a published or draft RFP/GeM bid."""

    __tablename__ = "tenders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tender_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    organization: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, native_enum=False, length=50),
        nullable=False,
        default=TenderStatus.DRAFT,
        index=True,
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
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="tender",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tender id={self.id} tender_number={self.tender_number} status={self.status}>"
