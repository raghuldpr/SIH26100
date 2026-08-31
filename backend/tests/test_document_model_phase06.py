import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.crud.crud_document import crud_document
from app.db.base import Base
from app.models import (
    Bidder,
    BidderStatus,
    Document,
    DocumentProcessingStatus,
    DocumentStatus,
    DocumentType,
    ProcessingStatus,
    Tender,
    TenderStatus,
    User,
    UserRole,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for document model testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_document_model_all_required_fields(db_session: Session):
    """Verify Document model instantiation with all standard and new phase 06 fields."""
    tender = Tender(
        tender_number="GEM/2026/B/778899",
        title="High Performance Computing Cluster",
        organization="Centre for Development of Advanced Computing (C-DAC)",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()

    doc = Document(
        tender_id=tender.id,
        bidder_id=None,
        original_filename="tender_rfp_specifications.pdf",
        storage_path="storage/tenders/778899/tender_rfp_specifications.pdf",
        document_type=DocumentType.TENDER,
        mime_type="application/pdf",
        file_size=1048576,
        status=DocumentStatus.ACTIVE,
        processing_status=ProcessingStatus.NOT_PROCESSED,
        processing_error=None,
        extracted_data=None,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    # Validate ID and foreign keys
    assert isinstance(doc.id, uuid.UUID)
    assert doc.tender_id == tender.id
    assert doc.bidder_id is None

    # Validate file metadata
    assert doc.original_filename == "tender_rfp_specifications.pdf"
    assert doc.storage_path == "storage/tenders/778899/tender_rfp_specifications.pdf"
    assert doc.document_type == DocumentType.TENDER
    assert doc.mime_type == "application/pdf"
    assert doc.file_size == 1048576

    # Validate statuses and processing fields
    assert doc.status == DocumentStatus.ACTIVE
    assert doc.processing_status == ProcessingStatus.NOT_PROCESSED
    assert doc.processing_error is None
    assert doc.extracted_data is None

    # Validate timestamps
    assert isinstance(doc.uploaded_at, datetime)
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)

    # Validate relationships
    assert doc.tender.tender_number == "GEM/2026/B/778899"
    assert len(tender.documents) == 1


def test_document_types_supported(db_session: Session):
    """Verify support for all required document types."""
    tender = Tender(
        tender_number="GEM/2026/B/TYPE_TEST",
        title="Type Verification Tender",
        organization="GeM Testing Org",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()

    required_types = [
        DocumentType.TENDER,
        DocumentType.PAN,
        DocumentType.GST,
        DocumentType.UDYAM,
        DocumentType.FINANCIAL_STATEMENT,
        DocumentType.EXPERIENCE_CERTIFICATE,
        DocumentType.OEM_AUTHORIZATION,
        DocumentType.MII_DECLARATION,
        DocumentType.OTHER,
    ]

    for doc_type in required_types:
        doc = Document(
            tender_id=tender.id,
            original_filename=f"{doc_type.value.lower()}_test.pdf",
            storage_path=f"storage/{doc_type.value.lower()}_test.pdf",
            document_type=doc_type,
            status=DocumentStatus.ACTIVE,
        )
        db_session.add(doc)

    db_session.commit()

    docs = db_session.query(Document).filter(Document.tender_id == tender.id).all()
    created_types = {d.document_type for d in docs}
    for req_type in required_types:
        assert req_type in created_types


def test_document_statuses_and_processing_statuses(db_session: Session):
    """Verify document lifecycle and processing statuses."""
    bidder = Bidder(
        company_name="Alpha Tech Pvt Ltd",
        gst_number="27AAAAA0000A1Z5",
        status=BidderStatus.ACTIVE,
    )
    db_session.add(bidder)
    db_session.commit()

    # Test ACTIVE, DELETED status and processing status transitions
    doc = Document(
        bidder_id=bidder.id,
        original_filename="oem_auth.pdf",
        storage_path="storage/oem_auth.pdf",
        document_type=DocumentType.OEM_AUTHORIZATION,
        status=DocumentStatus.ACTIVE,
        processing_status=ProcessingStatus.NOT_PROCESSED,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    assert doc.status == DocumentStatus.ACTIVE
    assert doc.processing_status == ProcessingStatus.NOT_PROCESSED

    # Transition to PROCESSING
    doc.processing_status = ProcessingStatus.PROCESSING
    db_session.commit()
    db_session.refresh(doc)
    assert doc.processing_status == ProcessingStatus.PROCESSING

    # Transition to PROCESSED with extracted_data
    extracted_payload = {
        "oem_name": "Cisco Systems",
        "authorization_code": "AUTH-2026-9901",
        "valid_until": "2028-12-31",
        "authorized_products": ["Switches", "Routers"],
    }
    doc.processing_status = ProcessingStatus.PROCESSED
    doc.extracted_data = extracted_payload
    db_session.commit()
    db_session.refresh(doc)
    assert doc.processing_status == ProcessingStatus.PROCESSED
    assert doc.extracted_data["oem_name"] == "Cisco Systems"
    assert doc.extracted_data["authorization_code"] == "AUTH-2026-9901"

    # Transition to FAILED with processing_error
    doc.processing_status = ProcessingStatus.FAILED
    doc.processing_error = "OCR failed to parse signature block on page 3"
    db_session.commit()
    db_session.refresh(doc)
    assert doc.processing_status == ProcessingStatus.FAILED
    assert "OCR failed" in doc.processing_error

    # Soft-delete status
    doc.status = DocumentStatus.DELETED
    db_session.commit()
    db_session.refresh(doc)
    assert doc.status == DocumentStatus.DELETED


def test_document_owner_check_constraint(db_session: Session):
    """Verify that a document cannot exist without either a tender_id or bidder_id."""
    doc_orphaned = Document(
        tender_id=None,
        bidder_id=None,
        original_filename="orphaned.pdf",
        storage_path="storage/orphaned.pdf",
        document_type=DocumentType.OTHER,
    )
    db_session.add(doc_orphaned)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_document_tender_and_bidder_dual_association(db_session: Session):
    """Verify document linked to both a tender and a bidder (e.g. submitted bid proposal)."""
    tender = Tender(
        tender_number="GEM/2026/B/DUAL_ASSOC",
        title="Dual Link Tender",
        organization="MoD",
        status=TenderStatus.OPEN,
    )
    bidder = Bidder(
        company_name="Defense Tech Corp",
        status=BidderStatus.ACTIVE,
    )
    db_session.add_all([tender, bidder])
    db_session.commit()

    doc = Document(
        tender_id=tender.id,
        bidder_id=bidder.id,
        original_filename="technical_bid.pdf",
        storage_path="storage/tenders/bids/tech_bid.pdf",
        document_type=DocumentType.TECHNICAL_BID,
        status=DocumentStatus.ACTIVE,
        processing_status=ProcessingStatus.PROCESSED,
        extracted_data={"compliance_score": 98.5, "deviations": []},
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    assert doc.tender_id == tender.id
    assert doc.bidder_id == bidder.id
    assert doc.tender.tender_number == "GEM/2026/B/DUAL_ASSOC"
    assert doc.bidder.company_name == "Defense Tech Corp"
    assert doc.extracted_data["compliance_score"] == 98.5


def test_document_cascade_delete_from_tender(db_session: Session):
    """Deleting a Tender cascades and removes its associated Documents."""
    tender = Tender(
        tender_number="GEM/2026/B/CASCADE_TENDER",
        title="Cascade Tender",
        organization="Railway Board",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()

    doc = Document(
        tender_id=tender.id,
        original_filename="railway_rfp.pdf",
        storage_path="storage/railway_rfp.pdf",
        document_type=DocumentType.TENDER,
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    # Delete Tender
    db_session.delete(tender)
    db_session.commit()

    # Document should be deleted
    assert db_session.get(Document, doc_id) is None


def test_document_cascade_delete_from_bidder(db_session: Session):
    """Deleting a Bidder cascades and removes its associated Documents."""
    bidder = Bidder(
        company_name="Solar Grid Solutions",
        status=BidderStatus.ACTIVE,
    )
    db_session.add(bidder)
    db_session.commit()

    doc = Document(
        bidder_id=bidder.id,
        original_filename="gst_reg.pdf",
        storage_path="storage/gst_reg.pdf",
        document_type=DocumentType.GST,
    )
    db_session.add(doc)
    db_session.commit()
    doc_id = doc.id

    # Delete Bidder
    db_session.delete(bidder)
    db_session.commit()

    # Document should be deleted
    assert db_session.get(Document, doc_id) is None


def test_crud_document_with_phase06_fields(db_session: Session):
    """Test CRUD functions create_document_metadata with processing and extraction fields."""
    tender = Tender(
        tender_number="GEM/2026/B/CRUD_TEST",
        title="CRUD Test Tender",
        organization="ISRO",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()

    doc = crud_document.create_metadata(
        db=db_session,
        original_filename="mii_declaration.pdf",
        storage_path="storage/mii_declaration.pdf",
        document_type=DocumentType.MII_DECLARATION,
        mime_type="application/pdf",
        file_size=204800,
        tender_id=tender.id,
        status=DocumentStatus.ACTIVE,
        processing_status=ProcessingStatus.PROCESSING,
        processing_error=None,
        extracted_data={"local_content_percentage": 65.0},
    )

    assert doc.id is not None
    assert doc.document_type == DocumentType.MII_DECLARATION
    assert doc.processing_status == ProcessingStatus.PROCESSING
    assert doc.extracted_data == {"local_content_percentage": 65.0}


def test_document_backward_compatibility_properties():
    """Test file_name and file_path backward compatibility getters, setters, and kwargs."""
    doc = Document(
        file_name="legacy_name.pdf",
        file_path="legacy/path/legacy_name.pdf",
        document_type=DocumentType.PAN,
    )
    assert doc.original_filename == "legacy_name.pdf"
    assert doc.storage_path == "legacy/path/legacy_name.pdf"
    assert doc.file_name == "legacy_name.pdf"
    assert doc.file_path == "legacy/path/legacy_name.pdf"

    # Property setters
    doc.file_name = "updated_name.pdf"
    doc.file_path = "updated/path.pdf"
    assert doc.original_filename == "updated_name.pdf"
    assert doc.storage_path == "updated/path.pdf"
