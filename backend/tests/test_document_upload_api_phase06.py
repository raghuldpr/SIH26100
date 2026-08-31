import io
import uuid
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppException
from app.core.storage import storage_service
from app.db.session import SessionLocal
from app.main import app
from app.models.bidder import Bidder
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus, UserRole
from app.models.tender import Tender
from app.models.user import User

client = TestClient(app)


def generate_pdf_bytes(title: str = "Tender Document") -> bytes:
    """Generates a valid mock PDF byte stream."""
    return (
        f"%PDF-1.4\n1 0 obj\n<< /Title ({title}) >>\nendobj\n"
        f"xref\n0 2\n0000000000 65535 f \n0000000010 00000 n \n"
        f"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n70\n%%EOF\n"
    ).encode("utf-8")


def generate_jpeg_bytes() -> bytes:
    """Generates a valid mock JPEG byte stream."""
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\xff\xd9"


def generate_png_bytes() -> bytes:
    """Generates a valid mock PNG byte stream."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def create_test_user(name: str, role: str) -> tuple[dict, dict]:
    """Helper to register and login a test user with a given role."""
    suffix = uuid.uuid4().hex[:6]
    email = f"{name.lower().replace(' ', '_')}_{suffix}@gem.gov.in"
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
    headers = {"Authorization": f"Bearer {token}"}
    return user_data, headers


@pytest.fixture
def test_context():
    """Sets up an officer, a bidder user, a tender, and a bidder."""
    officer, officer_headers = create_test_user("Procurement Officer", "PROCUREMENT_OFFICER")
    bidder_user, bidder_headers = create_test_user("Vendor Contact", "BIDDER")

    # Create Tender
    res_tender = client.post(
        "/api/v1/tenders",
        json={
            "tender_number": f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            "title": "Data Center Server Procurement",
            "organization": "National Informatics Centre",
        },
        headers=officer_headers,
    )
    assert res_tender.status_code == 201
    tender = res_tender.json()

    # Create Bidder
    res_bidder = client.post(
        "/api/v1/bidders",
        json={
            "company_name": f"ServerTech India Pvt Ltd {uuid.uuid4().hex[:4]}",
            "gst_number": "33AAAAA0000A1Z5",
            "pan_number": "AAAAA0000A",
            "contact_person": "Vikram Seth",
            "status": "ACTIVE",
        },
        headers=officer_headers,
    )
    assert res_bidder.status_code == 201
    bidder = res_bidder.json()

    yield {
        "officer_headers": officer_headers,
        "bidder_headers": bidder_headers,
        "tender": tender,
        "bidder": bidder,
        "officer": officer,
        "bidder_user": bidder_user,
    }

    # Teardown
    db = SessionLocal()
    try:
        t_id = uuid.UUID(tender["id"])
        b_id = uuid.UUID(bidder["id"])
        docs = db.query(Document).filter((Document.tender_id == t_id) | (Document.bidder_id == b_id)).all()
        for d in docs:
            db.delete(d)
        t = db.get(Tender, t_id)
        if t:
            db.delete(t)
        b = db.get(Bidder, b_id)
        if b:
            db.delete(b)
        u1 = db.get(User, uuid.UUID(officer["id"]))
        if u1:
            db.delete(u1)
        u2 = db.get(User, uuid.UUID(bidder_user["id"]))
        if u2:
            db.delete(u2)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# 1. Tender Single & Multiple Document Uploads

def test_tender_single_document_upload(test_context):
    """Test uploading a single RFP PDF document to a tender."""
    headers = test_context["officer_headers"]
    tender_id = test_context["tender"]["id"]

    pdf_bytes = generate_pdf_bytes("AIIMS Server Hardware RFP")
    files = {"file": ("rfp_hardware_spec.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"document_type": "TENDER"}

    response = client.post(
        f"/api/tenders/{tender_id}/documents",
        files=files,
        data=data,
        headers=headers,
    )
    assert response.status_code == 201
    doc = response.json()

    assert doc["tender_id"] == tender_id
    assert doc["original_filename"] == "rfp_hardware_spec.pdf"
    assert doc["document_type"] == "TENDER"
    assert doc["mime_type"] == "application/pdf"
    assert doc["status"] == "UPLOADED"
    assert doc["processing_status"] == "NOT_PROCESSED"
    assert doc["processing_error"] is None
    assert doc["extracted_data"] is None
    assert doc["storage_path"].startswith(f"tenders/{tender_id}/")


def test_tender_multiple_document_uploads(test_context):
    """Test uploading multiple documents simultaneously to a tender."""
    headers = test_context["officer_headers"]
    tender_id = test_context["tender"]["id"]

    pdf1 = generate_pdf_bytes("Tender Scope Part 1")
    pdf2 = generate_pdf_bytes("Tender Scope Part 2")

    multi_files = [
        ("files", ("scope_part1.pdf", io.BytesIO(pdf1), "application/pdf")),
        ("files", ("scope_part2.pdf", io.BytesIO(pdf2), "application/pdf")),
    ]
    data = {"document_type": "TENDER_NOTICE"}

    response = client.post(
        f"/api/tenders/{tender_id}/documents",
        files=multi_files,
        data=data,
        headers=headers,
    )
    assert response.status_code == 201
    docs = response.json()
    assert isinstance(docs, list)
    assert len(docs) == 2
    assert docs[0]["processing_status"] == "NOT_PROCESSED"
    assert docs[1]["processing_status"] == "NOT_PROCESSED"


# 2. Bidder Single & Multiple Document Uploads

def test_bidder_single_and_multi_upload(test_context):
    """Test uploading PAN, GST, and UDYAM documents for a Bidder."""
    headers = test_context["bidder_headers"]
    bidder_id = test_context["bidder"]["id"]

    # 1. Single PAN upload
    pan_pdf = generate_pdf_bytes("Company PAN Document")
    res_pan = client.post(
        f"/api/bidders/{bidder_id}/documents",
        files={"file": ("company_pan.pdf", io.BytesIO(pan_pdf), "application/pdf")},
        data={"document_type": "PAN"},
        headers=headers,
    )
    assert res_pan.status_code == 201
    pan_doc = res_pan.json()
    assert pan_doc["bidder_id"] == bidder_id
    assert pan_doc["document_type"] == "PAN"
    assert pan_doc["processing_status"] == "NOT_PROCESSED"
    assert f"bidders/{bidder_id}/PAN/" in pan_doc["storage_path"]

    # 2. Multi-file upload (JPEG & PNG certificates)
    jpeg_bytes = generate_jpeg_bytes()
    png_bytes = generate_png_bytes()
    multi_files = [
        ("files", ("gst_cert.jpg", io.BytesIO(jpeg_bytes), "image/jpeg")),
        ("files", ("udyam_cert.png", io.BytesIO(png_bytes), "image/png")),
    ]
    res_multi = client.post(
        f"/api/bidders/{bidder_id}/documents",
        files=multi_files,
        data={"document_type": "GST"},
        headers=headers,
    )
    assert res_multi.status_code == 201
    docs = res_multi.json()
    assert isinstance(docs, list)
    assert len(docs) == 2


# 3. Validation Failures (Invalid file, Oversized, Empty, Missing Extension)

def test_upload_invalid_file_format(test_context):
    """Test rejecting files that are not valid PDF or supported images."""
    headers = test_context["officer_headers"]
    tender_id = test_context["tender"]["id"]

    fake_text = b"This is plain text with no PDF or image magic header."
    response = client.post(
        f"/api/tenders/{tender_id}/documents",
        files={"file": ("fake.pdf", io.BytesIO(fake_text), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 400
    assert "Invalid file format" in response.json()["error"]["message"]


def test_upload_empty_file(test_context):
    """Test rejecting 0-byte empty file."""
    headers = test_context["officer_headers"]
    tender_id = test_context["tender"]["id"]

    response = client.post(
        f"/api/tenders/{tender_id}/documents",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 400
    assert "empty" in response.json()["error"]["message"].lower()


def test_upload_oversized_file(test_context):
    """Test rejecting files larger than configured limit."""
    headers = test_context["officer_headers"]
    tender_id = test_context["tender"]["id"]

    large_content = b"%PDF-1.4\n" + b"A" * (11 * 1024 * 1024)
    response = client.post(
        f"/api/tenders/{tender_id}/documents",
        files={"file": ("huge.pdf", io.BytesIO(large_content), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 400
    assert "exceeds" in response.json()["error"]["message"].lower()


# 4. Non-existent Entity Failures

def test_upload_to_nonexistent_tender(test_context):
    """Test 404 when uploading to non-existent tender ID."""
    headers = test_context["officer_headers"]
    fake_id = uuid.uuid4()
    pdf_bytes = generate_pdf_bytes()

    response = client.post(
        f"/api/tenders/{fake_id}/documents",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 404


def test_upload_to_nonexistent_bidder(test_context):
    """Test 404 when uploading to non-existent bidder ID."""
    headers = test_context["bidder_headers"]
    fake_id = uuid.uuid4()
    pdf_bytes = generate_pdf_bytes()

    response = client.post(
        f"/api/bidders/{fake_id}/documents",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=headers,
    )
    assert response.status_code == 404


# 5. Unauthorized & Unauthenticated Access

def test_unauthenticated_upload_rejected():
    """Test 401 when unauthenticated user attempts document upload."""
    fake_id = uuid.uuid4()
    pdf_bytes = generate_pdf_bytes()

    res_tender = client.post(
        f"/api/tenders/{fake_id}/documents",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res_tender.status_code == 401

    res_bidder = client.post(
        f"/api/bidders/{fake_id}/documents",
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert res_bidder.status_code == 401


def test_tender_upload_rbac_forbidden(test_context):
    """Test 403 when a BIDDER role attempts to upload a tender RFP document."""
    bidder_headers = test_context["bidder_headers"]
    tender_id = test_context["tender"]["id"]
    pdf_bytes = generate_pdf_bytes()

    response = client.post(
        f"/api/tenders/{tender_id}/documents",
        files={"file": ("rfp.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=bidder_headers,
    )
    assert response.status_code == 403


# 6. Database Failure Compensating Storage Cleanup

def test_database_failure_cleans_orphaned_storage(test_context):
    """Verify that if database record creation fails, the uploaded storage file is deleted."""
    headers = test_context["officer_headers"]
    tender_id = test_context["tender"]["id"]
    pdf_bytes = generate_pdf_bytes("Compensating Rollback Test")

    with patch("app.crud.crud_document.crud_document.create_metadata", side_effect=Exception("DB Failure")):
        with patch.object(storage_service, "delete", wraps=storage_service.delete) as mock_delete:
            response = client.post(
                f"/api/tenders/{tender_id}/documents",
                files={"file": ("rollback_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
                headers=headers,
            )
            assert response.status_code in (400, 500)
            # Ensure storage_service.delete was called to remove the orphaned file
            assert mock_delete.called
