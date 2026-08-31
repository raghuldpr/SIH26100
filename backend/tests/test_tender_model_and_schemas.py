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
    """Verify all procurement lifecycle states are defined, including OPEN and CANCELLED."""
    assert TenderStatus.DRAFT == "DRAFT"
    assert TenderStatus.OPEN == "OPEN"
    assert TenderStatus.PUBLISHED == "PUBLISHED"
    assert TenderStatus.EVALUATING == "EVALUATING"
    assert TenderStatus.CLOSED == "CLOSED"
    assert TenderStatus.CANCELLED == "CANCELLED"
    assert TenderStatus.ARCHIVED == "ARCHIVED"


def test_tender_table_metadata_indexes_and_constraints():
    """Verify Tender table definition has required indexes, uniqueness, and check constraint."""
    table = Tender.__table__

    # 1. Table Name & Primary Key
    assert table.name == "tenders"
    assert "id" in table.c
    assert table.c.id.primary_key is True

    # 2. Check Required Columns
    required_cols = [
        "tender_number",
        "title",
        "organization",
        "department",
        "category",
        "bid_start_date",
        "bid_end_date",
        "status",
        "created_at",
        "updated_at",
    ]
    for col in required_cols:
        assert col in table.c, f"Missing column: {col}"
        assert table.c[col].nullable is False, f"Column {col} should be non-nullable"

    # 3. Check Unique Constraint on tender_number
    assert table.c.tender_number.unique is True

    # 4. Check Indexes (tender_number, status, department, category, bid_end_date)
    index_cols = {col.name for idx in table.indexes for col in idx.columns}
    assert "tender_number" in index_cols
    assert "status" in index_cols
    assert "department" in index_cols
    assert "category" in index_cols
    assert "bid_end_date" in index_cols

    # 5. Check Bid Dates Database Constraint
    check_constraints = [c for c in table.constraints if c.__class__.__name__ == "CheckConstraint"]
    assert any("bid_end_date >= bid_start_date" in str(c.sqltext) for c in check_constraints)


def test_tender_model_open_and_cancelled_statuses(db_session):
    """Verify Tender model can be persisted with OPEN and CANCELLED statuses."""
    db, created_tenders, _ = db_session
    now = datetime.now(timezone.utc)

    # Test OPEN status
    tender_open = Tender(
        id=uuid.uuid4(),
        tender_number=f"GEM/2026/OPEN/{uuid.uuid4().hex[:6].upper()}",
        title="Open Bidding Tender",
        organization="Ministry of Power",
        department="Renewable Energy",
        category="Solar / Wind",
        bid_start_date=now,
        bid_end_date=now + timedelta(days=30),
        status=TenderStatus.OPEN,
    )
    db.add(tender_open)
    db.commit()
    db.refresh(tender_open)
    created_tenders.append(tender_open.id)

    assert tender_open.status == TenderStatus.OPEN

    # Test CANCELLED status
    tender_cancelled = Tender(
        id=uuid.uuid4(),
        tender_number=f"GEM/2026/CAN/{uuid.uuid4().hex[:6].upper()}",
        title="Cancelled Bidding Tender",
        organization="Ministry of Coal",
        department="Mining Ops",
        category="Machinery",
        bid_start_date=now,
        bid_end_date=now + timedelta(days=10),
        status=TenderStatus.CANCELLED,
    )
    db.add(tender_cancelled)
    db.commit()
    db.refresh(tender_cancelled)
    created_tenders.append(tender_cancelled.id)

    assert tender_cancelled.status == TenderStatus.CANCELLED


def test_tender_create_schema_empty_strings_rejected():
    """Verify TenderCreate schema rejects empty or whitespace-only strings."""
    now = datetime.now(timezone.utc)
    base_kwargs = {
        "tender_number": "GEM/2026/VALID/1",
        "title": "Valid Title",
        "organization": "Valid Org",
        "department": "Valid Dept",
        "category": "Valid Cat",
        "bid_start_date": now,
        "bid_end_date": now + timedelta(days=5),
    }

    # Empty tender_number
    with pytest.raises(ValidationError):
        TenderCreate(**{**base_kwargs, "tender_number": "   "})

    # Empty title
    with pytest.raises(ValidationError):
        TenderCreate(**{**base_kwargs, "title": ""})

    # Empty department
    with pytest.raises(ValidationError):
        TenderCreate(**{**base_kwargs, "department": "  "})

    # Empty category
    with pytest.raises(ValidationError):
        TenderCreate(**{**base_kwargs, "category": ""})


def test_tender_update_schema_allows_updating_all_fields():
    """Verify TenderUpdate accepts updates for all specified tender attributes."""
    now = datetime.now(timezone.utc)
    update = TenderUpdate(
        tender_number="GEM/2026/UPDATED/99",
        title="Updated Title RFP",
        organization="Updated Organization",
        department="Updated Dept",
        category="Updated Cat",
        bid_start_date=now,
        bid_end_date=now + timedelta(days=15),
        status=TenderStatus.OPEN,
    )
    data = update.model_dump(exclude_unset=True)
    assert data["tender_number"] == "GEM/2026/UPDATED/99"
    assert data["title"] == "Updated Title RFP"
    assert data["status"] == TenderStatus.OPEN


def test_tender_service_crud_lifecycle(db_session):
    """Verify create_tender, get_tender_by_id, get_tender_by_number, update_tender, list_tenders, archive_tender."""
    from app.core.exceptions import BadRequestException
    from app.services.tender_service import (
        archive_tender,
        create_tender,
        get_tender_by_id,
        get_tender_by_number,
        list_tenders,
        update_tender,
    )

    db, created_tenders, _ = db_session
    now = datetime.now(timezone.utc)
    t_num = f"GEM/2026/SVC/{uuid.uuid4().hex[:8].upper()}"

    # 1. Create tender
    create_dto = TenderCreate(
        tender_number=t_num,
        title="Automated Test Tender via Service",
        organization="Ministry of Defence",
        department="Naval Systems",
        category="Hardware",
        bid_start_date=now,
        bid_end_date=now + timedelta(days=20),
        status=TenderStatus.DRAFT,
    )
    tender = create_tender(db, tender_in=create_dto)
    created_tenders.append(tender.id)

    assert tender.id is not None
    assert tender.tender_number == t_num
    assert tender.status == TenderStatus.DRAFT

    # 2. Duplicate tender_number rejected
    with pytest.raises(BadRequestException, match="already exists"):
        create_tender(db, tender_in=create_dto)

    # 3. Retrieve by ID
    fetched_by_id = get_tender_by_id(db, tender_id=tender.id)
    assert fetched_by_id is not None
    assert fetched_by_id.id == tender.id

    # 4. Retrieve by number
    fetched_by_num = get_tender_by_number(db, tender_number=t_num)
    assert fetched_by_num is not None
    assert fetched_by_num.tender_number == t_num

    # 5. List with filters and pagination
    items, total = list_tenders(
        db,
        department="Naval Systems",
        category="Hardware",
        status=TenderStatus.DRAFT,
    )
    assert total >= 1
    assert any(t.id == tender.id for t in items)

    # 6. Update tender
    update_dto = TenderUpdate(
        title="Updated Naval Procurement RFP",
        department="Naval Headquarters",
        status=TenderStatus.OPEN,
    )
    updated = update_tender(db, db_tender=tender, tender_update=update_dto)
    assert updated.title == "Updated Naval Procurement RFP"
    assert updated.department == "Naval Headquarters"
    assert updated.status == TenderStatus.OPEN
    # Unchanged fields preserved
    assert updated.organization == "Ministry of Defence"

    # 7. Soft Archive tender (non-destructive)
    archived = archive_tender(db, db_tender=tender)
    assert archived.status == TenderStatus.ARCHIVED

    # Verify record still exists in DB
    persisted = get_tender_by_id(db, tender_id=tender.id)
    assert persisted is not None
    assert persisted.status == TenderStatus.ARCHIVED


