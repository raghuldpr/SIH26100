"""
Phase 12.7 — Verification Result Persistence, Audit Trail & Idempotency
verification.py: PostgreSQL / SQLAlchemy declarative models for verification executions and audit trail.

Preserves full traceability, auditability, and tamper-evident history:
- verification_executions: Persistent execution records containing final compliance, risk,
  granular requirement evaluations, agent results, and evidence snapshots.
- verification_audit_events: Immutable append-only lifecycle event logs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    JSON,
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


class VerificationExecution(Base):
    """
    Persistent record of a multi-agent verification execution and its finalized outcomes.
    Maintains request identity, status, overall compliance verdict, risk evaluation,
    and a tamper-evident SHA-256 result hash.
    """

    __tablename__ = "verification_executions"
    __table_args__ = (
        Index("ix_verification_executions_tender_bidder", "tender_id", "bidder_id"),
    )


    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    verification_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        doc="Canonical verification reference string (e.g. VER-XXXXXXXX)",
    )
    request_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
        doc="Correlation request ID",
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to target Tender",
    )
    bidder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bidders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Reference to target Bidder",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        default="QUEUED",
        doc="Execution lifecycle state: QUEUED, RUNNING, COMPLETED, FAILED, UNVERIFIED",
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Deterministic SHA-256 hash of canonical verification request payload",
    )
    result_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        doc="Deterministic SHA-256 digest of finalized logical verification output",
    )
    overall_compliance: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="Final compliance decision: COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, UNVERIFIED",
    )
    decision: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Overall qualification decision: QUALIFIED, NOT_QUALIFIED, CONDITIONALLY_QUALIFIED, MANUAL_REVIEW",
    )
    risk_level: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        doc="Composite risk level: LOW, MEDIUM, HIGH, CRITICAL, UNKNOWN",
    )
    risk_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Composite risk score (0.0 to 100.0)",
    )
    overall_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Composite confidence score (0.0 to 1.0)",
    )
    compliance_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Summary metrics: total, compliant, non_compliant, partially_compliant, unverified counts",
    )
    requirements: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Granular requirement evaluations with verbatim clause text and provenance references",
    )
    agent_results: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Normalized verification results returned from individual agents",
    )
    risk_assessment: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Detailed risk assessment breakdown, signals, drivers, and critical flags",
    )
    evidence_snapshot: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Safe snapshot of evidence records evaluated (references, hashes, fields, values)",
    )
    document_hashes: Mapped[Optional[Dict[str, str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Mapping of document IDs to SHA-256 origin hashes",
    )
    reasons: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        doc="High-level explanatory decision reasons",
    )
    failed_requirements: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        doc="List of failed requirement names",
    )
    warnings: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        doc="Non-fatal warnings and review items",
    )
    inconclusive_checks: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        doc="Inconclusive or unexecuted checks",
    )
    missing_documents: Mapped[Optional[List[str]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
        doc="Missing document notices",
    )
    error: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        doc="Sanitized failure details if verification execution failed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tender: Mapped["Tender"] = relationship("Tender", foreign_keys=[tender_id])
    bidder: Mapped["Bidder"] = relationship("Bidder", foreign_keys=[bidder_id])
    audit_events: Mapped[List["VerificationAuditEvent"]] = relationship(
        "VerificationAuditEvent",
        back_populates="verification",
        cascade="all, delete-orphan",
        order_by="VerificationAuditEvent.created_at.asc()",
    )

    def __repr__(self) -> str:
        return (
            f"<VerificationExecution id={self.id} verification_id='{self.verification_id}' "
            f"status='{self.status}' compliance='{self.overall_compliance}'>"
        )


class VerificationAuditEvent(Base):
    """
    Append-only immutable audit trail recording critical lifecycle events for a verification.
    Events: VERIFICATION_CREATED, VERIFICATION_STARTED, VERIFICATION_DISPATCHED,
            VERIFICATION_COMPLETED, VERIFICATION_FAILED, VERIFICATION_RETRIEVED.
    """

    __tablename__ = "verification_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    verification_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("verification_executions.verification_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Canonical verification identifier",
    )
    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="Target Tender UUID",
    )
    bidder_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        doc="Target Bidder UUID",
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        doc="Lifecycle event name",
    )
    result_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        doc="Result hash associated with event if completed",
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
        doc="Safe non-sensitive contextual metadata for the audit entry",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )



    # Relationships
    verification: Mapped["VerificationExecution"] = relationship(
        "VerificationExecution",
        back_populates="audit_events",
    )

    def __repr__(self) -> str:
        return (
            f"<VerificationAuditEvent id={self.id} verification_id='{self.verification_id}' "
            f"event_type='{self.event_type}'>"
        )
