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


def register_and_login_officer(prefix: str) -> tuple[dict, dict]:
    """Registers and authenticates a unique procurement officer."""
    suffix = uuid.uuid4().hex[:6]
    email = f"{prefix}_{suffix}@gem.gov.in"
    password = "SecurePassword123!"

    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Officer {prefix.capitalize()}",
            "email": email,
            "password": password,
            "role": "PROCUREMENT_OFFICER",
        },
    )
    assert reg_res.status_code == 201
    user_info = reg_res.json()

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return user_info, headers


@pytest.fixture
def auth_context():
    """Provides authenticated officers Alpha and Beta with cleanup."""
    officer_a, headers_a = register_and_login_officer("alpha")
    officer_b, headers_b = register_and_login_officer("beta")

    yield officer_a, headers_a, officer_b, headers_b

    # Cleanup DB records
    db = SessionLocal()
    try:
        user_ids = [uuid.UUID(officer_a["id"]), uuid.UUID(officer_b["id"])]
        db.query(Tender).filter(Tender.created_by.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ==========================================
# 1. AUTHENTICATION TESTS
# ==========================================

def test_unauthenticated_requests_rejected():
    """Ensure all tender endpoints reject unauthenticated requests."""
    fake_id = uuid.uuid4()
    endpoints = [
        ("POST", "/api/v1/tenders", {"tender_number": "T1", "title": "T", "organization": "O"}),
        ("GET", "/api/v1/tenders", None),
        ("GET", f"/api/v1/tenders/{fake_id}", None),
        ("PATCH", f"/api/v1/tenders/{fake_id}", {"title": "New Title"}),
        ("DELETE", f"/api/v1/tenders/{fake_id}", None),
    ]

    for method, url, payload in endpoints:
        if method == "POST":
            res = client.post(url, json=payload)
        elif method == "GET":
            res = client.get(url)
        elif method == "PATCH":
            res = client.patch(url, json=payload)
        elif method == "DELETE":
            res = client.delete(url)

        assert res.status_code == 401, f"Failed for {method} {url}"
        data = res.json()
        assert data["success"] is False
        assert data["error"]["code"] in ["UNAUTHORIZED", "INVALID_TOKEN"]


def test_authenticated_requests_accepted(auth_context):
    """Ensure valid authenticated requests succeed."""
    _, headers_a, _, _ = auth_context
    res = client.get("/api/v1/tenders", headers=headers_a)
    assert res.status_code == 200
    assert res.json()["success"] is True


# ==========================================
# 2. CREATE TESTS
# ==========================================

def test_create_valid_tender(auth_context):
    """Create a tender with valid fields and verify response schema."""
    officer_a, headers_a, _, _ = auth_context
    now = datetime.now(timezone.utc)
    t_num = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "tender_number": t_num,
        "title": "Supply of Enterprise Core Network Routers",
        "organization": "National Informatics Centre Services Inc",
        "department": "Infrastructure Division",
        "category": "Networking",
        "description": "High throughput routing equipment RFP",
        "bid_start_date": (now + timedelta(days=1)).isoformat(),
        "bid_end_date": (now + timedelta(days=20)).isoformat(),
        "status": "DRAFT",
    }
    res = client.post("/api/v1/tenders", json=payload, headers=headers_a)
    assert res.status_code == 201
    data = res.json()

    assert data["tender_number"] == t_num
    assert data["title"] == payload["title"]
    assert data["organization"] == payload["organization"]
    assert data["department"] == payload["department"]
    assert data["category"] == payload["category"]
    assert data["created_by"] == officer_a["id"]
    assert data["status"] == "DRAFT"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_missing_required_field(auth_context):
    """Ensure validation error when required fields are missing."""
    _, headers_a, _, _ = auth_context

    # Missing organization
    payload = {
        "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
        "title": "Incomplete Tender",
    }
    res = client.post("/api/v1/tenders", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"
    assert any("organization" in str(d) for d in data["error"]["details"])


def test_create_invalid_date_range(auth_context):
    """Ensure rejection when bid_end_date is earlier than bid_start_date."""
    _, headers_a, _, _ = auth_context
    now = datetime.now(timezone.utc)

    payload = {
        "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
        "title": "Invalid Dates Tender",
        "organization": "Ministry of Coal",
        "bid_start_date": (now + timedelta(days=10)).isoformat(),
        "bid_end_date": (now + timedelta(days=2)).isoformat(),  # Earlier than start date
    }
    res = client.post("/api/v1/tenders", json=payload, headers=headers_a)
    assert res.status_code == 422
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_create_duplicate_tender_number(auth_context):
    """Ensure duplicate tender numbers return 400 Bad Request."""
    _, headers_a, _, _ = auth_context
    t_num = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "tender_number": t_num,
        "title": "Primary Tender",
        "organization": "Ministry of Finance",
    }
    res1 = client.post("/api/v1/tenders", json=payload, headers=headers_a)
    assert res1.status_code == 201

    # Attempt duplicate creation
    res2 = client.post("/api/v1/tenders", json=payload, headers=headers_a)
    assert res2.status_code == 400
    data2 = res2.json()
    assert data2["success"] is False
    assert data2["error"]["code"] == "BAD_REQUEST"
    assert "already exists" in data2["error"]["message"].lower()


# ==========================================
# 3. READ & PAGINATION TESTS
# ==========================================

def test_read_list_and_pagination(auth_context):
    """Test tender listing and multi-page pagination."""
    _, headers_a, _, _ = auth_context

    # Create 3 tenders
    for i in range(3):
        client.post(
            "/api/v1/tenders",
            json={
                "tender_number": f"GEM/2026/PAG/{uuid.uuid4().hex[:8].upper()}",
                "title": f"Pagination Tender {i}",
                "organization": "Department of Commerce",
            },
            headers=headers_a,
        )

    # Page 1 with size 2
    res_p1 = client.get("/api/v1/tenders?page=1&page_size=2", headers=headers_a)
    assert res_p1.status_code == 200
    d1 = res_p1.json()
    assert d1["success"] is True
    assert len(d1["data"]) == 2
    assert d1["pagination"]["page"] == 1
    assert d1["pagination"]["page_size"] == 2
    assert d1["pagination"]["total_count"] >= 3
    assert d1["pagination"]["total_pages"] >= 2

    # Page 2 with size 2
    res_p2 = client.get("/api/v1/tenders?page=2&page_size=2", headers=headers_a)
    assert res_p2.status_code == 200
    d2 = res_p2.json()
    assert len(d2["data"]) >= 1
    assert d2["pagination"]["page"] == 2


def test_read_get_existing_tender(auth_context):
    """Test retrieving an existing tender by UUID."""
    _, headers_a, _, _ = auth_context
    t_num = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    create_res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": t_num,
            "title": "Specific Tender",
            "organization": "Indian Railways",
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    tender_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/tenders/{tender_id}", headers=headers_a)
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == tender_id
    assert data["tender_number"] == t_num


def test_read_get_nonexistent_tender(auth_context):
    """Test 404 response for nonexistent tender."""
    _, headers_a, _, _ = auth_context
    fake_id = uuid.uuid4()
    res = client.get(f"/api/v1/tenders/{fake_id}", headers=headers_a)
    assert res.status_code == 404
    data = res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"


# ==========================================
# 4. UPDATE TESTS
# ==========================================

def test_update_valid_tender(auth_context):
    """Test valid partial update of tender attributes."""
    _, headers_a, _, _ = auth_context
    t_num = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    create_res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": t_num,
            "title": "Original Title",
            "organization": "Ministry of Jal Shakti",
        },
        headers=headers_a,
    )
    tender_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/tenders/{tender_id}",
        json={"title": "Updated Title", "department": "Water Resources"},
        headers=headers_a,
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["title"] == "Updated Title"
    assert data["department"] == "Water Resources"
    assert data["tender_number"] == t_num


def test_update_invalid_date_range(auth_context):
    """Test update rejection when dates are invalid."""
    _, headers_a, _, _ = auth_context
    now = datetime.now(timezone.utc)

    create_res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            "title": "Date Test Tender",
            "organization": "Ministry of Power",
            "bid_start_date": (now + timedelta(days=5)).isoformat(),
            "bid_end_date": (now + timedelta(days=20)).isoformat(),
        },
        headers=headers_a,
    )
    tender_id = create_res.json()["id"]

    # Attempt to update bid_end_date to before bid_start_date
    patch_res = client.patch(
        f"/api/v1/tenders/{tender_id}",
        json={"bid_end_date": (now + timedelta(days=2)).isoformat()},
        headers=headers_a,
    )
    assert patch_res.status_code in [400, 422]
    data = patch_res.json()
    assert data["success"] is False


def test_update_unauthorized_ownership_modification(auth_context):
    """Test rejection when officer B attempts to update officer A's tender."""
    _, headers_a, _, headers_b = auth_context

    create_res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            "title": "Officer A Confidential",
            "organization": "PMO India",
        },
        headers=headers_a,
    )
    tender_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/tenders/{tender_id}",
        json={"title": "Unauthorized Modification"},
        headers=headers_b,
    )
    assert patch_res.status_code == 403
    data = patch_res.json()
    assert data["success"] is False
    assert data["error"]["code"] == "FORBIDDEN"


# ==========================================
# 5. ARCHIVE & HISTORICAL DATA TESTS
# ==========================================

def test_archive_tender_and_verify_history(auth_context):
    """Test soft-delete archiving, status update, and historical data preservation."""
    officer_a, headers_a, _, _ = auth_context
    t_num = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"

    # 1. Create tender
    create_res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": t_num,
            "title": "Historical Tender Archival Test",
            "organization": "Cabinet Secretariat",
            "category": "Security Services",
        },
        headers=headers_a,
    )
    assert create_res.status_code == 201
    tender_id = create_res.json()["id"]

    # 2. Archive tender via DELETE endpoint
    del_res = client.delete(f"/api/v1/tenders/{tender_id}", headers=headers_a)
    assert del_res.status_code == 200
    archived_dto = del_res.json()
    assert archived_dto["status"] == "ARCHIVED"

    # 3. Direct DB verification: record is NOT deleted, status is ARCHIVED
    db = SessionLocal()
    try:
        db_tender = db.query(Tender).filter(Tender.id == uuid.UUID(tender_id)).first()
        assert db_tender is not None
        assert db_tender.status == TenderStatus.ARCHIVED
        assert db_tender.tender_number == t_num
        assert str(db_tender.created_by) == officer_a["id"]
    finally:
        db.close()

    # 4. Standard active list excludes archived tender
    list_active = client.get("/api/v1/tenders", headers=headers_a)
    active_ids = [t["id"] for t in list_active.json()["data"]]
    assert tender_id not in active_ids

    # 5. Filter with include_archived=true returns the historical tender
    list_all = client.get("/api/v1/tenders?include_archived=true", headers=headers_a)
    all_ids = [t["id"] for t in list_all.json()["data"]]
    assert tender_id in all_ids


# ==========================================
# 6. SECURITY & JWT TESTS
# ==========================================

def test_security_invalid_and_missing_jwt():
    """Test security response on invalid or malformed JWT."""
    # Invalid JWT
    bad_headers = {"Authorization": "Bearer not.a.valid.jwt.token"}
    res_bad = client.get("/api/v1/tenders", headers=bad_headers)
    assert res_bad.status_code == 401
    assert res_bad.json()["error"]["code"] == "INVALID_TOKEN"

    # Missing JWT
    res_missing = client.get("/api/v1/tenders")
    assert res_missing.status_code == 401
    assert res_missing.json()["error"]["code"] == "UNAUTHORIZED"


def test_security_attempt_archive_another_user_tender(auth_context):
    """Test that officer B cannot archive officer A's tender."""
    _, headers_a, _, headers_b = auth_context

    create_res = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            "title": "Protected Tender",
            "organization": "National Security Council",
        },
        headers=headers_a,
    )
    tender_id = create_res.json()["id"]

    del_res = client.delete(f"/api/v1/tenders/{tender_id}", headers=headers_b)
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "FORBIDDEN"
