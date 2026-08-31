from typing import Dict, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Operational health check response model."""

    status: str = Field("healthy", description="Operational status of the service")
    service: str = Field(..., description="Service identifier")
    version: str = Field(..., description="Service release version")
    environment: str = Field(..., description="Deployment environment")


class ServiceInfoResponse(BaseModel):
    """Service metadata and OpenAPI discovery response model."""

    project: str = Field(..., description="Project name")
    service: str = Field(..., description="Service name")
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Release version")
    environment: str = Field(..., description="Environment (development, staging, production)")
    docs_url: str = Field(..., description="OpenAPI documentation path")
    api_prefix: str = Field(..., description="API base prefix for endpoints")
