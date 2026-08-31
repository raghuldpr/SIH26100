import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("document_engine.exceptions")

HTTP_422_STATUS = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

HTTP_413_STATUS = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)

STATUS_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    HTTP_413_STATUS: "PAYLOAD_TOO_LARGE",
    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: "UNSUPPORTED_MEDIA_TYPE",
    HTTP_422_STATUS: "VALIDATION_ERROR",
    422: "VALIDATION_ERROR",
    status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_SERVER_ERROR",
    status.HTTP_502_BAD_GATEWAY: "BAD_GATEWAY",
    status.HTTP_503_SERVICE_UNAVAILABLE: "SERVICE_UNAVAILABLE",
}


def build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Union[List[Dict[str, Any]], Dict[str, Any], Any]] = None,
) -> JSONResponse:
    """Creates a consistent JSON error response structure matching SIH26100 conventions."""
    content: Dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        content["error"]["details"] = details

    return JSONResponse(status_code=status_code, content=content)


class DocumentEngineException(Exception):
    """Base application exception for managed Document Engine operational errors."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        code: Optional[str] = None,
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or STATUS_CODE_MAP.get(status_code, "DOCUMENT_ENGINE_ERROR")
        self.details = details


class DocumentNotFoundException(DocumentEngineException):
    """Raised when a requested document cannot be located."""

    def __init__(self, message: str = "Document not found", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="DOCUMENT_NOT_FOUND",
            details=details,
        )


class UnsupportedDocumentException(DocumentEngineException):
    """Raised when an uploaded document type or mime is unsupported."""

    def __init__(
        self, message: str = "Unsupported document format", details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            code="UNSUPPORTED_DOCUMENT_TYPE",
            details=details,
        )


class FileSizeExceededException(DocumentEngineException):
    """Raised when an uploaded document exceeds the maximum permitted size."""

    def __init__(
        self, message: str = "File size exceeds the maximum permitted limit", details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            status_code=HTTP_413_STATUS,
            code="FILE_TOO_LARGE",
            details=details,
        )


class ExtractionException(DocumentEngineException):
    """Raised when document extraction or OCR parsing fails."""

    def __init__(
        self, message: str = "Document extraction failed", details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            status_code=HTTP_422_STATUS,
            code="EXTRACTION_FAILED",
            details=details,
        )


class DocumentValidationException(DocumentEngineException):
    """Raised when document parameters or structure fail verification."""

    def __init__(
        self, message: str = "Document validation failed", details: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="DOCUMENT_VALIDATION_ERROR",
            details=details,
        )


class CorruptedPDFException(ExtractionException):
    """Raised when a PDF is malformed, unreadable, or corrupted."""

    def __init__(
        self, message: str = "PDF file is damaged or corrupted", details: Optional[Any] = None
    ):
        super().__init__(message=message, details=details)
        self.code = "CORRUPTED_PDF"


class PasswordProtectedPDFException(ExtractionException):
    """Raised when a PDF file is password protected or encrypted."""

    def __init__(
        self,
        message: str = "PDF file is encrypted or password-protected",
        details: Optional[Any] = None,
    ):
        super().__init__(message=message, details=details)
        self.code = "PASSWORD_PROTECTED_PDF"


class EmptyPDFException(ExtractionException):
    """Raised when a PDF document has zero pages."""

    def __init__(
        self, message: str = "PDF document contains no pages", details: Optional[Any] = None
    ):
        super().__init__(message=message, details=details)
        self.code = "EMPTY_PDF"


class CorruptedImageException(ExtractionException):
    """Raised when an image is unreadable, corrupted, or cannot be decoded."""

    def __init__(
        self, message: str = "Image file is unreadable or corrupted", details: Optional[Any] = None
    ):
        super().__init__(message=message, details=details)
        self.code = "CORRUPTED_IMAGE"


class UnsupportedImageException(UnsupportedDocumentException):
    """Raised when an image format is unsupported."""

    def __init__(
        self, message: str = "Unsupported image format", details: Optional[Any] = None
    ):
        super().__init__(message=message, details=details)
        self.code = "UNSUPPORTED_IMAGE_FORMAT"


async def document_engine_exception_handler(
    request: Request, exc: DocumentEngineException
) -> JSONResponse:
    """Handler for custom managed Document Engine exceptions."""
    logger.warning(
        f"DocumentEngineException on {request.method} {request.url.path}: [{exc.code}] {exc.message}"
    )
    return build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handler for standard Starlette/FastAPI HTTPExceptions."""
    code = STATUS_CODE_MAP.get(exc.status_code, "HTTP_ERROR")
    message = exc.detail if isinstance(exc.detail, str) else "An HTTP error occurred."

    logger.warning(
        f"HTTPException on {request.method} {request.url.path}: [{exc.status_code}] {message}"
    )
    return build_error_response(status_code=exc.status_code, code=code, message=message)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handler for Pydantic and request parameter validation errors."""
    formatted_errors = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", []))
        formatted_errors.append(
            {
                "field": loc,
                "message": err.get("msg", "Invalid field"),
                "type": err.get("type", "value_error"),
            }
        )

    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {len(formatted_errors)} issue(s)"
    )
    return build_error_response(
        status_code=HTTP_422_STATUS,
        code="VALIDATION_ERROR",
        message="Request validation failed.",
        details=formatted_errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected internal exceptions."""
    logger.error(
        f"Unhandled internal exception on {request.method} {request.url.path}: {type(exc).__name__} - {str(exc)}",
        exc_info=True,
    )
    return build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected internal server error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers all global exception handlers onto the FastAPI application instance."""
    app.add_exception_handler(DocumentEngineException, document_engine_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
