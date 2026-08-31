import io
import uuid
import pytest
from fastapi.testclient import TestClient

from app.db.session import SessionLocal
from app.main import app
from app.models.bidder import Bidder
from app.models.document import Document
from app.models.tender import Tender
from app.models.user import User

client = TestClient(app)


def create_authenticated_officer(name: str, email_prefix: str) -> tuple[dict, dict]:
    """Registers and authenticates a test officer."""
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

    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]["access_token"]
    return reg_res.json(), {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_setup():
    """Sets up an authenticated officer, a test tender, and a test bidder."""
    user, headers = create_authenticated_officer("Doc Officer", "doc_officer")

    # Create Tender
    res_tender = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            "title": "Hospital Medical Imaging Equipment Procurement",
            "organization": "All India Institute of Medical Sciences",
        },
        headers=headers,
    )
    assert res_tender.status_code == 201
    tender = res_tender.json()

    # Create Bidder
    res_bidder = client.post(
        "/api/v1/bidders",
        json={
            "company_name": f"MedTech Diagnostic Systems {uuid.uuid4().hex[:4]}",
            "gst_number": "29ABCDE1234F1Z5",
            "pan_number": "ABCDE1234F",
            "contact_person": "Dr. Ananya Roy",
            "status": "ACTIVE",
        },
        headers=headers,
    )
    assert res_bidder.status_code == 201
    bidder = res_bidder.json()

    yield headers, tender, bidder

    # Teardown
    db = SessionLocal()
    try:
        user_id = uuid.UUID(user["id"])
        tender_id = uuid.UUID(tender["id"])
        bidder_id = uuid.UUID(bidder["id"])

        docs = db.query(Document).filter(
            (Document.tender_id == tender_id) | (Document.bidder_id == bidder_id)
        ).all()
        for d in docs:
            db.delete(d)

        t = db.get(Tender, tender_id)
        if t:
            db.delete(t)
        b = db.get(Bidder, bidder_id)
        if b:
            db.delete(b)
        u = db.get(User, user_id)
        if u:
            db.delete(u)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def generate_mock_pdf(content_text: str = "Mock PDF Content for GeM Tender") -> bytes:
    """Generates a valid mock PDF byte buffer starting with %PDF- header."""
    return f"%PDF-1.4\n1 0 obj\n<< /Title ({content_text}) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF".encode("utf-8")


def test_tender_document_upload_and_lifecycle(test_setup):
    """Test uploading a valid Tender RFP document, listing, and retrieving metadata."""
    headers, tender, _ = test_setup
    tender_id = tender["id"]

    pdf_bytes = generate_mock_pdf("AIIMS MRI & CT Scan Procurement RFP Specification")
    files = {
        "file": ("aiims_rfp_specifications.pdf", io.BytesIO(pdf_bytes), "application/pdf")
    }
    data = {"document_type": "TENDER_PDF"}

    # 1. UPLOAD Tender Document (POST /api/tenders/{tender_id}/documents)
    res_upload = client.post(
        f"/api/tenders/{tender_id}/documents",
        files=files,
        data=data,
        headers=headers,
    )
    assert res_upload.status_code == 201
    doc = res_upload.json()
    doc_id = doc["id"]

    assert doc["tender_id"] == tender_id
    assert doc["original_filename"] == "aiims_rfp_specifications.pdf"
    assert doc["document_type"] == "TENDER_PDF"
    assert doc["mime_type"] == "application/pdf"
    assert doc["status"] == "UPLOADED"
    assert "tenders/" in doc["storage_path"]
    assert "download_url" in doc

    # 2. LIST Tender Documents (GET /api/tenders/{tender_id}/documents)
    res_list = client.get(f"/api/tenders/{tender_id}/documents", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["success"] is True
    assert list_data["pagination"]["total_count"] == 1
    assert list_data["data"][0]["id"] == doc_id

    # 3. GET Document by ID (GET /api/documents/{document_id})
    res_get = client.get(f"/api/documents/{doc_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == doc_id
    assert res_get.json()["original_filename"] == "aiims_rfp_specifications.pdf"

    # 4. DELETE Document (DELETE /api/documents/{document_id})
    res_del = client.delete(f"/api/documents/{doc_id}", headers=headers)
    assert res_del.status_code == 200
    assert res_del.json()["success"] is True

    # 5. Verify Document is removed from list
    res_list_after = client.get(f"/api/tenders/{tender_id}/documents", headers=headers)
    assert res_list_after.status_code == 200
    assert res_list_after.json()["pagination"]["total_count"] == 0


def test_bidder_multiple_document_upload(test_setup):
    """Test uploading single and multiple compliance documents for a Bidder."""
    headers, _, bidder = test_setup
    bidder_id = bidder["id"]

    # 1. Single document upload (PAN)
    pan_pdf = generate_mock_pdf("PAN Card Document")
    res_pan = client.post(
        f"/api/bidders/{bidder_id}/documents",
        files={"files": ("company_pan_card.pdf", io.BytesIO(pan_pdf), "application/pdf")},
        data={"document_type": "PAN"},
        headers=headers,
    )
    assert res_pan.status_code == 201
    pan_doc = res_pan.json()
    assert pan_doc["bidder_id"] == bidder_id
    assert pan_doc["document_type"] == "PAN"
    assert "bidders/" in pan_doc["storage_path"]
    assert "/PAN/" in pan_doc["storage_path"]

    # 2. Multi-document upload (GST and UDYAM)
    gst_pdf = generate_mock_pdf("GST Registration Certificate")
    udyam_pdf = generate_mock_pdf("Udyam MSME Certificate")

    multi_files = [
        ("files", ("gst_certificate.pdf", io.BytesIO(gst_pdf), "application/pdf")),
        ("files", ("udyam_certificate.pdf", io.BytesIO(udyam_pdf), "application/pdf")),
    ]
    res_multi = client.post(
        f"/api/bidders/{bidder_id}/documents",
        files=multi_files,
        data={"document_type": "GST"},
        headers=headers,
    )
    assert res_multi.status_code == 201
    multi_docs = res_multi.json()
    assert isinstance(multi_docs, list)
    assert len(multi_docs) == 2

    # 3. LIST Bidder Documents
    res_bidder_docs = client.get(f"/api/bidders/{bidder_id}/documents", headers=headers)
    assert res_bidder_docs.status_code == 200
    b_data = res_bidder_docs.json()
    assert b_data["success"] is True
    assert b_data["pagination"]["total_count"] == 3


def test_document_validation_failures(test_setup):
    """Test file validation: invalid MIME / header, oversized files, empty files."""
    headers, tender, bidder = test_setup
    tender_id = tender["id"]

    # 1. Reject invalid file format (not a PDF)
    fake_txt = b"This is a plain text file pretending to be a pdf."
    res_invalid_format = client.post(
        f"/api/tenders/{tender_id}/documents",
        files={"file": ("fake_document.pdf", io.BytesIO(fake_txt), "application/pdf")},
        headers=headers,
    )
    assert res_invalid_format.status_code == 400
    err_data = res_invalid_format.json()
    assert err_data["success"] is False
    assert "valid pdf" in err_data["error"]["message"].lower()

    # 2. Reject empty file
    res_empty = client.post(
        f"/api/tenders/{tender_id}/documents",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        headers=headers,
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.json()["error"]["message"].lower()

    # 3. Reject oversized file (e.g., larger than 10MB)
    large_content = b"%PDF-" + b"0" * (11 * 1024 * 1024)
    res_large = client.post(
        f"/api/tenders/{tender_id}/documents",
        files={"file": ("large_file.pdf", io.BytesIO(large_content), "application/pdf")},
        headers=headers,
    )
    assert res_large.status_code == 400
    assert "exceeds" in res_large.json()["error"]["message"].lower()


def test_document_error_conditions(test_setup):
    """Test 404s for non-existent entities and unauthenticated access."""
    headers, _, _ = test_setup
    fake_id = uuid.uuid4()
    pdf_bytes = generate_mock_pdf("Sample PDF")

    # 404 non-existent tender upload
    res_non_t = client.post(
        f"/api/tenders/{fake_id}/documents",
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert res_non_t.status_code == 404

    # 404 non-existent bidder upload
    res_non_b = client.post(
        f"/api/bidders/{fake_id}/documents",
        files={"files": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert res_non_b.status_code == 404

    # 404 non-existent document
    assert client.get(f"/api/documents/{fake_id}", headers=headers).status_code == 404
    assert client.delete(f"/api/documents/{fake_id}", headers=headers).status_code == 404

    # 401 unauthenticated
    assert client.get(f"/api/documents/{fake_id}").status_code == 401
    assert client.delete(f"/api/documents/{fake_id}").status_code == 401
