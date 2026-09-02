"""
SIH-26100 — Phase 12.3: Bidder Intake Service
services/bidder_intake_service.py

Coordinates:
Tender
  ↓
Create / Register Bidder
  ↓
Associate Bidder with Tender
  ↓
Upload Bidder Documents
  ↓
Validate + SHA-256
  ↓
Store Document
  ↓
Classify Document
  ↓
Extract Evidence (Deterministic first)
  ↓
Persist Structured Evidence (Idempotent)
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from uuid import UUID

from fastapi import UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, BadRequestException, NotFoundException
from app.core.storage import generate_bidder_storage_path, storage_service, SupabaseStorageService
from app.core.validation import calculate_sha256, validate_single_upload_file, ValidatedFile
from app.crud.crud_bidder import crud_bidder
from app.crud.crud_document import crud_document
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus
from app.models.tender import Tender
from app.schemas.bidder import BidderCreate
from app.schemas.entities import StructuredDocumentOutput
from app.services.ai_gateway import AIGateway, ai_gateway
from app.services.compliance_service import compliance_service, ComplianceService
from app.services.document_processing_service import DocumentProcessingService, document_processing_service
from app.services.entity_extractor import DocumentEntityExtractor, entity_extractor
from app.services.tender_requirement_normalizer import TenderRequirementNormalizer

logger = logging.getLogger("app.services.bidder_intake_service")

# Regex definitions for deterministic validation & extraction
PAN_REGEX = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b")
GSTIN_REGEX = re.compile(r"\b(\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1})\b")
UDYAM_REGEX = re.compile(r"\b(UDYAM-[A-Z]{2}-\d{2}-\d{7})\b", re.IGNORECASE)


class BidderIntakeService:
    """
    Orchestrates bidder registration, tender association, document upload,
    deterministic layout/OCR processing, and structured evidence persistence.
    """

    def __init__(
        self,
        doc_processing_svc: Optional[DocumentProcessingService] = None,
        entity_ext: Optional[DocumentEntityExtractor] = None,
        storage_svc: Optional[SupabaseStorageService] = None,
        comp_svc: Optional[ComplianceService] = None,
        ai_gw: Optional[AIGateway] = None,
    ):
        self.doc_processing_service = doc_processing_svc or document_processing_service
        self.entity_extractor = entity_ext or entity_extractor
        self.storage_service = storage_svc or storage_service
        self.compliance_service = comp_svc or compliance_service
        self.ai_gateway = ai_gw or ai_gateway

    # -------------------------------------------------------------------------
    # 1. BIDDER REGISTRATION & TENDER ASSOCIATION
    # -------------------------------------------------------------------------

    def create_tender_bidder(
        self,
        db: Session,
        tender_id: Union[UUID, str],
        bidder_in: Union[BidderCreate, dict],
        user_id: Optional[UUID] = None,
    ) -> Tuple[Bidder, TenderBidder]:
        """
        Creates a new Bidder organization and immediately associates it with a target Tender.
        If the bidder is already assigned to the tender, returns the existing assignment.
        """
        if isinstance(tender_id, str):
            tender_id = UUID(tender_id.strip())

        tender = db.get(Tender, tender_id)
        if not tender:
            raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

        # Create bidder record
        bidder = crud_bidder.create(db, bidder_in=bidder_in, user_id=user_id)

        # Associate with tender
        try:
            assignment = crud_bidder.assign_bidder_to_tender(
                db, tender_id=tender_id, bidder_id=bidder.id
            )
        except AppException as e:
            if getattr(e, "status_code", None) == status.HTTP_409_CONFLICT:
                stmt = select(TenderBidder).where(
                    TenderBidder.tender_id == tender_id,
                    TenderBidder.bidder_id == bidder.id,
                )
                assignment = db.scalars(stmt).first()
                if not assignment:
                    raise e
            else:
                raise e

        logger.info(
            f"Created bidder '{bidder.company_name}' [{bidder.id}] and associated with tender [{tender_id}]"
        )
        return bidder, assignment

    # -------------------------------------------------------------------------
    # 2. DOCUMENT UPLOAD & INTAKE PROCESSING
    # -------------------------------------------------------------------------

    async def intake_bidder_document(
        self,
        db: Session,
        bidder_id: Union[UUID, str],
        file: UploadFile,
        document_type: DocumentType = DocumentType.OTHER,
        tender_id: Optional[Union[UUID, str]] = None,
        process_document: bool = True,
    ) -> Tuple[Document, List[BidderEvidenceModel]]:
        """
        Validates, uploads, processes, and extracts structured evidence from an UploadFile.
        """
        if isinstance(bidder_id, str):
            bidder_id = UUID(bidder_id.strip())
        if isinstance(tender_id, str):
            tender_id = UUID(tender_id.strip())

        # Step 1: Validate file (format, signature, extension, file size, SHA-256)
        val_file: ValidatedFile = await validate_single_upload_file(file)

        return self.intake_bidder_document_content(
            db=db,
            bidder_id=bidder_id,
            file_bytes=val_file.content,
            filename=val_file.original_filename,
            mime_type=val_file.mime_type,
            document_type=document_type,
            tender_id=tender_id,
            sha256=val_file.sha256,
            process_document=process_document,
        )

    def intake_bidder_document_content(
        self,
        db: Session,
        bidder_id: Union[UUID, str],
        file_bytes: bytes,
        filename: str,
        mime_type: str,
        document_type: DocumentType = DocumentType.OTHER,
        tender_id: Optional[Union[UUID, str]] = None,
        sha256: Optional[str] = None,
        process_document: bool = True,
    ) -> Tuple[Document, List[BidderEvidenceModel]]:
        """
        Direct content intake entry point (supports memory bytes or API uploads).
        Validates associations, performs SHA-256 deduplication check, stores document,
        processes layout/OCR, and persists structured evidence.
        """
        if isinstance(bidder_id, str):
            bidder_id = UUID(bidder_id.strip())
        if isinstance(tender_id, str):
            tender_id = UUID(tender_id.strip())

        bidder = crud_bidder.get_by_id(db, bidder_id=bidder_id)
        if not bidder:
            raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

        if tender_id:
            tender = db.get(Tender, tender_id)
            if not tender:
                raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

        # Compute SHA-256 if not pre-computed
        computed_sha256 = sha256 or calculate_sha256(file_bytes)

        # Step 10: Deduplication check (tender_id + bidder_id + document SHA-256)
        stmt = select(Document).where(
            Document.bidder_id == bidder_id,
            Document.sha256 == computed_sha256,
        )
        if tender_id:
            stmt = stmt.where(Document.tender_id == tender_id)

        existing_doc = db.scalars(stmt).first()
        if existing_doc and existing_doc.processing_status == ProcessingStatus.PROCESSED:
            logger.info(
                f"Document with sha256={computed_sha256} already processed for bidder {bidder_id}. "
                f"Returning existing record [id={existing_doc.id}]."
            )
            evidences = self.get_bidder_evidence(db, bidder_id=bidder_id, document_id=existing_doc.id)
            return existing_doc, evidences

        # Step 2: Storage path generation & cloud/mock storage upload
        storage_path = generate_bidder_storage_path(
            bidder_id=bidder_id,
            document_type=document_type,
            filename=filename,
        )
        uploaded_path = self.storage_service.upload(
            storage_path=storage_path,
            file_content=file_bytes,
            mime_type=mime_type,
        )

        # Step 3: Persist document record in PostgreSQL
        try:
            doc = crud_document.create_metadata(
                db=db,
                original_filename=filename,
                storage_path=uploaded_path,
                document_type=document_type,
                mime_type=mime_type,
                file_size=len(file_bytes),
                sha256=computed_sha256,
                tender_id=tender_id,
                bidder_id=bidder_id,
                status=DocumentStatus.ACTIVE,
                processing_status=ProcessingStatus.NOT_PROCESSED,
            )
        except Exception as exc:
            logger.error(f"Database error saving document record. Rolling back storage: {exc}")
            self.storage_service.delete(uploaded_path)
            raise AppException(message="Failed to record document metadata in database.")

        evidences: List[BidderEvidenceModel] = []
        if process_document:
            doc, evidences = self.process_bidder_document(db, document_id=doc.id, file_bytes=file_bytes)

        return doc, evidences

    # -------------------------------------------------------------------------
    # 3. DOCUMENT PROCESSING & EVIDENCE EXTRACTION
    # -------------------------------------------------------------------------

    def process_bidder_document(
        self,
        db: Session,
        document_id: Union[UUID, str],
        file_bytes: Optional[bytes] = None,
    ) -> Tuple[Document, List[BidderEvidenceModel]]:
        """
        Executes layout extraction, OCR fallback, document classification,
        entity extraction, and structured evidence persistence for a bidder document.
        """
        doc = crud_document.get_by_id(db, document_id=document_id)
        if not doc:
            raise NotFoundException(message=f"Document with ID '{document_id}' not found.")

        if not doc.bidder_id:
            raise BadRequestException(message="Document is not associated with any Bidder.")

        # Run Document Processing Service (Phase 06/11 pipeline)
        processed_doc = self.doc_processing_service.process_document(
            db=db,
            document_id=doc.id,
            file_bytes=file_bytes,
        )

        if processed_doc.processing_status != ProcessingStatus.PROCESSED:
            logger.warning(
                f"Document {processed_doc.id} processing ended with status {processed_doc.processing_status}."
            )
            return processed_doc, []

        # Extract and persist structured evidence
        evidences = self.extract_and_persist_evidence(db=db, doc=processed_doc)
        return processed_doc, evidences

    def extract_and_persist_evidence(
        self,
        db: Session,
        doc: Document,
    ) -> List[BidderEvidenceModel]:
        """
        Deterministically extracts compliance evidence from the processed document's
        structured entities and text, then idempotently persists records to BidderEvidenceModel.
        """
        if not doc.bidder_id:
            return []

        extracted_data = doc.extracted_data or {}
        entities: Dict[str, Any] = extracted_data.get("entities", {})
        raw_text = extracted_data.get("raw_text", "")
        doc_type_str = doc.document_type.value if hasattr(doc.document_type, "value") else str(doc.document_type)

        persisted_evidences: List[BidderEvidenceModel] = []

        # Retrieve bidder for registration updates
        bidder = crud_bidder.get_by_id(db, bidder_id=doc.bidder_id)

        # ---------------------------------------------------------------------
        # A. PAN NUMBER EXTRACTION (Deterministic)
        # ---------------------------------------------------------------------
        pan_val = None
        pan_page = 1
        pan_raw = None
        pan_conf = 0.99

        if "pan_number" in entities and entities["pan_number"].get("value"):
            pan_val = str(entities["pan_number"]["value"]).strip().upper()
            pan_page = entities["pan_number"].get("page", 1)
            pan_raw = entities["pan_number"].get("raw_match", pan_val)
            pan_conf = float(entities["pan_number"].get("confidence", 0.99))
        elif raw_text:
            pan_match = PAN_REGEX.search(raw_text)
            if pan_match:
                pan_val = pan_match.group(1).upper()
                pan_raw = pan_match.group(0)

        if pan_val:
            evidence_payload = {
                "pan": pan_val,
                "document_id": str(doc.id),
                "document_hash": doc.sha256,
                "document_type": doc_type_str,
                "page": pan_page,
                "source_text": pan_raw,
                "extraction_method": "DETERMINISTIC",
                "confidence": pan_conf,
                "tender_id": str(doc.tender_id) if doc.tender_id else None,
            }
            ev = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="pan",
                value=evidence_payload,
                source_document=doc.original_filename,
                confidence=pan_conf,
            )
            persisted_evidences.append(ev)

            # Mirror as pan_number for backward compatibility
            ev_mirror = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="pan_number",
                value=pan_val,
                source_document=doc.original_filename,
                confidence=pan_conf,
            )
            persisted_evidences.append(ev_mirror)

            if bidder and not bidder.pan_number:
                bidder.pan_number = pan_val
                db.add(bidder)

        # ---------------------------------------------------------------------
        # B. GSTIN / GST NUMBER EXTRACTION (Deterministic)
        # ---------------------------------------------------------------------
        gstin_val = None
        gst_page = 1
        gst_raw = None
        gst_conf = 0.99

        if "gstin" in entities and entities["gstin"].get("value"):
            gstin_val = str(entities["gstin"]["value"]).strip().upper()
            gst_page = entities["gstin"].get("page", 1)
            gst_raw = entities["gstin"].get("raw_match", gstin_val)
            gst_conf = float(entities["gstin"].get("confidence", 0.99))
        elif raw_text:
            gst_match = GSTIN_REGEX.search(raw_text)
            if gst_match:
                gstin_val = gst_match.group(1).upper()
                gst_raw = gst_match.group(0)

        if gstin_val:
            evidence_payload = {
                "gstin": gstin_val,
                "document_id": str(doc.id),
                "document_hash": doc.sha256,
                "document_type": doc_type_str,
                "page": gst_page,
                "source_text": gst_raw,
                "extraction_method": "DETERMINISTIC",
                "confidence": gst_conf,
                "tender_id": str(doc.tender_id) if doc.tender_id else None,
            }
            ev = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="gstin",
                value=evidence_payload,
                source_document=doc.original_filename,
                confidence=gst_conf,
            )
            persisted_evidences.append(ev)

            ev_mirror = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="gst_number",
                value=gstin_val,
                source_document=doc.original_filename,
                confidence=gst_conf,
            )
            persisted_evidences.append(ev_mirror)

            if bidder and not bidder.gst_number:
                bidder.gst_number = gstin_val
                db.add(bidder)

        # ---------------------------------------------------------------------
        # C. UDYAM / MSME REGISTRATION NUMBER (Deterministic)
        # ---------------------------------------------------------------------
        udyam_val = None
        udyam_page = 1
        udyam_raw = None
        udyam_conf = 0.98

        if "udyam_number" in entities and entities["udyam_number"].get("value"):
            udyam_val = str(entities["udyam_number"]["value"]).strip().upper()
            udyam_page = entities["udyam_number"].get("page", 1)
            udyam_raw = entities["udyam_number"].get("raw_match", udyam_val)
            udyam_conf = float(entities["udyam_number"].get("confidence", 0.98))
        elif raw_text:
            udyam_match = UDYAM_REGEX.search(raw_text)
            if udyam_match:
                udyam_val = udyam_match.group(1).upper()
                udyam_raw = udyam_match.group(0)

        if udyam_val:
            evidence_payload = {
                "udyam_number": udyam_val,
                "document_id": str(doc.id),
                "document_hash": doc.sha256,
                "document_type": doc_type_str,
                "page": udyam_page,
                "source_text": udyam_raw,
                "extraction_method": "DETERMINISTIC",
                "confidence": udyam_conf,
                "tender_id": str(doc.tender_id) if doc.tender_id else None,
            }
            ev = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="udyam_number",
                value=evidence_payload,
                source_document=doc.original_filename,
                confidence=udyam_conf,
            )
            persisted_evidences.append(ev)

            if bidder and not bidder.udyam_number:
                bidder.udyam_number = udyam_val
                db.add(bidder)

        # ---------------------------------------------------------------------
        # D. FINANCIAL / TURNOVER EXTRACTION (Deterministic)
        # ---------------------------------------------------------------------
        turnover_candidate = None
        fin_page = 1
        fin_raw = None
        fin_conf = 0.95

        if "annual_turnover" in entities and entities["annual_turnover"].get("value"):
            raw_t = entities["annual_turnover"]["value"]
            fin_page = entities["annual_turnover"].get("page", 1)
            fin_raw = entities["annual_turnover"].get("raw_match", str(raw_t))
            fin_conf = float(entities["annual_turnover"].get("confidence", 0.95))
            if isinstance(raw_t, (int, float)):
                turnover_candidate = float(raw_t)
            else:
                parsed_amount = TenderRequirementNormalizer.normalize_indian_currency(str(raw_t))
                if parsed_amount:
                    turnover_candidate = float(parsed_amount)
        elif raw_text and ("turnover" in raw_text.lower() or "crore" in raw_text.lower() or "lakh" in raw_text.lower()):
            parsed_amount = TenderRequirementNormalizer.normalize_indian_currency(raw_text)
            if parsed_amount:
                turnover_candidate = float(parsed_amount)

        if turnover_candidate is not None:
            # Format compatible with FinancialEvidenceInput: turnover dict or scalar
            turnover_payload = {
                "amount": turnover_candidate,
                "average": turnover_candidate,
                "currency": "INR",
                "document_id": str(doc.id),
                "document_hash": doc.sha256,
                "document_type": doc_type_str,
                "page": fin_page,
                "source_text": fin_raw,
                "extraction_method": "DETERMINISTIC",
                "confidence": fin_conf,
                "tender_id": str(doc.tender_id) if doc.tender_id else None,
            }
            ev = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="turnover",
                value={"average": turnover_candidate},
                source_document=doc.original_filename,
                confidence=fin_conf,
            )
            persisted_evidences.append(ev)

            ev_annual = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="annual_turnover",
                value=turnover_payload,
                source_document=doc.original_filename,
                confidence=fin_conf,
            )
            persisted_evidences.append(ev_annual)

        # ---------------------------------------------------------------------
        # E. EXPERIENCE / WORK ORDERS (Deterministic)
        # ---------------------------------------------------------------------
        if "work_order_number" in entities or "contract_value" in entities or doc.document_type == DocumentType.EXPERIENCE_CERTIFICATE:
            work_order = entities.get("work_order_number", {}).get("value") or f"WO-{uuid.uuid4().hex[:6].upper()}"
            client_name = entities.get("client_name", {}).get("value") or "Government Procuring Entity"
            contract_val = entities.get("contract_value", {}).get("value")
            num_val = 0.0
            if contract_val is not None:
                if isinstance(contract_val, (int, float)):
                    num_val = float(contract_val)
                else:
                    parsed = TenderRequirementNormalizer.normalize_indian_currency(str(contract_val))
                    if parsed:
                        num_val = float(parsed)


            project_item = {
                "project_id": str(work_order),
                "project_name": entities.get("work_description", {}).get("value") or "Supply and Installation Contract",
                "client_name": str(client_name),
                "project_value": num_val,
                "completion_date": "2024-03-31",
                "similarity": True,
                "completion_certificate": True,
                "certificate_document_id": str(doc.id),
                "document_hash": doc.sha256,
                "page": 1,
                "source_text": doc.original_filename,
            }

            ev_proj = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="projects",
                value=[project_item],
                source_document=doc.original_filename,
                confidence=0.92,
            )
            persisted_evidences.append(ev_proj)

            ev_exp = self._upsert_evidence(
                db=db,
                bidder_id=doc.bidder_id,
                field="experience",
                value={"projects": [project_item], "document_id": str(doc.id), "document_hash": doc.sha256},
                source_document=doc.original_filename,
                confidence=0.92,
            )
            persisted_evidences.append(ev_exp)

        db.commit()
        return persisted_evidences

    # -------------------------------------------------------------------------
    # 4. IDEMPOTENT EVIDENCE UPSERT & ISOLATION HELPERS
    # -------------------------------------------------------------------------

    def _upsert_evidence(
        self,
        db: Session,
        bidder_id: UUID,
        field: str,
        value: Any,
        source_document: Optional[str] = None,
        confidence: float = 1.0,
    ) -> BidderEvidenceModel:
        """
        Safely and idempotently records or updates evidence for a bidder.
        Guarantees that repeated processing of the same source document
        updates existing evidence rather than creating runaway duplicates.
        """
        field_norm = str(field).strip().lower().replace(" ", "_")
        stmt = select(BidderEvidenceModel).where(
            BidderEvidenceModel.bidder_id == bidder_id,
            BidderEvidenceModel.field == field_norm,
            BidderEvidenceModel.source_document == source_document,
        )
        existing = db.scalars(stmt).first()
        if existing:
            existing.value = value
            existing.confidence = float(confidence)
            db.add(existing)
            db.flush()
            return existing

        new_ev = BidderEvidenceModel(
            id=uuid.uuid4(),
            evidence_id=uuid.uuid4(),
            bidder_id=bidder_id,
            field=field_norm,
            value=value,
            source_document=source_document,
            confidence=float(confidence),
        )
        db.add(new_ev)
        db.flush()
        return new_ev

    def get_bidder_evidence(
        self,
        db: Session,
        bidder_id: Union[UUID, str],
        field: Optional[str] = None,
        document_id: Optional[Union[UUID, str]] = None,
    ) -> List[BidderEvidenceModel]:
        """
        Retrieves evidence strictly scoped to a single bidder (ensuring tenant/bidder isolation).
        Evidence belonging to Bidder A is never returned for Bidder B.
        """
        if isinstance(bidder_id, str):
            bidder_id = UUID(bidder_id.strip())

        query = select(BidderEvidenceModel).where(BidderEvidenceModel.bidder_id == bidder_id)
        if field:
            query = query.where(BidderEvidenceModel.field == str(field).strip().lower().replace(" ", "_"))

        evidences = list(db.scalars(query).all())
        if document_id:
            doc_id_str = str(document_id)
            filtered = []
            for ev in evidences:
                if isinstance(ev.value, dict) and ev.value.get("document_id") == doc_id_str:
                    filtered.append(ev)
                elif ev.source_document and doc_id_str in ev.source_document:
                    filtered.append(ev)
            if filtered:
                return filtered

        return evidences


bidder_intake_service = BidderIntakeService()
