"""
SIH-26100 — Phase 11.9: Verification Output Packaging & Traceability Mapping Service
Packages document extraction, section detection, and normalized requirement results into
a canonical, immutable, API-ready output package with full source provenance.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Union
import uuid

from app.schemas.normalized_content import NormalizedDocument
from app.schemas.packaged_output import (
    CanonicalDocumentOutput,
    DocumentTraceability,
    ExtractionSummary,
    PackagedDocumentMetadata,
    PackagedRequirement,
    PackagedSection,
    RequirementAIMetadata,
    RequirementResolution,
    RequirementTraceability,
)
from app.schemas.processing import ExtractionResult
from app.schemas.tender_requirement_normalizer import (
    NormalizationResult,
    NormalizationStatus,
    NormalizedRequirement,
)
from app.schemas.tender_section import DetectedTenderSection, TenderSectionDetectionResult

logger = logging.getLogger("app.services.verification_packaging_service")


class VerificationPackagingService:
    """
    Pure transformation engine that packages heterogeneous document intelligence outputs
    into the canonical Phase 11.9 verification DTO.
    Ensures complete source lineage, strict segregation of AI vs deterministic telemetry,
    and safe serialization for downstream verification agents.
    """

    @classmethod
    def package_verification_output(
        cls,
        document: Optional[Union[Dict[str, Any], Any]] = None,
        sections: Optional[Union[List[Union[DetectedTenderSection, Dict[str, Any]]], TenderSectionDetectionResult]] = None,
        requirements: Optional[Union[List[Union[NormalizedRequirement, Dict[str, Any]]], NormalizationResult]] = None,
        extraction_result: Optional[ExtractionResult] = None,
        document_id: Optional[Union[str, uuid.UUID]] = None,
        document_hash: Optional[str] = None,
        document_type: Optional[str] = None,
        processing_status: Optional[str] = None,
        filename: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: Optional[str] = None,
        total_pages: Optional[int] = None,
        extraction_format: Optional[str] = None,
    ) -> CanonicalDocumentOutput:
        """
        Builds a canonical, strongly-typed CanonicalDocumentOutput package.
        """
        # 1. Resolve Document-level Metadata
        doc_id_str: Optional[str] = str(document_id) if document_id else None
        doc_hash_str: Optional[str] = document_hash
        doc_type_str: str = document_type or "TENDER"
        proc_status_str: str = processing_status or "COMPLETED"
        orig_filename: Optional[str] = filename
        f_size: Optional[int] = file_size
        m_type: Optional[str] = mime_type

        # Extract from document object or dict if provided
        if document is not None:
            if isinstance(document, dict):
                doc_id_str = str(document.get("id") or document.get("document_id") or doc_id_str)
                doc_hash_str = document.get("sha256") or document.get("document_hash") or doc_hash_str
                doc_type_str = str(document.get("document_type") or doc_type_str)
                proc_status_str = str(document.get("processing_status") or proc_status_str)
                orig_filename = document.get("original_filename") or document.get("filename") or orig_filename
                f_size = document.get("file_size") if document.get("file_size") is not None else f_size
                m_type = document.get("mime_type") or m_type
            else:
                # SQLAlchemy Document model or Pydantic metadata
                if hasattr(document, "id") and document.id:
                    doc_id_str = str(document.id)
                if hasattr(document, "sha256") and document.sha256:
                    doc_hash_str = document.sha256
                if hasattr(document, "document_type") and document.document_type:
                    doc_type_str = getattr(document.document_type, "value", str(document.document_type))
                if hasattr(document, "processing_status") and document.processing_status:
                    proc_status_str = getattr(document.processing_status, "value", str(document.processing_status))
                if hasattr(document, "original_filename") and document.original_filename:
                    orig_filename = document.original_filename
                if hasattr(document, "file_size") and document.file_size is not None:
                    f_size = document.file_size
                if hasattr(document, "mime_type") and document.mime_type:
                    m_type = document.mime_type

        # Extract from extraction_result if provided
        ext_format = extraction_format or (extraction_result.format if extraction_result else "PDF")
        calc_total_pages = total_pages or (extraction_result.page_count if extraction_result else None)

        doc_meta = PackagedDocumentMetadata(
            document_id=doc_id_str,
            document_hash=doc_hash_str,
            document_type=doc_type_str,
            processing_status=proc_status_str,
            original_filename=orig_filename,
            file_size=f_size,
            mime_type=m_type,
        )

        # 2. Package Sections
        packaged_sections: List[PackagedSection] = []
        raw_sections_list: List[Any] = []

        if sections is not None:
            if isinstance(sections, TenderSectionDetectionResult):
                raw_sections_list = sections.sections
            elif isinstance(sections, list):
                raw_sections_list = sections

        for sec in raw_sections_list:
            if isinstance(sec, DetectedTenderSection):
                packaged_sections.append(
                    PackagedSection(
                        section_id=sec.section_id,
                        name=sec.name,
                        section_type=getattr(sec.section_type, "value", str(sec.section_type)),
                        heading_raw=sec.heading_raw,
                        page_start=sec.page_start,
                        page_end=sec.page_end,
                        source_reference=sec.source_reference,
                        confidence=sec.confidence,
                    )
                )
            elif isinstance(sec, dict):
                packaged_sections.append(
                    PackagedSection(
                        section_id=sec["section_id"],
                        name=sec["name"],
                        section_type=str(sec.get("section_type", "OTHER")),
                        heading_raw=sec.get("heading_raw"),
                        page_start=sec.get("page_start", 1),
                        page_end=sec.get("page_end", sec.get("page_start", 1)),
                        source_reference=sec.get("source_reference", f"Section {sec.get('section_id')}"),
                        confidence=sec.get("confidence", 1.0),
                    )
                )

        # 3. Package Requirements
        packaged_requirements: List[PackagedRequirement] = []
        raw_req_list: List[Any] = []

        if requirements is not None:
            if isinstance(requirements, NormalizationResult):
                raw_req_list = requirements.requirements
            elif isinstance(requirements, list):
                raw_req_list = requirements

        det_count = 0
        ai_count = 0
        amb_count = 0
        fail_count = 0

        for idx, r in enumerate(raw_req_list, start=1):
            if isinstance(r, NormalizedRequirement):
                status_str = r.status.value if hasattr(r.status, "value") else str(r.status)
                res_method = r.resolution_method or ("AI_GATEWAY" if status_str == "AI_RESOLVED" else "DETERMINISTIC")
                if status_str in ("AMBIGUOUS", "UNRESOLVED") and res_method != "AI_GATEWAY":
                    res_method = "UNRESOLVED"

                # Categorical summary metrics
                if status_str == "NORMALIZED":
                    det_count += 1
                elif status_str == "AI_RESOLVED":
                    ai_count += 1
                elif status_str == "AMBIGUOUS":
                    amb_count += 1
                else:
                    fail_count += 1

                # Construct AI metadata only if resolved by AI Gateway
                ai_meta: Optional[RequirementAIMetadata] = None
                if res_method == "AI_GATEWAY" and r.model_metadata:
                    m = r.model_metadata
                    ai_meta = RequirementAIMetadata(
                        provider=m.get("provider", "groq"),
                        model=m.get("model"),
                        prompt_tokens=m.get("prompt_tokens"),
                        completion_tokens=m.get("completion_tokens"),
                        total_tokens=m.get("total_tokens"),
                        latency_ms=m.get("latency_ms"),
                        escalation_reason=r.escalation_reason or m.get("reason_for_escalation"),
                    )

                req_id = f"REQ-{idx:03d}" if not r.document_id else f"{r.document_id[:8]}-REQ-{idx:03d}"

                packaged_req = PackagedRequirement(
                    requirement_id=req_id,
                    category=r.type or "OTHER",
                    type=r.rule or "GENERAL_CRITERIA",
                    description=r.description or r.source_text,
                    parameters=r.parameters or {},
                    mandatory=r.mandatory,
                    resolution=RequirementResolution(
                        status=status_str,
                        method=res_method,
                        confidence=r.confidence,
                        reason=r.ambiguity_reason or r.escalation_reason,
                    ),
                    traceability=RequirementTraceability(
                        document_id=r.document_id or doc_id_str,
                        document_hash=doc_hash_str,
                        page_start=r.page_start or r.source_page,
                        page_end=r.page_end or r.source_page,
                        source_page=r.source_page,
                        section_id=r.section_id,
                        source_section=r.source_section,
                        source_text=r.source_text,
                        extraction_method="groq" if res_method == "AI_GATEWAY" else "deterministic",
                        ai_metadata=ai_meta,
                    ),
                )
                packaged_requirements.append(packaged_req)

            elif isinstance(r, dict):
                status_str = str(r.get("status", "NORMALIZED"))
                res_method = str(r.get("resolution_method", "DETERMINISTIC"))
                if status_str == "NORMALIZED":
                    det_count += 1
                elif status_str == "AI_RESOLVED":
                    ai_count += 1
                elif status_str == "AMBIGUOUS":
                    amb_count += 1
                else:
                    fail_count += 1

                req_id = r.get("requirement_id") or f"REQ-{idx:03d}"

                packaged_req = PackagedRequirement(
                    requirement_id=req_id,
                    category=r.get("category") or r.get("type", "OTHER"),
                    type=r.get("rule") or r.get("type", "GENERAL_CRITERIA"),
                    description=r.get("description", r.get("source_text", "")),
                    parameters=r.get("parameters", {}),
                    mandatory=r.get("mandatory", True),
                    resolution=RequirementResolution(
                        status=status_str,
                        method=res_method,
                        confidence=r.get("confidence"),
                        reason=r.get("ambiguity_reason") or r.get("reason"),
                    ),
                    traceability=RequirementTraceability(
                        document_id=r.get("document_id") or doc_id_str,
                        document_hash=r.get("document_hash") or doc_hash_str,
                        page_start=r.get("page_start") or r.get("source_page"),
                        page_end=r.get("page_end") or r.get("source_page"),
                        source_page=r.get("source_page"),
                        section_id=r.get("section_id"),
                        source_section=r.get("source_section"),
                        source_text=r.get("source_text", ""),
                        extraction_method=r.get("extraction_method", "deterministic"),
                    ),
                )
                packaged_requirements.append(packaged_req)

        # 4. Compute Summary
        summary = ExtractionSummary(
            total_requirements=len(packaged_requirements),
            deterministic_requirements=det_count,
            ai_resolved_requirements=ai_count,
            ambiguous_requirements=amb_count,
            failed_requirements=fail_count,
        )

        # 5. Build Document Traceability
        doc_trace = DocumentTraceability(
            document_id=doc_id_str,
            document_hash=doc_hash_str,
            total_pages=calc_total_pages,
            total_sections=len(packaged_sections),
            extraction_format=ext_format,
            processed_at=datetime.now(timezone.utc),
        )

        logger.info(
            f"Verification output packaging complete [doc_id={doc_id_str}, "
            f"requirements={len(packaged_requirements)}, deterministic={det_count}, ai={ai_count}]"
        )

        return CanonicalDocumentOutput(
            document=doc_meta,
            sections=packaged_sections,
            requirements=packaged_requirements,
            extraction_summary=summary,
            traceability=doc_trace,
        )


verification_packaging_service = VerificationPackagingService()
package_verification_output = verification_packaging_service.package_verification_output
