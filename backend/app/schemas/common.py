from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """Structured representation of a validation or operational error detail."""
    field: Optional[str] = Field(None, description="Path to invalid request parameter or body property")
    message: str = Field(..., description="Human-readable description of the error condition")
    type: Optional[str] = Field(None, description="Machine-readable error type identifier")


class ErrorResponseContent(BaseModel):
    """Inner error payload for standardized error responses."""
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[List[ErrorDetail]] = Field(None, description="Optional granular list of error details")


class StandardResponse(BaseModel, Generic[DataT]):
    """Standard generic envelope for successful API responses."""
    success: bool = Field(True, description="Indicates request success state")
    data: Optional[DataT] = Field(None, description="Payload data returned by the endpoint")
    message: Optional[str] = Field(None, description="Optional informative message")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class StandardErrorResponse(BaseModel):
    """Standard envelope for failed API responses."""
    success: bool = Field(False, description="Indicates request failure state")
    error: ErrorResponseContent = Field(..., description="Error payload details")


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = Field("healthy", description="Current health status of the service")
    api_version: Optional[str] = Field(None, description="API version identifier")
    environment: Optional[str] = Field(None, description="Active environment name")
    database: Optional[str] = Field(None, description="Database connectivity status if probed")


class PaginationMeta(BaseModel):
    """Metadata describing a paginated list response."""
    total_count: int = Field(..., ge=0, description="Total number of matching records")
    page: int = Field(..., ge=1, description="Current page index (1-based)")
    page_size: int = Field(..., ge=1, le=100, description="Number of records per page")
    total_pages: int = Field(..., ge=0, description="Total number of available pages")


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Generic envelope for paginated collection responses."""
    success: bool = Field(True, description="Indicates request success state")
    data: List[DataT] = Field(default_factory=list, description="List of items for the requested page")
    items: List[DataT] = Field(default_factory=list, description="List of items for standard paginated schema")
    page: int = Field(1, ge=1, description="Current page index (1-based)")
    page_size: int = Field(20, ge=1, le=100, description="Number of records per page")
    total: int = Field(0, ge=0, description="Total number of matching records")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")
