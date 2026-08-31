"""
Phase 09 — Compliance Rule Engine
compliance.py: Pydantic schemas for compliance requirements, evidence, results, and evaluation requests.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.compliance.enums import ComplianceStatus, Operator, RuleType


# ---------------------------------------------------------------------------
# Requirement Schemas
# ---------------------------------------------------------------------------

class RequirementCreate(BaseModel):
    tender_id: uuid.UUID = Field(..., description="Parent tender ID")
    category: str = Field(..., description="Requirement category (FINANCIAL, EXPERIENCE, etc.)")
    field: str = Field(..., description="Canonical field name for evidence matching")
    rule_type: RuleType = Field(..., description="Rule engine evaluator type")
    rule_definition: Dict[str, Any] = Field(..., description="Structured rule definition parameters")
    mandatory: bool = Field(default=True, description="Whether requirement is mandatory")
    description: Optional[str] = Field(default=None, description="Human-readable requirement description")

    model_config = ConfigDict(extra="ignore")


class RequirementResponse(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    tender_id: uuid.UUID
    category: str
    field: str
    rule_type: str
    rule_definition: Dict[str, Any]
    mandatory: bool
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Bidder Evidence Schemas
# ---------------------------------------------------------------------------

class BidderEvidenceCreate(BaseModel):
    bidder_id: uuid.UUID = Field(..., description="Bidder organization ID")
    field: str = Field(..., description="Canonical field name matching requirement")
    value: Optional[Any] = Field(default=None, description="Evidence payload (scalar, dict, list)")
    source_document: Optional[str] = Field(default=None, description="Source document path/name")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Extraction confidence")

    model_config = ConfigDict(extra="ignore")


class BidderEvidenceResponse(BaseModel):
    id: uuid.UUID
    evidence_id: uuid.UUID
    bidder_id: uuid.UUID
    field: str
    value: Optional[Any] = None
    source_document: Optional[str] = None
    confidence: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Compliance Result Schemas
# ---------------------------------------------------------------------------

class ComplianceResultResponse(BaseModel):
    id: uuid.UUID
    requirement_id: uuid.UUID
    bidder_id: uuid.UUID
    status: ComplianceStatus
    reason: str
    evidence_reference: Optional[str] = None
    rule_type: Optional[str] = None
    operator_used: Optional[str] = None
    actual_value: Optional[Any] = None
    required_value: Optional[Any] = None
    evaluated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Evaluation Requests
# ---------------------------------------------------------------------------

class EvaluationRequest(BaseModel):
    requirement_id: uuid.UUID
    bidder_id: uuid.UUID
    exemptions: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional exemption rules")

    model_config = ConfigDict(extra="ignore")


class TenderBidderEvaluationRequest(BaseModel):
    tender_id: uuid.UUID
    bidder_id: uuid.UUID
    exemptions: Optional[List[Dict[str, Any]]] = Field(default=None, description="Optional exemption rules")

    model_config = ConfigDict(extra="ignore")
