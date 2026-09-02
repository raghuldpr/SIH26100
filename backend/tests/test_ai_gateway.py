import json
from unittest.mock import MagicMock, patch
import pytest
from pydantic import ValidationError

from app.models.enums import RequirementType
from app.schemas.ai_gateway import (
    AIGatewayResponse,
    AmbiguousClauseRequest,
    LLMClauseInterpretation,
)
from app.schemas.tender_requirement_normalizer import NormalizationStatus
from app.services.ai_gateway import AIGateway


def create_mock_groq_completion(content_dict: dict, prompt_tokens: int = 120, completion_tokens: int = 45):
    """Helper to generate a mock Groq ChatCompletion object."""
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(content_dict)

    mock_usage = MagicMock()
    mock_usage.prompt_tokens = prompt_tokens
    mock_usage.completion_tokens = completion_tokens
    mock_usage.total_tokens = prompt_tokens + completion_tokens

    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]
    mock_completion.usage = mock_usage
    return mock_completion


def test_escalation_reason_is_mandatory():
    """Verify that escalating a clause to AI Gateway strictly requires a non-empty technical reason."""
    gateway = AIGateway(api_key="mock_key")

    # 1. Empty string in string interface
    with pytest.raises(ValueError, match="Escalation reason is required"):
        gateway.analyze_ambiguous_clause("Some ambiguous clause", reason_for_escalation="")

    # 2. Whitespace string in string interface
    with pytest.raises(ValueError, match="Escalation reason is required"):
        gateway.analyze_ambiguous_clause("Some ambiguous clause", reason_for_escalation="   ")

    # 3. Pydantic validation error in AmbiguousClauseRequest
    with pytest.raises(ValidationError):
        AmbiguousClauseRequest(clause_text="Valid clause text here", reason_for_escalation="  ")


def test_ai_gateway_successful_interpretation():
    """Verify end-to-end interpretation of an escalated ambiguous clause using mocked Groq response."""
    mock_client = MagicMock()
    expected_content = {
        "requirement_type": "FINANCIAL",
        "rule": "AVERAGE_TURNOVER",
        "description": "Average annual turnover of INR 3.5 Crores across last 3 audited financial years",
        "parameters": {
            "minimum": 35000000,
            "currency": "INR",
            "period": 3,
            "period_unit": "YEARS",
        },
        "is_mandatory": True,
        "is_interpretable": True,
        "interpretation_confidence": 0.94,
        "rationale": "Clause specifies composite financial standing evaluated at three and a half crore rupees over three years.",
    }
    mock_client.chat.completions.create.return_value = create_mock_groq_completion(expected_content)

    gateway = AIGateway(api_key="mock_key", client=mock_client)
    ambiguous_text = "The financial standing of the tendering entity must reflect a volume of not less than three and a half crore rupees assessed over three consecutive audited cycles."

    response = gateway.analyze_ambiguous_clause(
        clause_text=ambiguous_text,
        reason_for_escalation="Monetary and period thresholds expressed in non-standard word syntax ('three and a half crore rupees assessed over three consecutive audited cycles')",
        source_page=14,
        source_section="Financial Capability",
        candidate_type="FINANCIAL",
    )

    assert response.success is True
    assert response.interpretation is not None
    assert response.interpretation.requirement_type == "FINANCIAL"
    assert response.interpretation.rule == "AVERAGE_TURNOVER"
    assert response.interpretation.parameters["minimum"] == 35000000
    assert response.interpretation.parameters["currency"] == "INR"
    assert response.interpretation.parameters["period"] == 3
    assert response.interpretation.interpretation_confidence == 0.94

    # Verify telemetry metadata recorded
    assert response.metadata.service == "tender_intelligence"
    assert response.metadata.success is True
    assert response.metadata.total_tokens == 165
    assert response.metadata.latency_ms >= 0.0
    assert "three and a half crore" in response.metadata.reason_for_escalation

    # Verify NormalizedRequirement output container
    assert response.normalized_requirement is not None
    assert response.normalized_requirement.status in (NormalizationStatus.NORMALIZED, NormalizationStatus.AI_RESOLVED)
    assert response.normalized_requirement.rule == "AVERAGE_TURNOVER"
    assert response.normalized_requirement.source_page == 14

    # Verify call parameters sent to Groq
    mock_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["response_format"] == {"type": "json_object"}
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["model"] == "llama-3.3-70b-versatile"


def test_ai_gateway_rejects_malformed_llm_json():
    """Verify that malformed or non-schema-compliant JSON output from LLM is safely rejected."""
    mock_client = MagicMock()
    # Missing required 'rule', 'interpretation_confidence', and 'rationale'
    malformed_content = {
        "requirement_type": "FINANCIAL",
        "description": "Some description",
    }
    mock_client.chat.completions.create.return_value = create_mock_groq_completion(malformed_content)

    gateway = AIGateway(api_key="mock_key", client=mock_client)
    response = gateway.analyze_ambiguous_clause(
        clause_text="Ambiguous text snippet",
        reason_for_escalation="Test malformed rejection",
    )

    assert response.success is False
    assert response.interpretation is None
    assert response.normalized_requirement is None
    assert response.metadata.success is False
    assert "Pydantic validation failed" in response.metadata.error_message


def test_ai_gateway_handles_uninterpretable_clause_gracefully():
    """Verify that when LLM flags a clause as uninterpretable, it is marked as AMBIGUOUS without guessing."""
    mock_client = MagicMock()
    uninterpretable_content = {
        "requirement_type": "OTHER",
        "rule": "UNINTERPRETABLE_CRITERIA",
        "description": "Vague statement with no actionable compliance criteria",
        "parameters": {},
        "is_mandatory": False,
        "is_interpretable": False,
        "interpretation_confidence": 0.20,
        "rationale": "Text contains contradictory and colloquial statements with no discernable criteria.",
    }
    mock_client.chat.completions.create.return_value = create_mock_groq_completion(uninterpretable_content)

    gateway = AIGateway(api_key="mock_key", client=mock_client)
    response = gateway.analyze_ambiguous_clause(
        clause_text="The committee reserves the right to consider good feelings and general vibes.",
        reason_for_escalation="Non-standard phrasing with undefined qualitative terms",
    )

    assert response.success is True
    assert response.interpretation is not None
    assert response.interpretation.is_interpretable is False
    assert response.normalized_requirement is not None
    assert response.normalized_requirement.status == NormalizationStatus.AMBIGUOUS
    assert "uninterpretable" in response.normalized_requirement.ambiguity_reason.lower()


def test_ai_gateway_graceful_when_api_key_missing():
    """Verify that when GROQ_API_KEY is not configured, gateway returns gracefully without throwing unhandled exceptions."""
    gateway = AIGateway(api_key="")

    response = gateway.analyze_ambiguous_clause(
        clause_text="Some clause needing escalation",
        reason_for_escalation="Test unconfigured key",
    )

    assert response.success is False
    assert response.metadata.success is False
    assert "GROQ_API_KEY not configured" in response.metadata.error_message


def test_ai_gateway_provider_error_handling_and_retry():
    """Verify that provider network/API errors are caught safely and recorded in telemetry."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = RuntimeError("Groq upstream 503 service unavailable")

    gateway = AIGateway(api_key="mock_key", client=mock_client, max_retries=1)
    response = gateway.analyze_ambiguous_clause(
        clause_text="Turnover criteria clause",
        reason_for_escalation="Test upstream failure handling",
    )

    assert response.success is False
    assert response.metadata.success is False
    assert "RuntimeError" in response.metadata.error_message
    assert "503 service unavailable" in response.metadata.error_message
