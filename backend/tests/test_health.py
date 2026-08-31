from fastapi.testclient import TestClient
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
