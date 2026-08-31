import pytest
from fastapi.testclient import TestClient
from starlette import status

from app.core.config import settings
from app.core.exceptions import (
    DocumentNotFoundException,
    UnsupportedDocumentException,
)
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify operational health check endpoint returns 200 OK and expected structure."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "document-engine"
    assert "version" in data
    assert "environment" in data


def test_api_v1_health_endpoint():
    """Verify versioned API health check route under /api/v1/health."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "document-engine"


def test_root_endpoint():
    """Verify service root discovery endpoint returns metadata."""
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["project"] == settings.APP_NAME
    assert data["service"] == "document-engine"
    assert data["status"] == "running"
    assert data["version"] == settings.VERSION
    assert data["docs_url"] == "/docs"
    assert data["api_prefix"] == "/api/v1"


def test_api_v1_info_endpoint():
    """Verify service discovery information endpoint under /api/v1/info."""
    response = client.get("/api/v1/info")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["project"] == settings.APP_NAME
    assert data["service"] == "document-engine"
    assert data["status"] == "running"


def test_not_found_standardized_error():
    """Verify accessing an unknown route returns centralized error envelope."""
    response = client.get("/non-existent-endpoint-route-test")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "message" in data["error"]


def test_custom_exception_handling():
    """Verify custom DocumentEngineException triggers centralized error response."""
    # Temporarily mount a test route that triggers DocumentNotFoundException
    @app.get("/test-custom-error")
    def trigger_custom_error():
        raise DocumentNotFoundException(message="Mock document not located.")

    response = client.get("/test-custom-error")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "DOCUMENT_NOT_FOUND"
    assert data["error"]["message"] == "Mock document not located."


def test_cors_headers():
    """Verify CORS preflight headers are returned for allowed origins."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/health", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert "access-control-allow-origin" in response.headers
