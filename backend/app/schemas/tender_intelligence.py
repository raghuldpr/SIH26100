from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tender_requirement import TenderRequirementResponse
from app.schemas.tender_requirement_normalizer import NormalizedRequirement


class TenderAnalysisRequest(BaseModel):
    """Optional configuration for triggering tender intelligence analysis."""

    document_id: Optional[UUID] = Field(
        None,
        description="ID of specific tender document to analyze if tender has multiple attachments",
    )
    raw_text: Optional[str] = Field(
        None,
        description="Optional raw text payload to analyze directly without document storage lookup",
    )
    force_reanalyze: bool = Field(
        default=False,
        description="If true, clears existing requirements and re-runs full analysis",
    )


class TenderComplianceProfileResponse(BaseModel):
    """
    Structured Tender Compliance Profile answering: 'What does this tender require?'
    Clearly delineates deterministic, AI-assisted, and unresolved criteria with audit provenance.
    """

    tender_id: UUID = Field(..., description="Tender primary key identifier")
    tender_number: str = Field(..., description="Official tender identifier (e.g. GEM/2026/B/...)")
    status: str = Field(
        ...,
        description="Analysis processing status: COMPLETED, NOT_ANALYZED, or FAILED",
    )
    requirement_count: int = Field(
        ...,
        ge=0,
        description="Total count of active compliance requirements",
    )
    deterministic_count: int = Field(
        default=0,
        ge=0,
        description="Count of requirements resolved with 100% deterministic rules",
    )
    ai_escalations: int = Field(
        default=0,
        ge=0,
        description="Count of requirements resolved via controlled AI Gateway escalation",
    )
    unresolved_count: int = Field(
        default=0,
        ge=0,
        description="Count of ambiguous criteria that could not be validated",
    )
    deterministic_requirements: List[TenderRequirementResponse] = Field(
        default_factory=list,
        description="Deterministic requirements",
    )
    ai_assisted_requirements: List[TenderRequirementResponse] = Field(
        default_factory=list,
        description="AI-assisted requirements with full model telemetry",
    )
    unresolved_requirements: List[NormalizedRequirement] = Field(
        default_factory=list,
        description="Criteria marked UNRESOLVED requiring manual buyer review",
    )
    requirements: List[TenderRequirementResponse] = Field(
        default_factory=list,
        description="Consolidated list of all persisted compliance requirements",
    )
    analyzed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when analysis was generated",
    )

    model_config = ConfigDict(from_attributes=True)
