from datetime import datetime, timedelta, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.enums import TenderStatus, UserRole
from app.models.tender import Tender
from app.models.user import User

client = TestClient(app)


@pytest.fixture
def auth_setup():
    """Setup test procurement officer and buyer users with JWT auth headers."""
    db = SessionLocal()
    clean_user_ids = []
    clean_tender_ids = []

    # 1. Procurement Officer
    officer = User(
        id=uuid.uuid4(),
        name="Procurement Officer Sharma",
        email=f"sharma_{uuid.uuid4().hex[:6]}@gem.gov.in",
        password_hash=hash_password("officerpassword123"),
        role=UserRole.PROCUREMENT_OFFICER,
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    clean_user_ids.append(officer.id)

    token = create_access_token(subject=str(officer.id), claims={"role": str(officer.role)})
    headers = {"Authorization": f"Bearer {token}"}

    yield db, officer, headers, clean_tender_ids

    # Teardown
    for tid in clean_tender_ids:
        try:
            t = db.get(Tender, tid)
            if t:
                db.delete(t)
                db.commit()
        except Exception:
            db.rollback()

    for uid in clean_user_ids:
        try:
            u = db.get(User, uid)
            if u:
                db.delete(u)
                db.commit()
        except Exception:
            db.rollback()

    db.close()


def test_openapi_schema_loads_and_routes_registered():
    """Verify FastAPI application starts and OpenAPI schema contains /api/tenders endpoints."""
    # Check OpenAPI endpoint
    res = client.get("/api/v1/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    assert "paths" in schema
    assert "/api/tenders" in schema["paths"]
    assert "/api/tenders/{tender_id}" in schema["paths"]
    assert "post" in schema["paths"]["/api/tenders"]
    assert "get" in schema["paths"]["/api/tenders"]
    assert "get" in schema["paths"]["/api/tenders/{tender_id}"]
    assert "put" in schema["paths"]["/api/tenders/{tender_id}"]
    assert "delete" in schema["paths"]["/api/tenders/{tender_id}"]


def test_1_create_tender(auth_setup):
    """1. Create tender via POST /api/tenders."""
    _, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)
    t_num = f"GEM/2026/P4/{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "tender_number": t_num,
        "title": "Procurement of High Capacity Server Racks",
        "organization": "National Informatics Centre",
        "department": "Infrastructure Services",
        "category": "IT Hardware",
        "bid_start_date": now.isoformat(),
        "bid_end_date": (now + timedelta(days=21)).isoformat(),
        "status": "DRAFT",
    }
    res = client.post("/api/tenders", json=payload, headers=headers)
    assert res.status_code == 201
    data = res.json()
    clean_tenders.append(uuid.UUID(data["id"]))

    assert data["tender_number"] == t_num
    assert data["title"] == payload["title"]
    assert data["organization"] == payload["organization"]
    assert data["department"] == "Infrastructure Services"
    assert data["category"] == "IT Hardware"
    assert data["status"] == "DRAFT"


def test_2_create_duplicate_tender_number_conflict(auth_setup):
    """2. Create duplicate tender number returns 400 conflict."""
    _, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)
    t_num = f"GEM/2026/DUP/{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "tender_number": t_num,
        "title": "Primary Tender for Duplication Test",
        "organization": "Ministry of Communications",
        "department": "Telecom",
        "category": "Networking",
        "bid_start_date": now.isoformat(),
        "bid_end_date": (now + timedelta(days=14)).isoformat(),
        "status": "DRAFT",
    }
    # 1st creation succeeds
    res1 = client.post("/api/tenders", json=payload, headers=headers)
    assert res1.status_code == 201
    clean_tenders.append(uuid.UUID(res1.json()["id"]))

    # 2nd creation with same number fails
    res2 = client.post("/api/tenders", json=payload, headers=headers)
    assert res2.status_code == 400
    err_body = res2.json()
    assert err_body["success"] is False
    assert "already exists" in err_body["error"]["message"].lower()


def test_3_list_tenders_pagination(auth_setup):
    """3. List tenders with structured paginated response."""
    _, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)

    # Create 3 test tenders
    for i in range(3):
        t_num = f"GEM/2026/LST/{uuid.uuid4().hex[:8].upper()}"
        res = client.post(
            "/api/tenders",
            json={
                "tender_number": t_num,
                "title": f"Listing Test Tender {i}",
                "organization": "Department of Space",
                "department": "Propulsion",
                "category": "Aerospace",
                "bid_start_date": now.isoformat(),
                "bid_end_date": (now + timedelta(days=10)).isoformat(),
                "status": "DRAFT",
            },
            headers=headers,
        )
        assert res.status_code == 201
        clean_tenders.append(uuid.UUID(res.json()["id"]))

    # List page 1 size 2
    res_list = client.get("/api/tenders?page=1&page_size=2", headers=headers)
    assert res_list.status_code == 200
    body = res_list.json()

    assert "items" in body
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert body["total"] >= 3


def test_4_filter_by_status(auth_setup):
    """4. Filter tenders by status."""
    _, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)
    t_open_num = f"GEM/2026/ST_OPEN/{uuid.uuid4().hex[:8].upper()}"

    res = client.post(
        "/api/tenders",
        json={
            "tender_number": t_open_num,
            "title": "Open Bidding Tender for Filter Test",
            "organization": "Ministry of Energy",
            "department": "Solar Power",
            "category": "Renewables",
            "bid_start_date": now.isoformat(),
            "bid_end_date": (now + timedelta(days=30)).isoformat(),
            "status": "OPEN",
        },
        headers=headers,
    )
    assert res.status_code == 201
    clean_tenders.append(uuid.UUID(res.json()["id"]))

    # Query with status=OPEN
    filter_res = client.get("/api/tenders?status=OPEN", headers=headers)
    assert filter_res.status_code == 200
    body = filter_res.json()
    assert all(item["status"] == "OPEN" for item in body["items"])
    assert any(item["tender_number"] == t_open_num for item in body["items"])


def test_5_filter_by_department(auth_setup):
    """5. Filter tenders by department."""
    _, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)
    dept_name = f"UniqueDept_{uuid.uuid4().hex[:6]}"
    t_num = f"GEM/2026/DEPT/{uuid.uuid4().hex[:8].upper()}"

    res = client.post(
        "/api/tenders",
        json={
            "tender_number": t_num,
            "title": "Department Filter Tender",
            "organization": "Ministry of Health",
            "department": dept_name,
            "category": "Medical Equipment",
            "bid_start_date": now.isoformat(),
            "bid_end_date": (now + timedelta(days=15)).isoformat(),
        },
        headers=headers,
    )
    assert res.status_code == 201
    clean_tenders.append(uuid.UUID(res.json()["id"]))

    # Query by department
    dept_res = client.get(f"/api/tenders?department={dept_name}", headers=headers)
    assert dept_res.status_code == 200
    body = dept_res.json()
    assert len(body["items"]) >= 1
    assert all(item["department"] == dept_name for item in body["items"])


def test_6_get_tender(auth_setup):
    """6. Get tender by ID."""
    _, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)
    t_num = f"GEM/2026/GET/{uuid.uuid4().hex[:8].upper()}"

    res = client.post(
        "/api/tenders",
        json={
            "tender_number": t_num,
            "title": "Specific Get Tender",
            "organization": "Ministry of Transport",
            "department": "Highways",
            "category": "Construction",
            "bid_start_date": now.isoformat(),
            "bid_end_date": (now + timedelta(days=45)).isoformat(),
        },
        headers=headers,
    )
    tender_id = res.json()["id"]
    clean_tenders.append(uuid.UUID(tender_id))

    get_res = client.get(f"/api/tenders/{tender_id}", headers=headers)
    assert get_res.status_code == 200
    tender_data = get_res.json()
    assert tender_data["id"] == tender_id
    assert tender_data["tender_number"] == t_num


def test_7_get_nonexistent_tender_404(auth_setup):
    """7. Get nonexistent tender returns HTTP 404."""
    _, _, headers, _ = auth_setup
    fake_id = uuid.uuid4()
    res = client.get(f"/api/tenders/{fake_id}", headers=headers)
    assert res.status_code == 404
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_8_update_tender(auth_setup):
    """8. Update tender via PUT /api/tenders/{tender_id}."""
    _, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)
    t_num = f"GEM/2026/PUT/{uuid.uuid4().hex[:8].upper()}"

    create_res = client.post(
        "/api/tenders",
        json={
            "tender_number": t_num,
            "title": "Original Title Before PUT",
            "organization": "Ministry of Heavy Industries",
            "department": "Heavy Machinery",
            "category": "Industrial",
            "bid_start_date": now.isoformat(),
            "bid_end_date": (now + timedelta(days=20)).isoformat(),
            "status": "DRAFT",
        },
        headers=headers,
    )
    tender_id = create_res.json()["id"]
    clean_tenders.append(uuid.UUID(tender_id))

    # Update via PUT
    update_res = client.put(
        f"/api/tenders/{tender_id}",
        json={
            "title": "Updated Title After PUT",
            "department": "Modern Heavy Machinery",
            "status": "OPEN",
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["title"] == "Updated Title After PUT"
    assert updated_data["department"] == "Modern Heavy Machinery"
    assert updated_data["status"] == "OPEN"
    # Preserved fields
    assert updated_data["organization"] == "Ministry of Heavy Industries"


def test_9_and_10_archive_tender_soft_delete(auth_setup):
    """9 & 10. Archive tender via DELETE /api/tenders/{tender_id} and confirm it remains in database."""
    db, _, headers, clean_tenders = auth_setup
    now = datetime.now(timezone.utc)
    t_num = f"GEM/2026/DEL/{uuid.uuid4().hex[:8].upper()}"

    res = client.post(
        "/api/tenders",
        json={
            "tender_number": t_num,
            "title": "Tender To Be Soft Archived",
            "organization": "Cabinet Secretariat",
            "department": "Strategic Ops",
            "category": "Consulting",
            "bid_start_date": now.isoformat(),
            "bid_end_date": (now + timedelta(days=10)).isoformat(),
        },
        headers=headers,
    )
    tender_id_str = res.json()["id"]
    tender_uuid = uuid.UUID(tender_id_str)
    clean_tenders.append(tender_uuid)

    # 9. Archive via DELETE endpoint
    del_res = client.delete(f"/api/tenders/{tender_id_str}", headers=headers)
    assert del_res.status_code == 200
    archived_data = del_res.json()
    assert archived_data["status"] == "ARCHIVED"

    # 10. Confirm record still exists in the database
    db_record = db.get(Tender, tender_uuid)
    assert db_record is not None
    assert db_record.status == TenderStatus.ARCHIVED
    assert db_record.tender_number == t_num


def test_11_invalid_bid_date_range_validation_error(auth_setup):
    """11. Invalid bid date range (end before start) rejected with validation error."""
    _, _, headers, _ = auth_setup
    now = datetime.now(timezone.utc)
    start_date = now + timedelta(days=10)
    invalid_end_date = now + timedelta(days=5)  # Earlier than start date

    res = client.post(
        "/api/tenders",
        json={
            "tender_number": f"GEM/2026/INVALID_DATES/{uuid.uuid4().hex[:6]}",
            "title": "Tender With Bad Dates",
            "organization": "Ministry of Mines",
            "bid_start_date": start_date.isoformat(),
            "bid_end_date": invalid_end_date.isoformat(),
        },
        headers=headers,
    )
    # Validation error code 422
    assert res.status_code == 422
    err_body = res.json()
    assert err_body["success"] is False
    assert err_body["error"]["code"] == "VALIDATION_ERROR"
