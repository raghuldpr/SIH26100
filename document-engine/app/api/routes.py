import logging
import uuid
from pathlib import Path
import shutil
from fastapi import APIRouter, File, UploadFile, status

from app.core.config import settings
from app.core.exceptions import (
    EmptyPDFException,
    FileSizeExceededException,
    UnsupportedDocumentException,
)
from app.extractors.pdf_extractor import PDFExtractor
from app.extractors.table_extractor import TableExtractor
from app.schemas.extractor import PDFExtractionResult
from app.schemas.health import HealthResponse, ServiceInfoResponse
from app.schemas.table import TableExtractionResult
from app.schemas.unified import UnifiedDocumentResponse
from app.services.document_service import DocumentService

logger = logging.getLogger("document_engine.api.routes")

api_router = APIRouter()

ALLOWED_PDF_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/acrobat",
    "applications/vnd.pdf",
    "text/pdf",
    "application/octet-stream",  # Sometimes set by generic clients
}


@api_router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Document Engine Health Check",
    tags=["health"],
)
def api_health() -> HealthResponse:
    """Returns the operational status of the Document Engine service."""
    return HealthResponse(
        status="healthy",
        service="document-engine",
        version=settings.VERSION,
        environment=settings.APP_ENV,
    )


@api_router.get(
    "/info",
    response_model=ServiceInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Service Information",
    tags=["service"],
)
def api_info() -> ServiceInfoResponse:
    """Returns discovery metadata for the Document Engine service."""
    return ServiceInfoResponse(
        project=settings.APP_NAME,
        service="document-engine",
        status="running",
        version=settings.VERSION,
        environment=settings.APP_ENV,
        docs_url="/docs",
        api_prefix=settings.API_V1_STR,
    )


@api_router.post(
    "/extract/pdf",
    response_model=PDFExtractionResult,
    status_code=status.HTTP_200_OK,
    summary="Extract Text from PDF Document",
    tags=["extraction"],
    description="Accepts a PDF document upload and extracts native text page-by-page with metadata.",
)
async def extract_pdf_endpoint(
    file: UploadFile = File(..., description="PDF file to extract text from"),
) -> PDFExtractionResult:
    """
    Extracts text page-by-page from an uploaded PDF.
    Validates MIME type, file extension, and %PDF- header magic bytes.
    """
    filename = file.filename or "document.pdf"

    # 1. Validate extension
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedDocumentException(
            message=f"Invalid file extension for '{filename}'. Only .pdf is supported.",
            details={"filename": filename},
        )

    # 2. Validate MIME type
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_PDF_MIME_TYPES:
        raise UnsupportedDocumentException(
            message=f"Unsupported MIME type '{content_type}'. Expected 'application/pdf'.",
            details={"content_type": content_type},
        )

    # 3. Read header to validate magic bytes before full processing
    header = await file.read(1024)
    if not header:
        raise EmptyPDFException(message=f"Uploaded file '{filename}' is empty (0 bytes)")

    if b"%PDF-" not in header:
        raise UnsupportedDocumentException(
            message=f"Uploaded file '{filename}' is not a valid PDF document (missing %PDF- header)",
            details={"filename": filename},
        )

    # Rewind file position
    await file.seek(0)

    # 4. Stream to temporary scratch file
    temp_filename = f"upload_{uuid.uuid4().hex}_{Path(filename).name}"
    temp_path = settings.temp_path / temp_filename

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 5. Execute extraction
        result = PDFExtractor.extract(temp_path)
        return result

    finally:
        # 6. Ensure temporary file is safely cleaned up
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove temporary file {temp_path}: {e}")


@api_router.post(
    "/extract/tables",
    response_model=TableExtractionResult,
    status_code=status.HTTP_200_OK,
    summary="Extract Tables from PDF Document",
    tags=["extraction"],
    description="Accepts a digital PDF document upload and extracts tabular data page-by-page using pdfplumber.",
)
async def extract_tables_endpoint(
    file: UploadFile = File(..., description="PDF file to extract tables from"),
) -> TableExtractionResult:
    """
    Extracts tables page-by-page from an uploaded PDF.
    Normalizes rows and columns, handles missing cells, and detects scanned documents.
    """
    filename = file.filename or "document.pdf"

    # 1. Validate extension
    if not filename.lower().endswith(".pdf"):
        raise UnsupportedDocumentException(
            message=f"Invalid file extension for '{filename}'. Only .pdf is supported.",
            details={"filename": filename},
        )

    # 2. Validate MIME type
    content_type = (file.content_type or "").lower()
    if content_type and content_type not in ALLOWED_PDF_MIME_TYPES:
        raise UnsupportedDocumentException(
            message=f"Unsupported MIME type '{content_type}'. Expected 'application/pdf'.",
            details={"content_type": content_type},
        )

    # 3. Read header to validate magic bytes before full processing
    header = await file.read(1024)
    if not header:
        raise EmptyPDFException(message=f"Uploaded file '{filename}' is empty (0 bytes)")

    if b"%PDF-" not in header:
        raise UnsupportedDocumentException(
            message=f"Uploaded file '{filename}' is not a valid PDF document (missing %PDF- header)",
            details={"filename": filename},
        )

    # Rewind file position
    await file.seek(0)

    # 4. Stream to temporary scratch file
    temp_filename = f"upload_tbl_{uuid.uuid4().hex}_{Path(filename).name}"
    temp_path = settings.temp_path / temp_filename

    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 5. Execute table extraction
        result = TableExtractor.extract(temp_path)
        return result

    finally:
        # 6. Ensure temporary file is safely cleaned up
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove temporary file {temp_path}: {e}")


ALLOWED_IMAGE_MIME_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/tiff",
    "image/bmp",
    "image/webp",
}
ALLOWED_ALL_DOCUMENT_MIME_TYPES = ALLOWED_PDF_MIME_TYPES | ALLOWED_IMAGE_MIME_TYPES


@api_router.post(
    "/documents/process",
    response_model=UnifiedDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Document through Unified Pipeline",
    tags=["pipeline"],
    description="Unified document processing endpoint: validates, routes native/OCR extraction, extracts tables, classifies type, and parses structured fields.",
)
async def process_document_endpoint(
    file: UploadFile = File(..., description="PDF or image document to process"),
) -> UnifiedDocumentResponse:
    """
    Unified document processing pipeline endpoint.
    Accepts PDF and images, validates size and MIME types, securely creates temporary scratch,
    runs DocumentService.process_document, and guarantees scratch cleanup.
    """
    filename = file.filename or "document.pdf"
    content_type = (file.content_type or "").lower()
    suffix = Path(filename).suffix.lower()

    # Secure request logging (omitting document content)
    logger.info(f"Incoming document processing request: filename='{filename}', mime='{content_type}'")

    # 1. Extension validation
    is_pdf = suffix == ".pdf"
    is_img = suffix in {".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"}

    if not is_pdf and not is_img:
        raise UnsupportedDocumentException(
            message=f"Unsupported file extension '{suffix}'. Supported formats: PDF, PNG, JPG, TIFF, BMP, WEBP.",
            details={"filename": filename},
        )

    # 2. MIME type validation
    if content_type and content_type not in ALLOWED_ALL_DOCUMENT_MIME_TYPES:
        raise UnsupportedDocumentException(
            message=f"Unsupported MIME type '{content_type}'.",
            details={"content_type": content_type},
        )

    # 3. Stream upload with size validation
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    temp_filename = f"proc_{uuid.uuid4().hex}_{Path(filename).name}"
    temp_path = settings.temp_path / temp_filename

    total_bytes = 0
    try:
        with open(temp_path, "wb") as buffer:
            while chunk := await file.read(64 * 1024):  # 64 KB chunks
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise FileSizeExceededException(
                        message=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB",
                        details={"file_size_bytes": total_bytes, "max_allowed_bytes": max_bytes},
                    )
                buffer.write(chunk)

        if total_bytes == 0:
            raise EmptyPDFException(message=f"Uploaded file '{filename}' is empty (0 bytes)")

        # 4. Execute unified pipeline
        response = DocumentService.process_document(temp_path, filename=filename)
        return response

    finally:
        # 5. Clean up temporary uploaded file
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError as e:
                logger.warning(f"Failed to remove temporary upload file {temp_path}: {e}")


