"""
Phase 09 — Compliance Rule Engine
compliance.py: PostgreSQL / SQLAlchemy declarative models for requirements, evidence, and results.

Preserves full auditability and historical integrity:
- requirements: Tender requirements with JSONB rule definitions.
- bidder_evidence: Normalized evidence submitted by bidders with JSONB value payloads.
- compliance_results: Evaluated compliance outcomes; historical evaluations are NEVER overwritten.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import UUID

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.bidder import Bidder
    from app.models.tender import Tender


class ComplianceRequirement(Base):
    """
    Tender compliance requirement persisted for deterministic rule engine evaluation.
    Contains structured rule definitions in JSONB format.
    """

    __tablename__ = "requirements"
    __table_args__ = (
        Index("ix_requirements_tender_category", "tender_id", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        default=uuid.uuid4,
        doc="Canonical requirement UUID, matches domain Requirement.requirement_id",
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to parent Tender",
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Requirement category (FINANCIAL, EXPERIENCE, TECHNICAL, STATUTORY, etc.)",
    )
    field: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        doc="Canonical field name for evidence matching (e.g. 'annual_turnover')",
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Rule type (NUMERIC, BOOLEAN, DATE_RANGE, DOCUMENT_PRESENCE, EXPERIENCE, LOGICAL, CONDITIONAL, EXEMPTION)",
    )
    rule_definition: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        doc="Structured rule parameters (operator, required_value, sub_rules, etc.)",
    )
    mandatory: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether this requirement is mandatory",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable explanation of requirement",
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
    tender: Mapped["Tender"] = relationship("Tender", back_populates="compliance_requirements")
    compliance_results: Mapped[List["ComplianceResultModel"]] = relationship(
        "ComplianceResultModel",
        back_populates="requirement",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceRequirement id={self.id} field='{self.field}' "
            f"rule_type='{self.rule_type}' mandatory={self.mandatory}>"
        )


class BidderEvidenceModel(Base):
    """
    Normalized bidder evidence submitted for compliance evaluation.
    Holds structured value payloads and extraction confidence.
    """

    __tablename__ = "bidder_evidence"
    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="check_bidder_evidence_confidence_range"),
        Index("ix_bidder_evidence_bidder_field", "bidder_id", "field"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        default=uuid.uuid4,
        doc="Canonical evidence UUID, matches domain BidderEvidence.evidence_id",
    )
    bidder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bidders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to Bidder organization submitting evidence",
    )
    field: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
        doc="Canonical field name matching requirement field",
    )
    value: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Extracted or declared value payload (scalar, dict, list, etc.)",
    )
    source_document: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Reference to the source document path or filename",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        doc="Extraction confidence score (0.0 to 1.0)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    bidder: Mapped["Bidder"] = relationship("Bidder", back_populates="evidence")

    def __repr__(self) -> str:
        return f"<BidderEvidenceModel id={self.id} bidder_id={self.bidder_id} field='{self.field}'>"


class ComplianceResultModel(Base):
    """
    Immutable historical record of a requirement evaluation against bidder evidence.
    Historical rows are NEVER overwritten to preserve audit integrity.
    """

    __tablename__ = "compliance_results"
    __table_args__ = (
        Index("ix_compliance_results_bidder_req", "bidder_id", "requirement_id"),
        Index("ix_compliance_results_evaluated_at", "evaluated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to evaluated requirement",
    )
    bidder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bidders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to Bidder whose evidence was evaluated",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        doc="Evaluation outcome: PASS, FAIL, REVIEW, EXEMPT, NOT_APPLICABLE",
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Deterministic human-readable explanation of the outcome",
    )
    evidence_reference: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        doc="Reference to the evidence used (document path, filename, or evidence_id)",
    )
    rule_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Rule type evaluated for auditability",
    )
    operator_used: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Comparison operator used during evaluation",
    )
    actual_value: Mapped[Optional[Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Audit snapshot of actual value evaluated",
    )
    required_value: Mapped[Optional[Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Audit snapshot of required threshold/condition evaluated",
    )
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp of evaluation",
    )


    # Relationships
    requirement: Mapped["ComplianceRequirement"] = relationship(
        "ComplianceRequirement",
        back_populates="compliance_results",
    )
    bidder: Mapped["Bidder"] = relationship(
        "Bidder",
        back_populates="compliance_results",
    )

    def __repr__(self) -> str:
        return (
            f"<ComplianceResultModel id={self.id} req_id={self.requirement_id} "
            f"bidder_id={self.bidder_id} status='{self.status}'>"
        )
