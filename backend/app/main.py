import logging
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SIH26100 API",
    description="AI-powered Bid Compliance Verification Platform",
    version="0.1.0",
)

# Enable CORS for development frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    """Root status endpoint."""
    return {
        "project": settings.APP_NAME,
        "status": "running",
        "version": "0.1.0",
        "environment": settings.APP_ENV,
    }


@app.get("/health")
def health_check():
    """Application health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/db")
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
