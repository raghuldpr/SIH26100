import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.tender import Tender


class TenderRequirement(Base):
    """
    Tender Requirement entity representing an extracted compliance rule or eligibility criterion.
    Maintains structured rule parameters and verbatim evidence from the tender document.
    """

    __tablename__ = "tender_requirements"
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="check_tender_requirement_confidence_range",
        ),
        Index("ix_tender_requirements_tender_type", "tender_id", "requirement_type"),
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
        doc="Reference to parent Tender",
    )
    requirement_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Requirement category (e.g. FINANCIAL, EXPERIENCE, TECHNICAL, STATUTORY, etc.)",
    )
    rule: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Normalized rule identifier (e.g. MINIMUM_TURNOVER, SIMILAR_WORK_EXPERIENCE)",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Human-readable explanation of the requirement and conditions",
    )
    parameters: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        doc="Flexible parameter payload (thresholds, currency, years, exemptions, etc.)",
    )
    mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether this requirement is mandatory for bidder qualification",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        doc="Extraction confidence score between 0.0 and 1.0",
    )
    source_page: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        doc="1-indexed page number in source tender PDF where requirement was located",
    )
    source_section: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        doc="Identified section title or clause heading in source tender",
    )
    source_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Exact verbatim textual snippet from tender PDF acting as audit evidence",
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
    tender: Mapped["Tender"] = relationship(
        "Tender",
        back_populates="requirements",
    )

    def __repr__(self) -> str:
        return (
            f"<TenderRequirement id={self.id} tender_id={self.tender_id} "
            f"type={self.requirement_type} rule={self.rule} mandatory={self.mandatory}>"
        )
