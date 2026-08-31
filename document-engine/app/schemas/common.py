from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Detailed validation or system error descriptor."""

    field: Optional[str] = Field(None, description="Path or name of field triggering the error")
    message: str = Field(..., description="Error explanation")
    type: Optional[str] = Field(None, description="Underlying error class or code")


class ErrorBody(BaseModel):
    """Encapsulated error details."""

    code: str = Field(..., description="Machine-readable error identifier")
    message: str = Field(..., description="Human-readable summary of the error")
    details: Optional[Any] = Field(None, description="Optional detailed error metadata or list")


class ErrorResponse(BaseModel):
    """Standard error response format across SIH26100 services."""

    success: bool = Field(False, description="Always false for error responses")
    error: ErrorBody

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": "The requested document was not found",
                    "details": None,
                },
            }
        }
    )


class ApiResponse(BaseModel, Generic[T]):
    """Generic envelope for successful API responses."""

    success: bool = Field(True, description="Always true for successful responses")
    data: T
    message: Optional[str] = Field(None, description="Optional informational message")
