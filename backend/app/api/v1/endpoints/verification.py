"""
Phase 10 — FastAPI ↔ n8n Verification Endpoints
api/v1/endpoints/verification.py: HTTP API routes for triggering bid verifications,
handling n8n asynchronous webhook callbacks, and monitoring orchestration health.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
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
from app.dependencies.database import get_db
from app.models.bidder import Bidder
from app.models.tender import Tender
from app.schemas.verification import (
    N8nVerificationResponse,
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
    "/webhook/callback",
    status_code=status.HTTP_200_OK,
    summary="n8n Asynchronous Webhook Callback",
    description="Receives asynchronous verification results from n8n Master Orchestrator with HMAC verification.",
)
async def webhook_callback_endpoint(
    request: Request,
    x_webhook_secret: Optional[str] = Header(None, alias="X-Webhook-Secret"),
    x_webhook_signature: Optional[str] = Header(None, alias="X-Webhook-Signature"),
) -> Dict[str, Any]:
    """
    Secure callback endpoint invoked by n8n upon workflow completion.
    Validates HMAC-SHA256 signature and secret token before processing.
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
        return {
            "status": "received",
            "verification_id": validated_resp.verification_id,
            "decision": validated_resp.decision,
            "risk_score": validated_resp.risk_score,
        }
    except Exception as exc:
        logger.error(f"[webhook-parse-error] Failed to parse n8n callback payload: {exc}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload format: {str(exc)}",
        )


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
