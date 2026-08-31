"""
Phase 09 — Compliance Rule Engine
logical.py: Deterministic AND / OR logical composition evaluator.

Three-valued logic
------------------
The compliance engine works with three truth values: PASS, FAIL, REVIEW.
REVIEW means "indeterminate" — we don't have enough information to decide.

AND truth table (short-circuit: FAIL wins over REVIEW)
  PASS   AND  PASS   → PASS
  PASS   AND  FAIL   → FAIL
  PASS   AND  REVIEW → REVIEW
  FAIL   AND  FAIL   → FAIL
  FAIL   AND  REVIEW → FAIL   (already definitively impossible)
  REVIEW AND  REVIEW → REVIEW

OR truth table (short-circuit: PASS wins over REVIEW)
  PASS   OR   PASS   → PASS
  PASS   OR   FAIL   → PASS
  PASS   OR   REVIEW → PASS   (already satisfied)
  FAIL   OR   FAIL   → FAIL
  FAIL   OR   REVIEW → REVIEW (might still be satisfied)
  REVIEW OR   REVIEW → REVIEW

Nesting
-------
Sub-rules may themselves be LOGICAL or CONDITIONAL rules, enabling arbitrary
depth: A AND (B OR C), (A AND B) OR (C AND D), etc.

Structure convention
--------------------
  RuleDefinition.logical_operator = "AND" | "OR"
  RuleDefinition.sub_rules = [RuleDefinition, ...]

Each entry in sub_rules is evaluated by building a child Requirement that
inherits tender_id / category / mandatory from the parent, with the
sub-rule's own field, rule_type and rule_definition.  The field name is
expected to appear in the sub-rule's extra dict under key "field", and
rule_type under key "rule_type".  Missing keys cause a REVIEW sub-result.

No LLM is called at any point.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable, List, Optional

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.evaluator import BaseEvaluator
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement, RuleDefinition

logger = logging.getLogger("app.compliance.logical")

# Type alias for the evaluate callable injected from the engine
EvaluateFn = Callable[[Requirement, Optional[BidderEvidence]], ComplianceResult]


# ---------------------------------------------------------------------------
# Three-valued AND / OR reduction helpers
# ---------------------------------------------------------------------------

def _and_reduce(results: List[ComplianceStatus]) -> ComplianceStatus:
    """
    Reduce a list of statuses under AND three-valued logic.

    FAIL beats REVIEW (a definitively-failing sub-rule kills the AND regardless
    of uncertain others).  REVIEW beats PASS only when there is no FAIL.
    """
    if not results:
        return ComplianceStatus.REVIEW  # no sub-rules → indeterminate

    has_fail   = any(s == ComplianceStatus.FAIL   for s in results)
    has_review = any(s == ComplianceStatus.REVIEW for s in results)

    if has_fail:
        return ComplianceStatus.FAIL    # short-circuit: FAIL is definitive
    if has_review:
        return ComplianceStatus.REVIEW  # uncertain
    return ComplianceStatus.PASS


def _or_reduce(results: List[ComplianceStatus]) -> ComplianceStatus:
    """
    Reduce a list of statuses under OR three-valued logic.

    PASS beats REVIEW (one satisfied alternative is enough).  REVIEW beats FAIL
    only when there is no PASS.
    """
    if not results:
        return ComplianceStatus.REVIEW

    has_pass   = any(s == ComplianceStatus.PASS   for s in results)
    has_review = any(s == ComplianceStatus.REVIEW for s in results)

    if has_pass:
        return ComplianceStatus.PASS    # short-circuit: already satisfied
    if has_review:
        return ComplianceStatus.REVIEW  # might still be satisfied
    return ComplianceStatus.FAIL


# ---------------------------------------------------------------------------
# Sub-rule requirement builder
# ---------------------------------------------------------------------------

def _build_sub_requirement(
    parent: Requirement,
    sub_def: RuleDefinition,
    index: int,
) -> Optional[Requirement]:
    """
    Build a Requirement for a single sub_rule entry.

    The sub-rule must carry its field and rule_type in sub_def.extra:
        { "field": "annual_turnover", "rule_type": "NUMERIC", ... }

    Returns None if the sub-rule is misconfigured (caller maps this to REVIEW).
    """
    field     = sub_def.extra.get("field")
    rule_type = sub_def.extra.get("rule_type")

    if not field or not rule_type:
        logger.warning(
            "Sub-rule #%d of requirement %s is missing 'field' or 'rule_type' in extra.",
            index, parent.requirement_id,
        )
        return None

    try:
        rt = RuleType(rule_type)
    except ValueError:
        logger.warning(
            "Sub-rule #%d of requirement %s has unknown rule_type '%s'.",
            index, parent.requirement_id, rule_type,
        )
        return None

    return Requirement(
        requirement_id=uuid.uuid4(),
        tender_id=parent.tender_id,
        category=parent.category,
        field=field,
        rule_type=rt,
        rule_definition=sub_def,
        mandatory=parent.mandatory,
        description=sub_def.extra.get("description"),
    )


# ---------------------------------------------------------------------------
# LogicalEvaluator
# ---------------------------------------------------------------------------

class LogicalEvaluator(BaseEvaluator):
    """
    Evaluates LOGICAL rules using three-valued AND / OR logic.

    Each sub-rule in RuleDefinition.sub_rules is evaluated independently.
    Results are combined with the parent logical_operator ("AND" or "OR").

    Nesting is supported: a sub-rule can itself be a LOGICAL rule, which
    will be dispatched recursively through the injected evaluate_fn.

    Parameters
    ----------
    evaluate_fn:
        Callable(Requirement, BidderEvidence | None) → ComplianceResult.
        Injected to avoid circular imports.  The module-level engine singleton
        sets this after engine construction.
    """

    def __init__(self, evaluate_fn: Optional[EvaluateFn] = None) -> None:
        self._evaluate_fn: Optional[EvaluateFn] = evaluate_fn

    @property
    def rule_type(self) -> RuleType:
        return RuleType.LOGICAL

    def set_evaluate_fn(self, fn: EvaluateFn) -> None:
        """Inject the engine's evaluate callable post-construction."""
        self._evaluate_fn = fn

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        rid      = requirement.requirement_id
        bidder_id = evidence.bidder_id if evidence else rid
        rule_def = requirement.rule_definition
        field    = requirement.field

        # ------------------------------------------------------------------
        # Validate logical_operator
        # ------------------------------------------------------------------
        logical_op = (rule_def.logical_operator or "").strip().upper()
        if logical_op not in ("AND", "OR"):
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"LOGICAL rule for '{field}' has invalid or missing "
                    f"logical_operator '{rule_def.logical_operator}'. "
                    "Expected 'AND' or 'OR'. Rule is misconfigured."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # ------------------------------------------------------------------
        # Validate sub_rules
        # ------------------------------------------------------------------
        sub_rules = rule_def.sub_rules or []
        if not sub_rules:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"LOGICAL rule for '{field}' has no sub_rules defined. "
                    "Rule is misconfigured."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # ------------------------------------------------------------------
        # Evaluate_fn must be wired up
        # ------------------------------------------------------------------
        if self._evaluate_fn is None:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=(
                    f"LogicalEvaluator has no evaluate_fn wired. "
                    "Engine initialisation is incomplete."
                ),
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # ------------------------------------------------------------------
        # Evaluate each sub-rule
        # ------------------------------------------------------------------
        sub_results: List[ComplianceResult] = []
        sub_statuses: List[ComplianceStatus] = []
        sub_reasons: List[str] = []

        for i, sub_def in enumerate(sub_rules):
            sub_req = _build_sub_requirement(requirement, sub_def, i)
            if sub_req is None:
                sub_status = ComplianceStatus.REVIEW
                sub_reason = (
                    f"Sub-rule #{i} is misconfigured (missing field/rule_type). "
                    "Manual review required."
                )
            else:
                # Look up evidence for this sub-rule's field
                sub_ev = evidence if (evidence and evidence.field == sub_req.field) else None
                ev_map = requirement.rule_definition.extra.get("evidence_map") or {}
                if sub_ev is None and sub_req.field in ev_map:
                    sub_ev = ev_map[sub_req.field]
                # Support multi-field evidence via extra["evidence_value"]
                if sub_ev is None and sub_def.extra.get("evidence_value") is not None:
                    from app.compliance.models import EvidenceSource
                    sub_ev = BidderEvidence(
                        bidder_id=bidder_id,
                        field=sub_req.field,
                        value=sub_def.extra["evidence_value"],
                        source=sub_def.extra.get("evidence_source", EvidenceSource.SYSTEM_DERIVED),
                        confidence=float(sub_def.extra.get("evidence_confidence", 1.0)),
                    )

                sub_result = self._evaluate_fn(sub_req, sub_ev)
                sub_status = sub_result.status
                sub_reason = sub_result.reason

            sub_statuses.append(sub_status)
            sub_reasons.append(f"[{i}:{sub_status}] {sub_reason}")

        # ------------------------------------------------------------------
        # Reduce with three-valued logic
        # ------------------------------------------------------------------
        if logical_op == "AND":
            combined = _and_reduce(sub_statuses)
        else:  # OR
            combined = _or_reduce(sub_statuses)

        combined_reason = (
            f"LOGICAL {logical_op} of {len(sub_rules)} sub-rule(s) → {combined.value}. "
            "Details: " + " | ".join(sub_reasons)
        )

        if combined == ComplianceStatus.PASS:
            return ComplianceResult.pass_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=combined_reason,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )
        elif combined == ComplianceStatus.FAIL:
            return ComplianceResult.fail_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=combined_reason,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )
        else:
            return ComplianceResult.review_result(
                requirement_id=rid,
                bidder_id=bidder_id,
                reason=combined_reason,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )
