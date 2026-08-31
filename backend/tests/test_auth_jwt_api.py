from datetime import timedelta
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.user import User

client = TestClient(app)


@pytest.fixture
def test_user_data():
    """Generates unique user registration data and cleans up after test."""
    unique_suffix = uuid.uuid4().hex[:8]
    email = f"officer_{unique_suffix}@gem.gov.in"
    password = "ProcurementSecure2026!"
    name = f"Procurement Officer {unique_suffix}"

    user_info = {
        "name": name,
        "email": email,
        "password": password,
        "role": "PROCUREMENT_OFFICER",
    }
    yield user_info

    # Cleanup DB record
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.lower()).first()
        if user:
            db.delete(user)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_successful_registration(test_user_data):
    """Test successful user registration with initial role PROCUREMENT_OFFICER."""
    response = client.post("/api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201
    data = response.json()

    assert "id" in data
    assert data["name"] == test_user_data["name"]
    assert data["email"] == test_user_data["email"].lower()
    assert data["role"] == "PROCUREMENT_OFFICER"
    assert data["is_active"] is True
    # Verify password and password_hash are NEVER exposed
    assert "password" not in data
    assert "password_hash" not in data


def test_duplicate_registration_rejected(test_user_data):
    """Test that registering an existing email is rejected with 400 Bad Request."""
    # First registration
    res1 = client.post("/api/v1/auth/register", json=test_user_data)
    assert res1.status_code == 201

    # Duplicate registration
    duplicate_payload = {
        "name": "Duplicate User",
        "email": test_user_data["email"].upper(),  # Test case-insensitivity
        "password": "AnotherPassword123!",
        "role": "PROCUREMENT_OFFICER",
    }
    res2 = client.post("/api/v1/auth/register", json=duplicate_payload)
    assert res2.status_code == 400
    data2 = res2.json()
    assert data2["success"] is False
    assert data2["error"]["code"] == "BAD_REQUEST"
    assert "already registered" in data2["error"]["message"].lower()


def test_successful_login_and_token_generation(test_user_data):
    """Test successful user login returning valid JWT access token."""
    # Register user first
    reg_res = client.post("/api/v1/auth/register", json=test_user_data)
    assert reg_res.status_code == 201

    # Login
    login_payload = {
        "email": test_user_data["email"],
        "password": test_user_data["password"],
    }
    login_res = client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    data = login_res.json()

    assert "token" in data
    assert "user" in data
    assert data["token"]["token_type"] == "bearer"
    assert isinstance(data["token"]["access_token"], str)
    assert len(data["token"]["access_token"]) > 20
    assert data["token"]["expires_in"] > 0

    assert data["user"]["email"] == test_user_data["email"].lower()
    assert data["user"]["role"] == "PROCUREMENT_OFFICER"
    # Verify password and password_hash are NEVER exposed
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]


def test_login_wrong_password(test_user_data):
    """Test login rejection when wrong password is supplied."""
    reg_res = client.post("/api/v1/auth/register", json=test_user_data)
    assert reg_res.status_code == 201

    login_payload = {
        "email": test_user_data["email"],
        "password": "IncorrectPassword123!",
    }
    login_res = client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 401
    data = login_res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "invalid email or password" in data["error"]["message"].lower()


def test_login_non_existent_email():
    """Test login rejection when email is not found."""
    login_payload = {
        "email": "nonexistent_officer_9999@gem.gov.in",
        "password": "SomePassword123!",
    }
    login_res = client.post("/api/v1/auth/login", json=login_payload)
    assert login_res.status_code == 401
    data = login_res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_get_me_missing_token():
    """Test GET /api/v1/auth/me rejects requests with missing token."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNAUTHORIZED"


def test_get_me_invalid_token():
    """Test GET /api/v1/auth/me rejects invalid / malformed tokens."""
    headers = {"Authorization": "Bearer invalid.malformed.jwt.token"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "INVALID_TOKEN"


def test_get_me_expired_token(test_user_data):
    """Test GET /api/v1/auth/me rejects expired tokens."""
    # Register user
    reg_res = client.post("/api/v1/auth/register", json=test_user_data)
    assert reg_res.status_code == 201
    user_id = reg_res.json()["id"]

    # Generate expired token (expired 10 minutes ago)
    expired_token = create_access_token(
        subject=user_id,
        expires_delta=timedelta(minutes=-10),
    )

    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "TOKEN_EXPIRED"


def test_get_me_successful_access(test_user_data):
    """Test GET /api/v1/auth/me successfully returns current authenticated user profile."""
    # 1. Register
    reg_res = client.post("/api/v1/auth/register", json=test_user_data)
    assert reg_res.status_code == 201

    # 2. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": test_user_data["email"], "password": test_user_data["password"]},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]["access_token"]

    # 3. Access protected /auth/me
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    data = me_res.json()

    assert data["email"] == test_user_data["email"].lower()
    assert data["name"] == test_user_data["name"]
    assert data["role"] == "PROCUREMENT_OFFICER"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data
