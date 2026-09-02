import enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.normalized_content import (
    NormalizedCurrency,
    NormalizedDate,
    NormalizedNumber,
    NormalizedTable,
)


class SectionType(str, enum.Enum):
    """Canonical classification of procurement tender document sections."""

    TENDER_INFORMATION = "TENDER_INFORMATION"
    ELIGIBILITY_CRITERIA = "ELIGIBILITY_CRITERIA"
    TECHNICAL_REQUIREMENTS = "TECHNICAL_REQUIREMENTS"
    FINANCIAL_REQUIREMENTS = "FINANCIAL_REQUIREMENTS"
    EXPERIENCE = "EXPERIENCE"
    STATUTORY_REQUIREMENTS = "STATUTORY_REQUIREMENTS"
    REQUIRED_DOCUMENTS = "REQUIRED_DOCUMENTS"
    EMD = "EMD"
    PERFORMANCE_SECURITY = "PERFORMANCE_SECURITY"
    TERMS_AND_CONDITIONS = "TERMS_AND_CONDITIONS"
    SCOPE_OF_WORK = "SCOPE_OF_WORK"
    EVALUATION_CRITERIA = "EVALUATION_CRITERIA"
    OTHER = "OTHER"


class DetectedTenderSection(BaseModel):
    """
    Structured representation of a detected tender section.
    Preserves exact source traceability, page boundaries, raw heading text,
    and associated structured tables/currencies/dates.
    """

    section_id: str = Field(..., description="Unique section identifier")
    name: str = Field(..., description="Standardized canonical section name")
    section_type: SectionType = Field(..., description="Canonical section type classification")
    heading_raw: Optional[str] = Field(None, description="Original raw heading text from document")
    document_id: Optional[str] = Field(None, description="Associated document record UUID")
    page_start: int = Field(..., description="1-indexed starting page number")
    page_end: int = Field(..., description="1-indexed ending page number")
    source_reference: str = Field(..., description="Traceable source reference string (e.g. 'Page 1 - Section 1: Eligibility')")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Detection confidence score")
    text: str = Field("", description="Consolidated normalized text content of this section")
    tables: List[NormalizedTable] = Field(default_factory=list, description="Tables belonging to this section")
    currencies: List[NormalizedCurrency] = Field(default_factory=list, description="Currencies detected within this section")
    dates: List[NormalizedDate] = Field(default_factory=list, description="Dates detected within this section")
    numbers: List[NormalizedNumber] = Field(default_factory=list, description="Numbers detected within this section")


class TenderSectionDetectionResult(BaseModel):
    """Collection of detected tender sections across a document."""

    document_id: Optional[str] = Field(None, description="Associated document record UUID")
    total_sections: int = Field(0, description="Total number of sections identified")
    sections: List[DetectedTenderSection] = Field(default_factory=list, description="List of detected sections in reading order")
    unclassified_text: Optional[str] = Field(None, description="Text not attributed to any specific section")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional detection metadata")
