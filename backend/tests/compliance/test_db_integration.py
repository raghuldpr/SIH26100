"""
Phase 09 — Compliance Rule Engine
tests/compliance/test_db_integration.py: PostgreSQL / SQLAlchemy database integration tests.

Verifies:
1. Requirement persistence & retrieval (JSONB rule definition, mandatory, category)
2. Evidence persistence & retrieval (JSONB value, confidence, bidder association)
3. Compliance result persistence & historical preservation (never overwrites silently)
4. Relationships (tender -> requirements, bidder -> evidence & results, requirement -> results)
5. ComplianceService end-to-end evaluation (single requirement, batch, and exemptions)
6. REST API endpoints integration via TestClient
"""
from __future__ import annotations

from decimal import Decimal
import uuid
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.bidder import Bidder
from app.models.compliance import (
    BidderEvidenceModel,
    ComplianceRequirement,
    ComplianceResultModel,
)
from app.models.enums import BidderStatus, RequirementType, TenderStatus
from app.models.tender import Tender
from app.schemas.compliance import (
    BidderEvidenceCreate,
    RequirementCreate,
)
from app.services.compliance_service import compliance_service

client = TestClient(app)
S = ComplianceStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide a transactional database session rolled back after test."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()



@pytest.fixture
def sample_tender(db_session: Session) -> Tender:
    """Create a persistent tender record."""
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"TND/2026/{uuid.uuid4().hex[:8].upper()}",
        title="Solar Power Plant Installation Tender",
        description="Turnkey EPC tender for 50MW Solar Installation",
        organization="Ministry of New and Renewable Energy",
        department="Solar Energy Division",
        category="Renewable Energy",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()
    db_session.refresh(tender)
    return tender


@pytest.fixture
def sample_bidder(db_session: Session) -> Bidder:
    """Create a persistent bidder record."""
    bidder = Bidder(
        id=uuid.uuid4(),
        company_name=f"SunTech Solutions Ltd {uuid.uuid4().hex[:6]}",
        registration_number=f"REG-{uuid.uuid4().hex[:8].upper()}",
        gst_number="27AAACS1234A1Z1",
        pan_number="AAACS1234A",
        status=BidderStatus.ACTIVE,
    )
    db_session.add(bidder)
    db_session.commit()
    db_session.refresh(bidder)
    return bidder


# ===========================================================================
# 1. Requirement Persistence & Retrieval
# ===========================================================================

class TestRequirementPersistence:

    def test_create_and_retrieve_requirement(self, db_session: Session, sample_tender: Tender):
        req_in = RequirementCreate(
            tender_id=sample_tender.id,
            category="FINANCIAL",
            field="annual_turnover",
            rule_type=RuleType.NUMERIC,
            rule_definition={
                "operator": "MINIMUM",
                "required_value": "1500000",
                "unit": "INR",
            },
            mandatory=True,
            description="Minimum turnover >= 15L",
        )

        db_req = compliance_service.create_requirement(db_session, req_in)
        assert db_req.id is not None
        assert db_req.requirement_id is not None
        assert db_req.tender_id == sample_tender.id
        assert db_req.category == "FINANCIAL"
        assert db_req.field == "annual_turnover"
        assert db_req.rule_type == "NUMERIC"
        assert db_req.rule_definition["operator"] == "MINIMUM"
        assert db_req.mandatory is True

        # Retrieve by ID
        fetched = compliance_service.get_requirement(db_session, db_req.id)
        assert fetched is not None
        assert fetched.id == db_req.id
        assert fetched.rule_definition["required_value"] == "1500000"

    def test_list_requirements_by_tender(self, db_session: Session, sample_tender: Tender):
        req1 = compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "FINANCIAL",
                "field": "annual_turnover",
                "rule_type": "NUMERIC",
                "rule_definition": {"operator": "MINIMUM", "required_value": 1500000},
            },
        )
        req2 = compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "STATUTORY",
                "field": "gst_registered",
                "rule_type": "BOOLEAN",
                "rule_definition": {"operator": "EQUAL", "required_value": True},
            },
        )

        reqs = compliance_service.list_requirements_by_tender(db_session, sample_tender.id)
        assert len(reqs) >= 2
        req_ids = [r.id for r in reqs]
        assert req1.id in req_ids
        assert req2.id in req_ids


# ===========================================================================
# 2. Bidder Evidence Persistence & Retrieval
# ===========================================================================

class TestEvidencePersistence:

    def test_save_and_retrieve_evidence(self, db_session: Session, sample_bidder: Bidder):
        ev_in = BidderEvidenceCreate(
            bidder_id=sample_bidder.id,
            field="annual_turnover",
            value="2100000",
            source_document="audited_balance_sheet_2025.pdf",
            confidence=0.98,
        )

        db_ev = compliance_service.save_bidder_evidence(db_session, ev_in)
        assert db_ev.id is not None
        assert db_ev.evidence_id is not None
        assert db_ev.bidder_id == sample_bidder.id
        assert db_ev.field == "annual_turnover"
        assert db_ev.value == "2100000"
        assert db_ev.source_document == "audited_balance_sheet_2025.pdf"
        assert db_ev.confidence == 0.98

        # Retrieve by bidder and field
        fetched = compliance_service.get_bidder_evidence(db_session, sample_bidder.id, "annual_turnover")
        assert fetched is not None
        assert fetched.id == db_ev.id

    def test_structured_jsonb_evidence_payload(self, db_session: Session, sample_bidder: Bidder):
        """Verify complex JSONB payloads (e.g. contracts list) persist cleanly."""
        contracts = [
            {"contract_id": "C-01", "years": 2, "category": "SOLAR"},
            {"contract_id": "C-02", "years": 3, "category": "SOLAR"},
        ]
        db_ev = compliance_service.save_bidder_evidence(
            db_session,
            {
                "bidder_id": sample_bidder.id,
                "field": "similar_work_experience",
                "value": contracts,
                "confidence": 1.0,
            },
        )
        assert len(db_ev.value) == 2
        assert db_ev.value[0]["contract_id"] == "C-01"


# ===========================================================================
# 3. Compliance Result Persistence & Historical Preservation
# ===========================================================================

class TestResultPersistenceAndAuditability:

    def test_result_persistence_and_no_silent_overwrite(
        self, db_session: Session, sample_tender: Tender, sample_bidder: Bidder
    ):
        """
        Preserve auditability:
        Re-evaluating a requirement creates a NEW row in compliance_results;
        historical rows are NEVER overwritten.
        """
        db_req = compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "FINANCIAL",
                "field": "annual_turnover",
                "rule_type": "NUMERIC",
                "rule_definition": {"operator": "MINIMUM", "required_value": 1500000, "unit": "INR"},
            },
        )

        # Initial evidence: 8L (FAIL)
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "annual_turnover", "value": 800000},
        )

        res1 = compliance_service.evaluate_requirement(db_session, db_req.id, sample_bidder.id)
        assert res1.status == "FAIL"
        assert res1.evaluated_at is not None

        # Bidder later submits updated evidence: 20L (PASS)
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "annual_turnover", "value": 2000000},
        )

        res2 = compliance_service.evaluate_requirement(db_session, db_req.id, sample_bidder.id)
        assert res2.status == "PASS"

        # Check that BOTH historical evaluations exist in the database!
        history = compliance_service.get_compliance_results(db_session, sample_bidder.id, db_req.id)
        assert len(history) == 2
        assert history[0].id != history[1].id
        statuses = [h.status for h in history]
        assert "PASS" in statuses
        assert "FAIL" in statuses


# ===========================================================================
# 4. Model Relationships
# ===========================================================================

class TestModelRelationships:

    def test_tender_requirements_relationship(
        self, db_session: Session, sample_tender: Tender
    ):
        compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "TECHNICAL",
                "field": "solar_panel_capacity",
                "rule_type": "NUMERIC",
                "rule_definition": {"operator": "MINIMUM", "required_value": 500},
            },
        )
        db_session.refresh(sample_tender)
        assert len(sample_tender.compliance_requirements) >= 1
        assert sample_tender.compliance_requirements[0].field == "solar_panel_capacity"

    def test_bidder_evidence_relationship(
        self, db_session: Session, sample_bidder: Bidder
    ):
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "iso_certified", "value": True},
        )
        db_session.refresh(sample_bidder)
        assert len(sample_bidder.evidence) >= 1
        assert sample_bidder.evidence[0].field == "iso_certified"


# ===========================================================================
# 5. ComplianceService End-to-End Evaluation Flow
# ===========================================================================

class TestComplianceServiceEndToEnd:

    def test_evaluate_bidder_full_tender(
        self, db_session: Session, sample_tender: Tender, sample_bidder: Bidder
    ):
        """Full tender evaluation: 3 requirements evaluated against bidder evidence."""
        # 1. Turnover >= 15L (Bidder: 20L -> PASS)
        compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "FINANCIAL",
                "field": "annual_turnover",
                "rule_type": "NUMERIC",
                "rule_definition": {"operator": "MINIMUM", "required_value": 1500000, "unit": "INR"},
            },
        )
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "annual_turnover", "value": 2000000},
        )

        # 2. GST registered == True (Bidder: True -> PASS)
        compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "STATUTORY",
                "field": "gst_registered",
                "rule_type": "BOOLEAN",
                "rule_definition": {"operator": "EQUAL", "required_value": True},
            },
        )
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "gst_registered", "value": True},
        )

        # 3. PAN document mandatory (Bidder: missing -> FAIL)
        compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "DOCUMENT",
                "field": "pan_document",
                "rule_type": "DOCUMENT_PRESENCE",
                "mandatory": True,
                "rule_definition": {"operator": "PRESENT", "required_value": "PAN"},
            },
        )

        # Run full evaluation
        results = compliance_service.evaluate_bidder_compliance(
            db_session, sample_tender.id, sample_bidder.id
        )
        assert len(results) == 3
        status_map = {r.requirement.field: r.status for r in results}
        assert status_map["annual_turnover"] == "PASS"
        assert status_map["gst_registered"] == "PASS"
        assert status_map["pan_document"] == "FAIL"

    def test_evaluate_with_startup_exemption(
        self, db_session: Session, sample_tender: Tender, sample_bidder: Bidder
    ):
        """Evaluating with supplied exemption rule."""
        db_req = compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "FINANCIAL",
                "field": "annual_turnover",
                "rule_type": "NUMERIC",
                "rule_definition": {
                    "operator": "MINIMUM",
                    "required_value": 1500000,
                    "extra": {"requirement_code": "MINIMUM_TURNOVER"},
                },
            },
        )

        # Bidder has insufficient turnover, but is a STARTUP
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "annual_turnover", "value": 100000},
        )
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "bidder_category", "value": "STARTUP"},
        )

        exemption = {
            "type": "EXEMPTION",
            "name": "STARTUP_WAIVER",
            "condition": {"field": "bidder_category", "operator": "EQUAL", "value": "STARTUP"},
            "exempts": ["MINIMUM_TURNOVER"],
        }

        result = compliance_service.evaluate_requirement(
            db_session, db_req.id, sample_bidder.id, exemptions=[exemption]
        )
        assert result.status == "EXEMPT"
        assert "STARTUP_WAIVER" in result.reason


# ===========================================================================
# 6. REST API Integration
# ===========================================================================

class TestComplianceAPIEndpoints:

    def test_api_create_requirement(self, sample_tender: Tender):
        response = client.post(
            "/api/v1/compliance/requirements",
            json={
                "tender_id": str(sample_tender.id),
                "category": "FINANCIAL",
                "field": "emd_amount",
                "rule_type": "NUMERIC",
                "rule_definition": {"operator": "MINIMUM", "required_value": 50000},
                "mandatory": True,
                "description": "EMD threshold",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["field"] == "emd_amount"
        assert data["rule_type"] == "NUMERIC"

    def test_api_record_evidence(self, sample_bidder: Bidder):
        response = client.post(
            "/api/v1/compliance/evidence",
            json={
                "bidder_id": str(sample_bidder.id),
                "field": "emd_amount",
                "value": 75000,
                "source_document": "emd_receipt.pdf",
                "confidence": 0.99,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["field"] == "emd_amount"
        assert data["confidence"] == 0.99

    def test_api_evaluate_single(
        self, db_session: Session, sample_tender: Tender, sample_bidder: Bidder
    ):
        req = compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "FINANCIAL",
                "field": "net_worth",
                "rule_type": "NUMERIC",
                "rule_definition": {"operator": "MINIMUM", "required_value": 1000000},
            },
        )
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "net_worth", "value": 2000000},
        )

        response = client.post(
            "/api/v1/compliance/evaluate",
            json={
                "requirement_id": str(req.id),
                "bidder_id": str(sample_bidder.id),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "PASS"
        assert "net worth" in data["reason"].lower()


    def test_api_get_audit_history(
        self, db_session: Session, sample_tender: Tender, sample_bidder: Bidder
    ):
        req = compliance_service.create_requirement(
            db_session,
            {
                "tender_id": sample_tender.id,
                "category": "FINANCIAL",
                "field": "turnover",
                "rule_type": "NUMERIC",
                "rule_definition": {"operator": "MINIMUM", "required_value": 1000},
            },
        )
        compliance_service.save_bidder_evidence(
            db_session,
            {"bidder_id": sample_bidder.id, "field": "turnover", "value": 5000},
        )
        compliance_service.evaluate_requirement(db_session, req.id, sample_bidder.id)

        response = client.get(f"/api/v1/compliance/results/bidder/{sample_bidder.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["bidder_id"] == str(sample_bidder.id)
