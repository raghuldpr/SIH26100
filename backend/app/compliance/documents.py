"""
Phase 09 — Compliance Rule Engine
documents.py: Deterministic mandatory and optional document compliance evaluator.

Evaluation Contract
-------------------
Evaluates:
  Requirement (Document requirement: mandatory flag, document_type, presence)
  + BidderEvidence (Document evidence: document_type, verification_status, confidence)
  → ComplianceResult (PASS / FAIL / REVIEW / EXEMPT / NOT_APPLICABLE)

Evidence States
---------------
1. Document present and verified (status in VERIFIED / VALID, conf >= 0.5, matching type)
   → PASS
2. Document definitely absent
   - If mandatory: FAIL
   - If optional:  NOT_APPLICABLE (collapses to PASS externally)
3. Document exists but cannot be confidently identified or verified
   (verification_status in AMBIGUOUS / PENDING / UNVERIFIED, or confidence < 0.5)
   → REVIEW
4. Document verification failure (status in FAILED / INVALID / REJECTED / EXPIRED)
   → FAIL
5. Wrong document type (submitted document does not match required type)
   → FAIL
6. Exemption applicable (bidder marked exempt or exemption certificate verified)
   → EXEMPT (collapses to PASS externally)
7. Multiple candidate documents (evaluates list; selects best matching verified document)

No LLM is called at any point.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.compliance.evaluator import LOW_CONFIDENCE_THRESHOLD, BaseEvaluator
from app.compliance.models import BidderEvidence, ComplianceResult, Requirement

logger = logging.getLogger("app.compliance.documents")

# Verification status normalization sets
_VERIFIED_STATUSES = {
    "VERIFIED", "VALID", "PASSED", "PASS", "SUCCESS", "APPROVED", "CONFIRMED", "TRUE"
}
_FAILED_STATUSES = {
    "FAILED", "FAIL", "INVALID", "REJECTED", "TAMPERED", "EXPIRED", "FRAUDULENT", "CORRUPTED"
}
_AMBIGUOUS_STATUSES = {
    "AMBIGUOUS", "UNCERTAIN", "PENDING", "UNVERIFIED", "NEEDS_REVIEW", "INCONCLUSIVE", "PARTIAL"
}
_ABSENT_STATUSES = {
    "ABSENT", "NOT_FOUND", "MISSING", "NONE", "NULL", "FALSE"
}
_EXEMPT_STATUSES = {
    "EXEMPT", "EXEMPTED", "WAIVED", "NOT_APPLICABLE"
}


def _normalize_token(val: Any) -> str:
    """Normalize string tokens (uppercase, underscores, trimmed, stripped extension)."""
    if val is None:
        return ""
    if hasattr(val, "value"):
        val = val.value
    s = str(val).strip().upper().replace("-", "_").replace(" ", "_")
    for ext in (".PDF", ".JPG", ".JPEG", ".PNG", ".DOC", ".DOCX"):
        if s.endswith(ext):
            s = s[:-len(ext)]
    return s


def _doc_types_match(required: str, actual: str) -> bool:
    """
    Check if actual document type matches the required type.
    Handles common suffixes e.g. GST == GST_CERTIFICATE, PAN == PAN_CARD.
    """
    req = _normalize_token(required)
    act = _normalize_token(actual)

    if not req or not act:
        return False
    if req == act:
        return True

    suffixes = ("_CERTIFICATE", "_CARD", "_DOCUMENT", "_DOC", "_PDF", "_COPY", "_RECEIPT")
    
    # Strip suffixes repeatedly
    req_core = req
    changed = True
    while changed:
        changed = False
        for s in suffixes:
            if req_core.endswith(s):
                req_core = req_core[:-len(s)]
                changed = True
                break

    act_core = act
    changed = True
    while changed:
        changed = False
        for s in suffixes:
            if act_core.endswith(s):
                act_core = act_core[:-len(s)]
                changed = True
                break

    if req_core and act_core and req_core == act_core:
        return True

    if req_core and act_core and (req_core in act_core or act_core in req_core):
        return True

    return False



class DocumentEvaluator(BaseEvaluator):
    """
    Evaluates document presence, verification status, and exemption for tender requirements.
    """

    @property
    def rule_type(self) -> RuleType:
        return RuleType.DOCUMENT_PRESENCE

    def evaluate(
        self,
        requirement: Requirement,
        evidence: Optional[BidderEvidence],
    ) -> ComplianceResult:
        req_id = requirement.requirement_id
        bidder_id = getattr(evidence, "bidder_id", req_id)
        mandatory = requirement.mandatory
        rule_def = requirement.rule_definition

        # ------------------------------------------------------------------
        # 1. Resolve required document type
        # ------------------------------------------------------------------
        required_type = (
            rule_def.required_value
            or rule_def.extra.get("document_type")
            or requirement.field
        )
        required_type_str = _normalize_token(required_type)

        # ------------------------------------------------------------------
        # 2. Check for missing evidence (definitely absent)
        # ------------------------------------------------------------------
        if evidence is None or evidence.value is None:
            if mandatory:
                return ComplianceResult.fail_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=(
                        f"Mandatory document '{requirement.field}' (type: {required_type_str}) "
                        "is definitely absent. No evidence submitted."
                    ),
                    rule_type=self.rule_type,
                    operator_used=rule_def.operator,
                    required_value=required_type_str,
                )
            else:
                return ComplianceResult.not_applicable_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=(
                        f"Optional document '{requirement.field}' was not submitted. "
                        "Requirement is NOT_APPLICABLE."
                    ),
                    rule_type=self.rule_type,
                )

        # ------------------------------------------------------------------
        # 3. Normalise candidate document items
        # ------------------------------------------------------------------
        # Evidence value can be:
        # - list of dicts (multiple candidate documents)
        # - single dict
        # - boolean (True/False)
        # - string (document name or status)
        candidates: List[Dict[str, Any]] = []
        raw_val = evidence.value

        if isinstance(raw_val, list):
            for item in raw_val:
                if isinstance(item, dict):
                    candidates.append(item)
                elif isinstance(item, str):
                    candidates.append({"document_name": item, "document_type": item})
        elif isinstance(raw_val, dict):
            candidates.append(raw_val)
        elif isinstance(raw_val, bool):
            if not raw_val:
                candidates.append({"verification_status": "ABSENT"})
            else:
                candidates.append({
                    "document_type": required_type_str,
                    "verification_status": "VERIFIED",
                    "confidence": evidence.confidence,
                })
        elif isinstance(raw_val, str):
            token = _normalize_token(raw_val)
            if token in _ABSENT_STATUSES:
                candidates.append({"verification_status": "ABSENT"})
            elif token in _EXEMPT_STATUSES:
                candidates.append({"is_exempt": True, "verification_status": "EXEMPT"})
            else:
                candidates.append({
                    "document_name": raw_val,
                    "document_type": raw_val,
                    "verification_status": "VERIFIED",
                })
        else:
            candidates.append({
                "document_name": str(raw_val),
                "verification_status": "VERIFIED",
            })

        # ------------------------------------------------------------------
        # 4. Check for statutory exemption
        # ------------------------------------------------------------------
        for cand in candidates:
            if cand.get("is_exempt") is True or _normalize_token(cand.get("verification_status")) in _EXEMPT_STATUSES:
                exemption_reason = cand.get("exemption_reason") or "Valid statutory exemption claimed and recorded"
                return ComplianceResult.exempt_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=(
                        f"Bidder is EXEMPT from requirement '{requirement.field}': {exemption_reason}."
                    ),
                    evidence_reference=evidence.source_document or cand.get("source_document"),
                    rule_type=self.rule_type,
                )

        # ------------------------------------------------------------------
        # 5. Evaluate candidates against required document type
        # ------------------------------------------------------------------
        matching_candidates: List[Dict[str, Any]] = []
        wrong_type_candidates: List[str] = []
        has_absent = False

        for cand in candidates:
            v_status = _normalize_token(cand.get("verification_status"))
            if v_status in _ABSENT_STATUSES:
                has_absent = True
                continue

            cand_type = (
                cand.get("document_type")
                or cand.get("type")
                or cand.get("document_name")
                or ""
            )
            cand_type_str = _normalize_token(cand_type)

            # If no type specified on candidate, inherit field or assume candidate matches
            if not cand_type_str or _doc_types_match(required_type_str, cand_type_str):
                matching_candidates.append(cand)
            else:
                wrong_type_candidates.append(cand_type_str)

        # If evidence was explicitly absent and no matching docs found
        if has_absent and not matching_candidates:
            if mandatory:
                return ComplianceResult.fail_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=f"Mandatory document '{requirement.field}' is confirmed absent.",
                    evidence_reference=evidence.source_document,
                    rule_type=self.rule_type,
                    operator_used=rule_def.operator,
                )
            else:
                return ComplianceResult.not_applicable_result(
                    requirement_id=req_id,
                    bidder_id=bidder_id,
                    reason=f"Optional document '{requirement.field}' is absent. NOT_APPLICABLE.",
                    rule_type=self.rule_type,
                )

        # If there were candidates submitted, but NONE matched the required type:
        if not matching_candidates and wrong_type_candidates:
            found_str = ", ".join(wrong_type_candidates)
            return ComplianceResult.fail_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Submitted document type(s) [{found_str}] do not match "
                    f"the required document type '{required_type_str}' for field '{requirement.field}'."
                ),
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=wrong_type_candidates,
                required_value=required_type_str,
            )

        if not matching_candidates:
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=f"No valid candidate documents found for field '{requirement.field}'.",
                evidence_reference=evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
            )

        # ------------------------------------------------------------------
        # 6. Evaluate matching candidates for verification and confidence
        # ------------------------------------------------------------------
        verified_candidates: List[Dict[str, Any]] = []
        failed_candidates: List[Dict[str, Any]] = []
        ambiguous_candidates: List[Dict[str, Any]] = []

        for cand in matching_candidates:
            # Check confidence on candidate or evidence
            cand_conf = cand.get("confidence")
            if cand_conf is None:
                cand_conf = evidence.confidence
            else:
                try:
                    cand_conf = float(cand_conf)
                except (ValueError, TypeError):
                    cand_conf = evidence.confidence

            cand_v_status = _normalize_token(cand.get("verification_status") or "VERIFIED")

            if cand_conf < LOW_CONFIDENCE_THRESHOLD:
                ambiguous_candidates.append(cand)
            elif cand_v_status in _VERIFIED_STATUSES:
                verified_candidates.append(cand)
            elif cand_v_status in _FAILED_STATUSES:
                failed_candidates.append(cand)
            elif cand_v_status in _AMBIGUOUS_STATUSES:
                ambiguous_candidates.append(cand)
            else:
                # Default unknown status to ambiguous
                ambiguous_candidates.append(cand)

        # At least one candidate verified with high confidence -> PASS
        if verified_candidates:
            best_cand = verified_candidates[0]
            doc_name = (
                best_cand.get("document_name")
                or evidence.source_document
                or best_cand.get("document_type")
                or requirement.field
            )
            return ComplianceResult.pass_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Document '{requirement.field}' (type: {required_type_str}) is present "
                    f"and verified ({doc_name})."
                ),
                evidence_reference=best_cand.get("source_document") or evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=best_cand.get("document_type") or required_type_str,
                required_value=required_type_str,
            )

        # If any matching candidate is ambiguous / pending and none verified -> REVIEW
        if ambiguous_candidates:
            amb_cand = ambiguous_candidates[0]
            status_desc = amb_cand.get("verification_status") or "low confidence"
            return ComplianceResult.review_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Document for '{requirement.field}' exists but cannot be confidently "
                    f"identified or verified (status: {status_desc}, confidence: {evidence.confidence:.2f}). "
                    "Manual review required."
                ),
                evidence_reference=amb_cand.get("source_document") or evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=amb_cand.get("document_type") or requirement.field,
                required_value=required_type_str,
            )

        # All matching candidates failed verification -> FAIL
        if failed_candidates:
            fail_cand = failed_candidates[0]
            fail_reason = fail_cand.get("rejection_reason") or fail_cand.get("verification_status") or "verification failed"
            return ComplianceResult.fail_result(
                requirement_id=req_id,
                bidder_id=bidder_id,
                reason=(
                    f"Document verification failed for '{requirement.field}': {fail_reason}."
                ),
                evidence_reference=fail_cand.get("source_document") or evidence.source_document,
                rule_type=self.rule_type,
                operator_used=rule_def.operator,
                actual_value=fail_cand.get("document_type") or requirement.field,
                required_value=required_type_str,
            )

        # Fallback
        return ComplianceResult.review_result(
            requirement_id=req_id,
            bidder_id=bidder_id,
            reason=f"Unable to deterministically evaluate document requirement '{requirement.field}'.",
            evidence_reference=evidence.source_document,
            rule_type=self.rule_type,
            operator_used=rule_def.operator,
        )
