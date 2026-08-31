from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.db.session import get_db
from app.main import app

client = TestClient(app)


def test_health():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_root():
    """Test root status endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == "SIH26100"
    assert data["status"] == "running"
    assert data["version"] == "0.1.0"
    assert data["environment"] == "development"


def test_health_db_success():
    """Test database health check endpoint on success."""
    response = client.get("/health/db")
    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "database": "connected",
    }


def test_health_db_failure():
    """Test database health check endpoint when database fails."""
    # Override get_db dependency with a failing session
    def mock_failing_db():
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("Connection refused to database")
        yield mock_session

    app.dependency_overrides[get_db] = mock_failing_db
    try:
        response = client.get("/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        # Ensure no sensitive error messages or credentials are leaked
        assert "Connection refused" not in response.text
    finally:
        app.dependency_overrides.clear()


def test_api_v1_health():
    """Test API version 1 health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api_version"] == "v1"
    assert data["environment"] == "development"


def test_api_v1_health_db_success():
    """Test API version 1 database health check endpoint on success."""
    response = client.get("/api/v1/health/db")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert data["api_version"] == "v1"


def test_api_v1_health_db_failure():
    """Test API version 1 database health check endpoint when database fails."""
    def mock_failing_db():
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("Connection timeout")
        yield mock_session

    app.dependency_overrides[get_db] = mock_failing_db
    try:
        response = client.get("/api/v1/health/db")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
    finally:
        app.dependency_overrides.clear()




def test_openapi_schema():
    """Test that OpenAPI schema is properly configured and accessible."""
    response = client.get("/api/v1/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "SIH26100"
    assert data["info"]["version"] == "0.1.0"


def test_cors_headers():
    """Test that CORS headers are returned for allowed origins."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_settings_validator():
    """Test CORS origin parsing and normalization."""
    from app.config import Settings

    # Comma-separated string parsing
    s = Settings(CORS_ORIGINS="http://localhost:5173, http://127.0.0.1:5173")
    assert s.CORS_ORIGINS == ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Single wildcard
    s_wildcard = Settings(CORS_ORIGINS="*")
    assert s_wildcard.CORS_ORIGINS == ["*"]

    # List format
    s_list = Settings(CORS_ORIGINS=["http://example.com"])
    assert s_list.CORS_ORIGINS == ["http://example.com"]


