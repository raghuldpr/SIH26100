from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings

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
    """Health check endpoint."""
    return {"status": "healthy"}
