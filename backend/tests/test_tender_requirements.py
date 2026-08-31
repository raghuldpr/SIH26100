import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.crud_tender_requirement import crud_tender_requirement
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.enums import RequirementType, TenderStatus
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.schemas.tender_requirement import (
    TenderRequirementCreate,
    TenderRequirementResponse,
    TenderRequirementUpdate,
)


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure all tables are created before running tests."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    """Yield a database session and clean up after each test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_tender(db_session: Session) -> Tender:
    """Creates a sample tender record for testing requirements."""
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
        title="Procurement of High Performance Computing Cluster",
        description="RFP for HPC infrastructure and maintenance",
        organization="Department of Science and Technology",
        department="Information Technology",
        category="Hardware",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()
    db_session.refresh(tender)
    return tender


def test_tender_requirement_model_creation(db_session: Session, sample_tender: Tender):
    """Verify TenderRequirement model persists all required attributes and timestamps."""
    req_id = uuid.uuid4()
    req = TenderRequirement(
        id=req_id,
        tender_id=sample_tender.id,
        requirement_type=RequirementType.FINANCIAL.value,
        rule="MINIMUM_ANNUAL_TURNOVER",
        description="Bidder must have minimum average annual turnover of INR 1.5 Cr over last 3 years.",
        parameters={
            "minimum": 15000000,
            "currency": "INR",
            "period": 3,
            "period_unit": "YEARS",
        },
        mandatory=True,
        confidence=0.96,
        source_page=4,
        source_section="Section 3.1: Minimum Eligibility Criteria",
        source_text="The minimum average annual financial turnover of the bidder during the last three years shall not be less than Rs. 1.50 Crore.",
    )
    db_session.add(req)
    db_session.commit()

    fetched = db_session.scalars(
        select(TenderRequirement).where(TenderRequirement.id == req_id)
    ).first()

    assert fetched is not None
    assert fetched.tender_id == sample_tender.id
    assert fetched.requirement_type == "FINANCIAL"
    assert fetched.rule == "MINIMUM_ANNUAL_TURNOVER"
    assert fetched.parameters["minimum"] == 15000000
    assert fetched.parameters["currency"] == "INR"
    assert fetched.mandatory is True
    assert fetched.confidence == 0.96
    assert fetched.source_page == 4
    assert fetched.source_section == "Section 3.1: Minimum Eligibility Criteria"
    assert "1.50 Crore" in fetched.source_text
    assert isinstance(fetched.created_at, datetime)
    assert isinstance(fetched.updated_at, datetime)


def test_tender_relationship_and_cascade_delete(db_session: Session, sample_tender: Tender):
    """Verify bidirectional relationship between Tender and TenderRequirement and cascade deletion."""
    req1 = TenderRequirement(
        id=uuid.uuid4(),
        requirement_type=RequirementType.EXPERIENCE.value,
        rule="PAST_EXPERIENCE",
        description="3 years of experience in similar work",
        parameters={"years": 3},
        mandatory=True,
        confidence=0.92,
    )
    req2 = TenderRequirement(
        id=uuid.uuid4(),
        requirement_type=RequirementType.OEM.value,
        rule="OEM_AUTHORIZATION",
        description="Valid OEM Authorization certificate required",
        parameters={"required": True},
        mandatory=True,
        confidence=0.98,
    )

    sample_tender.requirements.append(req1)
    sample_tender.requirements.append(req2)
    db_session.commit()
    db_session.refresh(sample_tender)

    assert len(sample_tender.requirements) == 2
    assert req1.tender.id == sample_tender.id
    assert req2.tender.id == sample_tender.id

    # Test cascade delete: deleting tender should delete attached requirements
    tender_id = sample_tender.id
    db_session.delete(sample_tender)
    db_session.commit()

    remaining_reqs = db_session.scalars(
        select(TenderRequirement).where(TenderRequirement.tender_id == tender_id)
    ).all()
    assert len(remaining_reqs) == 0


def test_jsonb_parameter_flexibility(db_session: Session, sample_tender: Tender):
    """Verify flexible JSON parameter payloads including exemption mappings."""
    # Exemption requirement
    exemption_req = TenderRequirement(
        id=uuid.uuid4(),
        tender_id=sample_tender.id,
        requirement_type=RequirementType.EXEMPTION.value,
        rule="STARTUP_TURNOVER_EXEMPTION",
        description="Startups recognized by DPIIT are exempted from turnover criteria.",
        parameters={
            "applies_to": ["STARTUP"],
            "target_rule": "AVERAGE_TURNOVER",
            "exemption_type": "FULL",
            "conditions": ["DPIIT_CERTIFICATE_MANDATORY"],
        },
        mandatory=False,
        confidence=0.95,
        source_page=6,
        source_section="Section 4: Policy Exemptions",
        source_text="Relaxation of Norms for Startups and MSEs: Prior turnover and prior experience criteria are relaxed.",
    )
    db_session.add(exemption_req)
    db_session.commit()

    fetched = db_session.scalars(
        select(TenderRequirement).where(TenderRequirement.id == exemption_req.id)
    ).first()

    assert fetched is not None
    assert fetched.parameters["applies_to"] == ["STARTUP"]
    assert fetched.parameters["target_rule"] == "AVERAGE_TURNOVER"
    assert fetched.parameters["conditions"] == ["DPIIT_CERTIFICATE_MANDATORY"]


def test_all_standard_requirement_types(db_session: Session, sample_tender: Tender):
    """Verify that all 11 standard requirement types can be created and queried."""
    expected_types = [
        "FINANCIAL",
        "EXPERIENCE",
        "TECHNICAL",
        "STATUTORY",
        "DOCUMENT",
        "OEM",
        "MII",
        "MSE",
        "STARTUP",
        "EXEMPTION",
        "OTHER",
    ]

    for req_type in expected_types:
        req = TenderRequirement(
            id=uuid.uuid4(),
            tender_id=sample_tender.id,
            requirement_type=req_type,
            rule=f"RULE_{req_type}",
            description=f"Description for {req_type}",
            parameters={"type": req_type},
            mandatory=True,
            confidence=0.90,
        )
        db_session.add(req)

    db_session.commit()

    persisted = db_session.scalars(
        select(TenderRequirement).where(TenderRequirement.tender_id == sample_tender.id)
    ).all()
    persisted_types = {r.requirement_type for r in persisted}

    assert len(persisted) == len(expected_types)
    for expected in expected_types:
        assert expected in persisted_types


def test_extensible_custom_requirement_types(db_session: Session, sample_tender: Tender):
    """Verify that future custom requirement types can be stored without database rejection."""
    custom_type = "CYBERSECURITY_AUDIT"
    req = TenderRequirement(
        id=uuid.uuid4(),
        tender_id=sample_tender.id,
        requirement_type=custom_type,
        rule="CERT_IN_EMPANELED_AUDIT",
        description="Bidder system must have passed CERT-In empaneled security audit within last 6 months.",
        parameters={"audit_validity_months": 6},
        mandatory=True,
        confidence=0.94,
    )
    db_session.add(req)
    db_session.commit()

    fetched = db_session.scalars(
        select(TenderRequirement).where(TenderRequirement.requirement_type == custom_type)
    ).first()
    assert fetched is not None
    assert fetched.requirement_type == custom_type


def test_pydantic_schema_validation():
    """Verify validation and normalization behavior of Pydantic schemas."""
    # 1. Valid instantiation
    schema = TenderRequirementCreate(
        requirement_type=RequirementType.MII,
        rule="LOCAL_CONTENT_MINIMUM",
        description="Make in India minimum 50% local content requirement.",
        parameters={"minimum_percentage": 50},
        confidence=0.95,
        source_page=2,
    )
    assert schema.requirement_type == "MII"
    assert schema.confidence == 0.95

    # 2. Case normalization from raw string
    schema_str = TenderRequirementCreate(
        requirement_type="financial",
        rule="annual_turnover",
        description="Min turnover",
    )
    assert schema_str.requirement_type == "FINANCIAL"
    assert schema_str.rule == "annual_turnover"

    # 3. Invalid confidence (> 1.0)
    with pytest.raises(ValidationError):
        TenderRequirementCreate(
            requirement_type="TECHNICAL",
            rule="TECH_SPEC",
            description="Specs",
            confidence=1.5,
        )

    # 4. Invalid confidence (< 0.0)
    with pytest.raises(ValidationError):
        TenderRequirementCreate(
            requirement_type="TECHNICAL",
            rule="TECH_SPEC",
            description="Specs",
            confidence=-0.1,
        )

    # 5. Invalid empty rule
    with pytest.raises(ValidationError):
        TenderRequirementCreate(
            requirement_type="TECHNICAL",
            rule="   ",
            description="Specs",
        )

    # 6. Response serialization
    res = TenderRequirementResponse(
        id=uuid.uuid4(),
        tender_id=uuid.uuid4(),
        requirement_type="OEM",
        rule="OEM_AUTH",
        description="OEM authorization mandatory",
        parameters={"required": True},
        mandatory=True,
        confidence=0.99,
        source_page=5,
        source_section="Eligibility",
        source_text="OEM authorization required",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert res.requirement_type == "OEM"
    assert res.confidence == 0.99


def test_crud_operations(db_session: Session, sample_tender: Tender):
    """Verify comprehensive CRUD functionality via CRUDTenderRequirement."""
    # 1. Single create
    created = crud_tender_requirement.create(
        db=db_session,
        tender_id=sample_tender.id,
        requirement_in=TenderRequirementCreate(
            requirement_type="FINANCIAL",
            rule="ANNUAL_TURNOVER",
            description="Average turnover of INR 2 Crores",
            parameters={"minimum": 20000000},
            confidence=0.95,
        ),
    )
    assert created.id is not None
    assert created.tender_id == sample_tender.id
    assert created.rule == "ANNUAL_TURNOVER"

    # 2. Get by ID
    fetched = crud_tender_requirement.get_by_id(db=db_session, requirement_id=created.id)
    assert fetched is not None
    assert fetched.id == created.id

    # 3. Bulk create
    bulk_list = [
        TenderRequirementCreate(
            requirement_type="EXPERIENCE",
            rule="SIMILAR_WORK",
            description="Completed at least 1 similar work",
            parameters={"min_orders": 1},
        ),
        TenderRequirementCreate(
            requirement_type="DOCUMENT",
            rule="GST_REGISTRATION",
            description="Copy of valid GST registration certificate",
            mandatory=True,
        ),
        TenderRequirementCreate(
            requirement_type="EXEMPTION",
            rule="MSE_EMD_EXEMPTION",
            description="MSEs exempted from EMD deposit",
            mandatory=False,
        ),
    ]
    bulk_created = crud_tender_requirement.bulk_create(
        db=db_session,
        tender_id=sample_tender.id,
        requirements_in=bulk_list,
    )
    assert len(bulk_created) == 3

    # 4. Get by tender (all)
    all_reqs = crud_tender_requirement.get_by_tender(db=db_session, tender_id=sample_tender.id)
    assert len(all_reqs) == 4  # 1 initial + 3 bulk

    # 5. Filter by requirement_type
    fin_reqs = crud_tender_requirement.get_by_tender(
        db=db_session, tender_id=sample_tender.id, requirement_type="FINANCIAL"
    )
    assert len(fin_reqs) == 1
    assert fin_reqs[0].rule == "ANNUAL_TURNOVER"

    # 6. Filter by mandatory_only
    mandatory_reqs = crud_tender_requirement.get_by_tender(
        db=db_session, tender_id=sample_tender.id, mandatory_only=True
    )
    assert len(mandatory_reqs) == 3  # 3 mandatory, 1 exemption is non-mandatory

    # 7. Update
    updated = crud_tender_requirement.update(
        db=db_session,
        db_obj=created,
        requirement_in=TenderRequirementUpdate(
            description="Updated description: turnover requirement revised to INR 2.5 Cr",
            parameters={"minimum": 25000000},
            confidence=0.99,
        ),
    )
    assert updated.parameters["minimum"] == 25000000
    assert updated.confidence == 0.99
    assert "revised to INR 2.5 Cr" in updated.description

    # 8. Delete single
    deleted = crud_tender_requirement.delete(db=db_session, requirement_id=created.id)
    assert deleted is True
    assert crud_tender_requirement.get_by_id(db=db_session, requirement_id=created.id) is None

    # 9. Delete by tender
    deleted_count = crud_tender_requirement.delete_by_tender(
        db=db_session, tender_id=sample_tender.id
    )
    assert deleted_count == 3
    remaining = crud_tender_requirement.get_by_tender(db=db_session, tender_id=sample_tender.id)
    assert len(remaining) == 0
