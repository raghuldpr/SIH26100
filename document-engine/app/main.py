import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.schemas.health import HealthResponse, ServiceInfoResponse

# Initialize structured logging
setup_logging()
logger = logging.getLogger("document_engine.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management for Document Engine service."""
    logger.info(
        f"Starting {settings.APP_NAME} [version: {settings.VERSION}] [env: {settings.APP_ENV}]"
    )
    # Ensure temporary scratch folder exists
    temp_dir = settings.temp_path
    logger.info(f"Scratch temporary directory initialized at: {temp_dir}")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Register centralized exception handlers
register_exception_handlers(app)

# Configurable CORS Middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["health"],
    summary="Health Check",
)
def health_check() -> HealthResponse:
    """Operational health check endpoint for Document Engine service."""
    return HealthResponse(
        status="healthy",
        service="document-engine",
        version=settings.VERSION,
        environment=settings.APP_ENV,
    )


@app.get(
    "/",
    response_model=ServiceInfoResponse,
    status_code=status.HTTP_200_OK,
    tags=["status"],
    summary="Service Root Metadata",
)
def root() -> ServiceInfoResponse:
    """Root discovery endpoint providing service status and metadata."""
    return ServiceInfoResponse(
        project=settings.APP_NAME,
        service="document-engine",
        status="running",
        version=settings.VERSION,
        environment=settings.APP_ENV,
        docs_url="/docs",
        api_prefix=settings.API_V1_STR,
    )


# Mount versioned API routes
app.include_router(api_router, prefix=settings.API_V1_STR)
