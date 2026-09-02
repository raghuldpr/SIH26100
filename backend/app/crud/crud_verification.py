"""
Phase 12.7 — Verification Result Persistence, Audit Trail & Idempotency
crud_verification.py: Database operations, canonical result hashing, error sanitization,
idempotency evaluation, and audit logging.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union
import uuid
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.verification import (
    VerificationAuditEvent,
    VerificationExecution,
)
from app.schemas.verification import (
    AgentStatusEnum,
    N8nAgentResult,
    OverallComplianceEnum,
    RequirementComplianceEnum,
    RequirementEvaluation,
    RiskLevelEnum,
    VerificationComplianceSummary,
    VerificationDecisionEnum,
    VerificationHistoryItem,
    VerificationResponse,
    VerificationRiskAssessment,
    VerificationStatusEnum,
)

logger = logging.getLogger("app.crud.crud_verification")

# Regex patterns for sanitizing secrets, database URLs, and internal server paths
SECRET_SCRUB_PATTERNS = [
    (re.compile(r"(postgresql|postgres|mysql|sqlite)://[^\s\"']+", re.IGNORECASE), "[REDACTED_DATABASE_URL]"),
    (re.compile(r"gsk_[a-zA-Z0-9_-]{20,}", re.IGNORECASE), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9_.\-]+", re.IGNORECASE), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"ey[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}", re.IGNORECASE), "[REDACTED_JWT]"),
    (re.compile(r"(?:password|secret|apikey|api_key|token)[\"'\s:=]+[\"']?[^\s\"',}]+[\"']?", re.IGNORECASE), "[REDACTED_CREDENTIAL]"),
    (re.compile(r"[A-Za-z]:\\[^\s\"'\n\r]+", re.IGNORECASE), "[REDACTED_INTERNAL_PATH]"),
    (re.compile(r"/(?:home|etc|root|var|tmp)/[^\s\"'\n\r]+", re.IGNORECASE), "[REDACTED_INTERNAL_PATH]"),
]


def sanitize_text(text: str) -> str:
    """Removes API keys, database credentials, JWTs, and internal paths from string."""
    if not text:
        return text
    sanitized = text
    for pattern, replacement in SECRET_SCRUB_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def sanitize_error_details(err: Any) -> Dict[str, Any]:
    """Sanitizes an exception or error payload to prevent credential or internal path leakage."""
    if isinstance(err, dict):
        clean_dict = {}
        for k, v in err.items():
            if any(term in k.lower() for term in ("key", "secret", "password", "token", "auth")):
                clean_dict[k] = "[REDACTED]"
            elif isinstance(v, str):
                clean_dict[k] = sanitize_text(v)
            elif isinstance(v, (int, float, bool)) or v is None:
                clean_dict[k] = v
            else:
                clean_dict[k] = sanitize_text(str(v))
        return clean_dict
    elif isinstance(err, Exception):
        msg = sanitize_text(str(err))
        return {
            "error_type": type(err).__name__,
            "message": msg,
        }
    else:
        return {"message": sanitize_text(str(err))}


def compute_canonical_result_hash(
    verification_id: str,
    tender_id: Union[UUID, str],
    bidder_id: Union[UUID, str],
    overall_compliance: Optional[str],
    decision: Optional[str],
    risk_level: Optional[str],
    risk_score: Optional[float],
    overall_confidence: Optional[float],
    requirements: Optional[List[Dict[str, Any]]] = None,
    agent_results: Optional[List[Dict[str, Any]]] = None,
    evidence_snapshot: Optional[List[Dict[str, Any]]] = None,
    document_hashes: Optional[Dict[str, str]] = None,
) -> str:
    """
    Computes a deterministic SHA-256 hash representing the tamper-evident logical result.
    Strictly excludes volatile timestamps, raw server metadata, and transient credentials.
    Uses canonical key ordering and strict JSON serialization.
    """
    canonical_reqs = []
    if requirements:
        for r in requirements:
            req_item = {
                "requirement_id": str(r.get("requirement_id", "")),
                "rule": str(r.get("rule", "")),
                "mandatory": bool(r.get("mandatory", True)),
                "decision": str(r.get("decision", "")),
                "confidence": round(float(r["confidence"]), 4) if r.get("confidence") is not None else None,
                "agent": str(r.get("agent", "")),
                "evidence_ids": sorted([str(e) for e in r.get("evidence_ids", [])]),
                "document_ids": sorted([str(d) for e in r.get("document_ids", []) for d in [e]]),
            }
            canonical_reqs.append(req_item)
    canonical_reqs.sort(key=lambda x: (x["requirement_id"], x["rule"]))

    canonical_agents = []
    if agent_results:
        for a in agent_results:
            name = a.get("agent_name") or a.get("agent") or ""
            agent_item = {
                "agent": str(name).strip().upper(),
                "status": str(a.get("status", "")).strip().upper(),
                "confidence": round(float(a["confidence"]), 4) if a.get("confidence") is not None else None,
                "issues": sorted([sanitize_text(str(i)) for i in a.get("issues", [])]),
            }
            canonical_agents.append(agent_item)
    canonical_agents.sort(key=lambda x: x["agent"])

    canonical_evidence = []
    if evidence_snapshot:
        for ev in evidence_snapshot:
            ev_item = {
                "evidence_id": str(ev.get("evidence_id", "")),
                "document_id": str(ev.get("document_id", "")),
                "document_hash": str(ev.get("document_hash", "")),
                "field": str(ev.get("field", "")),
                "confidence": round(float(ev["confidence"]), 4) if ev.get("confidence") is not None else None,
            }
            canonical_evidence.append(ev_item)
    canonical_evidence.sort(key=lambda x: (x["evidence_id"], x["field"]))

    canonical_doc_hashes = {}
    if document_hashes:
        for doc_id, h in sorted(document_hashes.items()):
            canonical_doc_hashes[str(doc_id)] = str(h)

    canonical_payload = {
        "verification_id": str(verification_id).strip(),
        "tender_id": str(tender_id).strip(),
        "bidder_id": str(bidder_id).strip(),
        "overall_compliance": str(overall_compliance) if overall_compliance else None,
        "decision": str(decision) if decision else None,
        "risk_level": str(risk_level) if risk_level else None,
        "risk_score": round(float(risk_score), 2) if risk_score is not None else None,
        "overall_confidence": round(float(overall_confidence), 4) if overall_confidence is not None else None,
        "requirements": canonical_reqs,
        "agent_results": canonical_agents,
        "evidence_snapshot": canonical_evidence,
        "document_hashes": canonical_doc_hashes,
    }

    canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class CRUDVerification:
    """CRUD operations for verification executions, result persistence, and audit logging."""

    # -------------------------------------------------------------------------
    # Execution Lifecycle Persistence
    # -------------------------------------------------------------------------

    def create_execution(
        self,
        db: Session,
        verification_id: str,
        request_id: str,
        tender_id: UUID,
        bidder_id: UUID,
        request_hash: str,
        status: str = "RUNNING",
    ) -> VerificationExecution:
        """Initializes a persistent verification execution record in RUNNING state."""
        execution = VerificationExecution(
            id=uuid.uuid4(),
            verification_id=verification_id,
            request_id=request_id,
            tender_id=tender_id,
            bidder_id=bidder_id,
            status=status,
            request_hash=request_hash,
            started_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        return execution

    def get_by_id(self, db: Session, id: UUID) -> Optional[VerificationExecution]:
        """Retrieves execution record by primary key UUID."""
        return db.query(VerificationExecution).filter(VerificationExecution.id == id).first()

    def get_by_verification_id(self, db: Session, verification_id: str) -> Optional[VerificationExecution]:
        """Retrieves execution record by its canonical string ID (e.g. VER-XXXXXXXX)."""
        return (
            db.query(VerificationExecution)
            .filter(VerificationExecution.verification_id == verification_id.strip())
            .first()
        )

    def find_existing_execution(
        self,
        db: Session,
        tender_id: UUID,
        bidder_id: UUID,
        request_hash: str,
    ) -> Optional[VerificationExecution]:
        """
        Idempotency lookup: checks for an active (RUNNING) or finalized (COMPLETED) execution
        matching the exact tender, bidder, and request payload hash.
        """
        stmt = (
            select(VerificationExecution)
            .where(
                VerificationExecution.tender_id == tender_id,
                VerificationExecution.bidder_id == bidder_id,
                VerificationExecution.request_hash == request_hash,
            )
            .order_by(desc(VerificationExecution.created_at))
        )
        return db.scalars(stmt).first()

    def update_execution_completed(
        self,
        db: Session,
        execution: VerificationExecution,
        resp: VerificationResponse,
        result_hash: str,
        evidence_snapshot: List[Dict[str, Any]],
        document_hashes: Dict[str, str],
    ) -> VerificationExecution:
        """Persists the final compliance verdict, risk evaluation, and snapshot upon workflow completion."""
        now = datetime.now(timezone.utc)
        execution.status = "COMPLETED"
        execution.result_hash = result_hash
        execution.overall_compliance = (
            resp.overall_compliance.value
            if isinstance(resp.overall_compliance, OverallComplianceEnum)
            else str(resp.overall_compliance) if resp.overall_compliance else None
        )
        execution.decision = (
            resp.decision.value
            if isinstance(resp.decision, VerificationDecisionEnum)
            else str(resp.decision) if resp.decision else None
        )
        execution.risk_level = (
            resp.risk_level.value
            if isinstance(resp.risk_level, RiskLevelEnum)
            else str(resp.risk_level) if resp.risk_level else None
        )
        execution.risk_score = resp.risk_score
        execution.overall_confidence = resp.overall_confidence
        execution.compliance_summary = resp.summary.model_dump() if resp.summary else None
        execution.requirements = [r.model_dump() for r in resp.requirements]
        execution.agent_results = [a.model_dump() for a in resp.agent_results]
        execution.risk_assessment = resp.risk.model_dump() if resp.risk else None
        execution.evidence_snapshot = evidence_snapshot
        execution.document_hashes = document_hashes
        execution.reasons = [sanitize_text(r) for r in resp.reasons]
        execution.failed_requirements = resp.failed_requirements
        execution.warnings = [sanitize_text(w) for w in resp.warnings]
        execution.inconclusive_checks = [sanitize_text(ic) for ic in resp.inconclusive_checks]
        execution.missing_documents = resp.missing_documents
        execution.completed_at = now
        execution.updated_at = now

        db.commit()
        db.refresh(execution)
        return execution

    def update_execution_failed(
        self,
        db: Session,
        execution: VerificationExecution,
        stage: str,
        error_msg: str,
    ) -> VerificationExecution:
        """Persists a sanitized failure state without exposing internal secrets or filesystem paths."""
        now = datetime.now(timezone.utc)
        sanitized_error = {
            "stage": sanitize_text(stage),
            "message": sanitize_text(error_msg),
            "failed_at": now.isoformat(),
        }
        execution.status = "FAILED"
        execution.error = sanitized_error
        execution.completed_at = now
        execution.updated_at = now

        db.commit()
        db.refresh(execution)
        return execution

    # -------------------------------------------------------------------------
    # Audit Trail Operations
    # -------------------------------------------------------------------------

    def record_audit_event(
        self,
        db: Session,
        verification_id: str,
        tender_id: UUID,
        bidder_id: UUID,
        event_type: str,
        result_hash: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> VerificationAuditEvent:
        """Appends an immutable audit event for a verification milestone."""
        clean_details = sanitize_error_details(details or {})
        audit_entry = VerificationAuditEvent(
            id=uuid.uuid4(),
            verification_id=verification_id,
            tender_id=tender_id,
            bidder_id=bidder_id,
            event_type=event_type,
            result_hash=result_hash,
            details=clean_details,
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry

    def get_history_for_tender_bidder(
        self,
        db: Session,
        tender_id: UUID,
        bidder_id: UUID,
    ) -> List[VerificationExecution]:
        """Returns all verification execution records for a specific tender/bidder pair."""
        stmt = (
            select(VerificationExecution)
            .where(
                VerificationExecution.tender_id == tender_id,
                VerificationExecution.bidder_id == bidder_id,
            )
            .order_by(desc(VerificationExecution.created_at))
        )
        return list(db.scalars(stmt).all())

    def get_audit_events_for_verification(
        self,
        db: Session,
        verification_id: str,
    ) -> List[VerificationAuditEvent]:
        """Returns all audit events recorded for a given verification ID."""
        stmt = (
            select(VerificationAuditEvent)
            .where(VerificationAuditEvent.verification_id == verification_id.strip())
            .order_by(VerificationAuditEvent.created_at.asc())
        )
        return list(db.scalars(stmt).all())

    # -------------------------------------------------------------------------
    # Response Reconstitution
    # -------------------------------------------------------------------------

    def to_verification_response(
        self,
        execution: VerificationExecution,
        bidder_name: Optional[str] = None,
    ) -> VerificationResponse:
        """
        Reconstructs a fully typed VerificationResponse from the database record,
        safely handling missing or malformed fields.
        """
        # Reconstruct requirements
        reconstructed_reqs: List[RequirementEvaluation] = []
        if execution.requirements:
            for raw_req in execution.requirements:
                try:
                    reconstructed_reqs.append(RequirementEvaluation.model_validate(raw_req))
                except Exception as ex:
                    logger.warning(f"Could not reconstitute requirement: {ex}")

        # Reconstruct agent results
        reconstructed_agents: List[N8nAgentResult] = []
        if execution.agent_results:
            for raw_agent in execution.agent_results:
                try:
                    reconstructed_agents.append(N8nAgentResult.model_validate(raw_agent))
                except Exception as ex:
                    logger.warning(f"Could not reconstitute agent result: {ex}")

        # Reconstruct risk assessment
        reconstructed_risk: Optional[VerificationRiskAssessment] = None
        if execution.risk_assessment:
            try:
                reconstructed_risk = VerificationRiskAssessment.model_validate(execution.risk_assessment)
            except Exception as ex:
                logger.warning(f"Could not reconstitute risk assessment: {ex}")

        # Reconstruct summary
        reconstructed_summary: Optional[VerificationComplianceSummary] = None
        if execution.compliance_summary:
            try:
                reconstructed_summary = VerificationComplianceSummary.model_validate(execution.compliance_summary)
            except Exception as ex:
                logger.warning(f"Could not reconstitute summary: {ex}")

        # Safe enum casting with fallback
        try:
            status_enum = VerificationStatusEnum(execution.status)
        except ValueError:
            status_enum = VerificationStatusEnum.UNVERIFIED

        try:
            decision_enum = (
                VerificationDecisionEnum(execution.decision)
                if execution.decision
                else VerificationDecisionEnum.MANUAL_REVIEW
            )
        except ValueError:
            decision_enum = VerificationDecisionEnum.MANUAL_REVIEW

        overall_comp_enum: Optional[OverallComplianceEnum] = None
        if execution.overall_compliance:
            try:
                overall_comp_enum = OverallComplianceEnum(execution.overall_compliance)
            except ValueError:
                overall_comp_enum = OverallComplianceEnum.UNVERIFIED

        try:
            risk_level_enum = (
                RiskLevelEnum(execution.risk_level)
                if execution.risk_level
                else RiskLevelEnum.UNKNOWN
            )
        except ValueError:
            risk_level_enum = RiskLevelEnum.UNKNOWN

        resolved_bidder_name = bidder_name or f"Bidder-{str(execution.bidder_id)[:8]}"

        return VerificationResponse(
            id=execution.id,
            verification_id=execution.verification_id,
            request_id=execution.request_id,
            tender_id=execution.tender_id,
            bidder_id=execution.bidder_id,
            bidder_name=resolved_bidder_name,
            status=status_enum,
            decision=decision_enum,
            overall_compliance=overall_comp_enum,
            risk_score=execution.risk_score if execution.risk_score is not None else 0.0,
            risk_level=risk_level_enum,
            overall_confidence=execution.overall_confidence,
            result_hash=execution.result_hash,
            reasons=execution.reasons or [],
            failed_requirements=execution.failed_requirements or [],
            warnings=execution.warnings or [],
            inconclusive_checks=execution.inconclusive_checks or [],
            missing_documents=execution.missing_documents or [],
            agent_results=reconstructed_agents,
            requirements=reconstructed_reqs,
            risk=reconstructed_risk,
            summary=reconstructed_summary,
            evidence_snapshot=execution.evidence_snapshot or [],
            document_hashes=execution.document_hashes or {},
            error=execution.error,
            created_at=execution.created_at,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            updated_at=execution.updated_at,
        )


# Global singleton instance
crud_verification = CRUDVerification()
