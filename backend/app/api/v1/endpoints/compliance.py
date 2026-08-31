"""
Phase 09 — Compliance Rule Engine
endpoints/compliance.py: REST API routes for requirements, evidence, and compliance evaluation.

Flow:
API
↓
Compliance Service
↓
Rule Engine
↓
PostgreSQL / SQLAlchemy
"""
from __future__ import annotations

import logging
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.schemas.compliance import (
    BidderEvidenceCreate,
    BidderEvidenceResponse,
    ComplianceResultResponse,
    EvaluationRequest,
    RequirementCreate,
    RequirementResponse,
    TenderBidderEvaluationRequest,
)
from app.services.compliance_service import compliance_service

logger = logging.getLogger("app.api.compliance")

compliance_router = APIRouter(
    prefix="/compliance",
    tags=["compliance"],
)


# ---------------------------------------------------------------------------
# Requirements Endpoints
# ---------------------------------------------------------------------------

@compliance_router.post(
    "/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Tender Compliance Requirement",
)
def create_requirement(
    requirement_in: RequirementCreate,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    """Create and persist a new tender compliance rule with structured rule definition."""
    req_obj = compliance_service.create_requirement(db, requirement_in)
    return RequirementResponse.model_validate(req_obj)


@compliance_router.get(
    "/requirements/tender/{tender_id}",
    response_model=List[RequirementResponse],
    summary="List Tender Compliance Requirements",
)
def list_tender_requirements(
    tender_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[RequirementResponse]:
    """Retrieve all compliance requirements configured for a specific tender."""
    req_objs = compliance_service.list_requirements_by_tender(db, tender_id)
    return [RequirementResponse.model_validate(r) for r in req_objs]


@compliance_router.get(
    "/requirements/{requirement_id}",
    response_model=RequirementResponse,
    summary="Get Single Requirement",
)
def get_requirement(
    requirement_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> RequirementResponse:
    """Retrieve a single requirement by ID."""
    req_obj = compliance_service.get_requirement(db, requirement_id)
    if not req_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement {requirement_id} not found",
        )
    return RequirementResponse.model_validate(req_obj)


# ---------------------------------------------------------------------------
# Bidder Evidence Endpoints
# ---------------------------------------------------------------------------

@compliance_router.post(
    "/evidence",
    response_model=BidderEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Bidder Evidence",
)
def record_evidence(
    evidence_in: BidderEvidenceCreate,
    db: Session = Depends(get_db),
) -> BidderEvidenceResponse:
    """Record normalized bidder evidence for compliance evaluation."""
    ev_obj = compliance_service.save_bidder_evidence(db, evidence_in)
    return BidderEvidenceResponse.model_validate(ev_obj)


@compliance_router.get(
    "/evidence/bidder/{bidder_id}",
    response_model=List[BidderEvidenceResponse],
    summary="List Evidence for Bidder",
)
def list_bidder_evidence(
    bidder_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> List[BidderEvidenceResponse]:
    """List all evidence recorded for a bidder."""
    ev_objs = compliance_service.list_bidder_evidence(db, bidder_id)
    return [BidderEvidenceResponse.model_validate(e) for e in ev_objs]


# ---------------------------------------------------------------------------
# Evaluation Endpoints
# ---------------------------------------------------------------------------

@compliance_router.post(
    "/evaluate",
    response_model=ComplianceResultResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Single Requirement",
)
def evaluate_single_requirement(
    payload: EvaluationRequest,
    db: Session = Depends(get_db),
) -> ComplianceResultResponse:
    """
    Evaluate a single requirement against bidder evidence using the deterministic rule engine.
    Persists evaluation result for auditability.
    """
    try:
        res_obj = compliance_service.evaluate_requirement(
            db,
            payload.requirement_id,
            payload.bidder_id,
            exemptions=payload.exemptions,
        )
        return ComplianceResultResponse.model_validate(res_obj)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@compliance_router.post(
    "/evaluate/tender/{tender_id}/bidder/{bidder_id}",
    response_model=List[ComplianceResultResponse],
    status_code=status.HTTP_200_OK,
    summary="Evaluate Full Tender Compliance for Bidder",
)
def evaluate_full_tender(
    tender_id: uuid.UUID,
    bidder_id: uuid.UUID,
    payload: Optional[TenderBidderEvaluationRequest] = None,
    db: Session = Depends(get_db),
) -> List[ComplianceResultResponse]:
    """
    Evaluate all requirements for a tender against bidder evidence in a single transaction.
    Persists all evaluation results immutably.
    """
    exemptions = payload.exemptions if payload else None
    res_objs = compliance_service.evaluate_bidder_compliance(
        db,
        tender_id,
        bidder_id,
        exemptions=exemptions,
    )
    return [ComplianceResultResponse.model_validate(r) for r in res_objs]


@compliance_router.get(
    "/results/bidder/{bidder_id}",
    response_model=List[ComplianceResultResponse],
    summary="Get Compliance Audit Trail",
)
def get_compliance_results(
    bidder_id: uuid.UUID,
    requirement_id: Optional[uuid.UUID] = Query(default=None),
    db: Session = Depends(get_db),
) -> List[ComplianceResultResponse]:
    """
    Retrieve historical compliance evaluation results for a bidder.
    Historical evaluations are preserved immutably.
    """
    res_objs = compliance_service.get_compliance_results(
        db,
        bidder_id,
        requirement_id=requirement_id,
    )
    return [ComplianceResultResponse.model_validate(r) for r in res_objs]
