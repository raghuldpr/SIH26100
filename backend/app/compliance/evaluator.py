"""
Phase 09 — Compliance Rule Engine
evaluator.py: BaseEvaluator ABC and EvaluatorRegistry.

Design:
- BaseEvaluator defines the single contract: evaluate(requirement, evidence)
- All concrete evaluators inherit from it and are stateless.
- EvaluatorRegistry maps RuleType → evaluator instance (singleton per type).
- Low-confidence evidence (< LOW_CONFIDENCE_THRESHOLD) is flagged in the
  result reason but does NOT automatically override a PASS — that policy
  decision belongs to the engine layer.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Dict, Optional

from app.compliance.enums import ComplianceStatus, RuleType
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement

logger = logging.getLogger("app.compliance.evaluator")

# Evidence confidence below this threshold will be noted in result reasons.
LOW_CONFIDENCE_THRESHOLD: float = 0.5


class BaseEvaluator(ABC):
    """
    Abstract base for all compliance rule evaluators.

    Contract
    --------
    • evaluate() MUST return a ComplianceResult — never raise.
    • Missing / None evidence MUST produce REVIEW, never silent PASS.
    • All reasons MUST be human-readable and deterministic.
    """

    @property
    @abstractmethod
    def rule_type(self) -> RuleType:
        """The RuleType this evaluator handles."""

    @abstractmethod
    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        """
        Evaluate *requirement* against *evidence*.

        Parameters
        ----------
        requirement:
            The normalised tender requirement to check.
        evidence:
            The bidder's evidence for the relevant field, or None if absent.

        Returns
        -------
        ComplianceResult
            A fully populated result including status, reason, and audit fields.
        """

    # ------------------------------------------------------------------
    # Helper: build a REVIEW result for missing evidence
    # ------------------------------------------------------------------

    def _missing_evidence_review(
        self,
        requirement: Requirement,
        bidder_id,
    ) -> ComplianceResult:
        """Standard REVIEW result when no evidence is available."""
        return ComplianceResult.review_result(
            requirement_id=requirement.requirement_id,
            bidder_id=bidder_id,
            reason=(
                f"No evidence provided for field '{requirement.field}'. "
                "Manual review required."
            ),
            rule_type=self.rule_type,
            operator_used=requirement.rule_definition.operator,
        )

    # ------------------------------------------------------------------
    # Helper: build a REVIEW result for low-confidence evidence
    # ------------------------------------------------------------------

    def _low_confidence_review(
        self,
        requirement: Requirement,
        evidence: BidderEvidence,
        *,
        extra_reason: str = "",
    ) -> ComplianceResult:
        """REVIEW result when evidence confidence is below the threshold."""
        suffix = f"  {extra_reason}" if extra_reason else ""
        return ComplianceResult.review_result(
            requirement_id=requirement.requirement_id,
            bidder_id=evidence.bidder_id,
            reason=(
                f"Evidence for '{requirement.field}' has low extraction confidence "
                f"({evidence.confidence:.2f} < {LOW_CONFIDENCE_THRESHOLD:.2f}). "
                f"Manual review required.{suffix}"
            ),
            evidence_reference=evidence.source_document,
            rule_type=self.rule_type,
            operator_used=requirement.rule_definition.operator,
            actual_value=evidence.value,
            required_value=requirement.rule_definition.required_value,
        )


# ---------------------------------------------------------------------------
# EvaluatorRegistry
# ---------------------------------------------------------------------------

class EvaluatorRegistry:
    """
    Thread-safe mapping of RuleType → BaseEvaluator.

    Usage::

        registry = EvaluatorRegistry()
        registry.register(NumericEvaluator())
        evaluator = registry.get(RuleType.NUMERIC)
    """

    def __init__(self) -> None:
        self._registry: Dict[RuleType, BaseEvaluator] = {}

    def register(self, evaluator: BaseEvaluator) -> None:
        """Register an evaluator.  Overwrites any existing entry for the same type."""
        self._registry[evaluator.rule_type] = evaluator
        logger.debug("Registered evaluator for rule_type=%s", evaluator.rule_type)

    def get(self, rule_type: RuleType) -> Optional[BaseEvaluator]:
        """Return the evaluator for *rule_type*, or None if not registered."""
        return self._registry.get(rule_type)

    def get_or_raise(self, rule_type: RuleType) -> BaseEvaluator:
        """Return the evaluator or raise KeyError."""
        ev = self._registry.get(rule_type)
        if ev is None:
            raise KeyError(
                f"No evaluator registered for RuleType.{rule_type}. "
                f"Registered: {list(self._registry.keys())}"
            )
        return ev

    @property
    def supported_rule_types(self) -> list[RuleType]:
        return list(self._registry.keys())
