from datetime import datetime
from typing import Any, Dict, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import RequirementType


class TenderRequirementBase(BaseModel):
    """Base schema for tender eligibility and compliance requirements."""

    requirement_type: Union[RequirementType, str] = Field(
        ...,
        description="Requirement category (e.g. FINANCIAL, EXPERIENCE, TECHNICAL, etc.)",
    )
    rule: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Normalized rule key (e.g. MINIMUM_TURNOVER, SIMILAR_WORK_EXPERIENCE)",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="Human-readable description and explanation of requirement",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Flexible parameter map (thresholds, currency, years, exemptions, etc.)",
    )
    mandatory: bool = Field(
        default=True,
        description="Whether this criterion is mandatory for qualification",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Extraction confidence rating between 0.0 and 1.0",
    )
    source_page: Optional[int] = Field(
        default=None,
        ge=1,
        description="1-indexed source page number in tender document",
    )
    source_section: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Identified section heading or clause identifier",
    )
    source_text: Optional[str] = Field(
        default=None,
        description="Verbatim excerpt from tender PDF used as evidence",
    )

    @field_validator("requirement_type", mode="before")
    @classmethod
    def normalize_requirement_type(cls, v: Any) -> str:
        """Ensures requirement type is normalized to uppercase string."""
        if hasattr(v, "value"):
            return str(v.value).upper()
        if isinstance(v, str):
            val = v.strip().upper()
            if not val:
                raise ValueError("requirement_type cannot be empty")
            return val
        raise ValueError(f"Invalid requirement_type: {v}")

    @field_validator("rule", mode="before")
    @classmethod
    def normalize_rule(cls, v: Any) -> str:
        """Trims and normalizes rule string."""
        if isinstance(v, str):
            val = v.strip()
            if not val:
                raise ValueError("rule cannot be empty")
            return val
        raise ValueError(f"Invalid rule: {v}")


class TenderRequirementCreate(TenderRequirementBase):
    """Schema for creating a new tender requirement."""
    pass


class TenderRequirementUpdate(BaseModel):
    """Schema for updating an existing tender requirement."""

    requirement_type: Optional[Union[RequirementType, str]] = None
    rule: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, min_length=1)
    parameters: Optional[Dict[str, Any]] = None
    mandatory: Optional[bool] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    source_page: Optional[int] = Field(None, ge=1)
    source_section: Optional[str] = Field(None, max_length=255)
    source_text: Optional[str] = None

    @field_validator("requirement_type", mode="before")
    @classmethod
    def normalize_opt_requirement_type(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if hasattr(v, "value"):
            return str(v.value).upper()
        if isinstance(v, str):
            val = v.strip().upper()
            if not val:
                raise ValueError("requirement_type cannot be empty")
            return val
        return v


class TenderRequirementResponse(TenderRequirementBase):
    """Public representation of an extracted or configured tender requirement."""

    id: UUID = Field(..., description="Unique requirement ID")
    tender_id: UUID = Field(..., description="Parent Tender ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)
