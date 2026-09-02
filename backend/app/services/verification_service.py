"""
Phase 10 — Verification Orchestration Service
services/verification_service.py: High-level verification service coordinating
database entities, Phase 11 document intelligence artifacts, and n8n Master Orchestrator dispatch.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Union
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models.bidder import Bidder
from app.models.compliance import BidderEvidenceModel, ComplianceRequirement
from app.models.document import Document
from app.models.tender import Tender
from app.schemas.verification import (
    DEFAULT_VERIFICATION_AGENTS,
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
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationStatusEnum,
    VerificationTriggerRequest,
)
from app.services.n8n_client import N8nClient, n8n_client

logger = logging.getLogger("app.services.verification_service")


class VerificationService:
    """
    Coordinates verification workflows between FastAPI domain services and n8n orchestrator.
    """

    def __init__(self, client: Optional[N8nClient] = None):
        self.client = client or n8n_client

    def build_n8n_payload(
        self,
        trigger_request: VerificationTriggerRequest,
        db: Optional[Session] = None,
    ) -> N8nVerificationPayload:
        """
        Assembles a strongly typed N8nVerificationPayload from the trigger request
        and database records (bidder, tender, documents, evidence).
        """
        tender_id_str = str(trigger_request.tender_id)
        bidder_id_str = str(trigger_request.bidder_id)
        request_id = f"REQ-VER-{uuid.uuid4().hex[:8].upper()}"
        verification_id = f"VER-{uuid.uuid4().hex[:12].upper()}"

        bidder_name = f"Bidder-{bidder_id_str[:8]}"
        tender_title = None
        tender_number = None
        gstin = None
        pan = None
        udyam = None
        cin = None
        documents_list: List[DocumentForensicInput] = []
        fin_req = trigger_request.financial_overrides
        exp_req = trigger_request.experience_overrides
        fin_evidence: Optional[FinancialEvidenceInput] = None
        exp_evidence: Optional[ExperienceEvidenceInput] = None

        if db:
            # Query tender
            tender = db.query(Tender).filter(Tender.id == trigger_request.tender_id).first()
            if tender:
                tender_title = tender.title
                tender_number = getattr(tender, "tender_number", None)

            # Query bidder
            bidder = db.query(Bidder).filter(Bidder.id == trigger_request.bidder_id).first()
            if bidder:
                bidder_name = getattr(bidder, "company_name", None) or getattr(bidder, "name", None) or bidder_name
                gstin = getattr(bidder, "gst_number", None) or getattr(bidder, "gstin", None)
                pan = getattr(bidder, "pan_number", None) or getattr(bidder, "pan", None)
                udyam = getattr(bidder, "udyam_number", None) or getattr(bidder, "udyam", None)
                cin = getattr(bidder, "registration_number", None) or getattr(bidder, "cin", None)

            # Query bidder documents
            docs = db.query(Document).filter(
                (Document.bidder_id == trigger_request.bidder_id) |
                (Document.tender_id == trigger_request.tender_id)
            ).all()
            for doc in docs:
                doc_type_val = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)
                documents_list.append(
                    DocumentForensicInput(
                        document_id=str(doc.id),
                        document_type=doc_type_val,
                        file_name=doc.file_name,
                        mime_type=doc.mime_type,
                        file_size=doc.file_size,
                        storage_path=doc.storage_path,
                        sha256=getattr(doc, "sha256", None),
                        ocr_text=doc.extracted_text,
                    )
                )

            # Query bidder evidence
            evidences = db.query(BidderEvidenceModel).filter(
                BidderEvidenceModel.bidder_id == trigger_request.bidder_id
            ).all()
            evidence_map = {ev.field.lower(): ev.value for ev in evidences if ev.field and ev.value}

            # Build financial evidence if available
            if "turnover" in evidence_map or "net_worth" in evidence_map:
                fin_evidence = FinancialEvidenceInput(
                    turnover=evidence_map.get("turnover"),
                    net_worth=float(evidence_map["net_worth"]) if isinstance(evidence_map.get("net_worth"), (int, float)) else None,
                    working_capital=float(evidence_map["working_capital"]) if isinstance(evidence_map.get("working_capital"), (int, float)) else None,
                    balance_sheet_filed=evidence_map.get("balance_sheet_filed", True),
                    ca_certified=evidence_map.get("ca_certified", True),
                    udin=evidence_map.get("udin"),
                )

            # Build experience evidence if available
            if "projects" in evidence_map and isinstance(evidence_map["projects"], list):
                project_items = []
                for p in evidence_map["projects"]:
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
                            )
                        )
                if project_items:
                    exp_evidence = ExperienceEvidenceInput(projects=project_items)

        # Build final payload
        payload = N8nVerificationPayload(
            request_id=request_id,
            verification_id=verification_id,
            tender_id=tender_id_str,
            tender_number=tender_number,
            tender_title=tender_title,
            bidder_id=bidder_id_str,
            bidder_name=bidder_name,
            required_agents=trigger_request.required_agents or list(DEFAULT_VERIFICATION_AGENTS),
            gstin=gstin,
            pan=pan,
            udyam=udyam,
            cin=cin,
            documents=documents_list,
            financial_requirements=fin_req,
            financial_evidence=fin_evidence,
            experience_requirements=exp_req,
            experience_evidence=exp_evidence,
            compliance_policy=trigger_request.compliance_policy,
            metadata=trigger_request.metadata,
        )
        return payload

    async def execute_verification(
        self,
        trigger_request: VerificationTriggerRequest,
        db: Optional[Session] = None,
    ) -> VerificationResponse:
        """
        Executes end-to-end verification by assembling context, dispatching to n8n,
        and returning the formatted verification response.
        """
        payload = self.build_n8n_payload(trigger_request=trigger_request, db=db)
        logger.info(f"Executing verification for bidder {payload.bidder_name} ({payload.bidder_id}) on tender {payload.tender_id}")

        n8n_response = await self.client.trigger_verification(payload=payload)
        return self.map_n8n_response_to_api_response(
            n8n_resp=n8n_response,
            tender_id=trigger_request.tender_id,
            bidder_id=trigger_request.bidder_id,
        )

    def map_n8n_response_to_api_response(
        self,
        n8n_resp: N8nVerificationResponse,
        tender_id: uuid.UUID,
        bidder_id: uuid.UUID,
    ) -> VerificationResponse:
        """
        Maps an n8n Master Orchestrator response to the client-facing VerificationResponse.
        """
        # Map decision string to enum
        try:
            decision_enum = VerificationDecisionEnum(n8n_resp.decision.upper())
        except ValueError:
            decision_enum = VerificationDecisionEnum.MANUAL_REVIEW

        # Map risk level string to enum
        try:
            risk_level_enum = RiskLevelEnum(n8n_resp.risk_level.upper())
        except ValueError:
            risk_level_enum = RiskLevelEnum.LOW

        # Map status
        status_val = n8n_resp.status.upper()
        if status_val == "COMPLETED":
            status_enum = VerificationStatusEnum.COMPLETED
        elif status_val == "FAILED":
            status_enum = VerificationStatusEnum.FAILED
        else:
            status_enum = VerificationStatusEnum.PROCESSING

        # Map failed requirements
        failed_req_strings: List[str] = []
        for fr in n8n_resp.failed_requirements:
            if isinstance(fr, str):
                failed_req_strings.append(fr)
            elif isinstance(fr, dict):
                failed_req_strings.append(str(fr.get("requirement", fr.get("message", str(fr)))))

        return VerificationResponse(
            id=uuid.uuid4(),
            verification_id=n8n_resp.verification_id,
            request_id=n8n_resp.request_id,
            tender_id=tender_id,
            bidder_id=bidder_id,
            bidder_name=n8n_resp.bidder_name,
            status=status_enum,
            decision=decision_enum,
            risk_score=float(n8n_resp.risk_score),
            risk_level=risk_level_enum,
            reasons=n8n_resp.reasons,
            failed_requirements=failed_req_strings,
            warnings=n8n_resp.warnings,
            missing_documents=n8n_resp.missing_documents,
            agent_results=n8n_resp.agent_results,
            raw_response=n8n_resp.model_dump(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )


# Singleton instance
verification_service = VerificationService()
