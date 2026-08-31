import uuid
import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.tender import Tender
from app.models.user import User

client = TestClient(app)


def create_test_officer(name: str, prefix: str) -> tuple[dict, dict]:
    """Helper to create and authenticate a test procurement officer."""
    suffix = uuid.uuid4().hex[:6]
    email = f"{prefix}_{suffix}@gem.gov.in"
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

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]["access_token"]
    return reg_res.json(), {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure all tables are created."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def auth_officer():
    """Yields authenticated procurement officer and auth headers."""
    user_data, headers = create_test_officer("Intelligence Officer", "intel_officer")
    yield user_data, headers

    # Cleanup
    db = SessionLocal()
    try:
        user_id = uuid.UUID(user_data["id"])
        tenders = db.query(Tender).filter(Tender.created_by == user_id).all()
        for t in tenders:
            db.delete(t)
        users = db.query(User).filter(User.id == user_id).all()
        for u in users:
            db.delete(u)
        db.commit()
    finally:
        db.close()


def create_sample_tender(headers: dict) -> dict:
    """Helper to create a tender via API."""
    unique_num = f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}"
    res = client.post(
        "/api/tenders",
        headers=headers,
        json={
            "tender_number": unique_num,
            "title": "Procurement of High End Server Infrastructure",
            "description": "Notice Inviting Tender for Cloud Computing Infrastructure",
            "organization": "Department of Technology",
            "department": "IT Infrastructure",
            "category": "Hardware",
        },
    )
    assert res.status_code == 201
    return res.json()


def test_get_intelligence_profile_not_analyzed(auth_officer):
    """Verify GET /api/tenders/{tender_id}/intelligence returns NOT_ANALYZED before running analysis."""
    _, headers = auth_officer
    tender = create_sample_tender(headers)
    tender_id = tender["id"]

    res = client.get(
        f"/api/tenders/{tender_id}/intelligence",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["tender_id"] == tender_id
    assert data["status"] == "NOT_ANALYZED"
    assert data["requirement_count"] == 0
    assert data["requirements"] == []


def test_post_intelligence_analyze_success(auth_officer):
    """
    Verify POST /api/tenders/{tender_id}/intelligence/analyze
    processes document content and produces structured Tender Compliance Profile.
    """
    _, headers = auth_officer
    tender = create_sample_tender(headers)
    tender_id = tender["id"]

    tender_text = (
        "SECTION III: MINIMUM ELIGIBILITY CRITERIA\n"
        "1. Average annual financial turnover shall not be less than Rs. 15 lakhs during the preceding three years.\n"
        "2. Bidder must possess at least 3 years of past experience executing similar government projects.\n"
        "3. In case the bidder is not an OEM, a valid Manufacturer Authorization Form (MAF) must be furnished.\n"
        "4. Minimum 50% local content requirement: Only Class-I Local Suppliers shall be eligible under Make in India policy.\n"
        "5. Relaxation of Norms for Startups and MSEs: Prior turnover criteria are relaxed for DPIIT recognized Startups.\n"
    )

    analyze_res = client.post(
        f"/api/tenders/{tender_id}/intelligence/analyze",
        headers=headers,
        json={"raw_text": tender_text},
    )
    assert analyze_res.status_code == 200
    profile = analyze_res.json()

    assert profile["tender_id"] == tender_id
    assert profile["status"] == "COMPLETED"
    assert profile["requirement_count"] == 5
    assert profile["deterministic_count"] >= 4
    assert len(profile["requirements"]) == 5

    # Verify requirements are structured with evidence
    req_rules = {r["rule"] for r in profile["requirements"]}
    assert "AVERAGE_TURNOVER" in req_rules
    assert "EXPERIENCE_PERIOD" in req_rules
    assert "OEM_AUTHORIZATION" in req_rules
    assert "MII_LOCAL_CONTENT" in req_rules

    # Check evidence traceability
    for req in profile["requirements"]:
        assert req["source_page"] is not None
        assert req["source_text"] is not None
        assert len(req["source_text"]) > 0


def test_get_intelligence_profile_after_analysis(auth_officer):
    """Verify GET /api/tenders/{tender_id}/intelligence returns COMPLETED profile after analysis."""
    _, headers = auth_officer
    tender = create_sample_tender(headers)
    tender_id = tender["id"]

    # Run analysis first
    tender_text = (
        "ELIGIBILITY CONDITIONS\n"
        "The bidder must have average annual turnover of not less than Rs. 50 lakhs over the last three financial years.\n"
    )
    client.post(
        f"/api/tenders/{tender_id}/intelligence/analyze",
        headers=headers,
        json={"raw_text": tender_text},
    )

    # Fetch profile
    res = client.get(
        f"/api/tenders/{tender_id}/intelligence",
        headers=headers,
    )
    assert res.status_code == 200
    profile = res.json()
    assert profile["status"] == "COMPLETED"
    assert profile["requirement_count"] == 1
    assert profile["deterministic_count"] == 1
    assert profile["requirements"][0]["rule"] == "AVERAGE_TURNOVER"


def test_get_tender_requirements_filtered(auth_officer):
    """Verify GET /api/tenders/{tender_id}/requirements with type and mandatory filtering."""
    _, headers = auth_officer
    tender = create_sample_tender(headers)
    tender_id = tender["id"]

    tender_text = (
        "SECTION 3: ELIGIBILITY CRITERIA\n"
        "1. Minimum annual turnover of Rs. 20 lakhs.\n"
        "2. Copy of valid GST registration certificate.\n"
        "3. Startups are exempted from prior turnover criteria.\n"
    )
    client.post(
        f"/api/tenders/{tender_id}/intelligence/analyze",
        headers=headers,
        json={"raw_text": tender_text},
    )

    # 1. Fetch all requirements
    all_res = client.get(f"/api/tenders/{tender_id}/requirements", headers=headers)
    assert all_res.status_code == 200
    all_reqs = all_res.json()
    assert len(all_reqs) == 3

    # 2. Filter by requirement_type=FINANCIAL
    fin_res = client.get(f"/api/tenders/{tender_id}/requirements?requirement_type=FINANCIAL", headers=headers)
    assert fin_res.status_code == 200
    fin_reqs = fin_res.json()
    assert len(fin_reqs) == 1
    assert fin_reqs[0]["requirement_type"] == "FINANCIAL"

    # 3. Filter by mandatory_only=true (excludes non-mandatory exemption)
    mand_res = client.get(f"/api/tenders/{tender_id}/requirements?mandatory_only=true", headers=headers)
    assert mand_res.status_code == 200
    mand_reqs = mand_res.json()
    assert len(mand_reqs) == 2
    for r in mand_reqs:
        assert r["mandatory"] is True


def test_unauthenticated_requests_rejected(auth_officer):
    """Verify unauthenticated requests are rejected with 401."""
    _, headers = auth_officer
    tender = create_sample_tender(headers)
    tender_id = tender["id"]

    # Unauthenticated POST analyze
    res1 = client.post(f"/api/tenders/{tender_id}/intelligence/analyze", json={})
    assert res1.status_code == 401

    # Unauthenticated GET intelligence
    res2 = client.get(f"/api/tenders/{tender_id}/intelligence")
    assert res2.status_code == 401

    # Unauthenticated GET requirements
    res3 = client.get(f"/api/tenders/{tender_id}/requirements")
    assert res3.status_code == 401


def test_nonexistent_tender_returns_404(auth_officer):
    """Verify non-existent tender IDs return 404."""
    _, headers = auth_officer
    fake_id = uuid.uuid4()

    res1 = client.post(f"/api/tenders/{fake_id}/intelligence/analyze", headers=headers, json={})
    assert res1.status_code == 404

    res2 = client.get(f"/api/tenders/{fake_id}/intelligence", headers=headers)
    assert res2.status_code == 404

    res3 = client.get(f"/api/tenders/{fake_id}/requirements", headers=headers)
    assert res3.status_code == 404
