"""
Phase 09 — Compliance Rule Engine
engine.py: ComplianceEngine — the public entry point.

Responsibilities:
1. Build and own the EvaluatorRegistry populated with all concrete evaluators.
2. Validate that requirement and evidence field names match before dispatching.
3. Dispatch to the correct evaluator based on requirement.rule_type.
4. Catch any unexpected exceptions and return a REVIEW result rather than
   letting them propagate.
5. Log all evaluation outcomes for auditability.

Design:
- ComplianceEngine is instantiated once (module-level singleton `engine`).
- It is stateless after init — safe for concurrent use.
- No LLM calls are made. Ever.
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from app.compliance.boolean import BooleanEvaluator
from app.compliance.conditional import ConditionalEvaluator
from app.compliance.dates import DateEvaluator
from app.compliance.documents import DocumentEvaluator
from app.compliance.enums import ComplianceStatus, RuleType
from app.compliance.evaluator import EvaluatorRegistry
from app.compliance.experience import ExperienceEvaluator
from app.compliance.exemptions import ExemptionEvaluator
from app.compliance.logical import LogicalEvaluator
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement
from app.compliance.numeric import NumericEvaluator

logger = logging.getLogger("app.compliance.engine")


def _build_default_registry() -> EvaluatorRegistry:
    """Build and return the default evaluator registry."""
    registry = EvaluatorRegistry()
    registry.register(NumericEvaluator())
    registry.register(BooleanEvaluator())
    registry.register(DateEvaluator())
    registry.register(DocumentEvaluator())
    registry.register(ExperienceEvaluator())
    registry.register(ExemptionEvaluator())
    registry.register(LogicalEvaluator())      # evaluate_fn wired after engine init
    registry.register(ConditionalEvaluator())  # evaluate_fn wired after engine init
    return registry


class ComplianceEngine:
    """
    Deterministic compliance evaluation engine.

    Usage::

        from app.compliance.engine import engine  # module-level singleton

        result = engine.evaluate(requirement, evidence)
        print(result.status, result.reason)
    """

    def __init__(self, registry: Optional[EvaluatorRegistry] = None) -> None:
        self._registry = registry or _build_default_registry()
        # Wire the engine's evaluate callable into evaluators that need
        # recursive dispatch (LogicalEvaluator, ConditionalEvaluator).
        self._wire_recursive_evaluators()
        logger.info(
            "ComplianceEngine initialised with evaluators: %s",
            self._registry.supported_rule_types,
        )

    def _wire_recursive_evaluators(self) -> None:
        """Inject self.evaluate into evaluators that recursively dispatch sub-rules."""
        from app.compliance.logical import LogicalEvaluator as LE
        from app.compliance.conditional import ConditionalEvaluator as CE
        logical = self._registry.get(RuleType.LOGICAL)
        if isinstance(logical, LE):
            logical.set_evaluate_fn(self.evaluate)
        conditional = self._registry.get(RuleType.CONDITIONAL)
        if isinstance(conditional, CE):
            conditional.set_evaluate_fn(self.evaluate)

    # ------------------------------------------------------------------
    # Primary public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
        *,
        exemptions: Optional[List[Any]] = None,
        evidence_map: Optional[dict[str, BidderEvidence]] = None,
    ) -> ComplianceResult:
        """
        Evaluate *requirement* against *evidence*, applying any supplied *exemptions*.

        Parameters
        ----------
        requirement:
            Normalised tender requirement.
        evidence:
            Bidder's evidence for the relevant field, or None if absent.
        exemptions:
            Optional list of ExemptionRule models or dictionaries.
        evidence_map:
            Optional map of field name -> BidderEvidence used to resolve
            exemption conditions across different fields.

        Returns
        -------
        ComplianceResult
            Always returns a result — never raises.
        """
        try:
            return self._evaluate_safe(requirement, evidence, exemptions=exemptions, evidence_map=evidence_map)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "Unexpected error evaluating requirement=%s bidder=%s: %s",
                requirement.requirement_id,
                getattr(evidence, "bidder_id", "unknown"),
                exc,
            )
            bidder_id = getattr(evidence, "bidder_id", requirement.requirement_id)
            return ComplianceResult.review_result(
                requirement_id=requirement.requirement_id,
                bidder_id=bidder_id,
                reason=(
                    f"Internal evaluation error for field '{requirement.field}': "
                    f"{type(exc).__name__}. Manual review required."
                ),
                rule_type=requirement.rule_type,
            )

    def evaluate_batch(
        self,
        requirements: List[Requirement],
        evidence_map: dict[str, BidderEvidence],
        *,
        exemptions: Optional[List[Any]] = None,
    ) -> List[ComplianceResult]:
        """
        Evaluate multiple requirements against an evidence map and optional exemptions.

        Parameters
        ----------
        requirements:
            List of normalised requirements to evaluate.
        evidence_map:
            Mapping of field name → BidderEvidence.
        exemptions:
            Optional list of ExemptionRule models or dictionaries.

        Returns
        -------
        List[ComplianceResult]
            One result per requirement, in the same order.
        """
        results = []
        for req in requirements:
            ev = evidence_map.get(req.field)
            results.append(self.evaluate(req, ev, exemptions=exemptions, evidence_map=evidence_map))
        return results

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _evaluate_safe(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
        *,
        exemptions: Optional[List[Any]] = None,
        evidence_map: Optional[dict[str, BidderEvidence]] = None,
    ) -> ComplianceResult:
        """Core dispatch — called inside try/except in evaluate()."""
        bidder_id = getattr(evidence, "bidder_id", requirement.requirement_id)

        # 1. Check for supplied exemptions
        all_exemptions: List[Any] = []
        if exemptions:
            all_exemptions.extend(exemptions)
        req_extra_exemptions = requirement.rule_definition.extra.get("exemptions")
        if req_extra_exemptions and isinstance(req_extra_exemptions, list):
            all_exemptions.extend(req_extra_exemptions)

        if all_exemptions:
            from app.compliance.exemptions import ExemptionEvaluator
            exemption_eval = self._registry.get(RuleType.EXEMPTION)
            if isinstance(exemption_eval, ExemptionEvaluator):
                merged_map: dict[str, BidderEvidence] = {}
                if evidence_map:
                    merged_map.update(evidence_map)
                if evidence:
                    merged_map[evidence.field] = evidence

                exemption_res = exemption_eval.check_exemptions_for_requirement(
                    requirement, all_exemptions, merged_map, bidder_id
                )
                if exemption_res is not None:
                    # Exemption was triggered (EXEMPT) or uncertain (REVIEW)
                    return exemption_res

        # 2. Propagate evidence_map to requirement.rule_definition.extra for logical/conditional evaluators
        if evidence_map:
            if not isinstance(requirement.rule_definition.extra, dict):
                requirement.rule_definition.extra = {}
            requirement.rule_definition.extra.setdefault("evidence_map", evidence_map)

        # 3. Dispatch to registered rule_type evaluator
        rule_type = requirement.rule_type


        evaluator = self._registry.get(rule_type)
        if evaluator is None:
            logger.warning(
                "No evaluator registered for rule_type=%s; returning REVIEW.",
                rule_type,
            )
            return ComplianceResult.review_result(
                requirement_id=requirement.requirement_id,
                bidder_id=bidder_id,
                reason=(
                    f"No evaluator is registered for rule type '{rule_type}'. "
                    "Manual review required."
                ),
                rule_type=rule_type,
            )

        result = evaluator.evaluate(requirement, evidence)
        logger.debug(
            "Evaluated requirement=%s field=%s status=%s",
            requirement.requirement_id,
            requirement.field,
            result.status,
        )
        return result


    @property
    def supported_rule_types(self) -> List[RuleType]:
        """List of rule types that have registered evaluators."""
        return self._registry.supported_rule_types


# ---------------------------------------------------------------------------
# Module-level singleton — import this for normal usage
# ---------------------------------------------------------------------------
engine = ComplianceEngine()
