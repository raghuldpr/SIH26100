import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.core.storage import storage_service
from app.crud.crud_document import crud_document
from app.crud.crud_tender import get_tender_by_id
from app.crud.crud_tender_requirement import crud_tender_requirement
from app.models.enums import ProcessingStatus, RequirementType
from app.schemas.ai_gateway import (
    AIGatewayResponse,
    AmbiguousClauseRequest,
    LLMClauseInterpretation,
)
from app.schemas.processing import ExtractionResult, PageExtractionResult
from app.schemas.tender_clause import ClauseCandidate
from app.schemas.tender_intelligence import (
    TenderAnalysisRequest,
    TenderComplianceProfileResponse,
)
from app.schemas.tender_requirement import TenderRequirementResponse
from app.schemas.tender_requirement_normalizer import (
    NormalizationResult,
    NormalizationStatus,
    NormalizedRequirement,
)
from app.services.ai_gateway import AIGateway, ai_gateway
from app.services.document_processor import document_processor
from app.services.tender_clause_extractor import (
    TenderClauseExtractor,
    tender_clause_extractor,
)
from app.services.tender_requirement_normalizer import (
    TenderRequirementNormalizer,
    tender_requirement_normalizer,
)
from app.services.tender_section_detector import (
    TenderSectionDetector,
    tender_section_detector,
)
from app.services.verification_packaging_service import (
    VerificationPackagingService,
    package_verification_output,
)

logger = logging.getLogger("app.services.tender_intelligence_service")


class TenderIntelligenceService:
    """
    Core orchestrator for Phase 08 (Tender Intelligence) & Phase 12.2 (Tender Flow).
    The deterministic pipeline is the primary path.
    The AI Gateway is invoked strictly when deterministic logic identifies an ambiguous clause.
    Enforces deterministic post-validation on LLM output to prevent hallucinations and conflicts.
    """

    def __init__(
        self,
        clause_extractor: Optional[TenderClauseExtractor] = None,
        requirement_normalizer: Optional[TenderRequirementNormalizer] = None,
        gateway: Optional[AIGateway] = None,
        section_detector: Optional[TenderSectionDetector] = None,
        packaging_service: Optional[VerificationPackagingService] = None,
    ) -> None:
        self.clause_extractor = clause_extractor or tender_clause_extractor
        self.normalizer = requirement_normalizer or tender_requirement_normalizer
        self.ai_gateway = gateway or ai_gateway
        self.section_detector = section_detector or tender_section_detector
        self.packaging_service = packaging_service or VerificationPackagingService

    # -------------------------------------------------------------------------
    # 1. DETERMINISTIC POST-VALIDATION OF LLM OUTPUT
    # -------------------------------------------------------------------------
    @classmethod
    def validate_llm_interpretation(
        cls,
        interpretation: LLMClauseInterpretation,
        source_text: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validates LLM output against source text and domain consistency rules.
        Rejects hallucinated parameters, missing required fields, or conflicting interpretations.
        """
        if not interpretation.is_interpretable:
            return False, f"Model marked clause as uninterpretable: {interpretation.rationale}"

        req_type = (interpretation.requirement_type or "").upper()
        rule = (interpretation.rule or "").upper()
        lower_source = source_text.lower()
        params = interpretation.parameters or {}

        # Check 1: Conflicting Requirement Type & Rule
        if req_type == "FINANCIAL" and any(term in rule for term in ("OEM", "MII", "EXPERIENCE", "DOCUMENT")):
            return False, f"Conflicting interpretation: type '{req_type}' contradicts rule '{rule}'"
        if req_type == "OEM" and "TURNOVER" in rule:
            return False, f"Conflicting interpretation: type '{req_type}' contradicts rule '{rule}'"
        if (req_type == "EXEMPTION" or "EXEMPTION" in rule) and interpretation.is_mandatory:
            return False, "Conflicting interpretation: exemptions/relaxations cannot be mandatory criteria"

        # Check 2: Missing Required Values by Rule
        if rule in ("AVERAGE_TURNOVER", "MINIMUM_TURNOVER"):
            if "minimum" not in params or params.get("minimum") is None:
                return False, f"Missing required parameter 'minimum' for rule '{rule}'"
            if "currency" not in params:
                return False, f"Missing required parameter 'currency' for rule '{rule}'"

        if rule == "OEM_AUTHORIZATION":
            if not any(term in params for term in ("authorization_type", "required")):
                return False, "Missing required parameters for OEM authorization"

        if req_type == "EXEMPTION" or "EXEMPTION" in rule:
            if "applies_to" not in params or not params.get("applies_to"):
                return False, "Missing required parameter 'applies_to' for exemption rule"

        # Check 3: Hallucination Detection (Numeric & Unit Grounding)
        # Verify that numeric values in parameters are grounded in the source text
        for param_key, param_val in params.items():
            if isinstance(param_val, (int, float)) and param_key in ("minimum", "min_years", "period", "min_completed_orders", "minimum_local_content_pct"):
                # Extract all numbers from source text
                source_numbers = re.findall(r"\d+(?:\.\d+)?", source_text)
                source_words = set(re.findall(r"\b[a-zA-Z]+\b", lower_source))

                # Check if the number, its factor, or words (crore, lakh, three, etc.) appear
                param_str = str(int(param_val) if isinstance(param_val, float) and param_val.is_integer() else param_val)

                # Check direct numeric presence
                direct_present = any(param_str == sn or sn in param_str for sn in source_numbers)

                # Check word representation presence (e.g. 1500000 -> 15 and lakh, 25000000 -> two and a half crore)
                word_grounded = False
                word_num_map = {
                    1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
                    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
                }

                if param_key == "minimum":
                    has_cr = "crore" in lower_source or "cr" in lower_source
                    has_lakh = "lakh" in lower_source or "lac" in lower_source
                    has_thousand = "thousand" in lower_source or "k" in lower_source

                    if has_cr and param_val >= 1000000:
                        cr_num = param_val / 10000000.0
                        int_part = int(cr_num)
                        word_part = word_num_map.get(int_part)
                        word_grounded = (
                            str(cr_num) in source_numbers
                            or str(int_part) in source_numbers
                            or (word_part and word_part in source_words)
                            or "half" in source_words
                        )
                    elif has_lakh and param_val >= 10000:
                        lakh_num = param_val / 100000.0
                        int_part = int(lakh_num)
                        word_part = word_num_map.get(int_part)
                        word_grounded = (
                            str(lakh_num) in source_numbers
                            or str(int_part) in source_numbers
                            or (word_part and word_part in source_words)
                        )
                    elif has_thousand:
                        word_grounded = True
                elif int(param_val) in word_num_map:
                    word_grounded = word_num_map[int(param_val)] in source_words or str(int(param_val)) in source_numbers
                elif str(param_val) in source_numbers:
                    word_grounded = True

                if not (direct_present or word_grounded):
                    return False, f"Hallucinated parameter '{param_key}: {param_val}' is not grounded in source text"

        return True, None

    # -------------------------------------------------------------------------
    # 2. HYBRID RESOLUTION PIPELINE (Deterministic First -> AI Escalation)
    # -------------------------------------------------------------------------
    def resolve_clause(
        self,
        clause: Union[ClauseCandidate, Dict[str, Any], str],
        page: Optional[int] = None,
        section: Optional[str] = None,
    ) -> NormalizedRequirement:
        """
        Resolves a single clause through the hybrid architecture:
        1. Attempt deterministic normalization.
        2. If reliable (NORMALIZED), accept immediately without invoking LLM.
        3. If ambiguous, escalate to AI Gateway with technical justification.
        4. Validate LLM response deterministically.
        5. If valid, return AI_RESOLVED requirement; otherwise mark UNRESOLVED.
        """
        # Step 1: Deterministic normalization
        det_result = self.normalizer.normalize_clause(clause, page=page, section=section)

        if det_result.status == NormalizationStatus.NORMALIZED:
            logger.debug(f"Clause resolved deterministically [rule={det_result.rule}]")
            return det_result

        # Step 2: Ambiguous clause identified -> Escalate to AI Gateway
        source_text = det_result.source_text
        escalation_reason = det_result.ambiguity_reason or "Clause syntax requires semantic interpretation of eligibility parameters"

        logger.info(
            f"Escalating ambiguous clause to AI Gateway [reason={escalation_reason[:80]}...]"
        )

        request = AmbiguousClauseRequest(
            clause_text=source_text,
            reason_for_escalation=escalation_reason,
            source_page=det_result.source_page,
            source_section=det_result.source_section,
            candidate_type=det_result.type,
            known_context=det_result.parameters,
        )

        ai_res: AIGatewayResponse = self.ai_gateway.analyze_ambiguous_clause(request)

        # Step 3: Check AI Gateway execution status
        if not ai_res.success or not ai_res.interpretation:
            logger.warning(f"AI Gateway could not resolve clause: {ai_res.metadata.error_message}")
            return NormalizedRequirement(
                status=NormalizationStatus.UNRESOLVED,
                type=det_result.type,
                rule=det_result.rule or "UNRESOLVED_CRITERIA",
                source_page=det_result.source_page,
                source_section=det_result.source_section,
                source_text=source_text,
                ambiguity_reason=f"AI resolution failed: {ai_res.metadata.error_message or 'Unknown provider error'}",
                confidence=0.30,
                resolution_method="AI_GATEWAY",
                escalation_reason=escalation_reason,
                model_metadata=ai_res.metadata.model_dump(),
            )

        # Step 4: Deterministic Post-Validation of LLM Output
        valid, failure_reason = self.validate_llm_interpretation(
            interpretation=ai_res.interpretation,
            source_text=source_text,
        )

        if not valid:
            logger.warning(f"Deterministic validation rejected LLM output: {failure_reason}")
            return NormalizedRequirement(
                status=NormalizationStatus.UNRESOLVED,
                type=ai_res.interpretation.requirement_type or det_result.type,
                rule=ai_res.interpretation.rule or "UNRESOLVED_CRITERIA",
                source_page=det_result.source_page,
                source_section=det_result.source_section,
                source_text=source_text,
                ambiguity_reason=failure_reason,
                confidence=0.30,
                resolution_method="AI_GATEWAY",
                ai_confidence=ai_res.interpretation.interpretation_confidence,
                escalation_reason=escalation_reason,
                model_metadata=ai_res.metadata.model_dump(),
            )

        # Step 5: Successful AI Resolution with Provenance
        logger.info(
            f"AI-assisted resolution successful [rule={ai_res.interpretation.rule}, confidence={ai_res.interpretation.interpretation_confidence}]"
        )
        return NormalizedRequirement(
            status=NormalizationStatus.AI_RESOLVED,
            type=ai_res.interpretation.requirement_type,
            rule=ai_res.interpretation.rule,
            description=ai_res.interpretation.description,
            parameters=ai_res.interpretation.parameters,
            mandatory=ai_res.interpretation.is_mandatory,
            confidence=ai_res.interpretation.interpretation_confidence,
            source_page=det_result.source_page,
            source_section=det_result.source_section,
            source_text=source_text,
            resolution_method="AI_GATEWAY",
            ai_confidence=ai_res.interpretation.interpretation_confidence,
            escalation_reason=escalation_reason,
            model_metadata=ai_res.metadata.model_dump(),
        )

    # -------------------------------------------------------------------------
    # 3. END-TO-END TENDER CONTENT PROCESSING & PERSISTENCE
    # -------------------------------------------------------------------------
    def process_tender_pages(
        self,
        pages: List[Union[Dict[str, Any], str]],
        tender_id: Optional[Union[UUID, str]] = None,
        db: Optional[Session] = None,
        persist: bool = False,
    ) -> NormalizationResult:
        """
        Executes end-to-end tender intelligence pipeline across document pages:
        1. Extract candidate clauses with section tracking.
        2. Resolve each clause (deterministic first -> AI fallback).
        3. Validate parameters deterministically.
        4. If persist=True and tender_id/db provided, save persistable requirements.
        """
        # Step 1: Extract candidate clauses
        extraction_res = self.clause_extractor.extract_from_pages(pages)

        # Step 2: Resolve requirements
        resolved_list: List[NormalizedRequirement] = []
        norm_count = 0
        ai_count = 0
        amb_count = 0
        unres_count = 0

        for cand in extraction_res.candidates:
            res = self.resolve_clause(cand)
            resolved_list.append(res)

            if res.status == NormalizationStatus.NORMALIZED:
                norm_count += 1
            elif res.status == NormalizationStatus.AI_RESOLVED:
                ai_count += 1
            elif res.status == NormalizationStatus.AMBIGUOUS:
                amb_count += 1
            elif res.status == NormalizationStatus.UNRESOLVED:
                unres_count += 1

        batch_result = NormalizationResult(
            total_evaluated=len(resolved_list),
            normalized_count=norm_count,
            ai_resolved_count=ai_count,
            ambiguous_count=amb_count,
            unresolved_count=unres_count,
            requirements=resolved_list,
        )

        # Step 3: Persist valid requirements if requested
        if persist and tender_id and db:
            persistable = batch_result.persistable_only()
            if persistable:
                req_creates = [req.to_tender_requirement_create() for req in persistable]
                crud_tender_requirement.upsert_requirements(
                    db=db,
                    tender_id=tender_id,
                    requirements_in=req_creates,
                )
                logger.info(f"Idempotently persisted {len(req_creates)} requirements to PostgreSQL for tender {tender_id}")

        return batch_result

    # -------------------------------------------------------------------------
    # 4. TENDER COMPLIANCE PROFILE GENERATION & RETRIEVAL
    # -------------------------------------------------------------------------
    def get_compliance_profile(
        self,
        db: Session,
        tender_id: Union[UUID, str],
    ) -> TenderComplianceProfileResponse:
        """Loads tender and returns its current Tender Compliance Profile."""
        tender = get_tender_by_id(db, tender_id)
        if not tender:
            raise NotFoundException(f"Tender {tender_id} not found")

        requirements = crud_tender_requirement.get_by_tender(db, tender.id)
        status = "COMPLETED" if requirements else "NOT_ANALYZED"

        det_reqs: List[TenderRequirementResponse] = []
        ai_reqs: List[TenderRequirementResponse] = []
        for r in requirements:
            resp = TenderRequirementResponse.model_validate(r)
            if r.parameters.get("resolution_method") == "AI_GATEWAY" or r.confidence < 0.90:
                ai_reqs.append(resp)
            else:
                det_reqs.append(resp)

        return TenderComplianceProfileResponse(
            tender_id=tender.id,
            tender_number=tender.tender_number,
            status=status,
            requirement_count=len(requirements),
            deterministic_count=len(det_reqs),
            ai_escalations=len(ai_reqs),
            unresolved_count=0,
            deterministic_requirements=det_reqs,
            ai_assisted_requirements=ai_reqs,
            unresolved_requirements=[],
            requirements=[TenderRequirementResponse.model_validate(r) for r in requirements],
        )

    def analyze_tender(
        self,
        db: Session,
        tender_id: Union[UUID, str],
        request: Optional[TenderAnalysisRequest] = None,
    ) -> TenderComplianceProfileResponse:
        """
        Executes the complete Phase 12.2 Tender Compliance Profile pipeline:
        1. Load tender from database.
        2. Obtain associated tender document from storage or raw text.
        3. Run multi-format document processing (PDF/DOCX/XLSX + selective OCR).
        4. Detect tender sections with page boundaries.
        5. Extract candidate clauses and normalize requirements deterministically.
        6. Selectively escalate ambiguous clauses to Groq AI Gateway with grounding validation.
        7. Persist requirements idempotently into PostgreSQL.
        8. Package canonical verification output (Phase 11.9).
        9. Generate and return structured Tender Compliance Profile.
        """
        tender = get_tender_by_id(db, tender_id)
        if not tender:
            raise NotFoundException(f"Tender {tender_id} not found")

        req_config = request or TenderAnalysisRequest()

        if req_config.force_reanalyze:
            crud_tender_requirement.delete_by_tender(db, tender.id)
        else:
            existing = crud_tender_requirement.get_by_tender(db, tender.id)
            if existing:
                return self.get_compliance_profile(db, tender.id)

        # Obtain document content
        pages: List[Dict[str, Any]] = []
        target_doc = None
        extraction: Optional[ExtractionResult] = None
        if req_config.raw_text:
            pages = [{"page_number": 1, "text": req_config.raw_text}]
        else:
            docs_tuple = crud_document.list_tender_documents(db, tender.id)
            attached_docs = docs_tuple[0] if docs_tuple else []
            if req_config.document_id:
                target_doc = crud_document.get_by_id(db, req_config.document_id)
            elif attached_docs:
                target_doc = attached_docs[0]

            if target_doc and target_doc.storage_path:
                try:
                    file_bytes = storage_service.download(target_doc.storage_path)
                    extraction = document_processor.process_document(
                        file_bytes=file_bytes,
                        mime_type=target_doc.mime_type,
                        filename=target_doc.original_filename,
                    )
                    pages = extraction.to_traceable_pages()

                    # Update document processing state in DB
                    if target_doc.processing_status != ProcessingStatus.PROCESSED:
                        crud_document.update_processing(
                            db=db,
                            document_id=target_doc.id,
                            processing_status=ProcessingStatus.PROCESSED,
                            extracted_data=extraction.model_dump(),
                        )
                except Exception as e:
                    logger.warning(f"Failed to extract text from document {target_doc.id}: {e}")

            if not pages:
                doc_text = f"TENDER TITLE: {tender.title}\n{tender.description or ''}"
                pages = [{"page_number": 1, "text": doc_text}]

        # Ensure we have an ExtractionResult for section detection
        if extraction is None:
            fake_pages = [
                PageExtractionResult(
                    page_number=p.get("page_number", idx + 1),
                    text=p.get("text", ""),
                )
                for idx, p in enumerate(pages)
            ]
            extraction = ExtractionResult(
                format="PDF",
                status="EXTRACTED",
                page_count=len(fake_pages),
                text="\n".join(p.get("text", "") for p in pages),
                pages=fake_pages,
            )

        # Detect tender sections
        detected_sections = self.section_detector.detect_sections(
            extraction_result=extraction,
            document_id=str(target_doc.id) if target_doc else None,
        )

        # Process pages with hybrid resolution and persist idempotently
        batch_result = self.process_tender_pages(
            pages=pages,
            tender_id=tender.id,
            db=db,
            persist=True,
        )


        # Build Canonical Verification Package (Phase 11.9)
        canonical_pkg = None
        try:
            canonical_pkg = self.packaging_service.package_verification_output(
                document=target_doc,
                sections=detected_sections.sections if hasattr(detected_sections, "sections") else detected_sections,
                requirements=batch_result.requirements,
                document_id=str(target_doc.id) if target_doc else None,
                document_hash=getattr(target_doc, "sha256", None) if target_doc else None,
                document_type="TENDER",
                filename=getattr(target_doc, "original_filename", None) if target_doc else None,
                file_size=getattr(target_doc, "file_size", None) if target_doc else None,
                mime_type=getattr(target_doc, "mime_type", None) if target_doc else None,
                total_pages=len(pages),
            )
        except Exception as e:
            logger.warning(f"Failed to assemble canonical packaging: {e}")

        persisted = crud_tender_requirement.get_by_tender(db, tender.id)
        det_reqs = [TenderRequirementResponse.model_validate(r) for r in persisted if r.parameters.get("resolution_method") != "AI_GATEWAY" and r.confidence >= 0.90]
        ai_reqs = [TenderRequirementResponse.model_validate(r) for r in persisted if r.parameters.get("resolution_method") == "AI_GATEWAY" or r.confidence < 0.90]

        return TenderComplianceProfileResponse(
            tender_id=tender.id,
            tender_number=tender.tender_number,
            status="COMPLETED",
            requirement_count=len(persisted),
            deterministic_count=len(det_reqs),
            ai_escalations=len(ai_reqs),
            unresolved_count=batch_result.unresolved_count,
            deterministic_requirements=det_reqs,
            ai_assisted_requirements=ai_reqs,
            unresolved_requirements=batch_result.unresolved_only(),
            requirements=[TenderRequirementResponse.model_validate(r) for r in persisted],
            canonical_output=canonical_pkg,
        )


tender_intelligence_service = TenderIntelligenceService()
resolve_clause = tender_intelligence_service.resolve_clause
process_tender_pages = tender_intelligence_service.process_tender_pages
analyze_tender = tender_intelligence_service.analyze_tender
get_compliance_profile = tender_intelligence_service.get_compliance_profile


