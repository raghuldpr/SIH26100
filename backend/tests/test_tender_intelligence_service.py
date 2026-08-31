import json
import uuid
from unittest.mock import MagicMock
import pytest
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.enums import RequirementType, TenderStatus
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.schemas.ai_gateway import (
    AIGatewayResponse,
    AIGatewayUsageMetadata,
    LLMClauseInterpretation,
)
from app.schemas.tender_clause import ClauseCandidate
from app.schemas.tender_requirement_normalizer import NormalizationStatus
from app.services.ai_gateway import AIGateway
from app.services.tender_intelligence_service import TenderIntelligenceService


@pytest.fixture(autouse=True)
def setup_database():
    """Ensure database tables exist for integration tests."""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    """Database session fixture."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_tender(db_session: Session) -> Tender:
    """Sample tender record for persistence verification."""
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"GEM/2026/B/{uuid.uuid4().hex[:8].upper()}",
        title="Procurement of Server Infrastructure",
        description="RFP for Data Center Infrastructure",
        organization="Ministry of Electronics and IT",
        department="NIC",
        category="Hardware",
        status=TenderStatus.OPEN,
    )
    db_session.add(tender)
    db_session.commit()
    db_session.refresh(tender)
    return tender


def create_ai_response(interpretation_dict: dict, success: bool = True) -> AIGatewayResponse:
    """Helper to construct a mock AIGatewayResponse."""
    interpretation = LLMClauseInterpretation.model_validate(interpretation_dict) if success else None
    metadata = AIGatewayUsageMetadata(
        service="tender_intelligence",
        reason_for_escalation="Test escalation",
        model="llama-3.3-70b-versatile",
        success=success,
        latency_ms=150.0,
        total_tokens=180,
    )
    return AIGatewayResponse(
        success=success,
        interpretation=interpretation,
        metadata=metadata,
    )


def test_deterministic_pipeline_remains_primary_path():
    """Verify that clear standard clauses are resolved deterministically WITHOUT calling the AI Gateway."""
    mock_gateway = MagicMock(spec=AIGateway)
    service = TenderIntelligenceService(gateway=mock_gateway)

    standard_clause = "Average annual turnover shall not be less than Rs. 15 lakhs during the preceding three years."
    result = service.resolve_clause(standard_clause, page=1, section="Eligibility Criteria")

    # Gateway should NEVER be called for clear deterministic clauses
    mock_gateway.analyze_ambiguous_clause.assert_not_called()

    assert result.status == NormalizationStatus.NORMALIZED
    assert result.resolution_method == "DETERMINISTIC"
    assert result.rule == "AVERAGE_TURNOVER"
    assert result.parameters["minimum"] == 1500000


def test_valid_ambiguous_clause_resolved_by_ai():
    """Verify valid ambiguous clause resolution through AI Gateway and deterministic post-validation."""
    mock_gateway = MagicMock(spec=AIGateway)
    ai_interpretation = {
        "requirement_type": "FINANCIAL",
        "rule": "AVERAGE_TURNOVER",
        "description": "Average annual turnover of INR 2.5 Crores over 3 years",
        "parameters": {
            "minimum": 25000000,
            "currency": "INR",
            "period": 3,
            "period_unit": "YEARS",
        },
        "is_mandatory": True,
        "is_interpretable": True,
        "interpretation_confidence": 0.96,
        "rationale": "Verbal expression 'two and a half crore rupees' correctly mapped to 25000000 INR over 3 years.",
    }
    mock_gateway.analyze_ambiguous_clause.return_value = create_ai_response(ai_interpretation)
    service = TenderIntelligenceService(gateway=mock_gateway)

    ambiguous_clause = "Tendering agency must show average turnover volume not less than two and a half crore rupees in the last 3 financial years."
    result = service.resolve_clause(ambiguous_clause, page=4, section="Financial Evaluation")

    mock_gateway.analyze_ambiguous_clause.assert_called_once()
    assert result.status == NormalizationStatus.AI_RESOLVED
    assert result.resolution_method == "AI_GATEWAY"
    assert result.rule == "AVERAGE_TURNOVER"
    assert result.parameters["minimum"] == 25000000
    assert result.ai_confidence == 0.96
    assert result.model_metadata.get("model") == "llama-3.3-70b-versatile"


def test_malformed_llm_output_rejected():
    """Verify that failures or malformed responses from AI Gateway result in UNRESOLVED status."""
    mock_gateway = MagicMock(spec=AIGateway)
    mock_gateway.analyze_ambiguous_clause.return_value = AIGatewayResponse(
        success=False,
        interpretation=None,
        metadata=AIGatewayUsageMetadata(
            service="tender_intelligence",
            reason_for_escalation="Test",
            model="llama-3.3-70b-versatile",
            success=False,
            latency_ms=50.0,
            error_message="Pydantic validation failed: missing rule field",
        ),
    )
    service = TenderIntelligenceService(gateway=mock_gateway)

    ambiguous_clause = "Firm must have adequate turnover as approved."
    result = service.resolve_clause(ambiguous_clause, page=2)

    assert result.status == NormalizationStatus.UNRESOLVED
    assert "AI resolution failed" in result.ambiguity_reason


def test_hallucinated_fields_rejected_by_deterministic_validation():
    """Verify that hallucinated numbers not grounded in the source text are caught and rejected."""
    mock_gateway = MagicMock(spec=AIGateway)
    # Source text only mentions turnover generally, but LLM hallucinates 85 Crores (85000000)
    ai_interpretation = {
        "requirement_type": "FINANCIAL",
        "rule": "AVERAGE_TURNOVER",
        "description": "Hallucinated 85 Crores turnover",
        "parameters": {
            "minimum": 85000000,
            "currency": "INR",
            "period": 3,
            "period_unit": "YEARS",
        },
        "is_mandatory": True,
        "is_interpretable": True,
        "interpretation_confidence": 0.90,
        "rationale": "Assumed 85 crores from general context.",
    }
    mock_gateway.analyze_ambiguous_clause.return_value = create_ai_response(ai_interpretation)
    service = TenderIntelligenceService(gateway=mock_gateway)

    ambiguous_clause = "Bidder must possess sound financial turnover over the last three years."
    result = service.resolve_clause(ambiguous_clause, page=5)

    assert result.status == NormalizationStatus.UNRESOLVED
    assert "Hallucinated parameter" in result.ambiguity_reason
    assert "85000000" in result.ambiguity_reason


def test_missing_required_values_rejected_by_deterministic_validation():
    """Verify that missing critical parameters for a rule are caught and rejected."""
    mock_gateway = MagicMock(spec=AIGateway)
    # Classifies as AVERAGE_TURNOVER but parameters dict is missing 'minimum' amount
    ai_interpretation = {
        "requirement_type": "FINANCIAL",
        "rule": "AVERAGE_TURNOVER",
        "description": "Incomplete turnover requirement",
        "parameters": {
            "currency": "INR",
            "period": 3,
        },
        "is_mandatory": True,
        "is_interpretable": True,
        "interpretation_confidence": 0.85,
        "rationale": "Missing minimum threshold.",
    }
    mock_gateway.analyze_ambiguous_clause.return_value = create_ai_response(ai_interpretation)
    service = TenderIntelligenceService(gateway=mock_gateway)

    ambiguous_clause = "Bidder must have turnover in INR over 3 years."
    result = service.resolve_clause(ambiguous_clause, page=3)

    assert result.status == NormalizationStatus.UNRESOLVED
    assert "Missing required parameter 'minimum'" in result.ambiguity_reason


def test_conflicting_interpretation_rejected():
    """Verify that contradictions between requirement_type and rule or mandatory status are rejected."""
    mock_gateway = MagicMock(spec=AIGateway)
    # Contradiction: requirement_type is FINANCIAL but rule is OEM_AUTHORIZATION
    ai_interpretation = {
        "requirement_type": "FINANCIAL",
        "rule": "OEM_AUTHORIZATION",
        "description": "Conflicting type and rule",
        "parameters": {"required": True},
        "is_mandatory": True,
        "is_interpretable": True,
        "interpretation_confidence": 0.80,
        "rationale": "Conflicting rule.",
    }
    mock_gateway.analyze_ambiguous_clause.return_value = create_ai_response(ai_interpretation)
    service = TenderIntelligenceService(gateway=mock_gateway)

    ambiguous_clause = "Vendors must submit requisite credentials as approved by the evaluation committee."
    result = service.resolve_clause(ambiguous_clause, page=7)

    assert result.status == NormalizationStatus.UNRESOLVED
    assert "Conflicting interpretation" in result.ambiguity_reason


def test_unresolved_clause_marking():
    """Verify that genuinely uninterpretable clauses are safely marked as UNRESOLVED without guessing."""
    mock_gateway = MagicMock(spec=AIGateway)
    ai_interpretation = {
        "requirement_type": "OTHER",
        "rule": "UNRESOLVED_CRITERIA",
        "description": "Vague non-quantifiable language",
        "parameters": {},
        "is_mandatory": False,
        "is_interpretable": False,
        "interpretation_confidence": 0.15,
        "rationale": "No compliance rules or measurable conditions identified.",
    }
    mock_gateway.analyze_ambiguous_clause.return_value = create_ai_response(ai_interpretation)
    service = TenderIntelligenceService(gateway=mock_gateway)

    vague_clause = "The firm should maintain a high standard of professional ethics and goodwill."
    result = service.resolve_clause(vague_clause, page=12)

    assert result.status == NormalizationStatus.UNRESOLVED
    assert "uninterpretable" in result.ambiguity_reason.lower()


def test_exemption_interpretation_via_ai():
    """Verify AI resolution of complex non-standard exemption clause."""
    mock_gateway = MagicMock(spec=AIGateway)
    ai_interpretation = {
        "requirement_type": "EXEMPTION",
        "rule": "STARTUP_TURNOVER_EXEMPTION",
        "description": "Waiver of prior turnover for DPIIT recognized startups",
        "parameters": {
            "applies_to": ["STARTUP"],
            "target_rule": "AVERAGE_TURNOVER",
            "exemption_type": "FULL",
        },
        "is_mandatory": False,
        "is_interpretable": True,
        "interpretation_confidence": 0.97,
        "rationale": "Clause explicitly waives prior turnover requirements for DPIIT startups.",
    }
    mock_gateway.analyze_ambiguous_clause.return_value = create_ai_response(ai_interpretation)
    service = TenderIntelligenceService(gateway=mock_gateway)

    ambiguous_clause = "In line with government directives, newly incorporated business entities certified under the startup initiative shall not be subject to prior turnover assessments."
    result = service.resolve_clause(ambiguous_clause, page=15)

    assert result.status == NormalizationStatus.AI_RESOLVED
    assert result.type == "EXEMPTION"
    assert result.mandatory is False
    assert "STARTUP" in result.parameters["applies_to"]
    assert result.parameters["target_rule"] == "AVERAGE_TURNOVER"


def test_end_to_end_pages_processing_and_database_persistence(db_session: Session, sample_tender: Tender):
    """Verify full pipeline: page extraction -> deterministic resolution -> AI resolution -> DB persistence."""
    mock_gateway = MagicMock(spec=AIGateway)
    ai_interpretation = {
        "requirement_type": "EXPERIENCE",
        "rule": "SIMILAR_WORK_EXPERIENCE",
        "description": "At least 4 years of experience in enterprise networks",
        "parameters": {
            "scope": "SIMILAR_WORK",
            "min_years": 4,
            "period_unit": "YEARS",
        },
        "is_mandatory": True,
        "is_interpretable": True,
        "interpretation_confidence": 0.95,
        "rationale": "Four years of enterprise network experience derived from source text.",
    }
    mock_gateway.analyze_ambiguous_clause.return_value = create_ai_response(ai_interpretation)
    service = TenderIntelligenceService(gateway=mock_gateway)

    # Document page containing 1 deterministic requirement and 1 ambiguous requirement
    page_text = (
        "SECTION III: ELIGIBILITY CRITERIA\n"
        "1. Average annual turnover shall not be less than Rs. 50 lakhs during the preceding three years.\n"
        "2. The applicant must demonstrate four years of proven operational track record in executing enterprise networks.\n"
    )

    batch_res = service.process_tender_pages(
        pages=[{"page_number": 2, "text": page_text}],
        tender_id=sample_tender.id,
        db=db_session,
        persist=True,
    )

    assert batch_res.total_evaluated == 2
    assert batch_res.normalized_count == 1   # Deterministic turnover
    assert batch_res.ai_resolved_count == 1  # AI resolved experience

    # Verify persisted to PostgreSQL
    from sqlalchemy import select
    persisted_reqs = db_session.scalars(
        select(TenderRequirement).where(TenderRequirement.tender_id == sample_tender.id)
    ).all()

    assert len(persisted_reqs) == 2
    rules = {r.rule for r in persisted_reqs}
    assert "AVERAGE_TURNOVER" in rules
    assert "SIMILAR_WORK_EXPERIENCE" in rules
