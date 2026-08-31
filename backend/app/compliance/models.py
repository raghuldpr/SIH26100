"""
Phase 09 — Compliance Rule Engine
models.py: Pydantic v2 value objects for the compliance engine.

All models are pure data containers (no SQLAlchemy).  They are decoupled
from the DB layer so the engine can be tested without a database.

Key models:
  RuleDefinition   — rule parameters (operator, value, unit, sub-rules …)
  Requirement      — normalised tender requirement ready for evaluation
  BidderEvidence   — a single piece of evidence from the bidder
  ComplianceResult — evaluation outcome (PASS / FAIL / REVIEW)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.compliance.enums import (
    ComplianceStatus,
    EvidenceSource,
    Operator,
    RuleType,
)
from app.models.enums import RequirementType


# ---------------------------------------------------------------------------
# RuleDefinition
# ---------------------------------------------------------------------------

class RuleDefinition(BaseModel):
    """
    Structured rule parameters that a specific evaluator needs.

    Generic fields cover most cases.  Evaluators may interpret `extra` for
    advanced or composite rule configurations.
    """

    operator: Operator = Field(
        ...,
        description="Comparison operator to apply (e.g. GREATER_THAN_OR_EQUAL)",
    )
    required_value: Optional[Any] = Field(
        default=None,
        description=(
            "The threshold or reference value for the comparison. "
            "For BETWEEN, supply [low, high].  For IN / NOT_IN, supply a list."
        ),
    )
    unit: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Unit of measurement (e.g. 'INR', 'years', 'projects')",
    )
    currency: Optional[str] = Field(
        default=None,
        max_length=10,
        description="ISO 4217 currency code when the rule is monetary (e.g. 'INR')",
    )
    sub_rules: Optional[List["RuleDefinition"]] = Field(
        default=None,
        description="Child rules for LOGICAL / CONDITIONAL evaluators",
    )
    logical_operator: Optional[str] = Field(
        default=None,
        description="'AND' or 'OR' for LOGICAL rules; 'IF' for CONDITIONAL",
    )
    extra: Dict[str, Any] = Field(
        default_factory=dict,
        description="Evaluator-specific overflow parameters",
    )

    model_config = ConfigDict(frozen=False)

    @field_validator("required_value", mode="before")
    @classmethod
    def _coerce_decimal_strings(cls, v: Any) -> Any:
        """
        Coerce string-encoded numbers to Decimal so rule definitions created
        from JSON are handled consistently.
        """
        if isinstance(v, str):
            cleaned = v.strip().replace(",", "")
            try:
                return Decimal(cleaned)
            except Exception:
                pass  # Leave non-numeric strings as-is (e.g. document type names)
        return v


# Allow self-reference for sub_rules
RuleDefinition.model_rebuild()


# ---------------------------------------------------------------------------
# Requirement
# ---------------------------------------------------------------------------

class Requirement(BaseModel):
    """
    A normalised tender requirement ready for compliance evaluation.

    This is a pure-Python value object mirroring the DB row shape of
    TenderRequirement (app.models.tender_requirement) without SQLAlchemy.
    Create from a TenderRequirement ORM object via Requirement.model_validate(orm_obj).
    """

    requirement_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique requirement identifier (mirrors TenderRequirement.id)",
    )
    tender_id: uuid.UUID = Field(
        ...,
        description="Parent tender identifier",
    )
    category: Union[RequirementType, str] = Field(
        ...,
        description="Requirement category (FINANCIAL, EXPERIENCE, TECHNICAL, etc.)",
    )
    field: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description=(
            "Canonical field name that should match the BidderEvidence.field "
            "(e.g. 'annual_turnover', 'gst_registered', 'pan_number')"
        ),
    )
    rule_type: RuleType = Field(
        ...,
        description="Evaluator dispatch key (NUMERIC, BOOLEAN, DOCUMENT_PRESENCE, etc.)",
    )
    rule_definition: RuleDefinition = Field(
        ...,
        description="Structured rule parameters consumed by the evaluator",
    )
    mandatory: bool = Field(
        default=True,
        description="When False a REVIEW result may be downgraded to NOT_APPLICABLE",
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable requirement description for audit logs",
    )

    model_config = ConfigDict(frozen=False, from_attributes=True)

    @field_validator("category", mode="before")
    @classmethod
    def _normalise_category(cls, v: Any) -> str:
        if hasattr(v, "value"):
            return str(v.value).upper()
        if isinstance(v, str):
            return v.strip().upper()
        raise ValueError(f"Invalid category: {v!r}")

    @field_validator("field", mode="before")
    @classmethod
    def _normalise_field(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower().replace(" ", "_")
            if not val:
                raise ValueError("field cannot be empty")
            return val
        raise ValueError(f"Invalid field: {v!r}")


# ---------------------------------------------------------------------------
# BidderEvidence
# ---------------------------------------------------------------------------

class BidderEvidence(BaseModel):
    """
    A single piece of compliance evidence submitted by a bidder.

    The engine evaluates one evidence item per requirement field.  If the
    bidder has multiple documents for the same field, the caller should
    pre-select the most relevant one (highest confidence, most recent, etc.)
    before passing to the engine.
    """

    evidence_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique evidence identifier",
    )
    bidder_id: uuid.UUID = Field(
        ...,
        description="Bidder whose evidence this is",
    )
    field: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Canonical field name (must match Requirement.field for evaluation)",
    )
    value: Optional[Any] = Field(
        default=None,
        description=(
            "Extracted or declared value for the field. "
            "May be Decimal, bool, str, int, float, date, list, or None."
        ),
    )
    source_document: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reference to the source document (filename, Supabase path, etc.)",
    )
    source: EvidenceSource = Field(
        default=EvidenceSource.UPLOADED_DOCUMENT,
        description="Provenance of the evidence value",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence (0.0–1.0). Below 0.5 may trigger REVIEW.",
    )
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the evidence was extracted or entered",
    )

    model_config = ConfigDict(frozen=False, from_attributes=True)

    @field_validator("field", mode="before")
    @classmethod
    def _normalise_field(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower().replace(" ", "_")
            if not val:
                raise ValueError("field cannot be empty")
            return val
        raise ValueError(f"Invalid field: {v!r}")

    @field_validator("confidence", mode="after")
    @classmethod
    def _validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be between 0.0 and 1.0, got {v}")
        return v


# ---------------------------------------------------------------------------
# ComplianceResult
# ---------------------------------------------------------------------------

class ComplianceResult(BaseModel):
    """
    The output of evaluating a single Requirement against a BidderEvidence.

    Immutable after creation (frozen=True) to prevent accidental mutation
    of audit records.
    """

    requirement_id: uuid.UUID = Field(
        ...,
        description="The requirement that was evaluated",
    )
    bidder_id: uuid.UUID = Field(
        ...,
        description="The bidder whose evidence was evaluated",
    )
    status: ComplianceStatus = Field(
        ...,
        description="Evaluation outcome (PASS / FAIL / REVIEW / EXEMPT / NOT_APPLICABLE)",
    )
    reason: str = Field(
        ...,
        min_length=1,
        description="Human-readable, deterministic explanation of the outcome",
    )
    evidence_reference: Optional[str] = Field(
        default=None,
        description=(
            "Reference to the evidence used (document path, evidence_id, etc.). "
            "None when evidence was absent."
        ),
    )
    evaluated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of evaluation",
    )
    rule_type: Optional[RuleType] = Field(
        default=None,
        description="Rule type that produced this result (for audit / debugging)",
    )
    operator_used: Optional[Operator] = Field(
        default=None,
        description="Operator applied during evaluation (for audit / debugging)",
    )
    actual_value: Optional[Any] = Field(
        default=None,
        description="The actual evidence value that was compared (for audit)",
    )
    required_value: Optional[Any] = Field(
        default=None,
        description="The required threshold / reference value (for audit)",
    )

    model_config = ConfigDict(frozen=True)

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def external_status(self) -> ComplianceStatus:
        """EXEMPT / NOT_APPLICABLE map to PASS for external callers."""
        return self.status.external_status

    @property
    def is_pass(self) -> bool:
        """True when the decision should be treated as passing."""
        return self.status.is_passing

    @property
    def is_fail(self) -> bool:
        """True for a hard, definitive failure."""
        return self.external_status == ComplianceStatus.FAIL

    @property
    def is_review(self) -> bool:
        """True when human review is required."""
        return self.external_status == ComplianceStatus.REVIEW

    @property
    def is_definitive(self) -> bool:
        """True when the result is not REVIEW (i.e. a hard PASS or FAIL)."""
        return self.status.is_definitive

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def pass_result(
        cls,
        requirement_id: uuid.UUID,
        bidder_id: uuid.UUID,
        reason: str,
        *,
        evidence_reference: Optional[str] = None,
        rule_type: Optional[RuleType] = None,
        operator_used: Optional[Operator] = None,
        actual_value: Optional[Any] = None,
        required_value: Optional[Any] = None,
    ) -> "ComplianceResult":
        return cls(
            requirement_id=requirement_id,
            bidder_id=bidder_id,
            status=ComplianceStatus.PASS,
            reason=reason,
            evidence_reference=evidence_reference,
            rule_type=rule_type,
            operator_used=operator_used,
            actual_value=actual_value,
            required_value=required_value,
        )

    @classmethod
    def fail_result(
        cls,
        requirement_id: uuid.UUID,
        bidder_id: uuid.UUID,
        reason: str,
        *,
        evidence_reference: Optional[str] = None,
        rule_type: Optional[RuleType] = None,
        operator_used: Optional[Operator] = None,
        actual_value: Optional[Any] = None,
        required_value: Optional[Any] = None,
    ) -> "ComplianceResult":
        return cls(
            requirement_id=requirement_id,
            bidder_id=bidder_id,
            status=ComplianceStatus.FAIL,
            reason=reason,
            evidence_reference=evidence_reference,
            rule_type=rule_type,
            operator_used=operator_used,
            actual_value=actual_value,
            required_value=required_value,
        )

    @classmethod
    def review_result(
        cls,
        requirement_id: uuid.UUID,
        bidder_id: uuid.UUID,
        reason: str,
        *,
        evidence_reference: Optional[str] = None,
        rule_type: Optional[RuleType] = None,
        operator_used: Optional[Operator] = None,
        actual_value: Optional[Any] = None,
        required_value: Optional[Any] = None,
    ) -> "ComplianceResult":
        return cls(
            requirement_id=requirement_id,
            bidder_id=bidder_id,
            status=ComplianceStatus.REVIEW,
            reason=reason,
            evidence_reference=evidence_reference,
            rule_type=rule_type,
            operator_used=operator_used,
            actual_value=actual_value,
            required_value=required_value,
        )

    @classmethod
    def exempt_result(
        cls,
        requirement_id: uuid.UUID,
        bidder_id: uuid.UUID,
        reason: str,
        *,
        evidence_reference: Optional[str] = None,
        rule_type: Optional[RuleType] = None,
    ) -> "ComplianceResult":
        return cls(
            requirement_id=requirement_id,
            bidder_id=bidder_id,
            status=ComplianceStatus.EXEMPT,
            reason=reason,
            evidence_reference=evidence_reference,
            rule_type=rule_type,
        )

    @classmethod
    def not_applicable_result(
        cls,
        requirement_id: uuid.UUID,
        bidder_id: uuid.UUID,
        reason: str,
        *,
        rule_type: Optional[RuleType] = None,
    ) -> "ComplianceResult":
        return cls(
            requirement_id=requirement_id,
            bidder_id=bidder_id,
            status=ComplianceStatus.NOT_APPLICABLE,
            reason=reason,
            rule_type=rule_type,
        )
