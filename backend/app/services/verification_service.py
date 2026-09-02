"""
Phase 10 & Phase 12.4 — Verification Orchestration & Validation Service
services/verification_service.py: High-level verification service coordinating
database entities, Phase 11 document intelligence artifacts, isolation enforcement,
provenance preservation, and n8n Master Orchestrator dispatch.
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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AppException, BadRequestException, NotFoundException
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel, ComplianceRequirement
from app.models.document import Document
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.schemas.verification import (
    DEFAULT_VERIFICATION_AGENTS,
    BidderEvidenceItemInput,
    CompliancePolicyInput,
    DocumentForensicInput,
    ExperienceEvidenceInput,
    ExperienceRequirementsInput,
    FinancialEvidenceInput,
    FinancialRequirementsInput,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    ProjectExperienceItem,
    RiskLevelEnum,
    TenderRequirementItemInput,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationStatusEnum,
    VerificationTriggerRequest,
)
from app.services.n8n_client import N8nClient, n8n_client

logger = logging.getLogger("app.services.verification_service")

# Regex patterns for scanning forbidden sensitive credentials/paths in serialized payloads
FORBIDDEN_CREDENTIAL_PATTERNS = [
    re.compile(r"postgres(?:ql)?://[^\s\"']+", re.IGNORECASE),
    re.compile(r"(?:db_password|password)\s*[:=]\s*['\"][^\s\"']+['\"]", re.IGNORECASE),
    re.compile(r"\bgsk_[a-zA-Z0-9]{20,}\b"),  # Live Groq API key
    re.compile(r"\bBearer\s+ey[A-Za-z0-9\-_.]+\b"),  # JWT bearer token
    re.compile(r"\b(?:sb_publishable|sb_secret|service_role)[_\-]?key\b", re.IGNORECASE),
    re.compile(r"[A-Z]:\\(?:Users|Windows|Program Files)\\[^\s\"']+", re.IGNORECASE),  # Windows internal paths
    re.compile(r"/(?:home|etc|root|var/run)/[^\s\"']+", re.IGNORECASE),  # Linux internal paths
]


class VerificationService:
    """
    Coordinates verification workflows between FastAPI domain services and n8n orchestrator.
    Builds, validates, and serializes the complete verification request with strict tenant isolation.
    """

    def __init__(self, client: Optional[N8nClient] = None):
        self.client = client or n8n_client

    # -------------------------------------------------------------------------
    # PHASE 12.4: COMPLETE VERIFICATION REQUEST BUILDER & VALIDATOR
    # -------------------------------------------------------------------------

    def build_and_validate_verification_request(
        self,
        tender_id: Union[UUID, str],
        bidder_id: Union[UUID, str],
        db: Session,
        trigger_request: Optional[VerificationTriggerRequest] = None,
    ) -> N8nVerificationPayload:
        """
        Builds and strictly validates the complete verification request.
        Combines tender requirements, bidder evidence, document forensic descriptors,
        and compliance policy into a single strongly typed N8nVerificationPayload.

        Fails closed on any tenant, bidder, or requirement isolation violation.
        """
        if isinstance(tender_id, str):
            tender_uuid = UUID(tender_id.strip())
        else:
            tender_uuid = tender_id

        if isinstance(bidder_id, str):
            bidder_uuid = UUID(bidder_id.strip())
        else:
            bidder_uuid = bidder_id

        # 1. Load Tender (Fail closed if not found)
        tender = db.query(Tender).filter(Tender.id == tender_uuid).first()
        if not tender:
            raise NotFoundException(message=f"Tender with ID '{tender_uuid}' not found.")

        # 2. Load Bidder (Fail closed if not found)
        bidder = db.query(Bidder).filter(Bidder.id == bidder_uuid).first()
        if not bidder:
            raise NotFoundException(message=f"Bidder with ID '{bidder_uuid}' not found.")

        # 3. Validate Tender ↔ Bidder Relationship (Step 6: Isolation)
        stmt_assoc = select(TenderBidder).where(
            TenderBidder.tender_id == tender_uuid,
            TenderBidder.bidder_id == bidder_uuid,
        )
        association = db.scalars(stmt_assoc).first()
        if not association:
            # Check if any document explicitly links bidder to tender
            doc_link = db.query(Document).filter(
                Document.tender_id == tender_uuid,
                Document.bidder_id == bidder_uuid,
            ).first()
            if not doc_link:
                raise BadRequestException(
                    message=f"Bidder isolation check failed: Bidder '{bidder_uuid}' is not associated with Tender '{tender_uuid}'."
                )

        # 4. Load & Map Tender Requirements (Step 3 & Step 8)
        raw_requirements = db.query(TenderRequirement).filter(
            TenderRequirement.tender_id == tender_uuid
        ).all()

        if not raw_requirements:
            raise BadRequestException(
                message=f"Tender '{tender_uuid}' has no compliance requirements configured. Cannot produce a false verification request."
            )

        tender_requirements_list: List[TenderRequirementItemInput] = []
        fin_req_candidate: Dict[str, Any] = {}
        exp_req_candidate: Dict[str, Any] = {}

        for req in raw_requirements:
            # Verify requirement isolation
            if req.tender_id != tender_uuid:
                raise BadRequestException(
                    message=f"Tender requirement isolation violation: requirement '{req.id}' belongs to a different tender."
                )

            params = req.parameters if isinstance(req.parameters, dict) else {}
            req_item = TenderRequirementItemInput(
                requirement_id=str(req.id),
                category=str(req.requirement_type).upper(),
                requirement_type=str(req.requirement_type).upper(),
                rule=req.rule,
                description=req.description,
                parameters=params,
                mandatory=bool(req.mandatory),
                confidence=float(req.confidence if req.confidence is not None else 1.0),
                source_page=req.source_page,
                source_section=req.source_section,
                source_text=req.source_text,
                resolution_method="DETERMINISTIC",
            )
            tender_requirements_list.append(req_item)

            # Auto-populate Financial thresholds from requirement parameters
            req_type_upper = str(req.requirement_type).upper()
            rule_upper = str(req.rule).upper()

            if "FINANCIAL" in req_type_upper or "TURNOVER" in rule_upper or "NET_WORTH" in rule_upper:
                if "minimum" in params or "minimum_annual_turnover" in params:
                    val = params.get("minimum") or params.get("minimum_annual_turnover")
                    if val is not None:
                        fin_req_candidate["minimum_annual_turnover"] = float(val)
                        fin_req_candidate["average_turnover"] = float(val)
                if "average" in params or "average_turnover" in params:
                    val = params.get("average") or params.get("average_turnover")
                    if val is not None:
                        fin_req_candidate["average_turnover"] = float(val)
                if "net_worth" in params or "minimum_net_worth" in params:
                    val = params.get("net_worth") or params.get("minimum_net_worth")
                    if val is not None:
                        fin_req_candidate["minimum_net_worth"] = float(val)
                if "working_capital" in params or "minimum_working_capital" in params:
                    val = params.get("working_capital") or params.get("minimum_working_capital")
                    if val is not None:
                        fin_req_candidate["minimum_working_capital"] = float(val)
                if "period" in params or "turnover_period_years" in params:
                    val = params.get("period") or params.get("turnover_period_years")
                    if val is not None:
                        fin_req_candidate["turnover_period_years"] = int(val)

            # Auto-populate Experience criteria from requirement parameters
            if "EXPERIENCE" in req_type_upper or "SIMILAR" in rule_upper:
                if "minimum_similar_works" in params or "minimum_projects" in params:
                    val = params.get("minimum_similar_works") or params.get("minimum_projects")
                    if val is not None:
                        exp_req_candidate["minimum_similar_works"] = int(val)
                if "minimum_project_value" in params or "contract_value" in params:
                    val = params.get("minimum_project_value") or params.get("contract_value")
                    if val is not None:
                        exp_req_candidate["minimum_project_value"] = float(val)
                if "experience_period_years" in params or "lookback_years" in params:
                    val = params.get("experience_period_years") or params.get("lookback_years")
                    if val is not None:
                        exp_req_candidate["experience_period_years"] = int(val)

        # 5. Load & Map Bidder Documents (Step 5 & Step 6: Provenance & Isolation)
        documents_list: List[DocumentForensicInput] = []
        docs = db.query(Document).filter(
            (Document.bidder_id == bidder_uuid) | (Document.tender_id == tender_uuid)
        ).all()

        for doc in docs:
            # Strict isolation check
            if doc.bidder_id and doc.bidder_id != bidder_uuid:
                continue
            if doc.tender_id and doc.tender_id != tender_uuid:
                raise BadRequestException(
                    message=f"Document isolation violation: Document '{doc.id}' belongs to another tender."
                )

            doc_type_val = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)
            fname = getattr(doc, "original_filename", None) or getattr(doc, "file_name", None) or f"doc_{doc.id}.pdf"
            documents_list.append(
                DocumentForensicInput(
                    document_id=str(doc.id),
                    document_type=doc_type_val,
                    file_name=fname,
                    mime_type=doc.mime_type or "application/pdf",
                    file_size=doc.file_size or 0,
                    storage_path=doc.storage_path,
                    sha256=getattr(doc, "sha256", None),
                    ocr_text=getattr(doc, "extracted_text", None),
                    extracted_data=doc.extracted_data or {},
                )
            )

        # 6. Load & Map Bidder Evidence (Step 4 & Step 6: Traceability & Isolation)
        bidder_evidence_list: List[BidderEvidenceItemInput] = []
        evidences = db.query(BidderEvidenceModel).filter(
            BidderEvidenceModel.bidder_id == bidder_uuid
        ).all()

        fin_evidence_candidate: Dict[str, Any] = {}
        project_items: List[ProjectExperienceItem] = []

        for ev in evidences:
            # Isolation check
            if ev.bidder_id != bidder_uuid:
                raise BadRequestException("Bidder isolation violation: evidence belongs to another bidder.")

            # Validate evidence structure (Fail closed on malformed records)
            if ev.confidence is not None and (ev.confidence < 0.0 or ev.confidence > 1.0):
                raise BadRequestException(
                    f"Malformed evidence detected: confidence {ev.confidence} is outside valid range [0, 1]."
                )
            if not ev.field or not str(ev.field).strip():
                raise BadRequestException("Malformed evidence detected: missing required field name.")

            ev_val = ev.value
            # Check tender isolation if embedded in evidence payload
            if isinstance(ev_val, dict) and ev_val.get("tender_id"):
                if str(ev_val["tender_id"]) != str(tender_uuid):
                    raise BadRequestException(
                        f"Evidence isolation violation: evidence belongs to tender '{ev_val['tender_id']}', not '{tender_uuid}'."
                    )

            # Traceability extraction
            doc_id_val = None
            doc_hash_val = None
            page_val = None
            source_text_val = None
            ext_method_val = "DETERMINISTIC"

            if isinstance(ev_val, dict):
                doc_id_val = ev_val.get("document_id")
                doc_hash_val = ev_val.get("document_hash")
                page_val = ev_val.get("page")
                source_text_val = ev_val.get("source_text")
                ext_method_val = ev_val.get("extraction_method", "DETERMINISTIC")

            bidder_evidence_list.append(
                BidderEvidenceItemInput(
                    evidence_id=str(ev.evidence_id or ev.id),
                    bidder_id=str(ev.bidder_id),
                    tender_id=str(tender_uuid),
                    document_id=doc_id_val,
                    field=ev.field,
                    value=ev.value,
                    source_document=ev.source_document,
                    source_page=page_val,
                    source_text=source_text_val,
                    confidence=float(ev.confidence if ev.confidence is not None else 1.0),
                    document_hash=doc_hash_val,
                    extraction_method=ext_method_val,
                )
            )

            # Parse domain values for Financial & Experience agents
            field_norm = ev.field.lower()
            if field_norm in ("turnover", "annual_turnover"):
                if isinstance(ev.value, dict) and ("amount" in ev.value or "average" in ev.value):
                    amt = ev.value.get("average") or ev.value.get("amount")
                    fin_evidence_candidate["turnover"] = {"annual": float(amt)}
                elif isinstance(ev.value, (int, float)):
                    fin_evidence_candidate["turnover"] = {"annual": float(ev.value)}
                elif isinstance(ev.value, dict):
                    fin_evidence_candidate["turnover"] = ev.value
            elif field_norm == "net_worth":
                if isinstance(ev.value, (int, float)):
                    fin_evidence_candidate["net_worth"] = float(ev.value)
            elif field_norm in ("projects", "experience"):
                raw_projects = []
                if isinstance(ev.value, list):
                    raw_projects = ev.value
                elif isinstance(ev.value, dict) and "projects" in ev.value and isinstance(ev.value["projects"], list):
                    raw_projects = ev.value["projects"]

                for p in raw_projects:
                    if isinstance(p, dict):
                        project_items.append(
                            ProjectExperienceItem(
                                project_id=str(p.get("project_id", f"PRJ-{uuid.uuid4().hex[:6]}")),
                                project_name=p.get("project_name"),
                                client_name=p.get("client_name"),
                                project_value=float(p.get("project_value", 0.0)),
                                completion_date=str(p.get("completion_date", "2024-01-01")),
                                similarity=bool(p.get("similarity", True)),
                                completion_certificate=bool(p.get("completion_certificate", True)),
                                certificate_document_id=p.get("certificate_document_id"),
                                document_hash=p.get("document_hash"),
                            )
                        )

        # 7. Synthesize Financial & Experience Context
        fin_req = (trigger_request.financial_overrides if trigger_request and trigger_request.financial_overrides else None)
        if not fin_req and fin_req_candidate:
            fin_req = FinancialRequirementsInput(**fin_req_candidate)

        exp_req = (trigger_request.experience_overrides if trigger_request and trigger_request.experience_overrides else None)
        if not exp_req and exp_req_candidate:
            exp_req = ExperienceRequirementsInput(**exp_req_candidate)

        fin_evidence = None
        if fin_evidence_candidate:
            fin_evidence = FinancialEvidenceInput(**fin_evidence_candidate)

        exp_evidence = None
        if project_items:
            exp_evidence = ExperienceEvidenceInput(projects=project_items)

        # 8. Deterministic Request & Verification Identifiers (Step 9: Idempotency)
        hash_seed = f"{tender_uuid}:{bidder_uuid}"
        deterministic_digest = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()[:12].upper()
        request_id = f"REQ-VER-{deterministic_digest}"
        verification_id = f"VER-{deterministic_digest}"

        # Bidder identity and statutory numbers
        bidder_name = getattr(bidder, "company_name", None) or getattr(bidder, "name", None) or f"Bidder-{str(bidder_uuid)[:8]}"
        gstin = getattr(bidder, "gst_number", None) or getattr(bidder, "gstin", None)
        pan = getattr(bidder, "pan_number", None) or getattr(bidder, "pan", None)
        udyam = getattr(bidder, "udyam_number", None) or getattr(bidder, "udyam", None)
        cin = getattr(bidder, "registration_number", None) or getattr(bidder, "cin", None)

        # 9. Construct Strongly Typed N8nVerificationPayload
        payload = N8nVerificationPayload(
            request_id=request_id,
            verification_id=verification_id,
            tender_id=str(tender_uuid),
            tender_number=getattr(tender, "tender_number", None),
            tender_title=tender.title,
            bidder_id=str(bidder_uuid),
            bidder_name=bidder_name,
            required_agents=(trigger_request.required_agents if trigger_request and trigger_request.required_agents else list(DEFAULT_VERIFICATION_AGENTS)),
            gstin=gstin,
            pan=pan,
            udyam=udyam,
            cin=cin,
            documents=documents_list,
            tender_requirements=tender_requirements_list,
            bidder_evidence=bidder_evidence_list,
            financial_requirements=fin_req,
            financial_evidence=fin_evidence,
            experience_requirements=exp_req,
            experience_evidence=exp_evidence,
            compliance_policy=(trigger_request.compliance_policy if trigger_request else None),
            metadata=(trigger_request.metadata if trigger_request and trigger_request.metadata else {}),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        # 10. Pre-dispatch Security Validation (Step 8 & 11)
        self._validate_security_and_provenance(payload)

        return payload

    def _validate_security_and_provenance(self, payload: N8nVerificationPayload) -> None:
        """
        Scans serialized payload to ensure no database credentials, API keys,
        tokens, or internal system paths leak to the n8n orchestrator.
        """
        serialized = payload.model_dump_json()

        for pattern in FORBIDDEN_CREDENTIAL_PATTERNS:
            match = pattern.search(serialized)
            if match:
                matched_snippet = match.group(0)
                # Obfuscate before logging
                safe_snippet = matched_snippet[:6] + "..." if len(matched_snippet) > 8 else "REDACTED"
                logger.error(f"Security validation failure: forbidden pattern detected ({safe_snippet})")
                raise AppException(
                    message=f"Security validation failed: sensitive credential or system path pattern detected in verification payload."
                )

    def build_n8n_payload(
        self,
        trigger_request: VerificationTriggerRequest,
        db: Optional[Session] = None,
    ) -> N8nVerificationPayload:
        """
        Assembles a strongly typed N8nVerificationPayload from the trigger request.
        Uses build_and_validate_verification_request if database session is provided.
        """
        if db:
            return self.build_and_validate_verification_request(
                tender_id=trigger_request.tender_id,
                bidder_id=trigger_request.bidder_id,
                db=db,
                trigger_request=trigger_request,
            )

        # Fallback minimal construction when called without DB session (e.g. lightweight schema unit tests)
        tender_id_str = str(trigger_request.tender_id)
        bidder_id_str = str(trigger_request.bidder_id)
        hash_seed = f"{tender_id_str}:{bidder_id_str}"
        deterministic_digest = hashlib.sha256(hash_seed.encode("utf-8")).hexdigest()[:12].upper()
        request_id = f"REQ-VER-{deterministic_digest}"
        verification_id = f"VER-{deterministic_digest}"

        return N8nVerificationPayload(
            request_id=request_id,
            verification_id=verification_id,
            tender_id=tender_id_str,
            bidder_id=bidder_id_str,
            bidder_name=f"Bidder-{bidder_id_str[:8]}",
            required_agents=trigger_request.required_agents or list(DEFAULT_VERIFICATION_AGENTS),
            financial_requirements=trigger_request.financial_overrides,
            experience_requirements=trigger_request.experience_overrides,
            compliance_policy=trigger_request.compliance_policy,
            metadata=trigger_request.metadata,
        )

    async def execute_verification(
        self,
        trigger_request: VerificationTriggerRequest,
        db: Optional[Session] = None,
    ) -> VerificationResponse:
        """
        Executes end-to-end verification with idempotency control, execution persistence,
        tamper-evident result hashing, and immutable audit event logging.
        """
        import hashlib
        import json
        from app.crud.crud_verification import (
            compute_canonical_result_hash,
            crud_verification,
        )

        payload = self.build_n8n_payload(trigger_request=trigger_request, db=db)
        logger.info(f"Executing verification for bidder {payload.bidder_name} ({payload.bidder_id}) on tender {payload.tender_id}")

        tender_uuid = trigger_request.tender_id
        bidder_uuid = trigger_request.bidder_id

        # Compute deterministic request hash for idempotency control
        request_hash_seed = {
            "tender_id": str(tender_uuid),
            "bidder_id": str(bidder_uuid),
            "required_agents": sorted(payload.required_agents),
            "requirements": sorted([r.rule for r in payload.tender_requirements]),
            "evidence_hashes": sorted([e.document_hash or "" for e in payload.bidder_evidence]),
        }
        request_hash = hashlib.sha256(
            json.dumps(request_hash_seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        execution = None
        force_refresh = False
        if trigger_request.metadata and trigger_request.metadata.get("force_refresh"):
            force_refresh = True

        if db is not None:
            existing = crud_verification.find_existing_execution(
                db=db,
                tender_id=tender_uuid,
                bidder_id=bidder_uuid,
                request_hash=request_hash,
            )
            if existing and not force_refresh:
                # Idempotency Policy:
                # 1. If completed -> return existing result without duplicate execution
                if existing.status == "COMPLETED":
                    logger.info(f"[idempotency] Returning existing COMPLETED verification {existing.verification_id}")
                    crud_verification.record_audit_event(
                        db=db,
                        verification_id=existing.verification_id,
                        tender_id=tender_uuid,
                        bidder_id=bidder_uuid,
                        event_type="VERIFICATION_RETRIEVED",
                        result_hash=existing.result_hash,
                        details={"reason": "idempotent_cached_result", "request_hash": request_hash},
                    )
                    return crud_verification.to_verification_response(existing, bidder_name=payload.bidder_name)

                # 2. If running / queued -> return in-flight execution status
                elif existing.status in {"RUNNING", "QUEUED"}:
                    logger.info(f"[idempotency] Verification {existing.verification_id} is currently {existing.status}")
                    crud_verification.record_audit_event(
                        db=db,
                        verification_id=existing.verification_id,
                        tender_id=tender_uuid,
                        bidder_id=bidder_uuid,
                        event_type="VERIFICATION_RETRIEVED",
                        details={"reason": "in_flight_status_check", "status": existing.status},
                    )
                    return crud_verification.to_verification_response(existing, bidder_name=payload.bidder_name)

                # 3. If failed -> controlled retry allowed; proceed with new execution
                elif existing.status == "FAILED":
                    logger.info(f"[idempotency] Previous verification {existing.verification_id} FAILED. Initiating controlled retry.")

            # Create persistent execution record in QUEUED state
            verification_id = payload.verification_id or f"VER-{uuid.uuid4().hex[:8].upper()}"
            request_id = payload.request_id or f"REQ-VER-{uuid.uuid4().hex[:8].upper()}"
            execution = crud_verification.create_execution(
                db=db,
                verification_id=verification_id,
                request_id=request_id,
                tender_id=tender_uuid,
                bidder_id=bidder_uuid,
                request_hash=request_hash,
                status="QUEUED",
            )
            crud_verification.record_audit_event(
                db=db,
                verification_id=verification_id,
                tender_id=tender_uuid,
                bidder_id=bidder_uuid,
                event_type="VERIFICATION_CREATED",
                details={"request_id": request_id, "bidder_name": payload.bidder_name},
            )

            # Transition to RUNNING before actual dispatch
            execution.status = "RUNNING"
            execution.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(execution)

            crud_verification.record_audit_event(
                db=db,
                verification_id=verification_id,
                tender_id=tender_uuid,
                bidder_id=bidder_uuid,
                event_type="VERIFICATION_STARTED",
                details={"required_agents": payload.required_agents},
            )
            crud_verification.record_audit_event(
                db=db,
                verification_id=verification_id,
                tender_id=tender_uuid,
                bidder_id=bidder_uuid,
                event_type="VERIFICATION_DISPATCHED",
                details={"agent_count": len(payload.required_agents)},
            )

        # Dispatch to n8n Master Orchestrator
        try:
            n8n_response = await self.client.trigger_verification(payload=payload)
        except Exception as exc:
            if db is not None and execution is not None:
                crud_verification.update_execution_failed(
                    db=db,
                    execution=execution,
                    stage="n8n_orchestration",
                    error_msg=str(exc),
                )
                crud_verification.record_audit_event(
                    db=db,
                    verification_id=execution.verification_id,
                    tender_id=tender_uuid,
                    bidder_id=bidder_uuid,
                    event_type="VERIFICATION_FAILED",
                    details={"stage": "n8n_orchestration", "error": str(exc)},
                )
            raise

        # Aggregate results
        api_response = self.map_n8n_response_to_api_response(
            n8n_resp=n8n_response,
            tender_id=tender_uuid,
            bidder_id=bidder_uuid,
            payload=payload,
        )

        if execution is not None:
            if n8n_response.verification_id and n8n_response.verification_id != execution.verification_id:
                existing_with_vid = crud_verification.get_by_verification_id(db, n8n_response.verification_id)
                if not existing_with_vid:
                    old_vid = execution.verification_id
                    execution.verification_id = n8n_response.verification_id
                    from app.models.verification import VerificationAuditEvent
                    db.query(VerificationAuditEvent).filter(
                        VerificationAuditEvent.verification_id == old_vid
                    ).update({"verification_id": n8n_response.verification_id})
                    db.commit()
            api_response.verification_id = execution.verification_id
            api_response.request_id = execution.request_id
            api_response.id = execution.id




        # Build evidence snapshot and document hashes
        evidence_snapshot = []
        document_hashes = {}
        for doc in payload.documents:
            if doc.document_id and doc.sha256:
                document_hashes[str(doc.document_id)] = doc.sha256

        for ev in payload.bidder_evidence:
            evidence_snapshot.append({
                "evidence_id": ev.evidence_id,
                "document_id": ev.document_id,
                "document_hash": ev.document_hash,
                "field": ev.field,
                "value": ev.value,
                "source_page": ev.source_page,
                "source_text": ev.source_text,
                "confidence": ev.confidence,
            })
            if ev.document_id and ev.document_hash:
                document_hashes[str(ev.document_id)] = ev.document_hash


        # Compute deterministic result hash
        result_hash = compute_canonical_result_hash(
            verification_id=api_response.verification_id,
            tender_id=tender_uuid,
            bidder_id=bidder_uuid,
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

        # Persist completed result and record audit event
        if db is not None and execution is not None:
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
                tender_id=tender_uuid,
                bidder_id=bidder_uuid,
                event_type="VERIFICATION_COMPLETED",
                result_hash=result_hash,
                details={
                    "overall_compliance": api_response.overall_compliance.value if api_response.overall_compliance else None,
                    "decision": api_response.decision.value if api_response.decision else None,
                    "risk_level": api_response.risk_level.value if api_response.risk_level else None,
                },
            )

        return api_response


    def map_n8n_response_to_api_response(
        self,
        n8n_resp: N8nVerificationResponse,
        tender_id: uuid.UUID,
        bidder_id: uuid.UUID,
        payload: Optional[N8nVerificationPayload] = None,
    ) -> VerificationResponse:
        """
        Maps an n8n Master Orchestrator response to the client-facing VerificationResponse
        via the fail-closed VerificationResultAggregator.
        """
        from app.services.verification_aggregator import verification_aggregator

        return verification_aggregator.aggregate(
            n8n_resp=n8n_resp,
            payload=payload,
            tender_id=tender_id,
            bidder_id=bidder_id,
        )



# Singleton instance
verification_service = VerificationService()
