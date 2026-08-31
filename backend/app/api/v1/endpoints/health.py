from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import check_database_connection
from app.dependencies.database import get_db
from app.schemas.common import HealthResponse

health_router = APIRouter(tags=["health"])


@health_router.get(
    "/health",
    response_model=HealthResponse,
    summary="API v1 Health Check",
    description="Returns the operational status of API v1.",
)
def api_v1_health_check() -> HealthResponse:
    """API version 1 operational health check endpoint."""
    return HealthResponse(
        status="healthy",
        api_version="v1",
        environment=settings.APP_ENV,
    )


@health_router.get(
    "/health/db",
    summary="API v1 Database Health Check",
    description="Probes PostgreSQL / Supabase database connectivity using a lightweight query.",
)
def api_v1_db_health_check(db: Session = Depends(get_db)):
    """API version 1 database connectivity health check endpoint."""
    if check_database_connection(db):
        return {
            "status": "healthy",
            "database": "connected",
            "api_version": "v1",
        }
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "unhealthy",
            "database": "disconnected",
            "api_version": "v1",
        },
    )
