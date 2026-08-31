from datetime import datetime, timedelta, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.enums import TenderStatus
from app.models.tender import Tender
from app.models.user import User

client = TestClient(app)


def create_authenticated_officer(name: str, email_prefix: str) -> tuple[dict, str]:
    """Helper to register and login a test procurement officer, returning user info and auth header."""
    suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{suffix}@gem.gov.in"
    password = "SecurePassword123!"

    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "role": "PROCUREMENT_OFFICER",
        },
    )
    assert reg_res.status_code == 201
    user_data = reg_res.json()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]["access_token"]
    auth_header = {"Authorization": f"Bearer {token}"}

    return user_data, auth_header


@pytest.fixture
def test_setup():
    """Sets up two distinct procurement officers and cleans up after testing."""
    officer_a, headers_a = create_authenticated_officer("Officer Alpha", "officer_a")
    officer_b, headers_b = create_authenticated_officer("Officer Beta", "officer_b")

    yield officer_a, headers_a, officer_b, headers_b

    # Cleanup created test users and tenders
    db = SessionLocal()
    try:
        user_ids = [uuid.UUID(officer_a["id"]), uuid.UUID(officer_b["id"])]
        tenders = db.query(Tender).filter(Tender.created_by.in_(user_ids)).all()
        for t in tenders:
            db.delete(t)
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        for u in users:
            db.delete(u)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_tender_complete_crud_lifecycle(test_setup):
    """Test full CRUD lifecycle for Tender management by authenticated officer."""
    officer_a, headers_a, _, _ = test_setup
    now = datetime.now(timezone.utc)
    start_date = (now + timedelta(days=2)).isoformat()
    end_date = (now + timedelta(days=30)).isoformat()
    tender_number = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    # 1. CREATE Tender
    create_payload = {
        "tender_number": tender_number,
        "title": "Procurement of High Performance Computing Cluster",
        "organization": "Indian Space Research Organisation",
        "department": "Supercomputing Systems",
        "category": "IT / High-End Computing",
        "description": "RFP for delivery, installation, and commissioning of GPU clusters.",
        "bid_start_date": start_date,
        "bid_end_date": end_date,
        "status": "DRAFT",
    }
    create_res = client.post("/api/v1/tenders", json=create_payload, headers=headers_a)
    assert create_res.status_code == 201
    tender = create_res.json()
    tender_id = tender["id"]

    assert tender["tender_number"] == tender_number
    assert tender["title"] == create_payload["title"]
    assert tender["organization"] == create_payload["organization"]
    assert tender["created_by"] == officer_a["id"]
    assert tender["status"] == "DRAFT"

    # 2. LIST Tenders
    list_res = client.get("/api/v1/tenders", headers=headers_a)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["success"] is True
    assert list_data["pagination"]["total_count"] >= 1
    tender_ids = [t["id"] for t in list_data["data"]]
    assert tender_id in tender_ids

    # 3. GET Tender by ID
    get_res = client.get(f"/api/v1/tenders/{tender_id}", headers=headers_a)
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["id"] == tender_id
    assert get_data["tender_number"] == tender_number

    # 4. UPDATE Tender (PATCH)
    patch_payload = {
        "title": "Procurement of HPC Cluster (Amended Scope)",
        "status": "PUBLISHED",
    }
    patch_res = client.patch(
        f"/api/v1/tenders/{tender_id}", json=patch_payload, headers=headers_a
    )
    assert patch_res.status_code == 200
    updated_tender = patch_res.json()
    assert updated_tender["title"] == "Procurement of HPC Cluster (Amended Scope)"
    assert updated_tender["status"] == "PUBLISHED"

    # 5. SOFT-DELETE / ARCHIVE Tender (DELETE)
    delete_res = client.delete(f"/api/v1/tenders/{tender_id}", headers=headers_a)
    assert delete_res.status_code == 200
    archived_tender = delete_res.json()
    assert archived_tender["status"] == "ARCHIVED"

    # 6. Verify soft-delete preserves record in DB but excludes from default active list
    list_after_delete = client.get("/api/v1/tenders", headers=headers_a)
    active_ids = [t["id"] for t in list_after_delete.json()["data"]]
    assert tender_id not in active_ids

    # Verify query with include_archived=true finds the archived tender
    list_with_archived = client.get(
        "/api/v1/tenders?include_archived=true", headers=headers_a
    )
    all_ids = [t["id"] for t in list_with_archived.json()["data"]]
    assert tender_id in all_ids


def test_tender_ownership_authorization(test_setup):
    """Verify that officer B cannot modify or archive officer A's tender."""
    _, headers_a, _, headers_b = test_setup
    tender_number = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    # Officer A creates tender
    create_res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": tender_number,
            "title": "Officer A Confidential Procurement",
            "organization": "National Security Council Secretariat",
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    tender_id = create_res.json()["id"]

    # Officer B attempts to PATCH Officer A's tender
    patch_res = client.patch(
        f"/api/v1/tenders/{tender_id}",
        json={"title": "Malicious Modification Attempt"},
        headers=headers_b,
    )
    assert patch_res.status_code == 403
    patch_data = patch_res.json()
    assert patch_data["success"] is False
    assert patch_data["error"]["code"] == "FORBIDDEN"

    # Officer B attempts to DELETE Officer A's tender
    del_res = client.delete(f"/api/v1/tenders/{tender_id}", headers=headers_b)
    assert del_res.status_code == 403
    del_data = del_res.json()
    assert del_data["success"] is False
    assert del_data["error"]["code"] == "FORBIDDEN"


def test_tender_unauthenticated_access():
    """Verify all tender endpoints require authentication."""
    fake_id = uuid.uuid4()

    assert client.post("/api/v1/tenders", json={}).status_code == 401
    assert client.get("/api/v1/tenders").status_code == 401
    assert client.get(f"/api/v1/tenders/{fake_id}").status_code == 401
    assert client.patch(f"/api/v1/tenders/{fake_id}", json={}).status_code == 401
    assert client.delete(f"/api/v1/tenders/{fake_id}").status_code == 401


def test_duplicate_tender_number_rejected(test_setup):
    """Verify creating a tender with duplicate tender_number is rejected."""
    _, headers_a, _, _ = test_setup
    tender_number = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    # First creation
    res1 = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": tender_number,
            "title": "Original Tender",
            "organization": "Ministry of Coal",
        },
        headers=headers_a,
    )
    assert res1.status_code == 201

    # Second creation with identical number
    res2 = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": tender_number,
            "title": "Duplicate Tender Attempt",
            "organization": "Ministry of Power",
        },
        headers=headers_a,
    )
    assert res2.status_code == 400
    data2 = res2.json()
    assert data2["success"] is False
    assert data2["error"]["code"] == "BAD_REQUEST"
    assert "already exists" in data2["error"]["message"].lower()


def test_invalid_bid_dates_rejected(test_setup):
    """Verify date validations for create and update endpoints."""
    _, headers_a, _, _ = test_setup
    now = datetime.now(timezone.utc)
    start_date = (now + timedelta(days=10)).isoformat()
    invalid_end = (now + timedelta(days=5)).isoformat()

    # Reject on creation
    res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            "title": "Invalid Date Tender",
            "organization": "Dept of Agriculture",
            "bid_start_date": start_date,
            "bid_end_date": invalid_end,
        },
        headers=headers_a,
    )
    assert res.status_code == 422
    assert res.json()["success"] is False
    assert res.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_non_existent_tender(test_setup):
    """Verify 404 response for non-existent tender."""
    _, headers_a, _, _ = test_setup
    fake_id = uuid.uuid4()
    response = client.get(f"/api/v1/tenders/{fake_id}", headers=headers_a)
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"
