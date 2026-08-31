import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models import Bidder, Document, DocumentType, Tender, TenderStatus, User, UserRole


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for model testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_user_model(db_session: Session):
    """Test User creation, defaults, UUID primary key, and role enum."""
    user = User(
        name="Test Officer",
        email="officer@gem.gov.in",
        password_hash="hashed_secret_123",
        role=UserRole.BUYER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.name == "Test Officer"
    assert user.email == "officer@gem.gov.in"
    assert user.role == UserRole.BUYER
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)
    assert isinstance(user.updated_at, datetime)


def test_tender_model(db_session: Session):
    """Test Tender creation, unique tender_number, status, and timestamps."""
    tender = Tender(
        tender_number="GEM/2026/B/998877",
        title="Procurement of IT Infrastructure Hardware",
        description="Supply and installation of server racks and edge computing nodes.",
        organization="Ministry of Electronics and Information Technology",
        status=TenderStatus.PUBLISHED,
    )
    db_session.add(tender)
    db_session.commit()
    db_session.refresh(tender)

    assert isinstance(tender.id, uuid.UUID)
    assert tender.tender_number == "GEM/2026/B/998877"
    assert tender.status == TenderStatus.PUBLISHED
    assert tender.organization == "Ministry of Electronics and Information Technology"
    assert tender.created_at is not None
    assert tender.updated_at is not None


def test_bidder_model_and_relationship(db_session: Session):
    """Test Bidder creation linked to User via foreign key."""
    user = User(
        name="Vendor Admin",
        email="admin@techcorp.in",
        password_hash="securehash",
        role=UserRole.BIDDER,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    bidder = Bidder(
        user_id=user.id,
        organization_name="TechCorp Solutions Pvt Ltd",
        registration_number="GSTIN29ABCDE1234F1Z5",
    )
    db_session.add(bidder)
    db_session.commit()
    db_session.refresh(bidder)

    assert isinstance(bidder.id, uuid.UUID)
    assert bidder.user_id == user.id
    assert bidder.user.email == "admin@techcorp.in"
    assert user.bidders[0].organization_name == "TechCorp Solutions Pvt Ltd"


def test_document_model_and_relationships(db_session: Session):
    """Test Document creation linked to Tender and Bidder."""
    user = User(
        name="Bidder User",
        email="bidder@supplier.com",
        password_hash="pwdhash",
        role=UserRole.BIDDER,
    )
    db_session.add(user)
    db_session.commit()

    bidder = Bidder(
        user_id=user.id,
        organization_name="Supplier Alpha Ltd",
        registration_number="GSTIN07AAAAA0000A1Z5",
    )
    tender = Tender(
        tender_number="GEM/2026/B/112233",
        title="Server Equipment Supply",
        organization="NIC",
        status=TenderStatus.PUBLISHED,
    )
    db_session.add_all([bidder, tender])
    db_session.commit()

    # Document tied to tender and bidder
    doc = Document(
        tender_id=tender.id,
        bidder_id=bidder.id,
        file_name="technical_bid_proposal.pdf",
        document_type=DocumentType.TECHNICAL_BID,
        file_path="storage/tenders/112233/bids/tech_bid.pdf",
        mime_type="application/pdf",
        file_size=2048576,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    assert isinstance(doc.id, uuid.UUID)
    assert doc.tender_id == tender.id
    assert doc.bidder_id == bidder.id
    assert doc.document_type == DocumentType.TECHNICAL_BID
    assert doc.tender.tender_number == "GEM/2026/B/112233"
    assert doc.bidder.organization_name == "Supplier Alpha Ltd"
    assert len(tender.documents) == 1
    assert len(bidder.documents) == 1


def test_document_tender_notice_without_bidder(db_session: Session):
    """Test buyer-uploaded tender notice document where bidder_id is null."""
    tender = Tender(
        tender_number="GEM/2026/B/445566",
        title="Network Cabling RFP",
        organization="BSNL",
        status=TenderStatus.PUBLISHED,
    )
    db_session.add(tender)
    db_session.commit()

    doc = Document(
        tender_id=tender.id,
        bidder_id=None,
        file_name="rfp_specification.pdf",
        document_type=DocumentType.TENDER_NOTICE,
        file_path="storage/tenders/445566/rfp.pdf",
        mime_type="application/pdf",
        file_size=512000,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    assert doc.bidder_id is None
    assert doc.tender_id == tender.id
    assert doc.tender.title == "Network Cabling RFP"
