from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequirementType
from app.schemas.tender_requirement import TenderRequirementCreate


class NormalizationStatus(str, Enum):
    """Status of clause normalization and resolution."""
    NORMALIZED = "NORMALIZED"
    AI_RESOLVED = "AI_RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"
    UNSUPPORTED = "UNSUPPORTED"


class NormalizedRequirement(BaseModel):
    """
    Deterministically normalized or AI-resolved requirement ready for TenderRequirement persistence
    or marked as UNRESOLVED / AMBIGUOUS if thresholds cannot be reliably validated.
    """

    status: NormalizationStatus = Field(
        default=NormalizationStatus.NORMALIZED,
        description="Normalization state: NORMALIZED, AI_RESOLVED, AMBIGUOUS, or UNRESOLVED",
    )
    type: Optional[str] = Field(
        None,
        description="Normalized requirement type (FINANCIAL, EXPERIENCE, OEM, etc.)",
    )
    rule: Optional[str] = Field(
        None,
        description="Standardized rule identifier (e.g. AVERAGE_TURNOVER, OEM_AUTHORIZATION)",
    )
    description: Optional[str] = Field(
        None,
        description="Clean, structured requirement description",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured, canonical parameters (monetary values in INR, periods in years, etc.)",
    )
    mandatory: bool = Field(
        default=True,
        description="Whether this criterion is mandatory for qualification",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall extraction and normalization confidence rating",
    )
    source_page: Optional[int] = Field(
        None,
        description="1-indexed source page number in the tender document",
    )
    page_start: Optional[int] = Field(
        None,
        description="1-indexed start page for multi-page requirements",
    )
    page_end: Optional[int] = Field(
        None,
        description="1-indexed end page for multi-page requirements",
    )
    source_section: Optional[str] = Field(
        None,
        description="Source section heading (e.g. 'Eligibility Criteria')",
    )
    section_id: Optional[str] = Field(
        None,
        description="Section identifier from tender_section_detector",
    )
    document_id: Optional[str] = Field(
        None,
        description="Source document UUID",
    )
    source_text: str = Field(
        ...,
        description="Original verbatim excerpt from tender document serving as evidence",
    )
    requires_semantic_interpretation: bool = Field(
        default=False,
        description="True if clause is ambiguous and deferred to Phase 11.8 semantic LLM processing",
    )
    ambiguity_reason: Optional[str] = Field(
        None,
        description="Explanation if marked as AMBIGUOUS or UNRESOLVED",
    )
    resolution_method: str = Field(
        default="DETERMINISTIC",
        description="How this requirement was resolved ('DETERMINISTIC' or 'AI_GATEWAY')",
    )
    ai_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="AI model self-assessed confidence if resolved via AI Gateway",
    )
    escalation_reason: Optional[str] = Field(
        None,
        description="Technical justification provided when escalating to AI Gateway",
    )
    model_metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="AI model and telemetry metadata (provider, model, token usage, latency)",
    )

    model_config = ConfigDict(from_attributes=True)

    def to_tender_requirement_create(self) -> TenderRequirementCreate:
        """Converts normalized requirement to TenderRequirementCreate schema for DB persistence."""
        if self.status not in (NormalizationStatus.NORMALIZED, NormalizationStatus.AI_RESOLVED):
            raise ValueError(f"Cannot persist requirement with status '{self.status}'. Must be NORMALIZED or AI_RESOLVED.")
        return TenderRequirementCreate(
            requirement_type=self.type or RequirementType.OTHER.value,
            rule=self.rule or "GENERAL_REQUIREMENT",
            description=self.description or self.source_text,
            parameters=self.parameters,
            mandatory=self.mandatory,
            confidence=self.confidence if self.confidence is not None else 1.0,
            source_page=self.source_page,
            source_section=self.source_section,
            source_text=self.source_text,
        )


class NormalizationResult(BaseModel):
    """Batch normalization result across multiple candidate clauses."""

    total_evaluated: int = Field(default=0)
    normalized_count: int = Field(default=0)
    ai_resolved_count: int = Field(default=0)
    ambiguous_count: int = Field(default=0)
    unresolved_count: int = Field(default=0)
    requirements: List[NormalizedRequirement] = Field(default_factory=list)

    def normalized_only(self) -> List[NormalizedRequirement]:
        """Returns deterministic normalized requirements."""
        return [r for r in self.requirements if r.status == NormalizationStatus.NORMALIZED]

    def ai_resolved_only(self) -> List[NormalizedRequirement]:
        """Returns requirements successfully resolved via AI Gateway."""
        return [r for r in self.requirements if r.status == NormalizationStatus.AI_RESOLVED]

    def persistable_only(self) -> List[NormalizedRequirement]:
        """Returns all requirements eligible for DB persistence (NORMALIZED + AI_RESOLVED)."""
        return [r for r in self.requirements if r.status in (NormalizationStatus.NORMALIZED, NormalizationStatus.AI_RESOLVED)]

    def ambiguous_only(self) -> List[NormalizedRequirement]:
        """Returns ambiguous requirements before escalation."""
        return [r for r in self.requirements if r.status == NormalizationStatus.AMBIGUOUS]

    def unresolved_only(self) -> List[NormalizedRequirement]:
        """Returns unresolvable/rejected requirements."""
        return [r for r in self.requirements if r.status == NormalizationStatus.UNRESOLVED]
