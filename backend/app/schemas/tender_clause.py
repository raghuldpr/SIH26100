from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequirementType


class ClauseCandidate(BaseModel):
    """
    Candidate tender eligibility/compliance clause extracted deterministically.
    Preserves verbatim source text, section context, and audit reasoning.
    """

    page: int = Field(
        ...,
        ge=1,
        description="1-indexed page number in the source tender document",
    )
    page_start: Optional[int] = Field(
        None,
        description="1-indexed start page if clause spans multiple pages",
    )
    page_end: Optional[int] = Field(
        None,
        description="1-indexed end page if clause spans multiple pages",
    )
    section: Optional[str] = Field(
        None,
        description="Identified section heading (e.g. 'Eligibility Criteria')",
    )
    section_id: Optional[str] = Field(
        None,
        description="Canonical section identifier from tender_section_detector",
    )
    document_id: Optional[str] = Field(
        None,
        description="Associated source document UUID",
    )
    source_text: str = Field(
        ...,
        min_length=1,
        description="Verbatim extracted sentence/clause from the tender",
    )
    candidate_type: str = Field(
        ...,
        description="Classified requirement type (e.g. FINANCIAL, EXPERIENCE, OEM, etc.)",
    )
    detection_reason: str = Field(
        ...,
        description="Explainable deterministic heuristic trigger (e.g. 'turnover + monetary threshold + period')",
    )
    detected_keywords: List[str] = Field(
        default_factory=list,
        description="Specific keywords and pattern indicators matched in the clause",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Detection confidence rating based on pattern density and section reinforcement",
    )
    rule: Optional[str] = Field(
        None,
        description="Suggested normalized rule identifier (e.g. 'MINIMUM_ANNUAL_TURNOVER')",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured parameter attributes parsed deterministically (amounts, years, etc.)",
    )
    is_mandatory: bool = Field(
        default=True,
        description="Whether this clause indicates a mandatory requirement or an exemption/waiver",
    )
    extraction_method: str = Field(
        default="deterministic",
        description="Extraction method ('deterministic' or 'ai_gateway')",
    )
    requires_semantic_interpretation: bool = Field(
        default=False,
        description="True if clause is ambiguous and deferred to semantic LLM interpretation",
    )

    model_config = ConfigDict(from_attributes=True)


class ClauseExtractionResult(BaseModel):
    """Aggregated output of the deterministic clause extraction process."""

    total_candidates: int = Field(
        ...,
        ge=0,
        description="Total number of candidate clauses identified",
    )
    candidates: List[ClauseCandidate] = Field(
        default_factory=list,
        description="Ordered list of candidate clauses with provenance",
    )
    sections_detected: List[str] = Field(
        default_factory=list,
        description="List of document sections identified during document traversal",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Processing latency in milliseconds",
    )

    def by_type(self, candidate_type: str) -> List[ClauseCandidate]:
        """Filters candidate clauses by requirement type."""
        target = candidate_type.strip().upper()
        return [c for c in self.candidates if c.candidate_type == target]

    def mandatory_only(self) -> List[ClauseCandidate]:
        """Returns only mandatory candidate clauses."""
        return [c for c in self.candidates if c.is_mandatory]

    def exemptions_only(self) -> List[ClauseCandidate]:
        """Returns only exemption/relaxation candidate clauses."""
        return [c for c in self.candidates if c.candidate_type == RequirementType.EXEMPTION.value or not c.is_mandatory]
