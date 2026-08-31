import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.router import api_v1_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import RequestLoggingMiddleware
from app.dependencies.database import get_db

# Initialize application logging
setup_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management for startup and shutdown procedures."""
    logger.info(
        f"Starting {settings.APP_NAME} [version: {settings.VERSION}] [env: {settings.APP_ENV}]"
    )
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# Register Global Exception Handlers
register_exception_handlers(app)

# Request / Response Logging Middleware
app.add_middleware(RequestLoggingMiddleware)

# Configurable CORS Middleware
if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount versioned API routes
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["status"])
def root():
    """Root status endpoint providing platform metadata."""
    return {
        "project": settings.APP_NAME,
        "status": "running",
        "version": settings.VERSION,
        "environment": settings.APP_ENV,
        "api_v1_docs": f"{settings.API_V1_STR}/openapi.json",
    }


@app.get("/health", tags=["health"])
def health_check():
    """Application operational health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/db", tags=["health"])
def db_health_check(db: Session = Depends(get_db)):
    """Database connectivity health check endpoint."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return {
                "status": "healthy",
                "database": "connected",
            }
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "unexpected_response",
            },
        )
    except Exception as e:
        logger.error(f"Database health check failed: {type(e).__name__}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
            },
        )


