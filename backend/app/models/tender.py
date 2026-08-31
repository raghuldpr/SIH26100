import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base
from app.models.enums import TenderStatus

if TYPE_CHECKING:
    from app.models.bidder import Bidder, TenderBidder
    from app.models.document import Document
    from app.models.user import User


class Tender(Base):
    """Tender procurement entity representing a published or draft RFP/GeM bid."""

    __tablename__ = "tenders"
    __table_args__ = (
        CheckConstraint(
            "bid_end_date >= bid_start_date",
            name="check_tender_bid_end_after_start_date",
        ),
    )

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
        doc="Unique official tender reference number",
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
        doc="Procuring organization name",
    )
    department: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
        default="General",
        doc="Procuring department / division",
    )
    category: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        default="General",
        doc="Procurement item/service classification category",
    )
    bid_start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="Bid submission commencement datetime (UTC)",
    )
    bid_end_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        doc="Bid submission deadline datetime (UTC)",
    )
    status: Mapped[TenderStatus] = mapped_column(
        Enum(TenderStatus, native_enum=False, length=50),
        nullable=False,
        default=TenderStatus.DRAFT,
        index=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="User ID of the creating procurement officer",
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
    creator: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="created_tenders",
        foreign_keys=[created_by],
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="tender",
        cascade="all, delete-orphan",
    )
    tender_bidders: Mapped[List["TenderBidder"]] = relationship(
        "TenderBidder",
        back_populates="tender",
        cascade="all, delete-orphan",
    )
    bidders: Mapped[List["Bidder"]] = relationship(
        "Bidder",
        secondary="tender_bidders",
        back_populates="tenders",
        viewonly=True,
    )

    def __repr__(self) -> str:
        return f"<Tender id={self.id} tender_number={self.tender_number} status={self.status}>"

