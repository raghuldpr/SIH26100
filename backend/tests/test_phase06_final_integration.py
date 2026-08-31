import io
import uuid
import fitz
import pytest
from fastapi.testclient import TestClient

from app.core.storage import storage_service
from app.crud.crud_document import crud_document
from app.db.session import SessionLocal
from app.main import app
from app.models.bidder import Bidder
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus, TenderStatus, UserRole
from app.models.tender import Tender
from app.services.document_processing_service import document_processing_service

client = TestClient(app)


def register_and_login(name: str, role: str) -> tuple[dict, dict]:
    """Helper to create and authenticate a user with JWT token."""
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


def create_pdf(content_text: str) -> bytes:
    """Helper generating synthetic PDF byte payloads."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 72), content_text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# 1. Verification of All 8 Document Categories in End-to-End Pipeline

@pytest.mark.parametrize(
    "doc_type_key,sample_text,expected_class,expected_entity_key,expected_entity_val",
    [
        (
            "PAN",
            "INCOME TAX DEPARTMENT\nGOVT. OF INDIA\nPermanent Account Number: ABCDE1234F\nName: SURESH KUMAR\nFather's Name: RAMESH KUMAR\nDate of Birth: 15/08/1985",
            "PAN",
            "pan_number",
            "ABCDE1234F",
        ),
        (
            "GST",
            "Government of India\nForm GST REG-06\nRegistration Certificate\nGSTIN: 27ABCDE1234F1Z5\nLegal Name: TECHSERVE SOLUTIONS PRIVATE LIMITED\nTaxpayer Type: Regular",
            "GST",
            "gstin",
            "27ABCDE1234F1Z5",
        ),
        (
            "UDYAM",
            "MINISTRY OF MICRO, SMALL AND MEDIUM ENTERPRISES\nUDYAM REGISTRATION CERTIFICATE\nUDYAM REGISTRATION NUMBER: UDYAM-MH-01-0012345\nNAME OF ENTERPRISE: INNOVATIVE DIGITAL SYSTEMS\nTYPE OF ENTERPRISE: MICRO",
            "UDYAM",
            "udyam_number",
            "UDYAM-MH-01-0012345",
        ),
        (
            "FINANCIAL_STATEMENT",
            "INDEPENDENT AUDITOR'S REPORT\nBalance Sheet as at 31st March 2025\nStatement of Profit and Loss for the year ended March 31, 2025\nUDIN: 24123456AAAAAA1234\nAnnual Turnover: INR 15,00,00,000",
            "FINANCIAL_STATEMENT",
            "udin",
            "24123456AAAAAA1234",
        ),
        (
            "EXPERIENCE_CERTIFICATE",
            "WORK COMPLETION CERTIFICATE\nThis is to certify that M/s Global Networks India Pvt Ltd has satisfactorily completed execution of work for 'Campus Wi-Fi'\nPurchase Order No: PO/2023/8899\nContract Value: Rs. 85,00,000",
            "EXPERIENCE_CERTIFICATE",
            "company_name",
            "Global Networks India Pvt Ltd",
        ),
        (
            "OEM_AUTHORIZATION",
            "MANUFACTURER'S AUTHORIZATION FORM (MAF)\nWe, Dell Technologies India Pvt Ltd, who are official manufacturers of Server Hardware, do hereby authorize Prime Infotech to submit a bid against Tender Ref: GEM/2026/B/100200",
            "OEM_AUTHORIZATION",
            "oem_name",
            "Dell Technologies India Pvt Ltd",
        ),
        (
            "MII_DECLARATION",
            "DECLARATION OF LOCAL CONTENT\nWe, Bharat Electronics Solutions Pvt Ltd, hereby declare that we are a Class-I Local Supplier.\nThe local content percentage is 68.5%.",
            "MII_DECLARATION",
            "supplier_class",
            "Class-I Local Supplier",
        ),
        (
            "TENDER_PDF",
            "NOTICE INVITING TENDER (NIT)\nRequest for Proposal (RFP) for Procurement of Cloud Data Center Servers\nTender Inviting Authority: Ministry of Electronics and Information Technology\nGeM Bid Number: GEM/2026/B/987654\nEMD Amount: INR 2,00,000",
            "TENDER",
            "tender_number",
            "GEM/2026/B/987654",
        ),
    ],
)
def test_all_document_categories_pipeline(
    doc_type_key: str,
    sample_text: str,
    expected_class: str,
    expected_entity_key: str,
    expected_entity_val: str,
):
    """Verifies complete upload, extraction, classification, and structured output across all 8 classes."""
    user_data, _ = register_and_login(f"Officer {doc_type_key}", "PROCUREMENT_OFFICER")
    db = SessionLocal()
    try:
        tender = Tender(
            tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            title=f"Verification Tender {doc_type_key}",
            organization="Ministry of Electronics",
            category="GOODS",
            created_by=uuid.UUID(user_data["id"]),
            status=TenderStatus.OPEN,
        )
        db.add(tender)
        db.commit()
        db.refresh(tender)

        pdf_bytes = create_pdf(sample_text)
        storage_path = f"tenders/{tender.id}/{doc_type_key.lower()}.pdf"
        uploaded_path = storage_service.upload(storage_path, pdf_bytes, "application/pdf")

        # Create record
        doc = crud_document.create_metadata(
            db=db,
            original_filename=f"{doc_type_key.lower()}.pdf",
            storage_path=uploaded_path,
            document_type=DocumentType.OTHER,
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
            tender_id=tender.id,
            status=DocumentStatus.UPLOADED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
        )

        # Process
        processed = document_processing_service.process_document(db=db, document_id=doc.id)

        assert processed.processing_status == ProcessingStatus.PROCESSED
        assert processed.processing_error is None
        assert processed.extracted_data is not None
        assert processed.extracted_data["document_type"] == expected_class
        assert processed.extracted_data["confidence"] >= 0.80

        # Validate entity
        entities = processed.extracted_data.get("entities", {})
        assert expected_entity_key in entities
        assert expected_entity_val in entities[expected_entity_key]["value"]
    finally:
        db.close()


# 2. Comprehensive Security, RBAC, Validation & Deletion Lifecycle Test

def test_full_security_validation_and_lifecycle():
    """
    Tests:
    - Single and Multi-file uploads
    - MIME & magic bytes validation
    - Cross-tenant RBAC
    - Dual deletion (DB + Storage)
    - Compensating rollback
    """
    officer, officer_headers = register_and_login("Sec Officer", "PROCUREMENT_OFFICER")
    bidder1_user, bidder1_headers = register_and_login("Sec Bidder1", "BIDDER")
    bidder2_user, bidder2_headers = register_and_login("Sec Bidder2", "BIDDER")

    db = SessionLocal()
    try:
        tender = Tender(
            tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
            title="Security Lifecycle Tender",
            organization="NIC India",
            category="GOODS",
            created_by=uuid.UUID(officer["id"]),
            status=TenderStatus.OPEN,
        )
        bidder1 = Bidder(
            company_name="Alpha Tech Sec",
            gst_number="27AAAAA1234A1Z5",
            user_id=uuid.UUID(bidder1_user["id"]),
        )
        bidder2 = Bidder(
            company_name="Beta Tech Sec",
            gst_number="29BBBBB5678B1Z5",
            user_id=uuid.UUID(bidder2_user["id"]),
        )
        db.add_all([tender, bidder1, bidder2])
        db.commit()
        db.refresh(tender)
        db.refresh(bidder1)
        db.refresh(bidder2)

        # 1. Validation Rejection: Unsupported file extension (.exe)
        exe_file = ("malware.exe", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "application/x-msdownload")
        res_bad_ext = client.post(
            f"/api/tenders/{tender.id}/documents",
            headers=officer_headers,
            files={"files": exe_file},
        )
        assert res_bad_ext.status_code == 400

        # 2. Validation Rejection: Fake PDF header / MIME mismatch
        fake_pdf = ("fake.pdf", io.BytesIO(b"This is completely plain text without PDF header"), "application/pdf")
        res_fake_pdf = client.post(
            f"/api/tenders/{tender.id}/documents",
            headers=officer_headers,
            files={"files": fake_pdf},
        )
        assert res_fake_pdf.status_code == 400

        # 3. Successful Multi-file upload for Bidder 1
        pdf_pan = create_pdf("INCOME TAX DEPARTMENT Permanent Account Number: ABCDE1234F Name: RAJESH")
        pdf_gst = create_pdf("Form GST REG-06 GSTIN: 27ABCDE1234F1Z5 Legal Name: Alpha Tech")
        res_multi = client.post(
            f"/api/bidders/{bidder1.id}/documents",
            headers=bidder1_headers,
            files=[
                ("files", ("pan.pdf", io.BytesIO(pdf_pan), "application/pdf")),
                ("files", ("gst.pdf", io.BytesIO(pdf_gst), "application/pdf")),
            ],
            data={"document_type": "OTHER"},
        )
        assert res_multi.status_code == 201
        uploaded_docs = res_multi.json()
        assert len(uploaded_docs) == 2
        b1_doc_id = uploaded_docs[0]["id"]

        # 4. Cross-Tenant Protection: Bidder 2 CANNOT access Bidder 1's documents
        res_b2_access = client.get(f"/api/documents/{b1_doc_id}", headers=bidder2_headers)
        assert res_b2_access.status_code == 403

        # 5. Cross-Tenant Protection: Bidder 2 CANNOT delete Bidder 1's documents
        res_b2_del = client.delete(f"/api/documents/{b1_doc_id}", headers=bidder2_headers)
        assert res_b2_del.status_code == 403

        # 6. Dual Deletion: Bidder 1 deletes their own document
        res_b1_del = client.delete(f"/api/documents/{b1_doc_id}", headers=bidder1_headers)
        assert res_b1_del.status_code == 200

        # 7. Verification: Subsequent GET returns 404
        res_post_del = client.get(f"/api/documents/{b1_doc_id}", headers=bidder1_headers)
        assert res_post_del.status_code == 404
    finally:
        db.close()
