"""
Phase 10 — n8n ↔ FastAPI Verification Integration Schemas
schemas/verification.py: Strongly typed Pydantic models for verification requests,
n8n webhook payloads, agent-level results, compliance decisions, and API responses.

Strictly aligned with the live n8n Master Orchestrator and child agent contracts.
"""
from __future__ import annotations

from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional, Union
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ==============================================================================
# Enumerations
# ==============================================================================

class VerificationStatusEnum(str, enum.Enum):
    """Overall lifecycle status of a verification request."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    ERROR = "ERROR"



class VerificationDecisionEnum(str, enum.Enum):
    """Synthesized qualification decision produced by Final Compliance Agent."""
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    CONDITIONALLY_QUALIFIED = "CONDITIONALLY_QUALIFIED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class RiskLevelEnum(str, enum.Enum):
    """Categorical risk classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class VerificationAgentEnum(str, enum.Enum):
    """Canonical identifier for all specialized verification agents."""
    TENDER_INTELLIGENCE_AGENT = "TENDER_INTELLIGENCE_AGENT"
    GST_AGENT = "GST_AGENT"
    PAN_AGENT = "PAN_AGENT"
    UDYAM_AGENT = "UDYAM_AGENT"
    FINANCIAL_AGENT = "FINANCIAL_AGENT"
    EXPERIENCE_AGENT = "EXPERIENCE_AGENT"
    DOCUMENT_FORENSICS_AGENT = "DOCUMENT_FORENSICS_AGENT"
    ENTITY_RESOLUTION_AGENT = "ENTITY_RESOLUTION_AGENT"
    RISK_INTELLIGENCE_AGENT = "RISK_INTELLIGENCE_AGENT"
    FINAL_COMPLIANCE_AGENT = "FINAL_COMPLIANCE_AGENT"


class AgentStatusEnum(str, enum.Enum):
    """Outcome status returned by an individual specialized agent."""
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    ERROR = "ERROR"
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    REVIEW = "REVIEW"
    WARNING = "WARNING"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"
    NOT_EXECUTED = "NOT_EXECUTED"
    FAILED = "FAILED"
    QUALIFIED = "QUALIFIED"


class OverallComplianceEnum(str, enum.Enum):
    """Separate compliance verdict distinct from risk."""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    UNVERIFIED = "UNVERIFIED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RequirementComplianceEnum(str, enum.Enum):
    """Requirement-level verification outcome."""
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    UNVERIFIED = "UNVERIFIED"




# Default list of all active verification agents dispatched for full verification
DEFAULT_VERIFICATION_AGENTS: List[str] = [
    VerificationAgentEnum.TENDER_INTELLIGENCE_AGENT.value,
    VerificationAgentEnum.GST_AGENT.value,
    VerificationAgentEnum.PAN_AGENT.value,
    VerificationAgentEnum.UDYAM_AGENT.value,
    VerificationAgentEnum.FINANCIAL_AGENT.value,
    VerificationAgentEnum.EXPERIENCE_AGENT.value,
    VerificationAgentEnum.DOCUMENT_FORENSICS_AGENT.value,
    VerificationAgentEnum.ENTITY_RESOLUTION_AGENT.value,
    VerificationAgentEnum.RISK_INTELLIGENCE_AGENT.value,
    VerificationAgentEnum.FINAL_COMPLIANCE_AGENT.value,
]


# ==============================================================================
# Domain Input Sub-Schemas (Context passed to n8n)
# ==============================================================================

class DocumentForensicInput(BaseModel):
    """Document artifact descriptor passed to Document Forensics Agent."""
    document_id: str = Field(..., description="Unique document artifact identifier")
    document_type: str = Field("OTHER", description="Classification type (e.g. GST_CERTIFICATE, PAN_CARD, etc.)")
    file_name: str = Field(..., description="Original filename")
    mime_type: Optional[str] = Field("application/pdf", description="MIME content type")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    storage_path: Optional[str] = Field(None, description="Supabase or local storage object key/path")
    sha256: Optional[str] = Field(None, description="SHA-256 hash for tamper detection")
    pdf_readable: Optional[bool] = Field(True, description="Whether document text/PDF stream is readable")
    page_count: Optional[int] = Field(None, ge=1, description="Number of pages in document")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Embedded PDF metadata (dates, producer, creator)")
    ocr_text: Optional[str] = Field(None, description="Extracted OCR text payload")
    extracted_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Structured parsed key-values from OCR")

    model_config = ConfigDict(extra="ignore")


class FinancialRequirementsInput(BaseModel):
    """Tender financial threshold requirements passed to Financial Agent."""
    average_turnover: Optional[float] = Field(None, ge=0, description="Minimum required average annual turnover (INR)")
    minimum_annual_turnover: Optional[float] = Field(None, ge=0, description="Minimum turnover threshold for every single year")
    minimum_net_worth: Optional[float] = Field(None, description="Minimum required net worth (INR)")
    minimum_working_capital: Optional[float] = Field(None, description="Minimum required working capital (INR)")
    turnover_period_years: Optional[int] = Field(3, ge=1, le=10, description="Evaluation period in years (default: 3)")

    model_config = ConfigDict(extra="ignore")


class FinancialEvidenceInput(BaseModel):
    """Bidder financial evidence submitted or resolved from MCA/audited records."""
    turnover: Optional[Union[Dict[str, float], List[float]]] = Field(
        None,
        description="Annual turnover figures mapped by FY string (e.g. {'2023-24': 1800000}) or sequence list",
    )
    net_worth: Optional[float] = Field(None, description="Audited net worth (INR)")
    working_capital: Optional[float] = Field(None, description="Audited working capital (INR)")
    balance_sheet_filed: Optional[bool] = Field(None, description="Whether audited balance sheet is filed")
    ca_certified: Optional[bool] = Field(None, description="Whether filings are Chartered Accountant certified")
    udin: Optional[str] = Field(None, description="18-character ICAI Unique Document Identification Number (UDIN)")

    model_config = ConfigDict(extra="ignore")


class ProjectExperienceItem(BaseModel):
    """Individual past completed project item submitted as experience evidence."""
    project_id: str = Field(..., description="Unique project reference identifier")
    project_name: Optional[str] = Field(None, description="Title or description of past contract/project")
    client_name: Optional[str] = Field(None, description="Procuring client / government department")
    project_value: float = Field(..., ge=0, description="Contract/project monetary value (INR)")
    completion_date: str = Field(..., description="Project completion date (YYYY-MM-DD or ISO string)")
    similarity: bool = Field(True, description="Whether project meets domain technical similarity criteria")
    is_similar: Optional[bool] = Field(None, description="Alias for similarity")
    completion_certificate: bool = Field(True, description="Whether mandatory completion certificate is attached")
    has_certificate: Optional[bool] = Field(None, description="Alias for completion_certificate")
    certificate_document_id: Optional[str] = Field(None, description="Reference document ID of certificate")

    model_config = ConfigDict(extra="ignore")


class ExperienceRequirementsInput(BaseModel):
    """Tender experience criteria passed to Experience & Eligibility Agent."""
    minimum_similar_works: int = Field(3, ge=0, description="Minimum number of qualifying completed projects required")
    minimum_project_value: float = Field(0.0, ge=0, description="Minimum threshold value for each qualifying project (INR)")
    experience_period_years: int = Field(5, ge=1, le=20, description="Cutoff lookback period in years (default: 5)")
    require_completion_certificate: bool = Field(True, description="Whether valid completion certificate is mandatory")
    similarity_required: bool = Field(True, description="Whether technical similarity is enforced")

    model_config = ConfigDict(extra="ignore")


class ExperienceEvidenceInput(BaseModel):
    """Bidder past performance projects container."""
    projects: List[ProjectExperienceItem] = Field(default_factory=list, description="List of submitted past projects")

    model_config = ConfigDict(extra="ignore")


class CompliancePolicyInput(BaseModel):
    """Custom policy overrides for the Final Compliance Agent."""
    mandatory_agents: Optional[List[str]] = Field(None, description="List of agents that must pass for QUALIFIED verdict")
    allow_review_status: bool = Field(False, description="Whether REVIEW/WARNING agent status can qualify conditionally")
    maximum_review_risk_score: float = Field(49.0, ge=0, le=100, description="Risk score threshold below which REVIEW is permitted")

    model_config = ConfigDict(extra="ignore")


class TenderRequirementItemInput(BaseModel):
    """
    Normalized requirement item mapped directly from tender_requirements.
    Preserves all Phase 11 extraction parameters and verbatim clause traceability.
    """
    requirement_id: str = Field(..., description="Unique requirement identifier")
    category: str = Field(..., description="Requirement category (FINANCIAL, EXPERIENCE, TECHNICAL, etc.)")
    requirement_type: str = Field(..., description="Normalized requirement type string")
    rule: str = Field(..., description="Canonical rule name (e.g. MINIMUM_TURNOVER, SIMILAR_WORK_EXPERIENCE)")
    description: Optional[str] = Field(None, description="Human-readable requirement summary")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Structured rule evaluation parameters")
    mandatory: bool = Field(True, description="Whether this requirement is strictly mandatory")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)")
    source_page: Optional[int] = Field(None, description="Tender document page where clause was found")
    source_section: Optional[str] = Field(None, description="Tender document section title")
    source_text: Optional[str] = Field(None, description="Verbatim clause text from tender")
    resolution_method: str = Field("DETERMINISTIC", description="Extraction method (DETERMINISTIC or GROQ_ASSISTED)")

    model_config = ConfigDict(extra="ignore")


class BidderEvidenceItemInput(BaseModel):
    """
    Structured compliance evidence item mapped from bidder_evidence records.
    Maintains cryptographic and textual provenance back to the original bidder document.
    """
    evidence_id: str = Field(..., description="Unique evidence record identifier")
    bidder_id: str = Field(..., description="Bidder UUID string")
    tender_id: Optional[str] = Field(None, description="Associated tender UUID string")
    document_id: Optional[str] = Field(None, description="Source document artifact UUID")
    field: str = Field(..., description="Canonical evidence field name (e.g. pan, gstin, turnover)")
    value: Any = Field(..., description="Structured evidence payload or scalar value")
    source_document: Optional[str] = Field(None, description="Origin filename or storage path")
    source_page: Optional[int] = Field(None, description="Page number of origin document")
    source_text: Optional[str] = Field(None, description="Verbatim matched text in document")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)")
    document_hash: Optional[str] = Field(None, description="Deterministic SHA-256 hash of origin document")
    extraction_method: str = Field("DETERMINISTIC", description="Extraction method (DETERMINISTIC or GROQ_ASSISTED)")

    model_config = ConfigDict(extra="ignore")


# ==============================================================================
# 1. FastAPI Verification Trigger Request (React -> FastAPI)
# ==============================================================================

class VerificationTriggerRequest(BaseModel):
    """
    API payload submitted from frontend to initiate bid verification.
    FastAPI will gather database records and forward the structured payload to n8n.
    """
    tender_id: uuid.UUID = Field(..., description="Target tender UUID")
    bidder_id: uuid.UUID = Field(..., description="Target bidder UUID to verify")
    required_agents: Optional[List[str]] = Field(
        None,
        description="Optional subset of agents to execute. Defaults to all 10 agents if omitted.",
    )
    financial_overrides: Optional[FinancialRequirementsInput] = Field(
        None,
        description="Optional override for tender financial criteria",
    )
    experience_overrides: Optional[ExperienceRequirementsInput] = Field(
        None,
        description="Optional override for tender experience criteria",
    )
    compliance_policy: Optional[CompliancePolicyInput] = Field(
        None,
        description="Optional compliance policy configuration",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional client contextual metadata (UI correlation, user notes, etc.)",
    )

    model_config = ConfigDict(extra="ignore")


# ==============================================================================
# 2. Structured n8n Request Payload (FastAPI -> n8n Webhook)
# ==============================================================================

class N8nVerificationPayload(BaseModel):
    """
    Strongly typed payload dispatched from FastAPI to the n8n Master Orchestrator webhook.
    Strictly conforms to the input validation node in master_orchestrator_prototype.json.
    """
    request_id: str = Field(..., description="Unique request tracking correlation ID (e.g. REQ-...)")
    verification_id: Optional[str] = Field(None, description="Pre-allocated verification identifier")
    tender_id: str = Field(..., description="Tender identifier or UUID string")
    tender_number: Optional[str] = Field(None, description="Official tender publication number")
    tender_title: Optional[str] = Field(None, description="Tender title / subject")
    bidder_id: str = Field(..., description="Bidder identifier or UUID string")
    bidder_name: str = Field(..., min_length=1, description="Official registered corporate name of bidder")
    required_agents: List[str] = Field(
        default_factory=lambda: list(DEFAULT_VERIFICATION_AGENTS),
        description="Array of verification agents to execute",
    )
    # Statutory Identifiers
    gstin: Optional[str] = Field(None, description="GSTIN (15-character statutory ID)")
    pan: Optional[str] = Field(None, description="PAN (10-character statutory ID)")
    udyam: Optional[str] = Field(None, description="MSME Udyam registration certificate number")
    cin: Optional[str] = Field(None, description="Corporate Identification Number (CIN)")

    # Specialized Agent Context
    documents: Optional[List[DocumentForensicInput]] = Field(
        default_factory=list,
        description="Document metadata and OCR payloads for Forensics & Entity Resolution",
    )
    tender_requirements: List[TenderRequirementItemInput] = Field(
        default_factory=list,
        description="Comprehensive array of all persisted tender requirements and clauses",
    )
    bidder_evidence: List[BidderEvidenceItemInput] = Field(
        default_factory=list,
        description="Comprehensive array of all structured bidder compliance evidence records",
    )
    financial_requirements: Optional[FinancialRequirementsInput] = Field(
        None,
        description="Tender financial eligibility thresholds",
    )
    financial_evidence: Optional[FinancialEvidenceInput] = Field(
        None,
        description="Bidder submitted financial values",
    )
    experience_requirements: Optional[ExperienceRequirementsInput] = Field(
        None,
        description="Tender experience eligibility criteria",
    )
    experience_evidence: Optional[ExperienceEvidenceInput] = Field(
        None,
        description="Bidder past project experience records",
    )
    compliance_policy: Optional[CompliancePolicyInput] = Field(
        None,
        description="Policy constraints for final qualification synthesis",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Correlation metadata (timestamps, initiator user_id, environment)",
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of request dispatch",
    )


    @field_validator("required_agents", mode="before")
    @classmethod
    def validate_required_agents(cls, v: Any) -> List[str]:
        if not v:
            return list(DEFAULT_VERIFICATION_AGENTS)
        if isinstance(v, list):
            clean_list = [str(item).strip().upper() for item in v if str(item).strip()]
            return clean_list if clean_list else list(DEFAULT_VERIFICATION_AGENTS)
        return list(DEFAULT_VERIFICATION_AGENTS)

    model_config = ConfigDict(extra="ignore")


# ==============================================================================
# 3. n8n Agent Result Schema (Child agent output in n8n)
# ==============================================================================

class N8nAgentResult(BaseModel):
    """
    Standardized result contract returned by every specialized n8n verification agent.
    Matches normalized_results in master_orchestrator_prototype.json while preserving
    Phase 12.5 and 12.6 agent execution metadata and provenance.
    """
    agent: str = Field(..., description="Name of the reporting agent (e.g. GST_AGENT, FINANCIAL_AGENT)")
    agent_name: Optional[str] = Field(None, description="Canonical name alias of reporting agent")
    status: str = Field(..., description="Outcome: PASS, FAIL, PARTIAL, UNKNOWN, ERROR, WARNING, INCONCLUSIVE, VERIFIED, NOT_VERIFIED, NOT_EXECUTED")
    verification_id: Optional[str] = Field(None, description="Correlated verification execution reference ID")
    tender_id: Optional[str] = Field(None, description="Tender ID reference")
    bidder_id: Optional[str] = Field(None, description="Bidder ID reference")
    decision: Optional[str] = Field(None, description="Granular agent qualification decision")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Verification confidence score (0.0 - 1.0)")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Structured verified evidence key-values")
    evidence_ids: List[str] = Field(default_factory=list, description="Associated evidence IDs")
    requirement_ids: List[str] = Field(default_factory=list, description="Associated requirement IDs")
    source_documents: List[str] = Field(default_factory=list, description="Source document references or IDs")
    findings: List[str] = Field(default_factory=list, description="Identified findings, discrepancies, or notes")
    issues: List[str] = Field(default_factory=list, description="Identified discrepancies, violations, or errors")
    errors: List[str] = Field(default_factory=list, description="Explicit error messages if execution failed")
    reason: Optional[str] = Field(None, description="Primary explanatory reason for agent outcome")
    risk_level: str = Field("LOW", description="Risk level: LOW, MEDIUM, HIGH, CRITICAL, UNKNOWN")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution timing, worker, and provenance metadata")
    timestamp: Optional[str] = Field(None, description="ISO 8601 evaluation timestamp")

    @model_validator(mode="after")
    def sync_agent_aliases(self) -> "N8nAgentResult":
        if not self.agent_name:
            self.agent_name = self.agent
        elif not self.agent:
            self.agent = self.agent_name

        # Synchronize findings, issues, errors
        if not self.issues and self.findings:
            self.issues = list(self.findings)
        elif not self.findings and self.issues:
            self.findings = list(self.issues)
        if not self.errors and self.issues:
            self.errors = list(self.issues)
        elif not self.issues and self.errors:
            self.issues = list(self.errors)

        # Synchronize evidence_ids from evidence dictionary if present
        if not self.evidence_ids and self.evidence:
            ev_id = self.evidence.get("evidence_id")
            if ev_id:
                self.evidence_ids = [str(ev_id)]

        # Synchronize source_documents from evidence dictionary if present
        if not self.source_documents and self.evidence:
            doc_ref = self.evidence.get("source_document") or self.evidence.get("document_id")
            if doc_ref:
                self.source_documents = [str(doc_ref)]

        if self.status:
            self.status = self.status.strip().upper()
        return self

    model_config = ConfigDict(extra="ignore")




# ==============================================================================
# 4. Final Compliance Result Schema (Synthesized decision)
# ==============================================================================

class FinalComplianceResult(BaseModel):
    """
    Detailed compliance synthesis output produced by the Final Compliance Agent.
    """
    decision: VerificationDecisionEnum = Field(..., description="QUALIFIED, NOT_QUALIFIED, CONDITIONALLY_QUALIFIED, MANUAL_REVIEW")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Composite weighted risk score (0 - 100)")
    risk_level: RiskLevelEnum = Field(..., description="Composite risk level (LOW, MEDIUM, HIGH, CRITICAL)")
    reasons: List[str] = Field(default_factory=list, description="Key summary reasons driving the decision")
    failed_requirements: List[Union[str, Dict[str, Any]]] = Field(default_factory=list, description="Failed criteria details")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warning notices")
    missing_documents: List[str] = Field(default_factory=list, description="Missing mandatory document types")

    model_config = ConfigDict(extra="ignore")


# ==============================================================================
# 5. n8n Response Schema (Inbound HTTP response from n8n Master Orchestrator)
# ==============================================================================

class N8nVerificationResponse(BaseModel):
    """
    Complete response payload returned by the n8n Master Orchestrator webhook.
    Strictly conforms to node-build-response in master_orchestrator_prototype.json.
    """
    verification_id: str = Field(..., description="Canonical verification execution ID (e.g. VER-...)")
    request_id: str = Field(..., description="Correlated request identifier")
    tender_id: Optional[str] = Field(None, description="Associated tender ID")
    bidder_id: Optional[str] = Field(None, description="Associated bidder ID")
    bidder_name: str = Field(..., description="Bidder corporate name")
    status: str = Field("COMPLETED", description="Orchestration status: COMPLETED, FAILED, ERROR")
    decision: str = Field("MANUAL_REVIEW", description="Qualification decision: QUALIFIED, NOT_QUALIFIED, etc.")
    risk_score: float = Field(0.0, ge=0.0, le=100.0, description="Aggregated risk score between 0 and 100")
    risk_level: str = Field("LOW", description="Overall risk level (LOW, MEDIUM, HIGH)")
    agent_results: List[N8nAgentResult] = Field(default_factory=list, description="Array of results from all executed agents")
    failed_requirements: List[Union[str, Dict[str, Any]]] = Field(default_factory=list, description="Mandatory requirements that failed")
    missing_documents: List[str] = Field(default_factory=list, description="List of unsubmitted mandatory documents")
    warnings: List[str] = Field(default_factory=list, description="List of non-fatal warnings")
    reasons: List[str] = Field(default_factory=list, description="Explanatory summary reasons")
    timestamp: Optional[str] = Field(None, description="Completion timestamp (ISO 8601)")

    # Optional failure handling fields
    error: Optional[bool] = Field(None, description="Set to true if workflow encountered uncaught exception")
    message: Optional[str] = Field(None, description="Error message if workflow failed")

    # ==============================================================================
# 6. Requirement Evaluation and Compliance Summary Schemas (Phase 12.6)
# ==============================================================================

class RequirementEvaluation(BaseModel):
    """
    Granular evaluation of an individual tender requirement against bidder evidence.
    Ensures complete clause-to-evidence provenance and explainability.
    """
    requirement_id: str = Field(..., description="Unique requirement ID")
    rule: Optional[str] = Field(None, description="Rule code, e.g. MINIMUM_TURNOVER")
    description: Optional[str] = Field(None, description="Requirement textual description")
    mandatory: bool = Field(True, description="Whether this requirement is mandatory")
    decision: RequirementComplianceEnum = Field(..., description="COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, UNVERIFIED")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Evaluation confidence score")
    agent: Optional[str] = Field(None, description="Responsible agent name, e.g. FINANCIAL_AGENT, GST_AGENT")
    evidence_ids: List[str] = Field(default_factory=list, description="Correlated evidence IDs")
    document_ids: List[str] = Field(default_factory=list, description="Correlated document IDs")
    source_page: Optional[int] = Field(None, description="Tender source page")
    source_section: Optional[str] = Field(None, description="Tender source section")
    source_text: Optional[str] = Field(None, description="Source requirement text from tender")
    reason: Optional[str] = Field(None, description="Explanatory justification for the decision")
    findings: List[str] = Field(default_factory=list, description="Specific findings or discrepancies")

    model_config = ConfigDict(extra="ignore")


class VerificationRiskAssessment(BaseModel):
    """Deterministic, explainable risk assessment aggregating all component signals."""
    level: RiskLevelEnum = Field(..., description="LOW, MEDIUM, HIGH, CRITICAL, UNKNOWN")
    score: float = Field(0.0, ge=0.0, le=100.0, description="Composite numeric risk score (0 - 100)")
    reasons: List[str] = Field(default_factory=list, description="High-level explanatory risk reasons")
    signals: Dict[str, Any] = Field(default_factory=dict, description="Granular component risk signals")
    critical_flags: List[str] = Field(default_factory=list, description="Triggered critical risk condition flags")

    model_config = ConfigDict(extra="ignore")


class VerificationComplianceSummary(BaseModel):
    """Aggregate tally of requirement compliance evaluations."""
    total_requirements: int = Field(0, ge=0, description="Total evaluated requirements")
    compliant: int = Field(0, ge=0, description="Number of fully compliant requirements")
    non_compliant: int = Field(0, ge=0, description="Number of non-compliant requirements")
    partially_compliant: int = Field(0, ge=0, description="Number of partially compliant requirements")
    unverified: int = Field(0, ge=0, description="Number of unverified requirements")

    model_config = ConfigDict(extra="ignore")


# ==============================================================================
# 7. Verification API Response Schema (FastAPI -> React Frontend)
# ==============================================================================

class VerificationResponse(BaseModel):
    """
    Standardized client-facing response returned by FastAPI verification endpoints.
    Combines n8n orchestration findings with database persistence metadata,
    requirement-level evaluation, explainable risk assessment, and summary metrics.
    """
    id: Optional[uuid.UUID] = Field(None, description="PostgreSQL primary key UUID for the verification record")
    verification_id: str = Field(..., description="Canonical verification execution reference ID")
    request_id: str = Field(..., description="Correlation request ID")
    tender_id: uuid.UUID = Field(..., description="Tender UUID")
    bidder_id: uuid.UUID = Field(..., description="Bidder UUID")
    bidder_name: str = Field(..., description="Bidder registered company name")
    status: VerificationStatusEnum = Field(..., description="Verification lifecycle status")
    decision: VerificationDecisionEnum = Field(..., description="Qualification verdict")
    overall_compliance: Optional[OverallComplianceEnum] = Field(None, description="Separate compliance verdict: COMPLIANT, NON_COMPLIANT, PARTIALLY_COMPLIANT, UNVERIFIED")
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Composite risk score (0 to 100)")
    risk_level: RiskLevelEnum = Field(..., description="Composite risk level (LOW, MEDIUM, HIGH, CRITICAL, UNKNOWN)")
    overall_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Composite verification confidence score")
    result_hash: Optional[str] = Field(None, description="Deterministic SHA-256 digest of logical verification result")
    reasons: List[str] = Field(default_factory=list, description="High-level explanatory decision reasons")
    failed_requirements: List[str] = Field(default_factory=list, description="Human-readable list of failed requirements")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings and review flags")
    inconclusive_checks: List[str] = Field(default_factory=list, description="Requirements or agent checks that were inconclusive or unexecuted")
    missing_documents: List[str] = Field(default_factory=list, description="Missing document notices")
    agent_results: List[N8nAgentResult] = Field(default_factory=list, description="Granular breakdown of each agent's findings")
    requirements: List[RequirementEvaluation] = Field(default_factory=list, description="Requirement-level verification evaluations")
    risk: Optional[VerificationRiskAssessment] = Field(None, description="Detailed explainable risk assessment")
    summary: Optional[VerificationComplianceSummary] = Field(None, description="Compliance summary counts")
    evidence_snapshot: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Safe snapshot of evidence records evaluated")
    document_hashes: Optional[Dict[str, str]] = Field(default_factory=dict, description="SHA-256 hashes of evaluated origin documents")
    error: Optional[Dict[str, Any]] = Field(None, description="Sanitized failure error details if execution failed")
    raw_response: Optional[Dict[str, Any]] = Field(None, description="Raw audit snapshot from n8n orchestrator")
    created_at: Optional[datetime] = Field(None, description="Verification initiation timestamp")
    started_at: Optional[datetime] = Field(None, description="Verification execution started timestamp")
    completed_at: Optional[datetime] = Field(None, description="Verification execution completed timestamp")
    updated_at: Optional[datetime] = Field(None, description="Verification completion timestamp")

    model_config = ConfigDict(from_attributes=True)


class VerificationHistoryItem(BaseModel):
    """Safe metadata summary for tender/bidder verification history listing."""
    verification_id: str = Field(..., description="Canonical verification ID")
    status: str = Field(..., description="Verification status (QUEUED, RUNNING, COMPLETED, FAILED, UNVERIFIED)")
    overall_compliance: Optional[str] = Field(None, description="Overall compliance verdict")
    risk_level: Optional[str] = Field(None, description="Composite risk level")
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    result_hash: Optional[str] = Field(None, description="Deterministic SHA-256 result digest")

    model_config = ConfigDict(from_attributes=True)


class VerificationAuditEventResponse(BaseModel):
    """Audit event tracking verification lifecycle milestones."""
    id: uuid.UUID = Field(..., description="Event UUID")
    verification_id: str = Field(..., description="Canonical verification ID")
    tender_id: uuid.UUID = Field(..., description="Tender UUID")
    bidder_id: uuid.UUID = Field(..., description="Bidder UUID")
    event_type: str = Field(..., description="Lifecycle event type (e.g. VERIFICATION_CREATED, VERIFICATION_COMPLETED)")
    result_hash: Optional[str] = Field(None, description="Result digest if available")
    details: Dict[str, Any] = Field(default_factory=dict, description="Safe event metadata")
    created_at: datetime = Field(..., description="Event recording timestamp")

    model_config = ConfigDict(from_attributes=True)


class VerificationSummaryItem(BaseModel):
    """Lightweight summary model for paginated or historical verification listings."""
    id: uuid.UUID = Field(..., description="Record UUID")
    verification_id: str = Field(..., description="Verification reference ID")
    tender_id: uuid.UUID = Field(..., description="Tender UUID")
    bidder_id: uuid.UUID = Field(..., description="Bidder UUID")
    bidder_name: str = Field(..., description="Bidder company name")
    status: VerificationStatusEnum = Field(..., description="Status")
    decision: VerificationDecisionEnum = Field(..., description="Verdict")
    risk_score: float = Field(..., description="Risk score")
    risk_level: RiskLevelEnum = Field(..., description="Risk level")
    agents_executed_count: int = Field(0, description="Total number of agents reporting")
    created_at: datetime = Field(..., description="Initiation timestamp")

    model_config = ConfigDict(from_attributes=True)

