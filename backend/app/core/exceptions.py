import logging
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.core.exceptions")

HTTP_422_STATUS = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)

# HTTP status code to standard error code mapping
STATUS_CODE_MAP = {
    status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
    status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
    status.HTTP_403_FORBIDDEN: "FORBIDDEN",
    status.HTTP_404_NOT_FOUND: "NOT_FOUND",
    status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
    status.HTTP_409_CONFLICT: "CONFLICT",
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
    details: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None,
) -> JSONResponse:
    """Creates a consistent JSON error response structure."""
    content: Dict[str, Any] = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        content["error"]["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=content,
    )


class AppException(Exception):
    """Base application exception for managed business and operational errors."""

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
        self.code = code or STATUS_CODE_MAP.get(status_code, "APPLICATION_ERROR")
        self.details = details


class NotFoundException(AppException):
    """Resource not found error."""

    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            details=details,
        )


class BadRequestException(AppException):
    """Bad request error."""

    def __init__(self, message: str = "Bad request", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
            details=details,
        )


class DatabaseException(AppException):
    """Database query or connectivity error."""

    def __init__(self, message: str = "Database operation failed", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_ERROR",
            details=details,
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler for custom managed application exceptions."""
    logger.warning(
        f"AppException on {request.method} {request.url.path}: [{exc.code}] {exc.message}"
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
    return build_error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
    )


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
    """
    Catch-all handler for unexpected internal exceptions.
    Logs full traceback securely on server side while returning sanitized error to clients.
    """
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
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
