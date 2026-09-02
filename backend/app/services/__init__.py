from app.services.document_classifier import (
    RuleBasedDocumentClassifier,
    document_classifier,
)
from app.services.document_processing_pipeline import (
    DocumentProcessingPipeline,
    processing_pipeline,
)
from app.services.document_processor import DocumentProcessor, document_processor
from app.services.entity_extractor import (
    DocumentEntityExtractor,
    entity_extractor,
)
from app.services.image_preprocessor import ImagePreprocessor, image_preprocessor
from app.services.content_normalizer import (
    DocumentContentNormalizer,
    content_normalizer,
    format_indian_number,
    format_standard_number,
)
from app.services.docx_extractor import DOCXExtractor, docx_extractor
from app.services.pdf_extractor import PDFExtractor, pdf_extractor
from app.services.tender_section_detector import TenderSectionDetector, tender_section_detector
from app.services.xlsx_extractor import XLSXExtractor, xlsx_extractor
from app.services.storage_service import (
    SupabaseStorageService,
    generate_bidder_storage_path,
    generate_tender_storage_path,
    sanitize_filename,
    sanitize_path_segment,
    storage_service,
    validate_storage_path,
)
from app.services.ai_gateway import (
    AIGateway,
    ai_gateway,
    analyze_ambiguous_clause,
)
from app.services.tender_clause_extractor import (
    TenderClauseExtractor,
    extract_clauses,
    extract_clauses_from_sections,
    extract_clauses_from_text,
    tender_clause_extractor,
)
from app.services.tender_requirement_normalizer import (
    TenderRequirementNormalizer,
    normalize_candidates,
    normalize_clause,
    normalize_indian_currency,
    normalize_sections,
    normalize_time_expression,
    resolve_ambiguous_requirements,
    tender_requirement_normalizer,
)
from app.services.verification_packaging_service import (
    VerificationPackagingService,
    package_verification_output,
    verification_packaging_service,
)

try:
    from app.services.document_processing_service import (
        DocumentProcessingService,
        document_processing_service,
    )
    from app.services.tender_service import (
        CRUDTender,
        archive_tender,
        create_tender,
        crud_tender,
        get_tender_by_id,
        get_tender_by_number,
        list_tenders,
        update_tender,
    )
    from app.services.tender_intelligence_service import (
        TenderIntelligenceService,
        process_tender_pages,
        resolve_clause,
        tender_intelligence_service,
    )
    from app.services.compliance_service import (
        ComplianceService,
        compliance_service,
    )
except ImportError:
    DocumentProcessingService = None  # type: ignore
    document_processing_service = None  # type: ignore
    CRUDTender = None  # type: ignore
    archive_tender = None  # type: ignore
    create_tender = None  # type: ignore
    crud_tender = None  # type: ignore
    get_tender_by_id = None  # type: ignore
    get_tender_by_number = None  # type: ignore
    list_tenders = None  # type: ignore
    update_tender = None  # type: ignore
    TenderIntelligenceService = None  # type: ignore
    process_tender_pages = None  # type: ignore
    resolve_clause = None  # type: ignore
    tender_intelligence_service = None  # type: ignore
    ComplianceService = None  # type: ignore
    compliance_service = None  # type: ignore

from app.services.n8n_client import (
    N8nClient,
    N8nClientError,
    N8nConnectionError,
    N8nTimeoutError,
    n8n_client,
)
from app.services.verification_service import (
    VerificationService,
    verification_service,
)

__all__ = [
    "create_tender",
    "get_tender_by_id",
    "get_tender_by_number",
    "list_tenders",
    "update_tender",
    "archive_tender",
    "CRUDTender",
    "crud_tender",
    "SupabaseStorageService",
    "storage_service",
    "sanitize_filename",
    "sanitize_path_segment",
    "validate_storage_path",
    "generate_tender_storage_path",
    "generate_bidder_storage_path",
    "PDFExtractor",
    "pdf_extractor",
    "DOCXExtractor",
    "docx_extractor",
    "XLSXExtractor",
    "xlsx_extractor",
    "DocumentContentNormalizer",
    "content_normalizer",
    "format_indian_number",
    "format_standard_number",
    "TenderSectionDetector",
    "tender_section_detector",
    "DocumentProcessor",
    "document_processor",
    "ImagePreprocessor",
    "image_preprocessor",
    "PaddleOCREngine",
    "OCRPipeline",
    "ocr_pipeline",
    "RuleBasedDocumentClassifier",
    "document_classifier",
    "DocumentEntityExtractor",
    "entity_extractor",
    "DocumentProcessingPipeline",
    "processing_pipeline",
    "DocumentProcessingService",
    "document_processing_service",
    "TenderClauseExtractor",
    "tender_clause_extractor",
    "extract_clauses",
    "extract_clauses_from_text",
    "extract_clauses_from_sections",
    "TenderRequirementNormalizer",
    "tender_requirement_normalizer",
    "normalize_clause",
    "normalize_candidates",
    "normalize_sections",
    "resolve_ambiguous_requirements",
    "normalize_indian_currency",
    "normalize_time_expression",
    "VerificationPackagingService",
    "verification_packaging_service",
    "package_verification_output",
    "AIGateway",
    "ai_gateway",
    "analyze_ambiguous_clause",
    "TenderIntelligenceService",
    "tender_intelligence_service",
    "resolve_clause",
    "process_tender_pages",
    "ComplianceService",
    "compliance_service",
    "N8nClient",
    "n8n_client",
    "N8nClientError",
    "N8nTimeoutError",
    "N8nConnectionError",
    "VerificationService",
    "verification_service",
]
