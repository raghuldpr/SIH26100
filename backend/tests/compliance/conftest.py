"""
Phase 09 — Compliance Rule Engine
tests/compliance/conftest.py: Shared pytest fixtures.

All fixtures are function-scoped (default) so each test gets a fresh instance.
They use uuid4 seeded to known values for reproducibility in assertion messages.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.compliance.enums import EvidenceSource, Operator, RuleType
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.models.enums import RequirementType

# Fixed UUIDs for deterministic test assertions
TENDER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
BIDDER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
REQUIREMENT_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
EVIDENCE_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")


# ---------------------------------------------------------------------------
# Requirement factories
# ---------------------------------------------------------------------------

@pytest.fixture
def turnover_requirement_gte() -> Requirement:
    """annual_turnover >= ₹15,00,000 (1_500_000 INR)."""
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.FINANCIAL,
        field="annual_turnover",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.GREATER_THAN_OR_EQUAL,
            required_value=Decimal("1500000"),
            unit="INR",
        ),
    )


@pytest.fixture
def turnover_requirement_minimum() -> Requirement:
    """annual_turnover MINIMUM ₹15,00,000 — tests MINIMUM alias."""
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.FINANCIAL,
        field="annual_turnover",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MINIMUM,
            required_value=Decimal("1500000"),
            unit="INR",
        ),
    )


@pytest.fixture
def turnover_requirement_maximum() -> Requirement:
    """bid_amount MAXIMUM ₹50,00,000."""
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.FINANCIAL,
        field="bid_amount",
        rule_type=RuleType.NUMERIC,
        rule_definition=RuleDefinition(
            operator=Operator.MAXIMUM,
            required_value=Decimal("5000000"),
            unit="INR",
        ),
    )


@pytest.fixture
def gst_boolean_requirement() -> Requirement:
    """gst_registered == True."""
    return Requirement(
        requirement_id=REQUIREMENT_ID,
        tender_id=TENDER_ID,
        category=RequirementType.STATUTORY,
        field="gst_registered",
        rule_type=RuleType.BOOLEAN,
        rule_definition=RuleDefinition(
            operator=Operator.EQUAL,
            required_value=True,
        ),
    )


# ---------------------------------------------------------------------------
# Evidence factories
# ---------------------------------------------------------------------------

def make_evidence(field: str, value, confidence: float = 1.0) -> BidderEvidence:
    """Helper to create BidderEvidence instances inline in tests."""
    return BidderEvidence(
        evidence_id=EVIDENCE_ID,
        bidder_id=BIDDER_ID,
        field=field,
        value=value,
        source_document="test_doc.pdf",
        source=EvidenceSource.UPLOADED_DOCUMENT,
        confidence=confidence,
    )
