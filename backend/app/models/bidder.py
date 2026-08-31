import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base
from app.models.enums import BidderStatus

if TYPE_CHECKING:
    from app.models.compliance import BidderEvidenceModel, ComplianceResultModel
    from app.models.document import Document
    from app.models.tender import Tender
    from app.models.user import User



class TenderBidder(Base):
    """Association entity linking Tenders and participating Bidders."""

    __tablename__ = "tender_bidders"
    __table_args__ = (
        UniqueConstraint("tender_id", "bidder_id", name="uq_tender_bidder"),
    )

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
    bidder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bidders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="tender_bidders",
    )
    bidder: Mapped["Bidder"] = relationship(
        "Bidder",
        back_populates="tender_bidders",
    )

    def __repr__(self) -> str:
        return f"<TenderBidder tender_id={self.tender_id} bidder_id={self.bidder_id}>"


class Bidder(Base):
    """Bidder organization entity participating in procurement bids."""

    __tablename__ = "bidders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
        doc="Official registered corporate name of the bidder organization",
    )
    registration_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True,
        nullable=True,
        doc="Corporate registration or incorporation identifier",
    )
    gst_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        doc="Goods and Services Tax Identification Number (GSTIN)",
    )
    pan_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        nullable=True,
        doc="Permanent Account Number (PAN)",
    )
    udyam_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="MSME Udyam registration certificate number",
    )
    contact_person: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Primary point of contact name",
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True,
        doc="Official corporate or contact email",
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Primary contact telephone / mobile number",
    )
    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Registered postal/office address",
    )
    status: Mapped[BidderStatus] = mapped_column(
        Enum(BidderStatus, native_enum=False, length=50),
        nullable=False,
        default=BidderStatus.ACTIVE,
        index=True,
        doc="Current eligibility/operational status of the bidder",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Optional link to a platform user account",
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
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="bidders",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="bidder",
        cascade="all, delete-orphan",
    )
    tender_bidders: Mapped[List["TenderBidder"]] = relationship(
        "TenderBidder",
        back_populates="bidder",
        cascade="all, delete-orphan",
    )
    tenders: Mapped[List["Tender"]] = relationship(
        "Tender",
        secondary="tender_bidders",
        back_populates="bidders",
        viewonly=True,
    )
    evidence: Mapped[List["BidderEvidenceModel"]] = relationship(
        "BidderEvidenceModel",
        back_populates="bidder",
        cascade="all, delete-orphan",
    )
    compliance_results: Mapped[List["ComplianceResultModel"]] = relationship(
        "ComplianceResultModel",
        back_populates="bidder",
        cascade="all, delete-orphan",
    )


    def __init__(self, **kwargs):
        # Support backward-compatible organization_name parameter
        if "organization_name" in kwargs and "company_name" not in kwargs:
            kwargs["company_name"] = kwargs.pop("organization_name")
        super().__init__(**kwargs)

    @property
    def organization_name(self) -> str:
        """Backward compatibility alias for company_name."""
        return self.company_name

    @organization_name.setter
    def organization_name(self, value: str) -> None:
        self.company_name = value

    def __repr__(self) -> str:
        return f"<Bidder id={self.id} company={self.company_name} status={self.status}>"
