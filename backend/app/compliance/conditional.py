"""
Phase 09 — Compliance Rule Engine
conditional.py: Deterministic IF / THEN conditional rule evaluator.

Semantics
---------
A conditional rule has the form:

    IF <condition_sub_rule>
    THEN <consequence_sub_rule>

Evaluation contract:

  1. Evaluate the condition sub-rule against condition evidence.
  2a. Condition is PASS (true)  → evaluate the THEN requirement.
       Return that result directly (PASS / FAIL / REVIEW).
  2b. Condition is FAIL (false) → requirement does not apply.
       Return NOT_APPLICABLE (collapses to PASS externally).
  2c. Condition is REVIEW (uncertain) → we cannot determine applicability.
       Return REVIEW.

Structure convention
--------------------
  RuleDefinition.logical_operator = "IF"
  RuleDefinition.sub_rules        = [condition_rule_def, consequence_rule_def]

  condition_rule_def.extra  must carry "field", "rule_type", and
                            optionally "evidence_value" / "evidence_confidence".
  consequence_rule_def.extra must carry "field" and "rule_type".

No LLM is called at any point.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable, Optional

from app.compliance.enums import ComplianceStatus, RuleType
from app.compliance.evaluator import BaseEvaluator
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition
from app.compliance.logical import EvaluateFn, _build_sub_requirement

logger = logging.getLogger("app.compliance.conditional")


class ConditionalEvaluator(BaseEvaluator):
    """
    Evaluates IF/THEN conditional requirements.

    Parameters
    ----------
    evaluate_fn:
        Callable(Requirement, BidderEvidence | None) → ComplianceResult.
        Injected from the engine to allow recursive evaluation without
        circular imports.
    """

    def __init__(self, evaluate_fn: Optional[EvaluateFn] = None) -> None:
        self._evaluate_fn: Optional[EvaluateFn] = evaluate_fn

    @property
    def rule_type(self) -> RuleType:
        return RuleType.CONDITIONAL

    def set_evaluate_fn(self, fn: EvaluateFn) -> None:
        """Inject the engine's evaluate callable post-construction."""
        self._evaluate_fn = fn

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        rid       = requirement.requirement_id
        bidder_id = evidence.bidder_id if evidence else rid
        rule_def  = requirement.rule_definition
        field     = requirement.field

        # ------------------------------------------------------------------
        # 1. Validate structure
        # ------------------------------------------------------------------
        logical_op = (rule_def.logical_operator or "").strip().upper()
        if logical_op != "IF":
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"CONDITIONAL rule for '{field}' has invalid logical_operator "
                    f"'{rule_def.logical_operator}'. Expected 'IF'. "
                    "Rule is misconfigured."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        sub_rules = rule_def.sub_rules or []
        if len(sub_rules) < 2:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"CONDITIONAL rule for '{field}' requires exactly 2 sub_rules "
                    f"[condition, consequence]; found {len(sub_rules)}. "
                    "Rule is misconfigured."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        if self._evaluate_fn is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    "ConditionalEvaluator has no evaluate_fn wired. "
                    "Engine initialisation is incomplete."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        condition_def    = sub_rules[0]
        consequence_def  = sub_rules[1]

        # ------------------------------------------------------------------
        # 2. Build & evaluate the condition
        # ------------------------------------------------------------------
        condition_req = _build_sub_requirement(requirement, condition_def, 0)
        if condition_req is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"CONDITIONAL rule for '{field}': condition sub-rule (index 0) "
                    "is misconfigured (missing field/rule_type in extra)."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # Resolve condition evidence
        cond_ev = self._resolve_evidence(
            evidence, condition_req, condition_def, bidder_id, parent_requirement=requirement
        )
        condition_result = self._evaluate_fn(condition_req, cond_ev)
        condition_status = condition_result.status

        # ------------------------------------------------------------------
        # 3. Branch on condition outcome
        # ------------------------------------------------------------------

        # 3b. Condition is FALSE → NOT_APPLICABLE
        if condition_status == ComplianceStatus.FAIL:
            return ComplianceResult.not_applicable_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Conditional requirement for '{field}' does not apply: "
                    f"condition '{condition_req.field}' evaluated to FAIL "
                    f"({condition_result.reason}). "
                    "Requirement is NOT_APPLICABLE."
                ),
                rule_type=self.rule_type,
            )


        # 3c. Condition is REVIEW → uncertain applicability
        if condition_status == ComplianceStatus.REVIEW:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"Conditional requirement for '{field}': condition "
                    f"'{condition_req.field}' is REVIEW ({condition_result.reason}). "
                    "Applicability is uncertain — manual review required."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # 3a. Condition is PASS (or EXEMPT / NOT_APPLICABLE = effectively pass)
        #    → evaluate the consequence
        consequence_req = _build_sub_requirement(requirement, consequence_def, 1)
        if consequence_req is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"CONDITIONAL rule for '{field}': consequence sub-rule (index 1) "
                    "is misconfigured (missing field/rule_type in extra). "
                    "Condition was PASS but consequence cannot be evaluated."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        cons_ev = self._resolve_evidence(
            evidence, consequence_req, consequence_def, bidder_id, parent_requirement=requirement
        )
        consequence_result = self._evaluate_fn(consequence_req, cons_ev)


        # Wrap result with context about the condition that triggered it
        cond_ctx = (
            f"[Condition '{condition_req.field}' was PASS] "
        )
        if consequence_result.status == ComplianceStatus.PASS:
            return ComplianceResult.pass_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=cond_ctx + consequence_result.reason,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=consequence_result.actual_value,
                required_value=consequence_result.required_value,
            )
        elif consequence_result.status == ComplianceStatus.FAIL:
            return ComplianceResult.fail_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=cond_ctx + consequence_result.reason,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=consequence_result.actual_value,
                required_value=consequence_result.required_value,
            )
        else:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=cond_ctx + consequence_result.reason,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

    # ------------------------------------------------------------------
    # Evidence resolution helper
    # ------------------------------------------------------------------

    def _resolve_evidence(
        self,
        parent_evidence: Optional[BidderEvidence],
        sub_req: Requirement,
        sub_def: RuleDefinition,
        bidder_id,
        parent_requirement: Optional[Requirement] = None,
    ) -> Optional[BidderEvidence]:
        """
        Resolve evidence for a sub-requirement.

        Priority:
          1. Parent evidence if field names match.
          2. Field in evidence_map (passed from engine or parent_requirement).
          3. Inline evidence_value in sub_def.extra.
          4. None (evaluator will produce REVIEW or definitely absent FAIL).
        """
        if parent_evidence is not None and parent_evidence.field == sub_req.field:
            return parent_evidence

        ev_map = None
        if parent_requirement and "evidence_map" in parent_requirement.rule_definition.extra:
            ev_map = parent_requirement.rule_definition.extra["evidence_map"]
        elif "evidence_map" in sub_def.extra:
            ev_map = sub_def.extra["evidence_map"]

        if ev_map and sub_req.field in ev_map:
            return ev_map[sub_req.field]

        if sub_def.extra.get("evidence_value") is not None:
            from app.compliance.models import EvidenceSource
            return BidderEvidence(
                bidder_id=bidder_id,
                field=sub_req.field,
                value=sub_def.extra["evidence_value"],
                source=sub_def.extra.get("evidence_source", EvidenceSource.SYSTEM_DERIVED),
                confidence=float(sub_def.extra.get("evidence_confidence", 1.0)),
            )

        return None

