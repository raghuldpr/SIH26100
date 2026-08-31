from datetime import datetime, timedelta, timezone
import uuid
import pytest
from pydantic import ValidationError

from app.db.session import SessionLocal
from app.models.enums import TenderStatus, UserRole
from app.models.tender import Tender
from app.models.user import User
from app.schemas.tender import TenderCreate, TenderResponse, TenderUpdate


@pytest.fixture
def db_session():
    """Yield a database session and clean up created test records."""
    db = SessionLocal()
    created_tender_ids = []
    created_user_ids = []
    yield db, created_tender_ids, created_user_ids

    for tid in created_tender_ids:
        try:
            tender = db.get(Tender, tid)
            if tender:
                db.delete(tender)
                db.commit()
        except Exception:
            db.rollback()

    for uid in created_user_ids:
        try:
            user = db.get(User, uid)
            if user:
                db.delete(user)
                db.commit()
        except Exception:
            db.rollback()

    db.close()


def test_tender_model_fields_and_relationships(db_session):
    """Verify Tender SQLAlchemy model fields, default values, and User relationship."""
    db, created_tenders, created_users = db_session

    # 1. Create procurement officer user
    officer = User(
        id=uuid.uuid4(),
        name="Officer Rajesh Kumar",
        email=f"rajesh_{uuid.uuid4().hex[:6]}@gem.gov.in",
        password_hash="hashed_pw_test",
        role=UserRole.PROCUREMENT_OFFICER,
    )
    db.add(officer)
    db.commit()
    db.refresh(officer)
    created_users.append(officer.id)

    # 2. Create Tender record
    now = datetime.now(timezone.utc)
    start_date = now + timedelta(days=1)
    end_date = now + timedelta(days=21)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
        title="Procurement of IT Networking Hardware & Firewalls",
        organization="Ministry of Electronics and Information Technology",
        department="NIC Division",
        category="Hardware / Networking",
        description="Comprehensive RFP for supply and commissioning of 10Gbps switches.",
        bid_start_date=start_date,
        bid_end_date=end_date,
        status=TenderStatus.DRAFT,
        created_by=officer.id,
    )
    db.add(tender)
    db.commit()
    db.refresh(tender)
    created_tenders.append(tender.id)

    # 3. Verify fields
    assert tender.id is not None
    assert tender.tender_number.startswith("GEM/2026/B/")
    assert tender.organization == "Ministry of Electronics and Information Technology"
    assert tender.department == "NIC Division"
    assert tender.category == "Hardware / Networking"
    assert tender.status == TenderStatus.DRAFT
    assert tender.created_by == officer.id
    assert tender.created_at is not None
    assert tender.updated_at is not None

    # 4. Verify Relationship
    assert tender.creator is not None
    assert tender.creator.id == officer.id
    assert tender.creator.name == "Officer Rajesh Kumar"
    assert tender in officer.created_tenders


def test_tender_create_schema_success():
    """Verify TenderCreate schema validates correctly with valid attributes."""
    now = datetime.now(timezone.utc)
    start_date = now + timedelta(days=2)
    end_date = now + timedelta(days=30)

    schema = TenderCreate(
        tender_number="GEM/2026/B/10001",
        title="Procurement of High-End Workstations",
        organization="Defence Research & Development Organisation",
        department="Aeronautical Systems",
        category="Computers & Peripherals",
        bid_start_date=start_date,
        bid_end_date=end_date,
        status=TenderStatus.DRAFT,
    )

    data = schema.model_dump()
    assert data["tender_number"] == "GEM/2026/B/10001"
    assert data["organization"] == "Defence Research & Development Organisation"
    assert data["bid_start_date"] == start_date
    assert data["bid_end_date"] == end_date
    assert data["status"] == TenderStatus.DRAFT


def test_tender_bid_dates_validation_rejects_earlier_end_date():
    """Verify TenderCreate rejects bid_end_date earlier than bid_start_date."""
    now = datetime.now(timezone.utc)
    start_date = now + timedelta(days=10)
    invalid_end_date = now + timedelta(days=5)  # 5 days before start_date

    with pytest.raises(ValidationError, match="bid_end_date must not be earlier than bid_start_date"):
        TenderCreate(
            tender_number="GEM/2026/B/10002",
            title="Procurement with Invalid Dates",
            organization="Ministry of Railways",
            bid_start_date=start_date,
            bid_end_date=invalid_end_date,
        )


def test_tender_update_schema_date_validation():
    """Verify TenderUpdate schema validates date ranges properly."""
    now = datetime.now(timezone.utc)
    valid_start = now + timedelta(days=1)
    valid_end = now + timedelta(days=15)
    invalid_end = now - timedelta(days=1)

    # Valid update
    update_valid = TenderUpdate(
        bid_start_date=valid_start,
        bid_end_date=valid_end,
        status=TenderStatus.PUBLISHED,
    )
    assert update_valid.status == TenderStatus.PUBLISHED

    # Invalid update with end_date < start_date
    with pytest.raises(ValidationError, match="bid_end_date must not be earlier than bid_start_date"):
        TenderUpdate(
            bid_start_date=valid_start,
            bid_end_date=invalid_end,
        )


def test_tender_response_schema_serialization():
    """Verify TenderResponse serializes ORM models cleanly without database internal details."""
    tender_id = uuid.uuid4()
    officer_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    tender_model = Tender(
        id=tender_id,
        tender_number="GEM/2026/B/554433",
        title="Supply of Cloud Servers",
        organization="National Informatics Centre",
        department="Cloud Operations",
        category="Cloud Services",
        description="Public Cloud Infrastructure RFP",
        bid_start_date=now,
        bid_end_date=now + timedelta(days=14),
        status=TenderStatus.PUBLISHED,
        created_by=officer_id,
        created_at=now,
        updated_at=now,
    )

    response_dto = TenderResponse.model_validate(tender_model)
    dumped = response_dto.model_dump()

    assert dumped["id"] == tender_id
    assert dumped["tender_number"] == "GEM/2026/B/554433"
    assert dumped["title"] == "Supply of Cloud Servers"
    assert dumped["organization"] == "National Informatics Centre"
    assert dumped["department"] == "Cloud Operations"
    assert dumped["category"] == "Cloud Services"
    assert dumped["status"] == TenderStatus.PUBLISHED
    assert dumped["created_by"] == officer_id


def test_tender_statuses_supported():
    """Verify all procurement lifecycle states are defined."""
    assert TenderStatus.DRAFT == "DRAFT"
    assert TenderStatus.PUBLISHED == "PUBLISHED"
    assert TenderStatus.EVALUATING == "EVALUATING"
    assert TenderStatus.CLOSED == "CLOSED"
    assert TenderStatus.ARCHIVED == "ARCHIVED"
