import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.bidder import Bidder, TenderBidder
from app.models.enums import BidderStatus, TenderStatus
from app.models.tender import Tender
from app.models.user import User

client = TestClient(app)


def create_authenticated_user(name: str, email_prefix: str, role: str = "PROCUREMENT_OFFICER") -> tuple[dict, dict]:
    """Helper to register and login a test user, returning user data and auth header."""
    suffix = uuid.uuid4().hex[:6]
    email = f"{email_prefix}_{suffix}@gem.gov.in"
    password = "SecurePassword123!"

    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "name": name,
            "email": email,
            "password": password,
            "role": role,
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
def auth_officer():
    """Sets up an authenticated procurement officer."""
    user, headers = create_authenticated_user("Procurement Lead", "lead_officer")
    yield user, headers

    # Teardown
    db = SessionLocal()
    try:
        user_id = uuid.UUID(user["id"])
        # Remove tenders and bidders created
        tenders = db.query(Tender).filter(Tender.created_by == user_id).all()
        for t in tenders:
            db.delete(t)
        u = db.get(User, user_id)
        if u:
            db.delete(u)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def test_bidder_crud_lifecycle(auth_officer):
    """Test full CRUD lifecycle for Bidder entities."""
    _, headers = auth_officer
    company_name = f"Bharat Infotech Ltd {uuid.uuid4().hex[:4]}"

    # 1. CREATE Bidder
    create_payload = {
        "company_name": company_name,
        "registration_number": "CIN-U72200DL2026PTC123456",
        "gst_number": "07AAAAA0000A1Z5",
        "pan_number": "ABCDE1234F",
        "udyam_number": "UDYAM-DL-01-0012345",
        "contact_person": "Vikram Singh",
        "email": "contact@bharatinfotech.in",
        "phone": "+91-9876543210",
        "address": "Electronics City, Phase 1, Bangalore, Karnataka",
        "status": "ACTIVE",
    }
    res_create = client.post("/api/bidders", json=create_payload, headers=headers)
    assert res_create.status_code == 201
    bidder = res_create.json()
    bidder_id = bidder["id"]

    assert bidder["company_name"] == company_name
    assert bidder["gst_number"] == "07AAAAA0000A1Z5"
    assert bidder["status"] == "ACTIVE"

    # 2. GET Bidder by ID
    res_get = client.get(f"/api/bidders/{bidder_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == bidder_id
    assert res_get.json()["company_name"] == company_name

    # 3. LIST Bidders with Pagination and Search
    res_list = client.get(f"/api/bidders?search={company_name}", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["success"] is True
    assert list_data["pagination"]["total_count"] >= 1
    found_ids = [b["id"] for b in list_data["data"]]
    assert bidder_id in found_ids

    # 4. UPDATE Bidder (PUT / PATCH)
    update_payload = {
        "contact_person": "Vikram Singh (Managing Director)",
        "phone": "+91-9988776655",
    }
    res_patch = client.patch(f"/api/bidders/{bidder_id}", json=update_payload, headers=headers)
    assert res_patch.status_code == 200
    updated_bidder = res_patch.json()
    assert updated_bidder["contact_person"] == "Vikram Singh (Managing Director)"
    assert updated_bidder["phone"] == "+91-9988776655"

    # 5. UPDATE Bidder Status
    res_status = client.patch(
        f"/api/bidders/{bidder_id}/status",
        json={"status": "SUSPENDED"},
        headers=headers,
    )
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "SUSPENDED"


def test_tender_bidder_many_to_many_workflow(auth_officer):
    """Test assigning multiple bidders to a tender, preventing duplicates, and listing."""
    user, headers = auth_officer

    # 1. Create a Tender
    tender_number = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"
    res_tender = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": tender_number,
            "title": "Supply of Enterprise Core Network Routers",
            "organization": "RailTel Corporation of India",
        },
        headers=headers,
    )
    assert res_tender.status_code == 201
    tender_id = res_tender.json()["id"]

    # 2. Create 3 distinct Bidders
    bidders = []
    for i in range(3):
        res_b = client.post(
            "/api/v1/bidders",
            json={
                "company_name": f"Telecom Bidder {i}_{uuid.uuid4().hex[:4]}",
                "gst_number": f"09ABCDE{i}234F1Z5",
                "contact_person": f"Agent {i}",
                "status": "ACTIVE",
            },
            headers=headers,
        )
        assert res_b.status_code == 201
        bidders.append(res_b.json())

    bidder_1_id = bidders[0]["id"]
    bidder_2_id = bidders[1]["id"]
    bidder_3_id = bidders[2]["id"]

    # 3. Assign Bidder 1 and Bidder 2 to Tender
    res_assign1 = client.post(
        f"/api/tenders/{tender_id}/bidders/{bidder_1_id}",
        headers=headers,
    )
    assert res_assign1.status_code == 201
    assign1_data = res_assign1.json()
    assert assign1_data["bidder_id"] == bidder_1_id
    assert "assignment_timestamp" in assign1_data

    res_assign2 = client.post(
        f"/api/tenders/{tender_id}/bidders/{bidder_2_id}",
        headers=headers,
    )
    assert res_assign2.status_code == 201

    # 4. Attempt duplicate assignment of Bidder 1 (Should return 409 Conflict)
    res_dup = client.post(
        f"/api/tenders/{tender_id}/bidders/{bidder_1_id}",
        headers=headers,
    )
    assert res_dup.status_code == 409
    dup_data = res_dup.json()
    assert dup_data["success"] is False
    assert dup_data["error"]["code"] == "CONFLICT"

    # 5. List Bidders for Tender (GET /api/tenders/{tender_id}/bidders)
    res_tender_bidders = client.get(
        f"/api/tenders/{tender_id}/bidders",
        headers=headers,
    )
    assert res_tender_bidders.status_code == 200
    tb_data = res_tender_bidders.json()
    assert tb_data["success"] is True
    assert tb_data["pagination"]["total_count"] == 2
    assigned_ids = [b["bidder_id"] for b in tb_data["data"]]
    assert bidder_1_id in assigned_ids
    assert bidder_2_id in assigned_ids
    assert bidder_3_id not in assigned_ids

    # 6. List Tenders for Bidder 1 (GET /api/bidders/{bidder_id}/tenders)
    res_bidder_tenders = client.get(
        f"/api/bidders/{bidder_1_id}/tenders",
        headers=headers,
    )
    assert res_bidder_tenders.status_code == 200
    bt_data = res_bidder_tenders.json()
    assert bt_data["success"] is True
    assert bt_data["pagination"]["total_count"] == 1
    assert bt_data["data"][0]["id"] == tender_id
    assert bt_data["data"][0]["tender_number"] == tender_number

    # 7. Remove Bidder 1 from Tender (DELETE /api/tenders/{tender_id}/bidders/{bidder_id})
    res_del = client.delete(
        f"/api/tenders/{tender_id}/bidders/{bidder_1_id}",
        headers=headers,
    )
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 8. Verify Bidder 1 is removed from Tender's bidders list
    res_tb_after_del = client.get(
        f"/api/tenders/{tender_id}/bidders",
        headers=headers,
    )
    assert res_tb_after_del.status_code == 200
    remaining_ids = [b["bidder_id"] for b in res_tb_after_del.json()["data"]]
    assert bidder_1_id not in remaining_ids
    assert bidder_2_id in remaining_ids
    assert res_tb_after_del.json()["pagination"]["total_count"] == 1


def test_bidder_error_conditions(auth_officer):
    """Test 404s and invalid data handling for bidders and tender associations."""
    _, headers = auth_officer
    fake_id = uuid.uuid4()

    # 404 for non-existent bidder
    assert client.get(f"/api/bidders/{fake_id}", headers=headers).status_code == 404
    assert client.patch(f"/api/bidders/{fake_id}", json={"company_name": "Test"}, headers=headers).status_code == 404
    assert client.patch(f"/api/bidders/{fake_id}/status", json={"status": "ACTIVE"}, headers=headers).status_code == 404

    # 404 for non-existent tender on assignment
    assert client.post(f"/api/tenders/{fake_id}/bidders/{fake_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/tenders/{fake_id}/bidders/{fake_id}", headers=headers).status_code == 404
    assert client.get(f"/api/tenders/{fake_id}/bidders", headers=headers).status_code == 404
    assert client.get(f"/api/bidders/{fake_id}/tenders", headers=headers).status_code == 404

    # 422 for invalid bidder create (empty company_name)
    res_inv = client.post(
        "/api/bidders",
        json={"company_name": ""},
        headers=headers,
    )
    assert res_inv.status_code == 422
