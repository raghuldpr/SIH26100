"""
Phase 09 — Compliance Rule Engine
exemptions.py: Generic deterministic exemption evaluator and rule structures.

Core Principles
---------------
1. Generic mechanism: Do NOT hard-code Startup / MSME / etc. exemptions directly into evaluators.
2. Explicit rules only: The rule engine must not invent exemptions. Only explicitly supplied
   exemption rules may be applied.
3. Behavior:
   - Exemption condition definitively TRUE   → EXEMPT (maps to PASS externally)
   - Exemption condition definitively FALSE  → evaluate the original requirement
   - Exemption condition UNCERTAIN / MISSING → REVIEW
4. Full Auditability:
   Every exemption decision records:
   - Exemption rule identifier / description
   - Triggering condition & evidence
   - Affected requirement
   - Result (EXEMPT)
   - Reason

Structure
---------
{
    "type": "EXEMPTION",
    "name": "STARTUP_TURNOVER_EXEMPTION",
    "condition": {
        "field": "bidder_category",
        "operator": "EQUAL",
        "value": "STARTUP"
    },
    "exempts": [
        "MINIMUM_TURNOVER"
    ]
}

No LLM is called at any point.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.evaluator import LOW_CONFIDENCE_THRESHOLD, BaseEvaluator
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.compliance.operators import compare, compare_bool

logger = logging.getLogger("app.compliance.exemptions")


def _normalize_token(v: Any) -> str:
    """Normalize string token for comparison (uppercase, trimmed, underscores)."""
    if v is None:
        return ""
    if hasattr(v, "value"):
        v = v.value
    return str(v).strip().upper().replace("-", "_").replace(" ", "_")


# ---------------------------------------------------------------------------
# Structured Exemption Models
# ---------------------------------------------------------------------------

class ExemptionCondition(BaseModel):
    """
    Condition that must evaluate to True for an exemption to be granted.
    """
    field: str = Field(..., min_length=1, description="Evidence field name to check")
    operator: Operator = Field(default=Operator.EQUAL, description="Comparison operator")
    value: Any = Field(..., description="Target value for the condition")

    model_config = ConfigDict(frozen=False)

    @field_validator("field", mode="before")
    @classmethod
    def _normalise_field(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower().replace(" ", "_")
            if not val:
                raise ValueError("field cannot be empty")
            return val
        raise ValueError(f"Invalid field: {v!r}")


class ExemptionRule(BaseModel):
    """
    Structured exemption rule specifying what requirement(s) are exempted
    when the condition is met.
    """
    rule_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Unique exemption rule ID")
    name: Optional[str] = Field(default=None, description="Human-readable rule name")
    condition: ExemptionCondition = Field(..., description="Condition required to trigger exemption")
    exempts: List[str] = Field(..., min_length=1, description="List of requirement fields or codes exempted")
    description: Optional[str] = Field(default=None, description="Description for audit logging")
    extra: Dict[str, Any] = Field(default_factory=dict, description="Metadata overflow")

    model_config = ConfigDict(frozen=False)


# ---------------------------------------------------------------------------
# Requirement Target Matcher
# ---------------------------------------------------------------------------

def matches_exemption_target(target: str, requirement: Requirement) -> bool:
    """
    Check if a target string from ExemptionRule.exempts applies to a Requirement.
    Matches exact field, category, extra['requirement_code'], or semantic keywords.
    """
    tgt = _normalize_token(target)
    fld = _normalize_token(requirement.field)
    cat = _normalize_token(requirement.category)
    code = _normalize_token(requirement.rule_definition.extra.get("requirement_code", ""))

    if tgt in (fld, cat, code):
        return True

    # Common canonical procurement keywords
    if "TURNOVER" in tgt and "TURNOVER" in fld:
        return True
    if "EMD" in tgt and "EMD" in fld:
        return True
    if "EXPERIENCE" in tgt and "EXPERIENCE" in fld:
        return True

    return False


# ---------------------------------------------------------------------------
# ExemptionEvaluator
# ---------------------------------------------------------------------------

class ExemptionEvaluator(BaseEvaluator):
    """
    Evaluates generic, structured exemption rules.
    """

    @property
    def rule_type(self) -> RuleType:
        return RuleType.EXEMPTION

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        """
        Evaluate a Requirement whose rule_type is EXEMPTION.
        """
        req_id = requirement.requirement_id
        bidder_id = getattr(evidence, "bidder_id", req_id)
        rule_def = requirement.rule_definition

        exemption_rule = self._parse_exemption_rule(rule_def, req_id)
        if isinstance(exemption_rule, ComplianceResult):
            return exemption_rule

        # Evaluate the exemption condition
        cond_status, reason, actual_val = self.evaluate_condition(exemption_rule.condition, evidence)

        if cond_status == ComplianceStatus.PASS:
            rule_name = exemption_rule.name or str(exemption_rule.rule_id)
            return ComplianceResult.exempt_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Requirement '{requirement.field}' exempted by rule '{rule_name}': "
                    f"{exemption_rule.condition.field} is '{actual_val}' (condition met). {reason}"
                ),
                evidence_reference=getattr(evidence, "source_document", None),
                rule_type=self.rule_type,
            )
        elif cond_status == ComplianceStatus.FAIL:
            return ComplianceResult.fail_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Exemption condition for '{requirement.field}' was not met: "
                    f"{exemption_rule.condition.field} is '{actual_val}'. {reason}"
                ),
                evidence_reference=getattr(evidence, "source_document", None),
                rule_type=self.rule_type,
                operator_used=exemption_rule.condition.operator,
                actual_value=actual_val,
                required_value=exemption_rule.condition.value,
            )
        else:
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Exemption condition for '{requirement.field}' is uncertain: {reason}. "
                    "Manual review required."
                ),
                evidence_reference=getattr(evidence, "source_document", None),
                rule_type=self.rule_type,
                operator_used=exemption_rule.condition.operator,
            )

    # ------------------------------------------------------------------
    # Evaluate a condition against evidence
    # ------------------------------------------------------------------

    def evaluate_condition(
        self,
        condition: ExemptionCondition,
        evidence: Optional[BidderEvidence],
    ) -> Tuple[ComplianceStatus, str, Any]:
        """
        Evaluate a single ExemptionCondition against evidence.

        Returns
        -------
        Tuple[ComplianceStatus, str, Any]:
            (status, explanation, actual_value)
        """
        if evidence is None or evidence.value is None:
            return (
                ComplianceStatus.REVIEW,
                f"Missing evidence for exemption condition field '{condition.field}'",
                None,
            )

        if evidence.confidence < LOW_CONFIDENCE_THRESHOLD:
            return (
                ComplianceStatus.REVIEW,
                f"Low extraction confidence ({evidence.confidence:.2f} < {LOW_CONFIDENCE_THRESHOLD:.2f}) "
                f"for exemption condition field '{condition.field}'",
                evidence.value,
            )

        actual = evidence.value
        expected = condition.value
        op = condition.operator

        try:
            # Boolean condition
            if isinstance(expected, bool) or isinstance(actual, bool):
                act_bool = bool(actual)
                exp_bool = bool(expected)
                matched = (act_bool == exp_bool) if op == Operator.EQUAL else (act_bool != exp_bool)
                if matched:
                    return ComplianceStatus.PASS, "Boolean condition matched", actual
                return ComplianceStatus.FAIL, "Boolean condition did not match", actual

            # String token condition
            if isinstance(expected, str) and isinstance(actual, str):
                act_tok = _normalize_token(actual)
                exp_tok = _normalize_token(expected)
                if op == Operator.EQUAL:
                    if act_tok == exp_tok:
                        return ComplianceStatus.PASS, f"'{act_tok}' == '{exp_tok}'", actual
                    return ComplianceStatus.FAIL, f"'{act_tok}' != '{exp_tok}'", actual
                elif op == Operator.NOT_EQUAL:
                    if act_tok != exp_tok:
                        return ComplianceStatus.PASS, f"'{act_tok}' != '{exp_tok}'", actual
                    return ComplianceStatus.FAIL, f"'{act_tok}' == '{exp_tok}'", actual
                elif op == Operator.IN:
                    if act_tok in exp_tok:
                        return ComplianceStatus.PASS, f"'{act_tok}' in '{exp_tok}'", actual
                    return ComplianceStatus.FAIL, f"'{act_tok}' not in '{exp_tok}'", actual

            # List / Membership condition
            if op == Operator.IN and isinstance(expected, (list, tuple, set)):
                act_norm = _normalize_token(actual)
                exp_set = {_normalize_token(x) for x in expected}
                if act_norm in exp_set or actual in expected:
                    return ComplianceStatus.PASS, f"'{actual}' is in allowed values", actual
                return ComplianceStatus.FAIL, f"'{actual}' is not in allowed values", actual

            # Numeric comparison fallback
            matched = compare(actual, op, expected)
            if matched:
                return ComplianceStatus.PASS, f"{actual} {op.value} {expected} is satisfied", actual
            return ComplianceStatus.FAIL, f"{actual} {op.value} {expected} is not satisfied", actual

        except Exception as exc:
            logger.warning("Error evaluating exemption condition: %s", exc)
            return (
                ComplianceStatus.REVIEW,
                f"Error evaluating condition: {exc}",
                actual,
            )

    # ------------------------------------------------------------------
    # Apply exemptions to a requirement (Pre-evaluation filter)
    # ------------------------------------------------------------------

    def check_exemptions_for_requirement(
        self,
        requirement: Requirement,
        exemption_rules: List[Union[ExemptionRule, Dict[str, Any]]],
        evidence_map: Dict[str, BidderEvidence],
        bidder_id: uuid.UUID,
    ) -> Optional[ComplianceResult]:
        """
        Check if any supplied exemption rule applies to the requirement.

        Returns
        -------
        - ComplianceResult(status=EXEMPT) if an exemption is triggered.
        - ComplianceResult(status=REVIEW) if an applicable exemption is uncertain.
        - None if no applicable exemption is triggered (caller proceeds to evaluate requirement).
        """
        for raw_rule in exemption_rules:
            parsed_rule = self._to_rule_model(raw_rule, requirement.requirement_id, bidder_id)
            if isinstance(parsed_rule, ComplianceResult):
                # Invalid exemption rule definition
                return parsed_rule

            # Check if this rule targets the requirement
            applies = any(matches_exemption_target(t, requirement) for t in parsed_rule.exempts)
            if not applies:
                continue

            # Look up evidence for the condition field
            cond_field = parsed_rule.condition.field
            cond_evidence = evidence_map.get(cond_field)

            status, reason, actual_val = self.evaluate_condition(parsed_rule.condition, cond_evidence)

            if status == ComplianceStatus.PASS:
                rule_desc = parsed_rule.name or parsed_rule.description or "supplied exemption rule"
                field_label = requirement.description or requirement.field
                return ComplianceResult.exempt_result(
                    requirement_id=requirement.requirement_id,
                    bidder_id=bidder_id,
                    reason=(
                        f"{field_label} requirement exempted because "
                        f"{cond_field} is {actual_val} and the {rule_desc} applies."
                    ),
                    evidence_reference=getattr(cond_evidence, "source_document", None),
                    rule_type=self.rule_type,
                )
            elif status == ComplianceStatus.REVIEW:
                return ComplianceResult.review_result(
                    requirement_id=requirement.requirement_id,
                    bidder_id=bidder_id,
                    reason=(
                        f"Exemption applicability for '{requirement.field}' is uncertain: "
                        f"{reason}. Manual review required."
                    ),
                    evidence_reference=getattr(cond_evidence, "source_document", None),
                    rule_type=self.rule_type,
                    operator_used=parsed_rule.condition.operator,
                )
            # If status == FAIL, condition does not hold for this rule. Check other rules.

        return None

    # ------------------------------------------------------------------
    # Parsing Helpers
    # ------------------------------------------------------------------

    def _to_rule_model(
        self,
        raw_rule: Union[ExemptionRule, Dict[str, Any]],
        req_id: uuid.UUID,
        bidder_id: uuid.UUID,
    ) -> Union[ExemptionRule, ComplianceResult]:
        if isinstance(raw_rule, ExemptionRule):
            return raw_rule
        if not isinstance(raw_rule, dict):
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason="Invalid exemption definition: rule must be a dict or ExemptionRule.",
                rule_type=self.rule_type,
            )
        try:
            cond_raw = raw_rule.get("condition")
            if not cond_raw or not isinstance(cond_raw, dict):
                return ComplianceResult.review_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason="Invalid exemption definition: missing or invalid 'condition'.",
                    rule_type=self.rule_type,
                )
            exempts = raw_rule.get("exempts")
            if not exempts or not isinstance(exempts, list):
                return ComplianceResult.review_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason="Invalid exemption definition: missing or empty 'exempts' list.",
                    rule_type=self.rule_type,
                )

            op_str = cond_raw.get("operator", "EQUAL")
            try:
                op = Operator(op_str)
            except ValueError:
                return ComplianceResult.review_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=f"Invalid exemption definition: unknown operator '{op_str}'.",
                    rule_type=self.rule_type,
                )

            condition = ExemptionCondition(
                field=cond_raw["field"],
                operator=op,
                value=cond_raw.get("value"),
            )
            return ExemptionRule(
                name=raw_rule.get("name"),
                condition=condition,
                exempts=exempts,
                description=raw_rule.get("description"),
            )
        except Exception as exc:
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=f"Invalid exemption definition: {exc}.",
                rule_type=self.rule_type,
            )

    def _parse_exemption_rule(
        self,
        rule_def: RuleDefinition,
        req_id: uuid.UUID,
    ) -> Union[ExemptionRule, ComplianceResult]:
        payload = rule_def.required_value or rule_def.extra
        if isinstance(payload, dict):
            return self._to_rule_model(payload, req_id, req_id)
        return ComplianceResult.review_result(
            requirement_id=req_id,
            bidder_id=req_id,
            reason="Exemption rule requirement has missing or invalid definition payload.",
            rule_type=self.rule_type,
        )
