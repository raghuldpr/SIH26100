import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

try:
    from groq import Groq, APIError, RateLimitError, APITimeoutError
    _GROQ_AVAILABLE = True
except ImportError:
    Groq = None
    APIError = Exception
    RateLimitError = Exception
    APITimeoutError = Exception
    _GROQ_AVAILABLE = False

from app.config import settings
from app.models.enums import RequirementType
from app.schemas.ai_gateway import (
    AIGatewayResponse,
    AIGatewayUsageMetadata,
    AmbiguousClauseRequest,
    LLMClauseInterpretation,
)
from app.schemas.tender_requirement_normalizer import (
    NormalizationStatus,
    NormalizedRequirement,
)

logger = logging.getLogger("app.services.ai_gateway")


class AIGateway:
    """
    Controlled AI Gateway for Phase 08 (Tender Intelligence).
    Enforces strict architectural boundaries:
    - Only accepts explicitly escalated ambiguous clauses with technical justification.
    - Uses Groq with open-source models (e.g. llama-3.3-70b-versatile).
    - Requests structured JSON and validates strictly via Pydantic.
    - Read-only: Never performs database mutations.
    - Full telemetry and error handling without exposing arbitrary prompt APIs.
    """

    SYSTEM_PROMPT = (
        "You are an expert procurement compliance intelligence parser for the Government e-Marketplace (GeM) India.\n"
        "Your task is to analyze an ambiguous, complex, or non-standard tender eligibility clause that could not be\n"
        "resolved deterministically, and extract structured compliance parameters.\n\n"
        "RULES:\n"
        "1. Ground all parameters strictly in the provided clause text. Do NOT hallucinate or assume unstated criteria.\n"
        "2. If the text is genuinely impossible to interpret, contradictory, or lacks compliance meaning, set 'is_interpretable': false.\n"
        "3. Standard requirement types: FINANCIAL, EXPERIENCE, TECHNICAL, STATUTORY, DOCUMENT, OEM, MII, MSE, STARTUP, EXEMPTION, OTHER.\n"
        "4. Standard rules: AVERAGE_TURNOVER, MINIMUM_TURNOVER, NET_WORTH, SIMILAR_WORK_EXPERIENCE, COMPLETED_PROJECTS,\n"
        "   EXPERIENCE_PERIOD, GST_REGISTRATION, PAN_REQUIREMENT, STATUTORY_LICENSE, OEM_AUTHORIZATION, MII_LOCAL_CONTENT,\n"
        "   MSE_PREFERENCE, STARTUP_CRITERIA, REQUIRED_DOCUMENT, STATUTORY_EXEMPTION.\n"
        "5. Normalize Indian currency to integer INR (e.g. 'Rs. 15 lakhs' -> 1500000, '4.5 Crores' -> 45000000).\n"
        "6. Normalize durations to 'period' (integer) and 'period_unit' ('YEARS' or 'MONTHS').\n"
        "7. Output ONLY valid JSON conforming to the requested schema.\n"
    )

    JSON_SCHEMA_HINT = {
        "requirement_type": "FINANCIAL",
        "rule": "AVERAGE_TURNOVER",
        "description": "Clear human-readable description of the requirement",
        "parameters": {
            "minimum": 1500000,
            "currency": "INR",
            "period": 3,
            "period_unit": "YEARS"
        },
        "is_mandatory": True,
        "is_interpretable": True,
        "interpretation_confidence": 0.95,
        "rationale": "Turnover threshold and period specified in text"
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        client: Optional[Any] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.GROQ_API_KEY
        self.model = model or getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        self.timeout_seconds = timeout_seconds or getattr(settings, "GROQ_TIMEOUT_SECONDS", 30.0)
        self.max_retries = max_retries if max_retries is not None else getattr(settings, "GROQ_MAX_RETRIES", 2)
        self.temperature = getattr(settings, "GROQ_TEMPERATURE", 0.0)

        # Allow injected client for testing/mocking
        if client is not None:
            self._client = client
        elif self.api_key and _GROQ_AVAILABLE:
            self._client = Groq(api_key=self.api_key, timeout=self.timeout_seconds)
        else:
            self._client = None

    def analyze_ambiguous_clause(
        self,
        request: Optional[Union[AmbiguousClauseRequest, Dict[str, Any], str]] = None,
        clause_text: Optional[str] = None,
        reason_for_escalation: Optional[str] = None,
        source_page: Optional[int] = None,
        source_section: Optional[str] = None,
        candidate_type: Optional[str] = None,
        known_context: Optional[Dict[str, Any]] = None,
    ) -> AIGatewayResponse:
        """
        Narrow internal interface: Interprets an ambiguous clause via controlled LLM reasoning.
        Enforces escalation reason validation, telemetry logging, and response parsing.
        """
        start_time = time.perf_counter()
        now_utc = datetime.now(timezone.utc)

        # Allow passing clause_text directly or via request
        target_clause = clause_text if clause_text is not None else request

        # Normalize into AmbiguousClauseRequest
        if isinstance(target_clause, AmbiguousClauseRequest):
            req_obj = target_clause
        elif isinstance(target_clause, dict):
            req_obj = AmbiguousClauseRequest(**target_clause)
        elif isinstance(target_clause, str):
            if not reason_for_escalation or not reason_for_escalation.strip():
                raise ValueError("Escalation reason is required. The LLM cannot be invoked without explicit justification.")
            req_obj = AmbiguousClauseRequest(
                clause_text=target_clause,
                reason_for_escalation=reason_for_escalation,
                source_page=source_page,
                source_section=source_section,
                candidate_type=candidate_type,
                known_context=known_context or {},
            )
        else:
            raise TypeError(f"Invalid request type: {type(target_clause)}. Expected AmbiguousClauseRequest, dict, or str.")

        # Guard: Check API key availability
        if not self._client and not self.api_key:
            logger.warning(
                "AIGateway invocation skipped: GROQ_API_KEY is not configured. "
                "Returning gracefully without crashing deterministic flow."
            )
            meta = AIGatewayUsageMetadata(
                service="tender_intelligence",
                reason_for_escalation=req_obj.reason_for_escalation,
                model=self.model,
                timestamp=now_utc,
                success=False,
                latency_ms=0.0,
                error_message="GROQ_API_KEY not configured",
            )
            return AIGatewayResponse(success=False, metadata=meta)

        # Construct prompt
        prompt_payload = {
            "ambiguous_clause_text": req_obj.clause_text,
            "escalation_reason": req_obj.reason_for_escalation,
            "section_context": req_obj.source_section or "Unknown",
            "suggested_type": req_obj.candidate_type or "Unknown",
            "partially_extracted_context": req_obj.known_context or {},
            "expected_json_format": self.JSON_SCHEMA_HINT,
        }

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Analyze and normalize this ambiguous clause:\n```json\n{json.dumps(prompt_payload, indent=2)}\n```",
            },
        ]

        # Execute with retry logic
        attempts = 0
        last_error: Optional[str] = None
        raw_response_text: Optional[str] = None
        prompt_tokens: Optional[int] = None
        completion_tokens: Optional[int] = None
        total_tokens: Optional[int] = None

        while attempts <= self.max_retries:
            attempts += 1
            try:
                chat_completion = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    response_format={"type": "json_object"},
                )

                raw_response_text = chat_completion.choices[0].message.content
                if hasattr(chat_completion, "usage") and chat_completion.usage:
                    prompt_tokens = getattr(chat_completion.usage, "prompt_tokens", None)
                    completion_tokens = getattr(chat_completion.usage, "completion_tokens", None)
                    total_tokens = getattr(chat_completion.usage, "total_tokens", None)

                last_error = None
                break  # Successful API call
            except (APITimeoutError, RateLimitError) as net_err:
                last_error = f"{type(net_err).__name__}: {str(net_err)}"
                logger.warning(f"Groq API retryable error (attempt {attempts}/{self.max_retries + 1}): {net_err}")
                if attempts <= self.max_retries:
                    time.sleep(1.0 * attempts)
            except Exception as e:
                last_error = f"{type(e).__name__}: {str(e)}"
                logger.error(f"Groq API call failure: {e}", exc_info=False)
                break

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Handle API execution error
        if last_error or not raw_response_text:
            meta = AIGatewayUsageMetadata(
                service="tender_intelligence",
                reason_for_escalation=req_obj.reason_for_escalation,
                model=self.model,
                timestamp=now_utc,
                success=False,
                latency_ms=latency_ms,
                error_message=last_error or "Empty response from Groq",
            )
            logger.info(
                f"AI Gateway completed with error [model={self.model}, reason={req_obj.reason_for_escalation}, latency={latency_ms}ms]"
            )
            return AIGatewayResponse(success=False, metadata=meta)

        # Parse & Validate structured JSON output via Pydantic
        try:
            parsed_dict = json.loads(raw_response_text)
            interpretation = LLMClauseInterpretation.model_validate(parsed_dict)
        except Exception as val_err:
            meta = AIGatewayUsageMetadata(
                service="tender_intelligence",
                reason_for_escalation=req_obj.reason_for_escalation,
                model=self.model,
                timestamp=now_utc,
                success=False,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                error_message=f"Pydantic validation failed: {str(val_err)}",
            )
            logger.warning(f"Malformed LLM output rejected by AI Gateway: {val_err}")
            return AIGatewayResponse(success=False, metadata=meta)

        # Convert to NormalizedRequirement if interpretable
        normalized_req: Optional[NormalizedRequirement] = None
        if interpretation.is_interpretable:
            normalized_req = NormalizedRequirement(
                status=NormalizationStatus.NORMALIZED,
                type=interpretation.requirement_type,
                rule=interpretation.rule,
                description=interpretation.description,
                parameters=interpretation.parameters,
                mandatory=interpretation.is_mandatory,
                confidence=interpretation.interpretation_confidence,
                source_page=req_obj.source_page,
                source_section=req_obj.source_section,
                source_text=req_obj.clause_text,
            )
        else:
            normalized_req = NormalizedRequirement(
                status=NormalizationStatus.AMBIGUOUS,
                type=interpretation.requirement_type or RequirementType.OTHER.value,
                rule=interpretation.rule or "UNINTERPRETABLE_CRITERIA",
                source_page=req_obj.source_page,
                source_section=req_obj.source_section,
                source_text=req_obj.clause_text,
                ambiguity_reason=f"Model determined clause is uninterpretable: {interpretation.rationale}",
                confidence=interpretation.interpretation_confidence,
            )

        meta = AIGatewayUsageMetadata(
            service="tender_intelligence",
            reason_for_escalation=req_obj.reason_for_escalation,
            model=self.model,
            timestamp=now_utc,
            success=True,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        logger.info(
            f"AI Gateway successfully resolved ambiguous clause [model={self.model}, "
            f"rule={interpretation.rule}, tokens={total_tokens}, latency={latency_ms}ms]"
        )

        return AIGatewayResponse(
            success=True,
            interpretation=interpretation,
            metadata=meta,
            normalized_requirement=normalized_req,
        )


ai_gateway = AIGateway()
analyze_ambiguous_clause = ai_gateway.analyze_ambiguous_clause
