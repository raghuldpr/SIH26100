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
