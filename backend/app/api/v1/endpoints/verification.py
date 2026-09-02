"""
Phase 10 & Phase 12.8 — FastAPI ↔ n8n Verification Endpoints
api/v1/endpoints/verification.py: HTTP API routes for triggering bid verifications,
handling n8n asynchronous webhook callbacks, and monitoring orchestration health.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
import uuid

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Request,
    status,
)
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.crud.crud_verification import (
    compute_canonical_result_hash,
    crud_verification,
)
from app.dependencies.auth import get_current_user_optional
from app.dependencies.database import get_db
from app.models.bidder import Bidder
from app.models.enums import UserRole
from app.models.tender import Tender
from app.models.user import User
from app.schemas.verification import (
    N8nVerificationPayload,
    N8nVerificationResponse,
    VerificationAuditEventResponse,
    VerificationHistoryItem,
    VerificationResponse,
    VerificationTriggerRequest,
)
from app.services.n8n_client import (
    N8nClientError,
    N8nConnectionError,
    N8nTimeoutError,
    n8n_client,
)
from app.services.verification_service import (
    VerificationService,
    verification_service,
)

logger = logging.getLogger("app.api.v1.verification")


verification_router = APIRouter(
    prefix="/verification",
    tags=["verification"],
)


@verification_router.post(
    "/build-request",
    response_model=N8nVerificationPayload,
    status_code=status.HTTP_200_OK,
    summary="Build and Validate Complete Verification Request",
    description="Constructs, validates, and returns the complete n8n verification payload without executing verification agents.",
)
def build_verification_request_endpoint(
    request: VerificationTriggerRequest,
    db: Session = Depends(get_db),
) -> N8nVerificationPayload:
    """Builds and validates the complete N8nVerificationPayload from database entities."""
    return verification_service.build_and_validate_verification_request(
        tender_id=request.tender_id,
        bidder_id=request.bidder_id,
        db=db,
        trigger_request=request,
    )



@verification_router.post(
    "/trigger",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger Multi-Agent Bid Verification",
    description="Initiates end-to-end multi-agent verification for a bidder on a tender via n8n Master Orchestrator.",
)
async def trigger_verification_endpoint(
    request: VerificationTriggerRequest,
    db: Session = Depends(get_db),
) -> VerificationResponse:
    """
    Assembles domain context (bidder, tender, documents, evidence), dispatches
    to the n8n Master Orchestrator, and returns the aggregated verification decision.
    """
    # Verify tender exists
    tender = db.query(Tender).filter(Tender.id == request.tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender with ID '{request.tender_id}' not found.",
        )

    # Verify bidder exists
    bidder = db.query(Bidder).filter(Bidder.id == request.bidder_id).first()
    if not bidder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bidder with ID '{request.bidder_id}' not found.",
        )

    try:
        response = await verification_service.execute_verification(
            trigger_request=request,
            db=db,
        )
        return response

    except (NotFoundException, BadRequestException):
        raise
    except N8nTimeoutError as exc:
        logger.error(f"n8n verification timed out: {exc}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"n8n Master Orchestrator timed out: {exc.message}",
        )
    except N8nConnectionError as exc:
        logger.error(f"n8n connection failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to connect to n8n Master Orchestrator: {exc.message}",
        )
    except N8nClientError as exc:
        logger.error(f"n8n client error: {exc}")
        status_code = exc.status_code if exc.status_code and exc.status_code >= 400 else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail=exc.message,
        )
    except Exception as exc:
        logger.error(f"Unexpected error during verification: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal verification error: {str(exc)}",
        )


@verification_router.post(
    "/run",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Run Complete Multi-Agent Bid Verification",
    description="Builds, validates, dispatches to n8n, and aggregates the multi-agent verification result.",
)
async def run_verification_endpoint(
    request: VerificationTriggerRequest,
    db: Session = Depends(get_db),
) -> VerificationResponse:
    """Executes the complete end-to-end bid verification workflow."""
    return await trigger_verification_endpoint(request=request, db=db)



@verification_router.post(
    "/webhook/callback",
    status_code=status.HTTP_200_OK,
    summary="n8n Asynchronous Webhook Callback",
    description="Receives asynchronous verification results from n8n Master Orchestrator with HMAC verification.",
)
async def webhook_callback_endpoint(
    request: Request,
    db: Session = Depends(get_db),
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
) -> Dict[str, Any]:
    """
    Secure callback endpoint invoked by n8n upon workflow completion.
    Validates HMAC-SHA256 signature and secret token before processing.
    Persists the verification result and updates execution state.
    """
    body_bytes = await request.body()

    # Verify secret if configured
    if settings.N8N_WEBHOOK_SECRET:
        if x_webhook_secret and x_webhook_secret != settings.N8N_WEBHOOK_SECRET:
            logger.warning("[webhook-auth-failed] Invalid X-Webhook-Secret provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook secret.",
            )

        if x_webhook_signature:
            is_valid = n8n_client.verify_webhook_signature(body_bytes, x_webhook_signature)
            if not is_valid:
                logger.warning("[webhook-signature-invalid] HMAC signature verification failed")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid webhook signature.",
                )

    try:
        data = await request.json()
        validated_resp = N8nVerificationResponse.model_validate(data)
        logger.info(
            f"[webhook-received] Successfully received callback for verification "
            f"'{validated_resp.verification_id}' (Decision: {validated_resp.decision}, Risk: {validated_resp.risk_score})"
        )
    except Exception as exc:
        logger.error(f"[webhook-parse-error] Failed to parse n8n callback payload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload format: {str(exc)}",
        )

    # Look up persisted execution by verification_id
    execution = crud_verification.get_by_verification_id(db=db, verification_id=validated_resp.verification_id)
    if not execution:
        logger.warning(f"[webhook-unknown-id] No execution found for verification_id '{validated_resp.verification_id}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification execution '{validated_resp.verification_id}' not found.",
        )

    # Validate ownership: tender_id and bidder_id must match the persisted execution
    if validated_resp.tender_id and str(execution.tender_id) != str(validated_resp.tender_id):
        logger.warning(
            f"[webhook-ownership-mismatch] Callback tender_id '{validated_resp.tender_id}' "
            f"does not match execution tender_id '{execution.tender_id}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Callback tender_id does not match the persisted verification execution.",
        )
    if validated_resp.bidder_id and str(execution.bidder_id) != str(validated_resp.bidder_id):
        logger.warning(
            f"[webhook-ownership-mismatch] Callback bidder_id '{validated_resp.bidder_id}' "
            f"does not match execution bidder_id '{execution.bidder_id}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Callback bidder_id does not match the persisted verification execution.",
        )

    # Prevent invalid state transitions: only QUEUED or RUNNING can transition
    if execution.status in {"COMPLETED", "FAILED"}:
        logger.info(f"[webhook-already-finalized] Execution '{execution.verification_id}' is already {execution.status}")
        return {
            "status": "already_finalized",
            "verification_id": execution.verification_id,
            "current_status": execution.status,
        }

    # Process through aggregator to build final response
    try:
        api_response = verification_service.map_n8n_response_to_api_response(
            n8n_resp=validated_resp,
            tender_id=execution.tender_id,
            bidder_id=execution.bidder_id,
        )

        # Build evidence snapshot and document hashes from execution context
        evidence_snapshot = []
        document_hashes = {}

        # Compute result hash
        result_hash = compute_canonical_result_hash(
            verification_id=execution.verification_id,
            tender_id=execution.tender_id,
            bidder_id=execution.bidder_id,
            overall_compliance=api_response.overall_compliance.value if api_response.overall_compliance else None,
            decision=api_response.decision.value if api_response.decision else None,
            risk_level=api_response.risk_level.value if api_response.risk_level else None,
            risk_score=api_response.risk_score,
            overall_confidence=api_response.overall_confidence,
            requirements=[r.model_dump() for r in api_response.requirements],
            agent_results=[a.model_dump() for a in api_response.agent_results],
            evidence_snapshot=evidence_snapshot,
            document_hashes=document_hashes,
        )
        api_response.result_hash = result_hash
        api_response.evidence_snapshot = evidence_snapshot
        api_response.document_hashes = document_hashes

        # Persist completed result
        crud_verification.update_execution_completed(
            db=db,
            execution=execution,
            resp=api_response,
            result_hash=result_hash,
            evidence_snapshot=evidence_snapshot,
            document_hashes=document_hashes,
        )
        crud_verification.record_audit_event(
            db=db,
            verification_id=execution.verification_id,
            tender_id=execution.tender_id,
            bidder_id=execution.bidder_id,
            event_type="VERIFICATION_COMPLETED",
            result_hash=result_hash,
            details={
                "source": "webhook_callback",
                "overall_compliance": api_response.overall_compliance.value if api_response.overall_compliance else None,
                "decision": api_response.decision.value if api_response.decision else None,
                "risk_level": api_response.risk_level.value if api_response.risk_level else None,
            },
        )
        logger.info(
            f"[webhook-persisted] Verification '{execution.verification_id}' "
            f"completed via callback: {api_response.decision}"
        )
    except Exception as exc:
        logger.error(f"[webhook-processing-error] Failed to process callback result: {exc}")
        crud_verification.update_execution_failed(
            db=db,
            execution=execution,
            stage="webhook_callback_processing",
            error_msg=str(exc),
        )
        crud_verification.record_audit_event(
            db=db,
            verification_id=execution.verification_id,
            tender_id=execution.tender_id,
            bidder_id=execution.bidder_id,
            event_type="VERIFICATION_FAILED",
            details={"stage": "webhook_callback_processing", "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process verification callback: {str(exc)}",
        )

    return {
        "status": "processed",
        "verification_id": execution.verification_id,
        "decision": api_response.decision.value if api_response.decision else None,
        "risk_score": api_response.risk_score,
        "result_hash": result_hash,
    }


@verification_router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="n8n Orchestration Health Status",
    description="Checks the health and connectivity of the n8n Master Orchestrator service.",
)
async def verification_health_endpoint() -> Dict[str, Any]:
    """
    Returns integration status with the n8n multi-agent orchestration service.
    """
    health = await n8n_client.check_health()
    return {
        "status": "healthy" if health.get("reachable") else "degraded",
        "n8n_service": health,
    }


@verification_router.get(
    "/{verification_id}",
    response_model=VerificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Persisted Verification Result",
    description="Retrieves a historical verification execution result by its canonical verification ID.",
)
def get_verification_endpoint(
    verification_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> VerificationResponse:
    """Retrieves the finalized verification execution from the database."""
    execution = crud_verification.get_by_verification_id(db=db, verification_id=verification_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification execution with ID '{verification_id}' not found.",
        )

    # Enforce tenant/user authorization & isolation (Section 13)
    tender = db.query(Tender).filter(Tender.id == execution.tender_id).first()
    if current_user and tender and tender.created_by:
        if current_user.role != UserRole.ADMIN and tender.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have permission to access verification results for this tender.",
            )

    # Record retrieval audit event
    crud_verification.record_audit_event(
        db=db,
        verification_id=execution.verification_id,
        tender_id=execution.tender_id,
        bidder_id=execution.bidder_id,
        event_type="VERIFICATION_RETRIEVED",
        result_hash=execution.result_hash,
        details={"source": "api_retrieval"},
    )

    return crud_verification.to_verification_response(execution)


@verification_router.get(
    "/tender/{tender_id}/bidder/{bidder_id}",
    response_model=List[VerificationHistoryItem],
    status_code=status.HTTP_200_OK,
    summary="Get Verification History for Tender and Bidder",
    description="Returns chronological verification history for a given tender and bidder pair.",
)
def get_verification_history_endpoint(
    tender_id: uuid.UUID,
    bidder_id: uuid.UUID,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> List[VerificationHistoryItem]:
    """Lists safe verification history for a specific tender/bidder pair."""
    tender = db.query(Tender).filter(Tender.id == tender_id).first()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender with ID '{tender_id}' not found.",
        )

    bidder = db.query(Bidder).filter(Bidder.id == bidder_id).first()
    if not bidder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bidder with ID '{bidder_id}' not found.",
        )

    # Enforce tenant authorization & isolation
    if current_user and tender.created_by:
        if current_user.role != UserRole.ADMIN and tender.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have permission to access verification history for this tender.",
            )

    history = crud_verification.get_history_for_tender_bidder(db=db, tender_id=tender_id, bidder_id=bidder_id)
    return [
        VerificationHistoryItem(
            verification_id=item.verification_id,
            status=item.status,
            overall_compliance=item.overall_compliance,
            risk_level=item.risk_level,
            created_at=item.created_at,
            completed_at=item.completed_at,
            result_hash=item.result_hash,
        )
        for item in history
    ]


@verification_router.get(
    "/{verification_id}/audit",
    response_model=List[VerificationAuditEventResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Verification Audit Trail",
    description="Retrieves the immutable audit events recorded for a given verification ID.",
)
def get_verification_audit_endpoint(
    verification_id: str,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
) -> List[VerificationAuditEventResponse]:
    """Returns lifecycle audit log entries for a verification execution."""
    execution = crud_verification.get_by_verification_id(db=db, verification_id=verification_id)
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Verification execution with ID '{verification_id}' not found.",
        )

    # Enforce tenant authorization
    tender = db.query(Tender).filter(Tender.id == execution.tender_id).first()
    if current_user and tender and tender.created_by:
        if current_user.role != UserRole.ADMIN and tender.created_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not have permission to access audit logs for this tender.",
            )

    events = crud_verification.get_audit_events_for_verification(db=db, verification_id=verification_id)
    return [
        VerificationAuditEventResponse(
            id=e.id,
            verification_id=e.verification_id,
            tender_id=e.tender_id,
            bidder_id=e.bidder_id,
            event_type=e.event_type,
            result_hash=e.result_hash,
            details=e.details or {},
            created_at=e.created_at,
        )
        for e in events
    ]

