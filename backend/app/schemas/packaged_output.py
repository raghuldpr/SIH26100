"""
SIH-26100 — Phase 11.9: Verification Output Packaging & Traceability Mapping
Canonical, API-friendly Pydantic schemas for the document intelligence pipeline.
Provides complete source provenance, deterministic vs AI resolution metadata,
and structured extraction summaries for downstream verification agents.
"""
from __future__ import annotations

from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ==============================================================================
# Document & Section Schemas
# ==============================================================================

class PackagedDocumentMetadata(BaseModel):
    """
    Sanitized document-level metadata without leaking raw filesystem or storage secrets.
    """

    document_id: Optional[str] = Field(
        None,
        description="Source document UUID",
    )
    document_hash: Optional[str] = Field(
        None,
        description="Cryptographic SHA-256 digest of the ingested document file",
    )
    document_type: str = Field(
        default="TENDER",
        description="Classified document type (e.g. TENDER, BIDDER_FINANCIAL, STATUTORY)",
    )
    processing_status: str = Field(
        default="COMPLETED",
        description="Lifecycle processing status (e.g. COMPLETED, FAILED, OCR_PROCESSED)",
    )
    original_filename: Optional[str] = Field(
        None,
        description="Original client-supplied filename",
    )
    file_size: Optional[int] = Field(
        None,
        ge=0,
        description="Document file size in bytes",
    )
    mime_type: Optional[str] = Field(
        None,
        description="Validated MIME type (e.g. application/pdf)",
    )

    model_config = ConfigDict(from_attributes=True)


class PackagedSection(BaseModel):
    """
    Bounded document section with page ranges, canonical type, and verbatim heading.
    """

    section_id: str = Field(
        ...,
        description="Unique canonical section identifier (e.g. sec_eligibility_001)",
    )
    name: str = Field(
        ...,
        description="Standardized human-readable section name",
    )
    section_type: str = Field(
        ...,
        description="Canonical classification (e.g. ELIGIBILITY_CRITERIA, FINANCIAL_REQUIREMENTS)",
    )
    heading_raw: Optional[str] = Field(
        None,
        description="Verbatim heading string as extracted from document layout",
    )
    page_start: int = Field(
        ...,
        ge=1,
        description="1-indexed starting page number",
    )
    page_end: int = Field(
        ...,
        ge=1,
        description="1-indexed ending page number",
    )
    source_reference: str = Field(
        ...,
        description="Traceable reference string (e.g. 'Page 3-5 - Section 2: Technical Eligibility')",
    )
    confidence: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Section detection confidence score",
    )

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Requirement Resolution & Traceability Schemas
# ==============================================================================

class RequirementResolution(BaseModel):
    """
    Explicit resolution outcome distinguishing deterministic logic from AI semantic fallback.
    """

    status: str = Field(
        ...,
        description="Resolution status: NORMALIZED, AI_RESOLVED, AMBIGUOUS, or UNRESOLVED",
    )
    method: str = Field(
        ...,
        description="Resolution mechanism: 'DETERMINISTIC', 'AI_GATEWAY', or 'UNRESOLVED'",
    )
    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Confidence rating (None for ambiguous clauses without statistical basis)",
    )
    reason: Optional[str] = Field(
        None,
        description="Audit explanation for ambiguous, unresolved, or AI-resolved criteria",
    )

    model_config = ConfigDict(from_attributes=True)


class RequirementAIMetadata(BaseModel):
    """
    Sanitized AI Gateway telemetry without exposing API keys or authorization headers.
    """

    provider: str = Field(
        default="groq",
        description="LLM Provider name",
    )
    model: Optional[str] = Field(
        None,
        description="Model identifier (e.g. llama-3.3-70b-versatile)",
    )
    prompt_tokens: Optional[int] = Field(
        None,
        ge=0,
        description="Token count for prompt input",
    )
    completion_tokens: Optional[int] = Field(
        None,
        ge=0,
        description="Token count for generated completion",
    )
    total_tokens: Optional[int] = Field(
        None,
        ge=0,
        description="Total tokens consumed",
    )
    latency_ms: Optional[float] = Field(
        None,
        ge=0.0,
        description="End-to-end LLM inference latency in milliseconds",
    )
    escalation_reason: Optional[str] = Field(
        None,
        description="Technical justification provided when escalating to AI Gateway",
    )

    model_config = ConfigDict(from_attributes=True)


class RequirementTraceability(BaseModel):
    """
    Complete audit trail and source evidence for an extracted requirement.
    """

    document_id: Optional[str] = Field(
        None,
        description="UUID of source document",
    )
    document_hash: Optional[str] = Field(
        None,
        description="SHA-256 cryptographic digest of originating document",
    )
    page_start: Optional[int] = Field(
        None,
        ge=1,
        description="1-indexed start page where requirement occurs",
    )
    page_end: Optional[int] = Field(
        None,
        ge=1,
        description="1-indexed end page if requirement spans pages",
    )
    source_page: Optional[int] = Field(
        None,
        ge=1,
        description="Primary 1-indexed source page number",
    )
    section_id: Optional[str] = Field(
        None,
        description="Associated section identifier",
    )
    source_section: Optional[str] = Field(
        None,
        description="Section heading context where requirement was detected",
    )
    source_text: str = Field(
        ...,
        min_length=1,
        description="Verbatim clause text from tender document serving as primary evidence",
    )
    extraction_method: str = Field(
        default="deterministic",
        description="Extraction method ('deterministic' or 'groq')",
    )
    ai_metadata: Optional[RequirementAIMetadata] = Field(
        None,
        description="AI telemetry metadata if resolved via AI Gateway; None for deterministic rules",
    )

    model_config = ConfigDict(from_attributes=True)


class PackagedRequirement(BaseModel):
    """
    Canonical requirement representation exposing full parameters, resolution status,
    and granular traceability for downstream verification agents.
    """

    requirement_id: str = Field(
        ...,
        description="Unique requirement identifier (UUID string or prefixed ID like REQ-001)",
    )
    category: str = Field(
        ...,
        description="Requirement category (e.g. FINANCIAL, EXPERIENCE, TECHNICAL, STATUTORY, DOCUMENT, OEM)",
    )
    type: str = Field(
        ...,
        description="Specific normalized rule key (e.g. AVERAGE_TURNOVER, EMD_REQUIREMENT, SIMILAR_WORK_EXPERIENCE)",
    )
    description: str = Field(
        ...,
        description="Structured, human-readable specification of the requirement",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Canonical parameter dictionary (minimum, currency, period, operator, etc.)",
    )
    mandatory: bool = Field(
        default=True,
        description="True if requirement is mandatory for bidder qualification",
    )
    resolution: RequirementResolution = Field(
        ...,
        description="Resolution status, method (DETERMINISTIC vs AI_GATEWAY), and confidence",
    )
    traceability: RequirementTraceability = Field(
        ...,
        description="Complete source lineage and evidence references",
    )

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Summary & Canonical Output
# ==============================================================================

class ExtractionSummary(BaseModel):
    """
    Deterministic summary counts of extracted and resolved requirements.
    Calculated directly from actual requirements list.
    """

    total_requirements: int = Field(
        default=0,
        ge=0,
        description="Total count of requirements in the document package",
    )
    deterministic_requirements: int = Field(
        default=0,
        ge=0,
        description="Count of requirements resolved 100% deterministically",
    )
    ai_resolved_requirements: int = Field(
        default=0,
        ge=0,
        description="Count of requirements resolved via AI Gateway semantic escalation",
    )
    ambiguous_requirements: int = Field(
        default=0,
        ge=0,
        description="Count of ambiguous criteria requiring buyer clarification",
    )
    failed_requirements: int = Field(
        default=0,
        ge=0,
        description="Count of criteria that failed parsing or grounding validation",
    )

    model_config = ConfigDict(from_attributes=True)


class DocumentTraceability(BaseModel):
    """
    Global document-level provenance summary.
    """

    document_id: Optional[str] = Field(
        None,
        description="Source document UUID",
    )
    document_hash: Optional[str] = Field(
        None,
        description="Cryptographic SHA-256 digest of original file",
    )
    total_pages: Optional[int] = Field(
        None,
        ge=0,
        description="Total page count of document",
    )
    total_sections: int = Field(
        default=0,
        ge=0,
        description="Total number of detected sections",
    )
    extraction_format: str = Field(
        default="PDF",
        description="Originating document file format (PDF, DOCX, XLSX, IMAGE)",
    )
    processed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of package generation",
    )

    model_config = ConfigDict(from_attributes=True)


class CanonicalDocumentOutput(BaseModel):
    """
    Phase 11.9 Canonical Structured Document Output.
    Encapsulates all extracted sections, normalized requirements, provenance mappings,
    and summary metrics ready for downstream consumption by Verification Agents.
    """

    document: PackagedDocumentMetadata = Field(
        ...,
        description="Sanitized document metadata",
    )
    sections: List[PackagedSection] = Field(
        default_factory=list,
        description="Sequence of detected document sections with page boundaries",
    )
    requirements: List[PackagedRequirement] = Field(
        default_factory=list,
        description="Structured, traceable eligibility and compliance criteria",
    )
    extraction_summary: ExtractionSummary = Field(
        ...,
        description="Calculated extraction breakdown counts",
    )
    traceability: DocumentTraceability = Field(
        ...,
        description="Document-wide provenance and hashing metadata",
    )

    model_config = ConfigDict(from_attributes=True)
