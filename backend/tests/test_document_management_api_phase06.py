import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.core.storage import storage_service
from app.db.session import SessionLocal
from app.main import app
from app.models.bidder import Bidder
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus, UserRole
from app.models.tender import Tender
from app.models.user import User

client = TestClient(app)


def generate_mock_pdf(title: str = "Test PDF") -> bytes:
    """Generates a valid mock PDF byte stream."""
    return (
        f"%PDF-1.4\n1 0 obj\n<< /Title ({title}) >>\nendobj\n"
        f"xref\n0 2\n0000000000 65535 f \n0000000010 00000 n \n"
        f"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n70\n%%EOF\n"
    ).encode("utf-8")


def register_and_login(name: str, role: str) -> tuple[dict, dict]:
    """Helper to create and authenticate a user."""
    suffix = uuid.uuid4().hex[:6]
    email = f"{name.lower().replace(' ', '_')}_{suffix}@gem.gov.in"
    password = "SecurePassword123!"

    reg_res = client.post(
        "/api/v1/auth/register",
        json={"name": name, "email": email, "password": password, "role": role},
    )
    assert reg_res.status_code == 201

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]["access_token"]
    return reg_res.json(), {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mgmt_test_context():
    """Sets up an officer, two separate bidders, a tender, and documents."""
    officer, officer_headers = register_and_login("Officer One", "PROCUREMENT_OFFICER")
    bidder1_user, bidder1_headers = register_and_login("Bidder One User", "BIDDER")
    bidder2_user, bidder2_headers = register_and_login("Bidder Two User", "BIDDER")

    db = SessionLocal()
    try:
        # Create Tender
        tender = Tender(
            tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            title="Management Test Tender",
            organization="NIC India",
            created_by=uuid.UUID(officer["id"]),
        )
        # Create Bidder 1 (linked to bidder1_user)
        bidder1 = Bidder(
            company_name=f"Alpha Solutions {uuid.uuid4().hex[:4]}",
            gst_number="27AAAAA1234A1Z5",
            user_id=uuid.UUID(bidder1_user["id"]),
        )
        # Create Bidder 2 (linked to bidder2_user)
        bidder2 = Bidder(
            company_name=f"Beta Enterprises {uuid.uuid4().hex[:4]}",
            gst_number="29BBBBB5678B1Z5",
            user_id=uuid.UUID(bidder2_user["id"]),
        )
        db.add_all([tender, bidder1, bidder2])
        db.commit()
        db.refresh(tender)
        db.refresh(bidder1)
        db.refresh(bidder2)

        # Upload Tender Document
        t_doc_path = f"tenders/{tender.id}/rfp_spec.pdf"
        storage_service.upload(t_doc_path, generate_mock_pdf("RFP Doc"))
        tender_doc = Document(
            tender_id=tender.id,
            original_filename="rfp_spec.pdf",
            storage_path=t_doc_path,
            document_type=DocumentType.TENDER_PDF,
            mime_type="application/pdf",
            file_size=1024,
            status=DocumentStatus.ACTIVE,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        # Upload Bidder 1 Document
        b1_doc_path = f"bidders/{bidder1.id}/PAN/pan_card.pdf"
        storage_service.upload(b1_doc_path, generate_mock_pdf("PAN Doc"))
        bidder1_doc = Document(
            bidder_id=bidder1.id,
            original_filename="pan_card.pdf",
            storage_path=b1_doc_path,
            document_type=DocumentType.PAN,
            mime_type="application/pdf",
            file_size=2048,
            status=DocumentStatus.ACTIVE,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        # Upload Bidder 2 Document
        b2_doc_path = f"bidders/{bidder2.id}/GST/gst_cert.pdf"
        storage_service.upload(b2_doc_path, generate_mock_pdf("GST Doc"))
        bidder2_doc = Document(
            bidder_id=bidder2.id,
            original_filename="gst_cert.pdf",
            storage_path=b2_doc_path,
            document_type=DocumentType.GST,
            mime_type="application/pdf",
            file_size=4096,
            status=DocumentStatus.ACTIVE,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        db.add_all([tender_doc, bidder1_doc, bidder2_doc])
        db.commit()
        db.refresh(tender_doc)
        db.refresh(bidder1_doc)
        db.refresh(bidder2_doc)

        context = {
            "officer_headers": officer_headers,
            "bidder1_headers": bidder1_headers,
            "bidder2_headers": bidder2_headers,
            "tender_id": str(tender.id),
            "bidder1_id": str(bidder1.id),
            "bidder2_id": str(bidder2.id),
            "tender_doc_id": str(tender_doc.id),
            "bidder1_doc_id": str(bidder1_doc.id),
            "bidder2_doc_id": str(bidder2_doc.id),
            "officer_id": officer["id"],
            "bidder1_user_id": bidder1_user["id"],
            "bidder2_user_id": bidder2_user["id"],
        }
    finally:
        db.close()

    yield context

    # Teardown
    db_clean = SessionLocal()
    try:
        docs = db_clean.query(Document).filter(
            (Document.tender_id == uuid.UUID(context["tender_id"]))
            | (Document.bidder_id == uuid.UUID(context["bidder1_id"]))
            | (Document.bidder_id == uuid.UUID(context["bidder2_id"]))
        ).all()
        for d in docs:
            db_clean.delete(d)
        t = db_clean.get(Tender, uuid.UUID(context["tender_id"]))
        if t:
            db_clean.delete(t)
        b1 = db_clean.get(Bidder, uuid.UUID(context["bidder1_id"]))
        if b1:
            db_clean.delete(b1)
        b2 = db_clean.get(Bidder, uuid.UUID(context["bidder2_id"]))
        if b2:
            db_clean.delete(b2)
        u1 = db_clean.get(User, uuid.UUID(context["officer_id"]))
        if u1:
            db_clean.delete(u1)
        u2 = db_clean.get(User, uuid.UUID(context["bidder1_user_id"]))
        if u2:
            db_clean.delete(u2)
        u3 = db_clean.get(User, uuid.UUID(context["bidder2_user_id"]))
        if u3:
            db_clean.delete(u3)
        db_clean.commit()
    except Exception:
        db_clean.rollback()
    finally:
        db_clean.close()


# 1. GET /api/tenders/{tender_id}/documents

def test_list_tender_documents_success(mgmt_test_context):
    """Test listing tender documents returns complete metadata."""
    headers = mgmt_test_context["officer_headers"]
    tender_id = mgmt_test_context["tender_id"]

    response = client.get(f"/api/tenders/{tender_id}/documents", headers=headers)
    assert response.status_code == 200
    res_data = response.json()

    assert res_data["success"] is True
    assert res_data["pagination"]["total_count"] == 1
    doc = res_data["data"][0]

    assert doc["id"] == mgmt_test_context["tender_doc_id"]
    assert doc["tender_id"] == tender_id
    assert doc["document_type"] == "TENDER_PDF"
    assert doc["original_filename"] == "rfp_spec.pdf"
    assert doc["mime_type"] == "application/pdf"
    assert doc["file_size"] == 1024
    assert doc["processing_status"] == "NOT_PROCESSED"
    assert "download_url" in doc


def test_list_tender_documents_nonexistent_404(mgmt_test_context):
    """Test listing documents for non-existent tender returns 404."""
    headers = mgmt_test_context["officer_headers"]
    fake_id = uuid.uuid4()
    response = client.get(f"/api/tenders/{fake_id}/documents", headers=headers)
    assert response.status_code == 404


# 2. GET /api/bidders/{bidder_id}/documents

def test_list_bidder_documents_authorized(mgmt_test_context):
    """Test bidder can list their own documents and officer can list bidder documents."""
    # 1. Bidder 1 viewing their own documents
    b1_headers = mgmt_test_context["bidder1_headers"]
    b1_id = mgmt_test_context["bidder1_id"]

    res_b1 = client.get(f"/api/bidders/{b1_id}/documents", headers=b1_headers)
    assert res_b1.status_code == 200
    assert res_b1.json()["pagination"]["total_count"] == 1
    assert res_b1.json()["data"][0]["document_type"] == "PAN"

    # 2. Officer viewing Bidder 1 documents
    off_headers = mgmt_test_context["officer_headers"]
    res_off = client.get(f"/api/bidders/{b1_id}/documents", headers=off_headers)
    assert res_off.status_code == 200
    assert res_off.json()["pagination"]["total_count"] == 1


def test_list_bidder_documents_unauthorized_forbidden(mgmt_test_context):
    """Test Bidder 2 cannot list Bidder 1's documents (403 Forbidden)."""
    b2_headers = mgmt_test_context["bidder2_headers"]
    b1_id = mgmt_test_context["bidder1_id"]

    response = client.get(f"/api/bidders/{b1_id}/documents", headers=b2_headers)
    assert response.status_code == 403


# 3. GET /api/documents/{document_id}

def test_get_document_metadata_and_signed_url(mgmt_test_context):
    """Test retrieving individual document metadata and pre-signed download URL."""
    headers = mgmt_test_context["officer_headers"]
    doc_id = mgmt_test_context["tender_doc_id"]

    response = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert response.status_code == 200
    doc = response.json()

    assert doc["id"] == doc_id
    assert doc["original_filename"] == "rfp_spec.pdf"
    assert doc["processing_status"] == "NOT_PROCESSED"
    assert doc["download_url"] is not None


def test_get_document_unauthorized_bidder(mgmt_test_context):
    """Test Bidder 2 cannot view Bidder 1's private compliance document (403)."""
    b2_headers = mgmt_test_context["bidder2_headers"]
    b1_doc_id = mgmt_test_context["bidder1_doc_id"]

    response = client.get(f"/api/documents/{b1_doc_id}", headers=b2_headers)
    assert response.status_code == 403


def test_get_document_nonexistent_404(mgmt_test_context):
    """Test retrieving non-existent document ID returns 404."""
    headers = mgmt_test_context["officer_headers"]
    fake_id = uuid.uuid4()
    response = client.get(f"/api/documents/{fake_id}", headers=headers)
    assert response.status_code == 404


def test_get_document_unauthenticated_401(mgmt_test_context):
    """Test unauthenticated request to get document returns 401."""
    doc_id = mgmt_test_context["tender_doc_id"]
    response = client.get(f"/api/documents/{doc_id}")
    assert response.status_code == 401


# 4. DELETE /api/documents/{document_id}

def test_delete_document_success(mgmt_test_context):
    """Test authorized officer deleting tender document removes it from DB and storage."""
    headers = mgmt_test_context["officer_headers"]
    doc_id = mgmt_test_context["tender_doc_id"]

    del_res = client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Subsequent GET returns 404
    get_res = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert get_res.status_code == 404


def test_bidder_delete_own_document_success(mgmt_test_context):
    """Test Bidder 1 can delete their own compliance document."""
    b1_headers = mgmt_test_context["bidder1_headers"]
    b1_doc_id = mgmt_test_context["bidder1_doc_id"]

    del_res = client.delete(f"/api/documents/{b1_doc_id}", headers=b1_headers)
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True


def test_bidder_delete_tender_document_forbidden(mgmt_test_context):
    """Test Bidder cannot delete official Tender RFP document (403 Forbidden)."""
    b1_headers = mgmt_test_context["bidder1_headers"]
    t_doc_id = mgmt_test_context["tender_doc_id"]

    del_res = client.delete(f"/api/documents/{t_doc_id}", headers=b1_headers)
    assert del_res.status_code == 403


def test_bidder_delete_other_bidder_document_forbidden(mgmt_test_context):
    """Test Bidder 1 cannot delete Bidder 2's document (403 Forbidden)."""
    b1_headers = mgmt_test_context["bidder1_headers"]
    b2_doc_id = mgmt_test_context["bidder2_doc_id"]

    del_res = client.delete(f"/api/documents/{b2_doc_id}", headers=b1_headers)
    assert del_res.status_code == 403


def test_delete_document_nonexistent_404(mgmt_test_context):
    """Test deleting non-existent document ID returns 404."""
    headers = mgmt_test_context["officer_headers"]
    fake_id = uuid.uuid4()
    del_res = client.delete(f"/api/documents/{fake_id}", headers=headers)
    assert del_res.status_code == 404


def test_delete_document_unauthenticated_401(mgmt_test_context):
    """Test unauthenticated delete request returns 401."""
    doc_id = mgmt_test_context["tender_doc_id"]
    del_res = client.delete(f"/api/documents/{doc_id}")
    assert del_res.status_code == 401
