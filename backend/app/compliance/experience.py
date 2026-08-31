"""
Phase 09 — Compliance Rule Engine
experience.py: Deterministic similar-work and technical experience rule evaluator.

Evaluation Contract
-------------------
Evaluates:
  Requirement (minimum_years, minimum_contracts, required_category, completion requirement)
  + BidderEvidence (contracts/projects list or summary experience values)
  → ComplianceResult (PASS / FAIL / REVIEW)

Principles
----------
1. Deterministic Python rules — NO LLM calls.
2. If category relevance cannot be determined confidently → REVIEW (do not guess).
3. Invalid or reversed dates (start > end, unparseable) → REVIEW.
4. Completion status verified when qualifying contracts are evaluated.
5. Exact boundary conditions: actual >= required → PASS; actual < required → FAIL.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Union

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.evaluator import LOW_CONFIDENCE_THRESHOLD, BaseEvaluator
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement
from app.compliance.operators import coerce_to_date

logger = logging.getLogger("app.compliance.experience")

_QUALIFYING_COMPLETION_STATUSES = {"COMPLETED", "COMPLETE", "SUCCESSFUL", "DELIVERED", "CLOSED"}
_DISQUALIFIED_COMPLETION_STATUSES = {"ONGOING", "TERMINATED", "FAILED", "INCOMPLETE", "CANCELLED"}
_VERIFIED_STATUSES = {"VERIFIED", "VALID", "APPROVED", "CONFIRMED", "PASSED"}
_FAILED_STATUSES = {"FAILED", "REJECTED", "INVALID", "FRAUDULENT"}
_UNCERTAIN_STATUSES = {"UNCERTAIN", "AMBIGUOUS", "UNKNOWN", "PENDING", "UNVERIFIED", "NEEDS_REVIEW"}


def _clean_token(v: Any) -> str:
    """Standardize string tokens for comparison."""
    if v is None:
        return ""
    if hasattr(v, "value"):
        v = v.value
    return str(v).strip().upper().replace("-", "_").replace(" ", "_")


def _categories_match(required: str, actual: str) -> bool:
    """Check if actual category matches required category deterministically."""
    r = _clean_token(required)
    a = _clean_token(actual)
    if not r or not a:
        return False
    if r == a:
        return True
    # Word prefix or subset match
    if r in a or a in r:
        return True
    return False


class ExperienceEvaluator(BaseEvaluator):
    """
    Evaluates bidder past performance, contracts, and years of experience.
    """

    @property
    def rule_type(self) -> RuleType:
        return RuleType.EXPERIENCE

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        req_id = requirement.requirement_id
        bidder_id = getattr(evidence, "bidder_id", req_id)
        field = requirement.field
        rule_def = requirement.rule_definition

        # ------------------------------------------------------------------
        # 1. Missing evidence check
        # ------------------------------------------------------------------
        if evidence is None or evidence.value is None:
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=f"No experience evidence provided for field '{field}'. Manual review required.",
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                required_value=rule_def.required_value,
            )

        # ------------------------------------------------------------------
        # 2. Check evidence confidence
        # ------------------------------------------------------------------
        if evidence.confidence < LOW_CONFIDENCE_THRESHOLD:
            return self._low_confidence_review(requirement, evidence)

        # ------------------------------------------------------------------
        # 3. Extract requirement specification parameters
        # ------------------------------------------------------------------
        # Parameters can be in rule_definition.extra or rule_definition.required_value
        req_dict: Dict[str, Any] = {}
        if isinstance(rule_def.required_value, dict):
            req_dict.update(rule_def.required_value)
        if isinstance(rule_def.extra, dict):
            req_dict.update(rule_def.extra)

        min_years = req_dict.get("minimum_years")
        min_contracts = req_dict.get("minimum_contracts")
        req_category = req_dict.get("required_category")
        require_completed = req_dict.get("require_completed", True)

        # If not structured dict, use required_value as scalar threshold
        if min_years is None and min_contracts is None and rule_def.required_value is not None:
            # Check field name to guess if it's years or count
            field_clean = _clean_token(field)
            if "YEAR" in field_clean:
                min_years = rule_def.required_value
            elif "COUNT" in field_clean or "CONTRACT" in field_clean or "PROJECT" in field_clean:
                min_contracts = rule_def.required_value
            else:
                # Default scalar to min_years if not specified
                min_years = rule_def.required_value

        # ------------------------------------------------------------------
        # 4. Handle Evidence Values
        # ------------------------------------------------------------------
        val = evidence.value

        # Case A: Evidence is a scalar number (e.g. 5 years or 3 projects)
        if isinstance(val, (int, float, Decimal)) or (isinstance(val, str) and val.strip().replace(".", "", 1).isdigit()):
            return self._evaluate_scalar(
                req_id, bidder_id, field, rule_def, val, min_years, min_contracts, evidence
            )

        # Case B: Evidence is a list of contract records or a single contract dict
        contracts: List[Dict[str, Any]] = []
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    contracts.append(item)
        elif isinstance(val, dict):
            # Check if dict represents summary or a single contract
            if "contracts" in val and isinstance(val["contracts"], list):
                contracts = [c for c in val["contracts"] if isinstance(c, dict)]
            else:
                contracts = [val]

        if not contracts:
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=f"Incomplete or malformed experience evidence format for field '{field}'.",
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=val,
            )

        # ------------------------------------------------------------------
        # 5. Process Contract Records
        # ------------------------------------------------------------------
        qualifying_contracts: List[Dict[str, Any]] = []
        total_verified_years = Decimal("0.0")
        has_uncertain_category = False
        has_invalid_dates = False
        date_error_msg = ""
        category_error_msg = ""

        for idx, contract in enumerate(contracts):
            cid = contract.get("contract_id") or contract.get("project_id") or f"Contract #{idx+1}"

            # 5a. Category & Relevance check
            cat = contract.get("category")
            relevance = _clean_token(contract.get("relevance") or contract.get("relevance_status"))

            if relevance in _UNCERTAIN_STATUSES or _clean_token(cat) in _UNCERTAIN_STATUSES:
                has_uncertain_category = True
                category_error_msg = f"Category relevance for '{cid}' is uncertain ({relevance or cat})."
                continue

            if req_category:
                req_cat_token = _clean_token(req_category)
                if relevance not in ("RELEVANT", "MATCH", "CONFIRMED"):
                    if not cat or not _categories_match(req_cat_token, str(cat)):
                        # Not a qualifying contract for this category
                        continue

            # 5b. Verification status check
            v_status = _clean_token(contract.get("verification_status") or "VERIFIED")
            if v_status in _FAILED_STATUSES:
                # Disqualified
                continue
            if v_status in _UNCERTAIN_STATUSES:
                has_uncertain_category = True
                category_error_msg = f"Verification status for '{cid}' is uncertain ({v_status})."
                continue

            # 5c. Completion status check
            if require_completed:
                comp_status = _clean_token(contract.get("completion_status") or "COMPLETED")
                if comp_status in _DISQUALIFIED_COMPLETION_STATUSES:
                    # Incomplete contract
                    continue

            # 5d. Date validity & duration calculation
            start_raw = contract.get("start_date")
            end_raw = contract.get("end_date")
            duration_val = contract.get("duration_years") or contract.get("duration")

            contract_years = Decimal("0.0")
            if duration_val is not None:
                try:
                    contract_years = Decimal(str(duration_val))
                except Exception:
                    has_invalid_dates = True
                    date_error_msg = f"Invalid duration value '{duration_val}' in {cid}."
            elif start_raw and end_raw:
                s_date = coerce_to_date(start_raw)
                e_date = coerce_to_date(end_raw)
                if s_date is None or e_date is None:
                    has_invalid_dates = True
                    date_error_msg = f"Unparseable contract dates (start: {start_raw}, end: {end_raw}) in {cid}."
                elif s_date > e_date:
                    has_invalid_dates = True
                    date_error_msg = f"Reversed contract dates: start {s_date} is after end {e_date} in {cid}."
                else:
                    days = (e_date - s_date).days
                    contract_years = Decimal(str(round(days / 365.25, 2)))
            elif contract.get("years") is not None:
                try:
                    contract_years = Decimal(str(contract["years"]))
                except Exception:
                    has_invalid_dates = True
                    date_error_msg = f"Invalid years value in {cid}."

            qualifying_contracts.append(contract)
            total_verified_years += contract_years

        # ------------------------------------------------------------------
        # 6. Branch on validation flags
        # ------------------------------------------------------------------
        # Invalid dates must trigger REVIEW
        if has_invalid_dates:
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=f"Date validity error in experience evidence: {date_error_msg}. Manual review required.",
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # Uncertain relevance must trigger REVIEW
        if has_uncertain_category and not qualifying_contracts:
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=f"Experience relevance cannot be determined confidently: {category_error_msg}. Manual review required.",
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # ------------------------------------------------------------------
        # 7. Evaluate Minimum Requirements
        # ------------------------------------------------------------------
        num_qualifying = len(qualifying_contracts)

        # If required_category was specified and 0 qualifying contracts found:
        if req_category and num_qualifying == 0:
            if has_uncertain_category:
                return ComplianceResult.review_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=f"Category relevance is uncertain for candidate experience records.",
                    evidence_reference=evidence.source_document,
                    rule_type=self.rule_type,
                    operator_used=rule_def.operator,
                )
            return ComplianceResult.fail_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"No qualifying contracts matched the required category '{req_category}' "
                    f"out of {len(contracts)} submitted contract(s)."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=[c.get("category") for c in contracts],
                required_value=req_category,
            )

        # Evaluate minimum contracts
        if min_contracts is not None:
            min_c = int(min_contracts)
            if num_qualifying < min_c:
                return ComplianceResult.fail_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=(
                        f"Insufficient qualifying contracts: found {num_qualifying} "
                        f"qualifying contract(s), required at least {min_c}."
                    ),
                    evidence_reference=evidence.source_document,
                    rule_type=self.rule_type,
                    operator_used=rule_def.operator,
                    actual_value=num_qualifying,
                    required_value=min_c,
                )

        # Evaluate minimum years
        if min_years is not None:
            min_y = Decimal(str(min_years))
            if total_verified_years < min_y:
                return ComplianceResult.fail_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=(
                        f"Insufficient experience: verified {total_verified_years} years, "
                        f"required at least {min_y} years."
                    ),
                    evidence_reference=evidence.source_document,
                    rule_type=self.rule_type,
                    operator_used=rule_def.operator,
                    actual_value=total_verified_years,
                    required_value=min_y,
                )

        # If uncertain category exists but we already satisfied both thresholds comfortably:
        # Note: per specification: "If relevance cannot be determined confidently -> REVIEW. Do not guess."
        # If any contract used to meet the threshold was ambiguous, we should review. But if qualifying contracts
        # are definitively verified, it passes.
        return ComplianceResult.pass_result(
            requirement_id=req_id,
            bidder_id=bidder_id,
            reason=(
                f"Experience requirement satisfied: {num_qualifying} qualifying contract(s) "
                f"totalling {total_verified_years} verified years."
            ),
            evidence_reference=evidence.source_document,
            rule_type=self.rule_type,
            operator_used=rule_def.operator,
            actual_value={"contracts": num_qualifying, "years": total_verified_years},
            required_value=req_dict or rule_def.required_value,
        )

    # ------------------------------------------------------------------
    # Helper: Evaluate scalar evidence value (e.g. integer years or count)
    # ------------------------------------------------------------------
    def _evaluate_scalar(
        self,
        req_id,
        bidder_id,
        field: str,
        rule_def,
        actual_val: Any,
        min_years: Optional[Any],
        min_contracts: Optional[Any],
        evidence: BidderEvidence,
    ) -> ComplianceResult:
        actual_num = Decimal(str(actual_val))
        threshold_num = Decimal(str(min_years if min_years is not None else min_contracts or 0))

        if actual_num >= threshold_num:
            return ComplianceResult.pass_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Experience requirement for '{field}' satisfied: "
                    f"verified {actual_num} >= required {threshold_num}."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=actual_num,
                required_value=threshold_num,
            )
        else:
            return ComplianceResult.fail_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Insufficient experience for '{field}': "
                    f"verified {actual_num} < required {threshold_num}."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=actual_num,
                required_value=threshold_num,
            )
