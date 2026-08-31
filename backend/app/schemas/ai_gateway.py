from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RequirementType
from app.schemas.tender_requirement_normalizer import (
    NormalizationStatus,
    NormalizedRequirement,
)


class AmbiguousClauseRequest(BaseModel):
    """
    Strict payload for escalating an unresolvable or ambiguous clause to the AI Gateway.
    Requires an explicit escalation rationale to enforce AI minimalism.
    """

    clause_text: str = Field(
        ...,
        min_length=5,
        max_length=4000,
        description="Verbatim excerpt of the ambiguous clause",
    )
    reason_for_escalation: str = Field(
        ...,
        min_length=3,
        description="Explicit technical reason why deterministic logic could not resolve this clause",
    )
    source_page: Optional[int] = Field(
        None,
        ge=1,
        description="1-indexed source page number in the tender document",
    )
    source_section: Optional[str] = Field(
        None,
        description="Identified section heading if available",
    )
    candidate_type: Optional[str] = Field(
        None,
        description="Suggested requirement type from deterministic analysis if any",
    )
    known_context: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Any partially resolved key-value parameters or metadata",
    )

    @field_validator("reason_for_escalation")
    @classmethod
    def validate_reason_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("reason_for_escalation cannot be empty. Escalation requires explicit technical justification.")
        return v.strip()


class LLMClauseInterpretation(BaseModel):
    """
    Validated structured JSON output expected from Groq open-source models.
    """

    requirement_type: str = Field(
        ...,
        description="Standardized requirement type (e.g. FINANCIAL, EXPERIENCE, OEM, etc.)",
    )
    rule: str = Field(
        ...,
        description="Specific normalized rule identifier (e.g. AVERAGE_TURNOVER, OEM_AUTHORIZATION)",
    )
    description: str = Field(
        ...,
        description="Clear, structured description of the eligibility requirement",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured parameter dictionary (minimum, currency, period, etc.)",
    )
    is_mandatory: bool = Field(
        default=True,
        description="Whether this criterion is mandatory for bidder qualification",
    )
    is_interpretable: bool = Field(
        default=True,
        description="Set to false if clause is truly vacuous, contradictory, or lacks any compliance meaning",
    )
    interpretation_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model's self-assessed confidence in the correctness of this structured interpretation",
    )
    rationale: str = Field(
        ...,
        description="Brief audit explanation justifying why this classification and parameter set was derived",
    )

    model_config = ConfigDict(from_attributes=True)


class AIGatewayUsageMetadata(BaseModel):
    """
    Auditing and observability telemetry for every AI Gateway invocation.
    Does not log sensitive document content.
    """

    service: str = Field(
        default="tender_intelligence",
        description="Calling subsystem identifier",
    )
    reason_for_escalation: str = Field(
        ...,
        description="Justification provided by deterministic engine",
    )
    model: str = Field(
        ...,
        description="Groq model identifier used for inference (e.g. llama-3.3-70b-versatile)",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Invocation timestamp in UTC",
    )
    success: bool = Field(
        ...,
        description="Whether inference and validation succeeded",
    )
    latency_ms: float = Field(
        ...,
        ge=0.0,
        description="End-to-end request latency in milliseconds",
    )
    prompt_tokens: Optional[int] = Field(None, ge=0)
    completion_tokens: Optional[int] = Field(None, ge=0)
    total_tokens: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = Field(None)


class AIGatewayResponse(BaseModel):
    """
    Safe output container returned by AIGateway.
    Never executes database operations directly.
    """

    success: bool = Field(
        ...,
        description="Overall execution status",
    )
    interpretation: Optional[LLMClauseInterpretation] = Field(
        None,
        description="Validated structured clause interpretation if successful and interpretable",
    )
    metadata: AIGatewayUsageMetadata = Field(
        ...,
        description="Audit and telemetry metadata",
    )
    normalized_requirement: Optional[NormalizedRequirement] = Field(
        None,
        description="Constructed NormalizedRequirement ready for persistence consideration",
    )

    model_config = ConfigDict(from_attributes=True)
