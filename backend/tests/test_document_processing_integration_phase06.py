import uuid
import fitz
import pytest
from fastapi.testclient import TestClient

from app.core.storage import storage_service
from app.crud.crud_document import crud_document
from app.db.session import SessionLocal
from app.main import app
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus, TenderStatus, UserRole
from app.models.tender import Tender
from app.models.user import User
from app.services.document_processing_service import document_processing_service

client = TestClient(app)


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


def create_sample_gst_pdf() -> bytes:
    """Generates synthetic GST PDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        fitz.Point(50, 72),
        "Government of India\nForm GST REG-06\nRegistration Certificate\n"
        "Registration Number (GSTIN): 27ABCDE1234F1Z5\n"
        "Legal Name: TECHSERVE SOLUTIONS PRIVATE LIMITED\n"
        "Taxpayer Type: Regular\n"
        "Principal Place of Business: Plot 45, MIDC Pune",
        fontsize=12,
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# 1. Complete Integration: Upload -> Storage -> DB -> Processing -> Extraction -> DB Persistence

def test_full_document_processing_lifecycle():
    """
    Demonstrates the complete Phase 06 Step 10 pipeline:
    GST.pdf -> Supabase Storage -> PostgreSQL metadata -> Processing -> Extraction -> Classification -> PostgreSQL extracted_data
    """
    user_data, headers = register_and_login("Officer Lifecycle", "PROCUREMENT_OFFICER")
    db = SessionLocal()
    try:
        tender = Tender(
            tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            title="Cloud Server Tender",
            organization="Ministry of Electronics",
            category="GOODS",
            created_by=uuid.UUID(user_data["id"]),
            status=TenderStatus.OPEN,
        )

        db.add(tender)
        db.commit()
        db.refresh(tender)

        # 1. Generate GST PDF binary
        pdf_bytes = create_sample_gst_pdf()

        # 2. Upload to Storage
        storage_path = f"tenders/{tender.id}/test_gst_cert.pdf"
        uploaded_path = storage_service.upload(
            storage_path=storage_path,
            file_content=pdf_bytes,
            mime_type="application/pdf",
        )

        # 3. Create Document Record in PostgreSQL
        doc = crud_document.create_metadata(
            db=db,
            original_filename="gst_registration.pdf",
            storage_path=uploaded_path,
            document_type=DocumentType.OTHER,  # Initially generic
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            tender_id=tender.id,
            status=DocumentStatus.UPLOADED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        assert doc.processing_status == ProcessingStatus.NOT_PROCESSED
        assert doc.extracted_data is None

        # 4. Trigger Processing Service
        processed_doc = document_processing_service.process_document(
            db=db,
            document_id=doc.id,
        )

        # 5. Verify PostgreSQL Updates
        assert processed_doc.processing_status == ProcessingStatus.PROCESSED
        assert processed_doc.processing_error is None
        assert processed_doc.document_type == DocumentType.GST

        # Verify Structured JSON in PostgreSQL
        data = processed_doc.extracted_data
        assert isinstance(data, dict)
        assert data["document_type"] == "GST"
        assert data["confidence"] >= 0.85
        assert "entities" in data
        assert data["entities"]["gstin"]["value"] == "27ABCDE1234F1Z5"
        assert "TECHSERVE" in data["entities"]["company_name"]["value"]
    finally:
        db.close()


# 2. Retry Safety Test

def test_document_processing_retry_safety():
    """Test that retry_processing updates document idempotently and safely."""
    user_data, _ = register_and_login("Officer Retry", "PROCUREMENT_OFFICER")
    db = SessionLocal()
    try:
        tender = Tender(
            tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            title="Retry Test Tender",
            organization="Ministry of Electronics",
            category="GOODS",
            created_by=uuid.UUID(user_data["id"]),
            status=TenderStatus.OPEN,
        )
        db.add(tender)
        db.commit()
        db.refresh(tender)

        pdf_bytes = create_sample_gst_pdf()
        storage_path = f"tenders/{tender.id}/retry_gst.pdf"
        uploaded_path = storage_service.upload(storage_path, pdf_bytes, "application/pdf")

        doc = crud_document.create_metadata(
            db=db,
            original_filename="retry_gst.pdf",
            storage_path=uploaded_path,
            document_type=DocumentType.GST,
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            tender_id=tender.id,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        # First run
        doc_1 = document_processing_service.process_document(db=db, document_id=doc.id)
        assert doc_1.processing_status == ProcessingStatus.PROCESSED

        # Retry run
        doc_2 = document_processing_service.retry_processing(db=db, document_id=doc.id)
        assert doc_2.processing_status == ProcessingStatus.PROCESSED
        assert doc_2.extracted_data["entities"]["gstin"]["value"] == "27ABCDE1234F1Z5"
    finally:
        db.close()


# 3. Non-Destructive Failure Handling Test

def test_document_processing_non_destructive_failure():
    """Test that corrupted files transition to FAILED without deleting the file or DB metadata."""
    user_data, _ = register_and_login("Officer Failure", "PROCUREMENT_OFFICER")
    db = SessionLocal()
    try:
        tender = Tender(
            tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            title="Failure Test Tender",
            organization="Ministry of Electronics",
            category="GOODS",
            created_by=uuid.UUID(user_data["id"]),
            status=TenderStatus.OPEN,
        )
        db.add(tender)
        db.commit()
        db.refresh(tender)

        bad_storage_path = f"tenders/{tender.id}/non_existent_file.pdf"

        # Create metadata pointing to missing storage object
        doc = crud_document.create_metadata(
            db=db,
            original_filename="corrupted.pdf",
            storage_path=bad_storage_path,
            document_type=DocumentType.OTHER,
            mime_type="application/pdf",
            file_size=100,
            tender_id=tender.id,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        failed_doc = document_processing_service.process_document(db=db, document_id=doc.id)

        # Status must be FAILED
        assert failed_doc.processing_status == ProcessingStatus.FAILED
        assert failed_doc.processing_error is not None

        # Document must still exist in DB
        refetched = crud_document.get_by_id(db, doc.id)
        assert refetched is not None
        assert refetched.id == doc.id
        assert refetched.storage_path == bad_storage_path
    finally:
        db.close()


# 4. API Endpoints Test: POST /api/documents/{document_id}/process & retry

def test_document_process_and_retry_api_endpoints():
    """Test triggering document processing and retry via FastAPI endpoints."""
    user_data, headers = register_and_login("Officer API", "PROCUREMENT_OFFICER")
    db = SessionLocal()
    try:
        tender = Tender(
            tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            title="API Process Test Tender",
            organization="Ministry of Electronics",
            category="GOODS",
            created_by=uuid.UUID(user_data["id"]),
            status=TenderStatus.OPEN,
        )

        db.add(tender)
        db.commit()
        db.refresh(tender)

        pdf_bytes = create_sample_gst_pdf()
        storage_path = f"tenders/{tender.id}/api_test_gst.pdf"
        uploaded_path = storage_service.upload(storage_path, pdf_bytes, "application/pdf")

        doc = crud_document.create_metadata(
            db=db,
            original_filename="api_test_gst.pdf",
            storage_path=uploaded_path,
            document_type=DocumentType.GST,
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            tender_id=tender.id,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        # Trigger Process API
        resp_process = client.post(f"/api/v1/documents/{doc.id}/process", headers=headers)
        assert resp_process.status_code == 200
        data_process = resp_process.json()
        assert data_process["processing_status"] == "PROCESSED"
        assert data_process["extracted_data"]["entities"]["gstin"]["value"] == "27ABCDE1234F1Z5"

        # Trigger Retry API
        resp_retry = client.post(f"/api/v1/documents/{doc.id}/retry", headers=headers)
        assert resp_retry.status_code == 200
        data_retry = resp_retry.json()
        assert data_retry["processing_status"] == "PROCESSED"
    finally:
        db.close()
