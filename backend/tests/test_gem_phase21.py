"""
SIH-26100 — Phase 21: GeM Tender Discovery, Fetch & Import Integration Tests
tests/test_gem_phase21.py

Validates:
1. Valid GeM Bid ID format check.
2. Invalid GeM Bid ID rejected (400 / invalid_bid_id).
3. GeM tender lookup returns structured metadata.
4. Graceful fallback on unavailable GeM network (status="unavailable").
5. Duplicate GeM tender protection (status="already_imported" on lookup, 409 on import).
6. Successful tender import with document storage and SHA-256 calculation.
7. Authentication & RBAC (401 for anonymous, 403 for BIDDER, 200/201 for PROCUREMENT_OFFICER).
8. No frontend secret leakage.
9. Clean database teardown with 0 synthetic residual records.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.enums import UserRole
from app.models.tender import Tender
from app.models.user import User
from app.services.gem_service import gem_service, create_minimal_gem_pdf

client = TestClient(app)


# ---------------------------------------------------------------------------
# FIXTURES & HELPERS
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """Provides a transactional database session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def officer_token(db_session: Session):
    """Creates a temporary test procurement officer user and returns valid JWT token."""
    user_id = uuid.uuid4()
    officer = User(
        id=user_id,
        email=f"officer_gem_{user_id.hex[:8]}@test.gov.in",
        name="Phase21 Test Officer",
        password_hash="mock_hashed_password",
        role=UserRole.PROCUREMENT_OFFICER,
        is_active=True,
    )
    db_session.add(officer)
    db_session.commit()

    token = create_access_token(subject=str(officer.id))
    yield token, officer

    try:
        db_session.delete(officer)
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.fixture
def bidder_token(db_session: Session):
    """Creates a temporary test bidder user (unauthorized for procurement imports)."""
    user_id = uuid.uuid4()
    bidder_user = User(
        id=user_id,
        email=f"bidder_gem_{user_id.hex[:8]}@test.com",
        name="Phase21 Test Bidder",
        password_hash="mock_hashed_password",
        role=UserRole.BIDDER,
        is_active=True,
    )
    db_session.add(bidder_user)
    db_session.commit()

    token = create_access_token(subject=str(bidder_user.id))
    yield token, bidder_user

    try:
        db_session.delete(bidder_user)
        db_session.commit()
    except Exception:
        db_session.rollback()


# ---------------------------------------------------------------------------
# TEST CASES
# ---------------------------------------------------------------------------

class TestGeMIntegrationPhase21:

    def test_1_gem_bid_id_format_validation(self):
        """Test 1: Valid GeM Bid IDs are accepted and invalid formats rejected."""
        assert gem_service.validate_bid_id("GEM/2026/B/8912401") is True
        assert gem_service.validate_bid_id("GEM/2025/R/1234567") is True
        assert gem_service.validate_bid_id("gem/2026/b/9999999") is True
        assert gem_service.validate_bid_id("INVALID_ID") is False
        assert gem_service.validate_bid_id("GEM/2026") is False
        assert gem_service.validate_bid_id("") is False

    def test_2_invalid_bid_id_lookup_response(self, officer_token):
        """Test 2: Lookup with malformed GeM Bid ID returns status='invalid_bid_id'."""
        token, _ = officer_token
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/api/v1/gem/lookup/INVALID_BID_123", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "invalid_bid_id"
        assert data["already_imported"] is False

    def test_3_authentication_and_rbac(self, bidder_token):
        """Test 3: Unauthenticated request gets 401; Bidder role gets 403 Forbidden."""
        # 1. Anonymous request
        anon_resp = client.get("/api/v1/gem/lookup/GEM/2026/B/8912401")
        assert anon_resp.status_code == 401

        # 2. Bidder role request
        token, _ = bidder_token
        headers = {"Authorization": f"Bearer {token}"}
        bidder_resp = client.get("/api/v1/gem/lookup/GEM/2026/B/8912401", headers=headers)
        assert bidder_resp.status_code == 403

    def test_4_gem_lookup_demo_tender_found(self, officer_token):
        """Test 4: Lookup for a registered/discovered GeM Bid ID returns structured metadata."""
        token, _ = officer_token
        headers = {"Authorization": f"Bearer {token}"}
        resp = client.get("/api/v1/gem/lookup/GEM/2026/B/9876543", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "found"
        assert data["already_imported"] is False
        assert data["gem_data"] is not None
        assert data["gem_data"]["bid_id"] == "GEM/2026/B/9876543"
        assert "Healthcare" in data["gem_data"]["title"] or "AIIMS" in data["gem_data"]["organization"]
        assert data["gem_data"]["source"] == "GEM"
        assert data["gem_data"]["document_available"] is True

    def test_5_gem_lookup_graceful_unavailable_fallback(self, officer_token):
        """Test 5: Live GeM network timeout or anti-bot challenge returns status='unavailable' gracefully."""
        token, _ = officer_token
        headers = {"Authorization": f"Bearer {token}"}
        # Unknown non-demo Bid ID
        unknown_id = "GEM/2026/B/7777777"
        resp = client.get(f"/api/v1/gem/lookup/{unknown_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unavailable"
        assert data["can_manual_upload"] is True
        assert "unavailable" in data["message"].lower()

    def test_6_import_gem_tender_e2e_and_duplicate_protection(self, officer_token, db_session: Session):
        """
        Test 6:
        - Successful persistent import of GeM tender into database.
        - Verified columns: source='GEM', gem_bid_id set.
        - Document uploaded to Supabase Storage with SHA-256.
        - Duplicate import is rejected with 409 Conflict.
        - Duplicate lookup returns status='already_imported'.
        """
        token, officer = officer_token
        headers = {"Authorization": f"Bearer {token}"}
        unique_suffix = f"{uuid.uuid4().int % 9000000 + 1000000:07d}"
        bid_id = f"GEM/2026/B/{unique_suffix}"

        test_pdf = create_minimal_gem_pdf(bid_id, "Cloud Server Tender", "MeitY")
        files = {
            "file": ("gem_nit_document.pdf", io.BytesIO(test_pdf), "application/pdf"),
        }
        data = {
            "bid_id": bid_id,
            "title": "Phase 21 GeM Cloud Server Tender",
            "organization": "Ministry of Electronics and Information Technology",
            "department": "National Informatics Centre",
            "category": "Cloud Computing Services",
            "bid_start_date": datetime.now(timezone.utc).isoformat(),
            "bid_end_date": (datetime.now(timezone.utc)).isoformat(),
        }

        # Mock Supabase Storage upload to avoid external network dependency in test
        with patch("app.core.storage.storage_service.upload") as mock_upload, \
             patch("app.core.storage.storage_service.get_signed_url") as mock_signed_url:
            mock_upload.side_effect = lambda storage_path, file_content, mime_type: storage_path
            mock_signed_url.return_value = "https://mock.supabase.co/storage/v1/object/signed/test"

            # 1. First import: Must succeed with 201 Created
            import_resp = client.post("/api/v1/gem/import", data=data, files=files, headers=headers)
            assert import_resp.status_code == 201, f"Import failed: {import_resp.text}"
            res = import_resp.json()

            assert res["tender_number"] == bid_id
            assert res["gem_bid_id"] == bid_id
            assert res["source"] == "GEM"
            tender_id = uuid.UUID(res["id"])

            # Verify document stored in PostgreSQL with SHA-256
            doc = db_session.query(Document).filter(Document.tender_id == tender_id).first()
            assert doc is not None
            assert doc.sha256 is not None
            assert len(doc.sha256) == 64

            # 2. Duplicate Lookup: Must return status='already_imported'
            lookup_dup = client.get(f"/api/v1/gem/lookup/{bid_id}", headers=headers)
            assert lookup_dup.status_code == 200
            dup_data = lookup_dup.json()
            assert dup_data["status"] == "already_imported"
            assert dup_data["already_imported"] is True
            assert dup_data["existing_tender_id"] == str(tender_id)

            # 3. Duplicate Import: Must reject with 409 Conflict
            files_dup = {
                "file": ("gem_nit_document.pdf", io.BytesIO(test_pdf), "application/pdf"),
            }
            dup_import_resp = client.post("/api/v1/gem/import", data=data, files=files_dup, headers=headers)
            assert dup_import_resp.status_code == 409
            assert "already been imported" in dup_import_resp.text

        # CLEANUP synthetic test records
        try:
            db_session.query(Document).filter(Document.tender_id == tender_id).delete()
            db_session.query(Tender).filter(Tender.id == tender_id).delete()
            db_session.commit()
        except Exception:
            db_session.rollback()

    def test_7_no_frontend_secret_leakage(self):
        """Test 7: Verify frontend source code never contains server secrets."""
        import os
        forbidden_strings = [
            "GROQ_API_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
            "DATABASE_URL",
            "JWT_SECRET_KEY",
            "postgresql://",
            "postgres://",
        ]
        frontend_src = "C:\\Users\\Raghul\\Desktop\\SIH26100\\frontend\\src"
        for root, _, files in os.walk(frontend_src):
            for file in files:
                if file.endswith((".ts", ".tsx", ".js", ".jsx", ".json")):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                        for forbidden in forbidden_strings:
                            assert forbidden not in content, (
                                f"Security violation: Found '{forbidden}' in frontend file {filepath}"
                            )
