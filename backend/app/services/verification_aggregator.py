"""
Phase 12.6 — Verification Result Aggregation, Final Compliance & Risk Decision
services/verification_aggregator.py: Deterministic, fail-closed aggregation of
individual agent results into requirement-level evaluations, unified compliance verdicts,
and explainable risk assessments.
"""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from app.schemas.verification import (
    DEFAULT_VERIFICATION_AGENTS,
    AgentConfidenceItem,
    AgentStatusEnum,
    AppliedPolicyRule,
    CrossVerificationCheckItem,
    CrossVerificationValueItem,
    ForensicAnomalyItem,
    ForensicDocumentResult,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    PolicyFindingItem,
    OverallComplianceEnum,
    RequirementComplianceEnum,
    RequirementConfidenceItem,
    RequirementEvaluation,
    RiskLevelEnum,
    StructuredEvidenceItem,
    UnresolvedConfidenceItem,
    VerificationComplianceSummary,
    VerificationConfidenceBreakdown,
    VerificationCrossVerification,
    VerificationDecisionEnum,
    VerificationDocumentForensics,
    VerificationDocumentSimilarity,
    VerificationCompliancePolicy,
    VerificationResponse,
    VerificationRiskAssessment,
    VerificationStatusEnum,
    normalize_agent_status,
)
from app.services.document_similarity_service import document_similarity_service

logger = logging.getLogger("app.services.verification_aggregator")

# Critical agents whose execution is mandatory for full qualification
CRITICAL_AGENTS: Set[str] = {
    "GST_AGENT",
    "PAN_AGENT",
    "FINANCIAL_AGENT",
    "EXPERIENCE_AGENT",
    "DOCUMENT_FORENSICS_AGENT",
    "FINAL_COMPLIANCE_AGENT",
}

POSITIVE_STATUSES: Set[str] = {"PASS", "VERIFIED", "QUALIFIED", "SUCCESS"}
NEGATIVE_STATUSES: Set[str] = {"FAIL", "FAILED", "NOT_QUALIFIED", "REJECTED"}
UNVERIFIED_STATUSES: Set[str] = {"NOT_VERIFIED", "UNVERIFIED", "UNRESOLVED"}
PARTIAL_STATUSES: Set[str] = {"PARTIAL", "WARNING", "REVIEW", "CONDITIONALLY_QUALIFIED"}
ERROR_STATUSES: Set[str] = {"ERROR", "NOT_EXECUTED", "INCONCLUSIVE", "SKIPPED", "UNKNOWN", "NOT_APPLICABLE"}

# Patterns indicating critical risk conditions
CRITICAL_FORGERY_PATTERNS = [
    re.compile(r"forg(ery|ed)", re.IGNORECASE),
    re.compile(r"tamper(ed|ing)", re.IGNORECASE),
    re.compile(r"alter(ed|ation)", re.IGNORECASE),
    re.compile(r"manipulat(ed|ion)", re.IGNORECASE),
    re.compile(r"fraud", re.IGNORECASE),
]

CRITICAL_ENTITY_PATTERNS = [
    re.compile(r"mismatch", re.IGNORECASE),
    re.compile(r"identity conflict", re.IGNORECASE),
    re.compile(r"shell company", re.IGNORECASE),
    re.compile(r"blacklisted", re.IGNORECASE),
    re.compile(r"debarred", re.IGNORECASE),
]

CRITICAL_STATUTORY_PATTERNS = [
    re.compile(r"cancel(led|ation)", re.IGNORECASE),
    re.compile(r"inactiv(e|ity)", re.IGNORECASE),
    re.compile(r"suspend(ed|sion)", re.IGNORECASE),
    re.compile(r"invalid", re.IGNORECASE),
    re.compile(r"revoked", re.IGNORECASE),
]

CRITICAL_FINANCIAL_PATTERNS = [
    re.compile(r"insolven(t|cy)", re.IGNORECASE),
    re.compile(r"negative net worth", re.IGNORECASE),
    re.compile(r"bankrupt", re.IGNORECASE),
    re.compile(r"npa", re.IGNORECASE),
    re.compile(r"major discrepancy", re.IGNORECASE),
]


class VerificationResultAggregator:
    """
    Deterministic aggregation layer that validates agent results, performs requirement-level
    evaluations, computes overall compliance, conducts explainable risk assessment,
    and preserves complete provenance.
    """

    def aggregate(
        self,
        n8n_resp: N8nVerificationResponse,
        payload: Optional[N8nVerificationPayload] = None,
        tender_id: Optional[uuid.UUID] = None,
        bidder_id: Optional[uuid.UUID] = None,
    ) -> VerificationResponse:
        """
        Synthesizes an n8n Master Orchestrator response and outgoing payload
        into a finalized, strongly typed VerificationResponse.
        """
        # 1. Resolve entity UUIDs
        t_uuid = tender_id
        if not t_uuid and payload and payload.tender_id:
            try:
                t_uuid = uuid.UUID(str(payload.tender_id))
            except Exception:
                t_uuid = uuid.uuid4()
        elif not t_uuid and n8n_resp.tender_id:
            try:
                t_uuid = uuid.UUID(str(n8n_resp.tender_id))
            except Exception:
                t_uuid = uuid.uuid4()
        if not t_uuid:
            t_uuid = uuid.uuid4()

        b_uuid = bidder_id
        if not b_uuid and payload and payload.bidder_id:
            try:
                b_uuid = uuid.UUID(str(payload.bidder_id))
            except Exception:
                b_uuid = uuid.uuid4()
        elif not b_uuid and n8n_resp.bidder_id:
            try:
                b_uuid = uuid.UUID(str(n8n_resp.bidder_id))
            except Exception:
                b_uuid = uuid.uuid4()
        if not b_uuid:
            b_uuid = uuid.uuid4()

        verification_id = n8n_resp.verification_id or (payload.verification_id if payload else f"VER-{uuid.uuid4().hex[:8].upper()}")
        request_id = n8n_resp.request_id or (payload.request_id if payload else f"REQ-VER-{uuid.uuid4().hex[:8].upper()}")
        bidder_name = n8n_resp.bidder_name or (payload.bidder_name if payload else f"Bidder-{str(b_uuid)[:8]}")

        # 2. Validate, Normalize & Deduplicate Agent Results (Untrusted Input Boundary)
        seen_agents: Set[str] = set()
        deduped_results: List[N8nAgentResult] = []

        for raw_agent in n8n_resp.agent_results:
            try:
                if isinstance(raw_agent, dict):
                    agent_obj = N8nAgentResult.model_validate(raw_agent)
                else:
                    agent_obj = raw_agent

                # Enforce confidence boundary validation [0.0, 1.0] if provided
                if agent_obj.confidence is not None and not (0.0 <= agent_obj.confidence <= 1.0):
                    logger.warning(f"[aggregator] Rejected agent result with invalid confidence: {agent_obj.confidence}")
                    continue
            except Exception as exc:
                logger.warning(f"[aggregator] Rejected malformed agent result: {exc}")
                continue

            name = (agent_obj.agent or agent_obj.agent_name or "").strip().upper()
            if not name:
                continue
            if name in seen_agents:
                logger.warning(f"[aggregator-dedup] Duplicate result for agent '{name}' ignored to prevent double-counting.")
                continue
            seen_agents.add(name)

            # Preserve metadata & IDs onto result
            enriched_agent = agent_obj.model_copy()
            enriched_agent.agent = name
            enriched_agent.agent_id = name
            enriched_agent.agent_name = agent_obj.agent_name or name
            enriched_agent.verification_id = verification_id
            enriched_agent.tender_id = str(t_uuid)
            enriched_agent.bidder_id = str(b_uuid)
            if not getattr(enriched_agent, "result", None):
                enriched_agent.result = enriched_agent.decision
            if not getattr(enriched_agent, "summary", None):
                enriched_agent.summary = enriched_agent.reason
            if isinstance(agent_obj.evidence, (dict, list)):
                enriched_agent.execution_metadata["raw_evidence"] = agent_obj.evidence
            enriched_agent.evidence = self._build_agent_evidence(name, agent_obj.evidence, payload)
            deduped_results.append(enriched_agent)

        # 3. Detect Missing Required Agents (Flag as NOT_EXECUTED / UNKNOWN)
        required_agents = (
            payload.required_agents
            if payload and payload.required_agents
            else list(DEFAULT_VERIFICATION_AGENTS)
        )
        for req_agent in required_agents:
            norm_name = req_agent.strip().upper()
            if norm_name not in seen_agents:
                missing_result = N8nAgentResult(
                    agent=norm_name,
                    agent_id=norm_name,
                    agent_name=norm_name,
                    status="NOT_EXECUTED",
                    normalized_status="NOT_APPLICABLE",
                    verification_id=verification_id,
                    tender_id=str(t_uuid),
                    bidder_id=str(b_uuid),
                    confidence=0.0,
                    decision="NOT_QUALIFIED",
                    result="NOT_QUALIFIED",
                    evidence=[],
                    issues=[f"Required agent '{norm_name}' was not executed or returned no results."],
                    findings=[f"Required agent '{norm_name}' was not executed or returned no results."],
                    errors=[f"Required agent '{norm_name}' was not executed or returned no results."],
                    risk_level="HIGH",
                    reason="Required agent was not executed or omitted from workflow output.",
                    summary="Required agent was not executed or omitted from workflow output.",
                    execution_metadata={"missing": True},
                    timestamp=datetime.now(timezone.utc).isoformat(),
                )
                deduped_results.append(missing_result)
                seen_agents.add(norm_name)

        agent_map: Dict[str, N8nAgentResult] = {ag.agent: ag for ag in deduped_results}

        # 4. Requirement-Level Evaluation (Section 3)
        requirements_eval: List[RequirementEvaluation] = []
        if payload and payload.tender_requirements:
            for req in payload.tender_requirements:
                eval_item = self._evaluate_single_requirement(
                    req=req,
                    evidence_list=payload.bidder_evidence or [],
                    agent_map=agent_map,
                )
                requirements_eval.append(eval_item)

        # 5. Deterministic Overall Compliance Decision (Section 4)
        failed_checks: List[str] = []
        critical_errors: List[str] = []
        warnings: List[str] = []
        inconclusive_checks: List[str] = []
        reasons: List[str] = []

        # Pull pre-existing n8n notifications
        for fr in n8n_resp.failed_requirements:
            msg = str(fr.get("requirement", fr.get("message", str(fr)))) if isinstance(fr, dict) else str(fr)
            if msg:
                failed_checks.append(msg)
        for w in n8n_resp.warnings:
            if w:
                warnings.append(str(w))

        # Check agent-level outcomes
        for ag in deduped_results:
            st = ag.status.upper()
            ag_name = ag.agent
            is_critical = ag_name in CRITICAL_AGENTS

            if st in NEGATIVE_STATUSES:
                detail = f"{ag_name} failed: {'; '.join(ag.issues)}" if ag.issues else f"{ag_name} failed verification."
                failed_checks.append(detail)
            elif st in UNVERIFIED_STATUSES:
                detail = f"{ag_name} not verified: {'; '.join(ag.issues)}" if ag.issues else f"{ag_name} could not be verified."
                inconclusive_checks.append(detail)
            elif st in {"ERROR", "NOT_EXECUTED"}:
                detail = f"{ag_name} encountered an error: {'; '.join(ag.issues)}" if ag.issues else f"{ag_name} did not execute successfully."
                if is_critical:
                    critical_errors.append(detail)
                else:
                    inconclusive_checks.append(detail)
            elif st in PARTIAL_STATUSES or st == "INCONCLUSIVE":
                detail = f"{ag_name} raised review items: {'; '.join(ag.issues)}" if ag.issues else f"{ag_name} requires manual verification."
                if st == "INCONCLUSIVE":
                    inconclusive_checks.append(detail)
                else:
                    warnings.append(detail)

        # Deduplicate failure messages, warnings, and inconclusive checks
        def _dedup_list(items: List[str]) -> List[str]:
            seen = set()
            out = []
            for it in items:
                norm = re.sub(r"\s+", " ", str(it).strip().lower())
                if norm and norm not in seen:
                    seen.add(norm)
                    out.append(it)
            return out

        failed_checks = _dedup_list(failed_checks)
        critical_errors = _dedup_list(critical_errors)
        warnings = _dedup_list(warnings)
        inconclusive_checks = _dedup_list(inconclusive_checks)

        # Execute deterministic compliance aggregation rules
        has_requirements = bool(requirements_eval)
        if has_requirements:
            has_mandatory_fail = any(r.mandatory and r.decision == RequirementComplianceEnum.NON_COMPLIANT for r in requirements_eval)
            has_mandatory_unverified = any(r.mandatory and r.decision == RequirementComplianceEnum.UNVERIFIED for r in requirements_eval)
            has_mandatory_partial = any(r.mandatory and r.decision == RequirementComplianceEnum.PARTIALLY_COMPLIANT for r in requirements_eval)

            if has_mandatory_fail or failed_checks:
                overall_compliance = OverallComplianceEnum.NON_COMPLIANT
                decision = VerificationDecisionEnum.NOT_QUALIFIED
                reasons.append("One or more mandatory compliance requirements failed.")
            elif has_mandatory_unverified or critical_errors:
                overall_compliance = OverallComplianceEnum.UNVERIFIED
                decision = VerificationDecisionEnum.MANUAL_REVIEW
                reasons.append("One or more mandatory requirements or critical agents are unverified.")
            elif has_mandatory_partial or warnings or inconclusive_checks:
                overall_compliance = OverallComplianceEnum.PARTIALLY_COMPLIANT
                decision = VerificationDecisionEnum.CONDITIONALLY_QUALIFIED
                reasons.append("All mandatory requirements evaluated with conditional or partial compliance.")
            else:
                overall_compliance = OverallComplianceEnum.COMPLIANT
                decision = VerificationDecisionEnum.QUALIFIED
                reasons.append("All mandatory tender requirements and verification checks successfully passed.")
        else:
            # Fallback for direct agent result payloads without granular requirements
            if failed_checks:
                overall_compliance = OverallComplianceEnum.NON_COMPLIANT
                decision = VerificationDecisionEnum.NOT_QUALIFIED
                reasons.append("One or more mandatory compliance criteria failed.")
            elif critical_errors:
                overall_compliance = OverallComplianceEnum.UNVERIFIED
                decision = VerificationDecisionEnum.MANUAL_REVIEW
                reasons.append("Critical verification agent(s) failed or did not execute.")
            elif inconclusive_checks:
                overall_compliance = OverallComplianceEnum.UNVERIFIED
                decision = VerificationDecisionEnum.CONDITIONALLY_QUALIFIED
                reasons.append("Verification concluded with inconclusive checks requiring review.")
            elif warnings:
                overall_compliance = OverallComplianceEnum.PARTIALLY_COMPLIANT
                decision = VerificationDecisionEnum.CONDITIONALLY_QUALIFIED
                reasons.append("All mandatory checks passed with warning flags.")
            elif (payload and payload.bidder_evidence) or (n8n_resp.decision.upper() == "QUALIFIED" and not critical_errors):
                overall_compliance = OverallComplianceEnum.COMPLIANT
                decision = VerificationDecisionEnum.QUALIFIED
                reasons.append("All required verification criteria successfully passed.")
            else:
                overall_compliance = OverallComplianceEnum.UNVERIFIED
                decision = VerificationDecisionEnum.MANUAL_REVIEW
                reasons.append("Insufficient evidence or requirements to grant unconditional qualification.")

        for r in n8n_resp.reasons:
            if r and r not in reasons:
                reasons.append(r)

        # 6. Deterministic Risk Assessment & Critical Risk Conditions (Sections 5 & 6)
        risk_assessment = self._calculate_risk_assessment(
            deduped_results=deduped_results,
            requirements_eval=requirements_eval,
            n8n_risk_score=n8n_resp.risk_score,
            failed_checks=failed_checks,
            critical_errors=critical_errors,
        )

        # 7. Calculate Overall Confidence (Section 8)
        # Preserve known confidence; missing represented as null; low confidence preserved
        known_confidences = [ag.confidence for ag in deduped_results if ag.confidence is not None]
        if known_confidences:
            overall_confidence = round(sum(known_confidences) / len(known_confidences), 2)
        else:
            overall_confidence = None

        # 8. Compute Compliance Summary (Section 10)
        compliance_summary = VerificationComplianceSummary(
            total_requirements=len(requirements_eval),
            compliant=sum(1 for r in requirements_eval if r.decision == RequirementComplianceEnum.COMPLIANT),
            non_compliant=sum(1 for r in requirements_eval if r.decision == RequirementComplianceEnum.NON_COMPLIANT),
            partially_compliant=sum(1 for r in requirements_eval if r.decision == RequirementComplianceEnum.PARTIALLY_COMPLIANT),
            unverified=sum(1 for r in requirements_eval if r.decision == RequirementComplianceEnum.UNVERIFIED),
        )

        # 9. Lifecycle Status
        status_val = (n8n_resp.status or "COMPLETED").strip().upper()
        if status_val == "COMPLETED":
            status_enum = VerificationStatusEnum.COMPLETED
        elif status_val == "FAILED":
            status_enum = VerificationStatusEnum.FAILED
        else:
            status_enum = VerificationStatusEnum.PROCESSING

        # 10. Traceability & Audit Trail
        traceability_data: Dict[str, Any] = {
            "verification_id": verification_id,
            "request_id": request_id,
            "tender_id": str(t_uuid),
            "bidder_id": str(b_uuid),
            "tender_number": getattr(payload, "tender_number", None) if payload else n8n_resp.tender_id,
            "bidder_name": bidder_name,
            "document_hashes": [
                {
                    "document_id": doc.document_id,
                    "sha256": doc.sha256,
                    "file_name": doc.file_name,
                    "mime_type": doc.mime_type,
                }
                for doc in (payload.documents or [])
                if doc.sha256
            ] if payload else [],
            "requirements": [
                {
                    "requirement_id": r.requirement_id,
                    "rule": r.rule,
                    "decision": r.decision.value,
                    "agent": r.agent,
                    "confidence": r.confidence,
                    "evidence_ids": r.evidence_ids,
                    "document_ids": r.document_ids,
                    "source_page": r.source_page,
                    "source_section": r.source_section,
                    "source_text": r.source_text,
                    "reason": r.reason,
                }
                for r in requirements_eval
            ],
            "evidence": [
                {
                    "evidence_id": e.evidence_id,
                    "document_id": e.document_id,
                    "document_hash": e.document_hash,
                    "field": e.field,
                    "source_page": e.source_page,
                    "source_text": e.source_text,
                    "confidence": e.confidence,
                    "extraction_method": e.extraction_method,
                }
                for e in (payload.bidder_evidence or [])
            ] if payload else [],
            "agent_verdicts": {
                ag.agent: {
                    "status": ag.status,
                    "confidence": ag.confidence,
                    "risk_level": ag.risk_level,
                    "issues": ag.issues,
                    "errors": ag.errors,
                }
                for ag in deduped_results
            },
            "risk_signals": risk_assessment.signals,
            "critical_flags": risk_assessment.critical_flags,
        }

        raw_audit = n8n_resp.model_dump()
        raw_audit["traceability"] = traceability_data
        raw_audit["execution_metadata"] = {
            "required_agents_count": len(required_agents),
            "executed_agents_count": len(deduped_results),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # 8b. Compute Semantically Separated Agent vs Requirement Collections
        def is_agent_identifier(val: str) -> bool:
            if not isinstance(val, str):
                return False
            v = val.strip().upper()
            return (
                v.endswith("_AGENT")
                or v in DEFAULT_VERIFICATION_AGENTS
                or v in CRITICAL_AGENTS
                or v in {
                    "TENDER_INTELLIGENCE_AGENT",
                    "GST_AGENT",
                    "PAN_AGENT",
                    "UDYAM_AGENT",
                    "MSME_UDYAM_AGENT",
                    "FINANCIAL_AGENT",
                    "EXPERIENCE_AGENT",
                    "DOCUMENT_FORENSICS_AGENT",
                    "ENTITY_RESOLUTION_AGENT",
                    "RISK_INTELLIGENCE_AGENT",
                    "FINAL_COMPLIANCE_AGENT",
                }
            )

        passed_agents: List[str] = []
        failed_agents: List[str] = []
        review_agents: List[str] = []

        for ag in deduped_results:
            ag_id = ag.agent
            st = (ag.status or "").upper()
            if st in POSITIVE_STATUSES or st in {"PASS", "VERIFIED", "QUALIFIED"}:
                if ag_id not in passed_agents:
                    passed_agents.append(ag_id)
            elif st in NEGATIVE_STATUSES or st in {"FAIL", "FAILED", "ERROR", "NOT_VERIFIED"}:
                if ag_id not in failed_agents:
                    failed_agents.append(ag_id)
            else:
                if ag_id not in review_agents:
                    review_agents.append(ag_id)

        for a in getattr(n8n_resp, "passed_agents", []):
            if is_agent_identifier(a) and a not in passed_agents:
                passed_agents.append(a)
        for a in getattr(n8n_resp, "failed_agents", []):
            if is_agent_identifier(a) and a not in failed_agents:
                failed_agents.append(a)
        for a in getattr(n8n_resp, "review_agents", []):
            if is_agent_identifier(a) and a not in review_agents:
                review_agents.append(a)

        passed_requirements: List[str] = []
        failed_requirements: List[str] = []
        review_requirements: List[str] = []

        if requirements_eval:
            for req_eval in requirements_eval:
                req_id = req_eval.rule or req_eval.requirement_id
                if not req_id or is_agent_identifier(req_id):
                    continue
                if req_eval.decision == RequirementComplianceEnum.COMPLIANT:
                    if req_id not in passed_requirements:
                        passed_requirements.append(req_id)
                elif req_eval.decision == RequirementComplianceEnum.NON_COMPLIANT:
                    if req_id not in failed_requirements:
                        failed_requirements.append(req_id)
                else:
                    if req_id not in review_requirements:
                        review_requirements.append(req_id)
        else:
            # Fallback if no granular requirements in payload
            for r in (n8n_resp.passed_requirements or []):
                r_str = str(r).strip()
                if r_str and not is_agent_identifier(r_str) and r_str not in passed_requirements:
                    passed_requirements.append(r_str)
            for r in (n8n_resp.failed_requirements or []):
                r_str = (r.get("requirement", r.get("rule", str(r))) if isinstance(r, dict) else str(r)).strip()
                if r_str and not is_agent_identifier(r_str) and r_str not in failed_requirements:
                    failed_requirements.append(r_str)
            for r in (getattr(n8n_resp, "review_requirements", []) or []):
                r_str = str(r).strip()
                if r_str and not is_agent_identifier(r_str) and r_str not in review_requirements:
                    review_requirements.append(r_str)

        confidence_breakdown = self._build_confidence_breakdown(
            overall_confidence=overall_confidence,
            known_confidences=known_confidences,
            deduped_results=deduped_results,
            requirements_eval=requirements_eval,
        )

        cross_verification = self._build_cross_verification(
            payload=payload,
            deduped_results=deduped_results,
            requirements_eval=requirements_eval,
            bidder_name=bidder_name,
        )

        document_forensics = self._build_document_forensics(
            payload=payload,
            deduped_results=deduped_results,
            requirements_eval=requirements_eval,
        )

        document_similarity = self._build_document_similarity(
            payload=payload,
            requirements_eval=requirements_eval,
        )

        compliance_policy = self._evaluate_compliance_policy(
            requirements_eval=requirements_eval,
            deduped_results=deduped_results,
            cross_verification=cross_verification,
            document_forensics=document_forensics,
            warnings=warnings,
            failed_checks=failed_checks,
            critical_errors=critical_errors,
            inconclusive_checks=inconclusive_checks,
            existing_decision=decision,
        )

        # Align final decision and compliance with deterministic compliance policy
        if compliance_policy.final_status == "NOT_QUALIFIED":
            decision = VerificationDecisionEnum.NOT_QUALIFIED
            overall_compliance = OverallComplianceEnum.NON_COMPLIANT
        elif compliance_policy.final_status == "MANUAL_REVIEW":
            decision = VerificationDecisionEnum.MANUAL_REVIEW
            overall_compliance = OverallComplianceEnum.UNVERIFIED
        elif compliance_policy.final_status == "QUALIFIED":
            if decision not in (VerificationDecisionEnum.QUALIFIED, VerificationDecisionEnum.CONDITIONALLY_QUALIFIED):
                decision = VerificationDecisionEnum.QUALIFIED

        # Enforce strict invariant: QUALIFIED has no failed or review items
        if decision == VerificationDecisionEnum.QUALIFIED:
            failed_requirements = []
            review_requirements = []
            failed_agents = []
            review_agents = []

        # An unresolved requirement is represented in review_requirements and NOT in failed_requirements
        failed_requirements = [r for r in failed_requirements if r not in review_requirements and not is_agent_identifier(r)]
        passed_requirements = [r for r in passed_requirements if not is_agent_identifier(r)]
        review_requirements = [r for r in review_requirements if not is_agent_identifier(r)]

        passed_agents = [a for a in passed_agents if is_agent_identifier(a)]
        failed_agents = [a for a in failed_agents if is_agent_identifier(a)]
        review_agents = [a for a in review_agents if is_agent_identifier(a)]

        decision_explanation, decision_factors = self._generate_decision_explanation(
            decision=decision,
            overall_compliance=overall_compliance,
            requirements_eval=requirements_eval,
            deduped_results=deduped_results,
            failed_checks=failed_checks,
            critical_errors=critical_errors,
            warnings=warnings,
            inconclusive_checks=inconclusive_checks,
            compliance_policy=compliance_policy,
        )

        raw_audit["document_forensics"] = document_forensics.model_dump() if document_forensics else None
        raw_audit["document_similarity"] = document_similarity.model_dump() if document_similarity else None
        raw_audit["compliance_policy"] = compliance_policy.model_dump() if compliance_policy else None

        return VerificationResponse(
            id=uuid.uuid4(),
            verification_id=verification_id,
            request_id=request_id,
            tender_id=t_uuid,
            bidder_id=b_uuid,
            bidder_name=bidder_name,
            status=status_enum,
            decision=decision,
            overall_compliance=overall_compliance,
            risk_score=risk_assessment.score,
            risk_level=risk_assessment.level,
            overall_confidence=overall_confidence,
            confidence_breakdown=confidence_breakdown,
            cross_verification=cross_verification,
            document_forensics=document_forensics,
            document_similarity=document_similarity,
            compliance_policy=compliance_policy,
            reasons=reasons,
            decision_explanation=decision_explanation,
            decision_factors=decision_factors,
            passed_agents=passed_agents,
            failed_agents=failed_agents,
            review_agents=review_agents,
            passed_requirements=passed_requirements,
            failed_requirements=failed_requirements,
            review_requirements=review_requirements,
            warnings=warnings,
            inconclusive_checks=inconclusive_checks,
            missing_documents=n8n_resp.missing_documents or [],
            agent_results=deduped_results,
            requirements=requirements_eval,
            risk=risk_assessment,
            summary=compliance_summary,
            raw_response=raw_audit,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

    def _evaluate_single_requirement(
        self,
        req: Any,
        evidence_list: List[Any],
        agent_map: Dict[str, N8nAgentResult],
    ) -> RequirementEvaluation:
        """
        Evaluates an individual tender requirement against relevant bidder evidence
        and responsible verification agent outcomes.
        """
        rule = (req.rule or "").upper()
        req_type = (req.requirement_type or "").upper()
        agent_name = self._map_requirement_to_agent(rule, req_type)
        agent_res = agent_map.get(agent_name)

        # Correlate evidence
        correlated_evidence = [
            e for e in evidence_list
            if self._evidence_matches_requirement(e, rule, req_type)
        ]
        ev_ids = [str(e.evidence_id) for e in correlated_evidence if getattr(e, "evidence_id", None)]
        doc_ids = [str(e.document_id) for e in correlated_evidence if getattr(e, "document_id", None)]

        findings: List[str] = []
        reason = ""
        decision: RequirementComplianceEnum

        # Extract threshold / expected value from requirement
        expected_val = None
        if getattr(req, "parameters", None) and isinstance(req.parameters, dict):
            expected_val = (
                req.parameters.get("required_value")
                or req.parameters.get("min_turnover")
                or req.parameters.get("min_years")
                or req.parameters.get("experience_period_years")
            )
        if not expected_val and getattr(req, "description", None):
            expected_val = req.description

        structured_ev_list: List[StructuredEvidenceItem] = []
        for e in correlated_evidence:
            source_p = getattr(e, "source_page", None) if getattr(e, "source_page", None) is not None else getattr(e, "page_number", None)
            ev_item = StructuredEvidenceItem(
                source_document=getattr(e, "source_document", None),
                page_number=int(source_p) if source_p is not None and int(source_p) > 0 else None,
                field=getattr(e, "field", None),
                detected_value=getattr(e, "value", None),
                normalized_value=getattr(e, "value", None),
                expected_value=expected_val,
                requirement=req.rule,
                evidence_text=getattr(e, "source_text", None) or getattr(e, "text_snippet", None),
                reference=getattr(e, "source_document", None) or getattr(e, "document_id", None),
                confidence=float(e.confidence) if getattr(e, "confidence", None) is not None else None,
                evidence_id=str(e.evidence_id) if getattr(e, "evidence_id", None) else None,
                document_id=str(e.document_id) if getattr(e, "document_id", None) else None,
            )
            structured_ev_list.append(ev_item)

        if not structured_ev_list and agent_res and getattr(agent_res, "evidence", None):
            if isinstance(agent_res.evidence, list):
                for ag_ev in agent_res.evidence:
                    if isinstance(ag_ev, StructuredEvidenceItem):
                        structured_ev_list.append(ag_ev)
                    elif isinstance(ag_ev, dict):
                        try:
                            structured_ev_list.append(StructuredEvidenceItem.model_validate(ag_ev))
                        except Exception:
                            pass

        # Invariant: If mandatory evidence is missing -> UNVERIFIED (Never COMPLIANT)
        if not correlated_evidence and not structured_ev_list:
            decision = RequirementComplianceEnum.UNVERIFIED
            reason = f"No relevant evidence provided for requirement '{req.rule}'."
            findings.append("Missing required supporting documentation or evidence.")
            return RequirementEvaluation(
                requirement_id=str(req.requirement_id),
                rule=req.rule,
                description=req.description,
                mandatory=req.mandatory,
                status="UNRESOLVED",
                decision=decision,
                confidence=None,
                agent=agent_name,
                evidence_ids=ev_ids,
                document_ids=doc_ids,
                source_page=req.source_page,
                source_section=req.source_section,
                source_text=req.source_text,
                reason=reason,
                findings=findings,
                evidence=[],
            )

        # Invariant: If responsible agent is unavailable or encountered error
        if not agent_res or agent_res.status.upper() in {"ERROR", "NOT_EXECUTED", "UNKNOWN"}:
            decision = RequirementComplianceEnum.UNVERIFIED
            reason = f"Responsible verification agent '{agent_name}' did not execute successfully."
            findings.append(f"Agent execution failure or omission for '{agent_name}'.")
            return RequirementEvaluation(
                requirement_id=str(req.requirement_id),
                rule=req.rule,
                description=req.description,
                mandatory=req.mandatory,
                status="UNRESOLVED",
                decision=decision,
                confidence=0.0,
                agent=agent_name,
                evidence_ids=ev_ids,
                document_ids=doc_ids,
                source_page=req.source_page,
                source_section=req.source_section,
                source_text=req.source_text,
                reason=reason,
                findings=findings,
                evidence=structured_ev_list,
            )

        ag_status = agent_res.status.upper()
        ag_confidence = agent_res.confidence

        # Invariant: Agent reports FAIL
        if ag_status in NEGATIVE_STATUSES:
            decision = RequirementComplianceEnum.NON_COMPLIANT
            reason = f"Requirement failed validation by {agent_name}: {'; '.join(agent_res.issues)}"
            findings.extend(agent_res.issues or [f"Criteria violated for {req.rule}"])
        # Low confidence (< 0.60) does not automatically convert to PASS
        elif ag_confidence is not None and ag_confidence < 0.60:
            decision = RequirementComplianceEnum.PARTIALLY_COMPLIANT
            reason = f"Verification confidence ({ag_confidence}) is too low for unconditional compliance."
            findings.append(f"Low evaluation confidence from {agent_name}.")
        # Partial / warning status
        elif ag_status in PARTIAL_STATUSES:
            decision = RequirementComplianceEnum.PARTIALLY_COMPLIANT
            reason = f"Requirement conditionally met with review items from {agent_name}."
            findings.extend(agent_res.issues or ["Review required."])
        # Success status with sufficient confidence
        elif ag_status in POSITIVE_STATUSES:
            decision = RequirementComplianceEnum.COMPLIANT
            reason = f"Requirement successfully verified against evidence by {agent_name}."
            findings.append("Verified compliant.")
        else:
            decision = RequirementComplianceEnum.UNVERIFIED
            reason = f"Verification outcome for {agent_name} is inconclusive."
            findings.append("Inconclusive agent outcome.")

        if decision == RequirementComplianceEnum.COMPLIANT:
            req_status = "PASS"
        elif decision == RequirementComplianceEnum.NON_COMPLIANT:
            req_status = "FAIL"
        else:
            req_status = "UNRESOLVED"

        return RequirementEvaluation(
            requirement_id=str(req.requirement_id),
            rule=req.rule,
            description=req.description,
            mandatory=req.mandatory,
            status=req_status,
            decision=decision,
            confidence=ag_confidence,
            agent=agent_name,
            evidence_ids=ev_ids,
            document_ids=doc_ids,
            source_page=req.source_page,
            source_section=req.source_section,
            source_text=req.source_text,
            reason=reason,
            findings=findings,
            evidence=structured_ev_list,
        )


    def _map_requirement_to_agent(self, rule: str, req_type: str) -> str:
        """Determines the primary specialized verification agent responsible for a rule."""
        r = rule.upper()
        t = req_type.upper()
        if "TURNOVER" in r or "FINANCIAL" in t or "NET_WORTH" in r or "PROFIT" in r or "SOLVENCY" in r:
            return "FINANCIAL_AGENT"
        if "EXPERIENCE" in t or "SIMILAR_WORK" in r or "YEARS_IN_OPERATION" in r or "PROJECT" in r:
            return "EXPERIENCE_AGENT"
        if "GST" in r or "GST" in t:
            return "GST_AGENT"
        if "PAN" in r or "PAN" in t:
            return "PAN_AGENT"
        if "UDYAM" in r or "MSME" in r or "UDYAM" in t:
            return "UDYAM_AGENT"
        if "DOCUMENT" in t or "FORENSIC" in t or "FORGERY" in r or "INTEGRITY" in r or "TAMPER" in r:
            return "DOCUMENT_FORENSICS_AGENT"
        if "ENTITY" in t or "IDENTITY" in r or "BLACKLIST" in r:
            return "ENTITY_RESOLUTION_AGENT"
        return "FINAL_COMPLIANCE_AGENT"

    def _evidence_matches_requirement(self, evidence: Any, rule: str, req_type: str) -> bool:
        """Checks if a piece of bidder evidence correlates to a tender requirement."""
        field = str(getattr(evidence, "field", "")).lower()
        r = rule.lower()
        t = req_type.lower()
        if "turnover" in r and "turnover" in field:
            return True
        if "net_worth" in r and "net_worth" in field:
            return True
        if "experience" in t or "experience" in r or "similar_work" in r:
            if "experience" in field or "work" in field or "project" in field:
                return True
        if "gst" in r and "gst" in field:
            return True
        if "pan" in r and "pan" in field:
            return True
        if ("udyam" in r or "msme" in r) and ("udyam" in field or "msme" in field):
            return True
        if ("oem" in r or "manufacturer" in r) and ("oem" in field or "manufacturer" in field):
            return True
        if "document" in r or "document" in t:
            return True
        # If generic matching
        if field in r or r in field:
            return True
        return False

    def _build_agent_evidence(
        self,
        agent_name: str,
        agent_evidence: Any,
        payload: Optional[N8nVerificationPayload],
    ) -> List[StructuredEvidenceItem]:
        """
        Builds or correlates structured evidence items for an individual agent result.
        Reuses existing bidder evidence records, ensuring provenance (source document, page, values).
        """
        items: List[StructuredEvidenceItem] = []

        # 1. If agent already provides a list of StructuredEvidenceItem / dicts
        if isinstance(agent_evidence, list) and agent_evidence:
            for ev in agent_evidence:
                if isinstance(ev, StructuredEvidenceItem):
                    items.append(ev)
                elif isinstance(ev, dict):
                    try:
                        items.append(StructuredEvidenceItem.model_validate(ev))
                    except Exception:
                        pass
            if items:
                return items

        # 2. Correlate with payload.bidder_evidence if available
        if payload and payload.bidder_evidence:
            for be in payload.bidder_evidence:
                field = (getattr(be, "field", "") or "").lower()
                matched = False
                expected_val = None
                rule_name = None

                if agent_name == "GST_AGENT" and ("gst" in field):
                    matched = True
                    expected_val = "Valid GSTIN registration"
                    rule_name = "GST_REGISTRATION"
                elif agent_name == "PAN_AGENT" and ("pan" in field):
                    matched = True
                    expected_val = "Valid statutory PAN card"
                    rule_name = "PAN_CARD"
                elif agent_name == "FINANCIAL_AGENT" and ("turnover" in field or "financial" in field or "net_worth" in field):
                    matched = True
                    rule_name = "MINIMUM_TURNOVER"
                    if payload.financial_requirements:
                        expected_val = (
                            payload.financial_requirements.average_turnover
                            or payload.financial_requirements.minimum_annual_turnover
                        )
                elif agent_name == "EXPERIENCE_AGENT" and ("experience" in field or "work" in field or "project" in field):
                    matched = True
                    rule_name = "YEARS_OF_EXPERIENCE"
                    if payload.experience_requirements:
                        expected_val = payload.experience_requirements.experience_period_years
                elif agent_name == "DOCUMENT_FORENSICS_AGENT" and ("document" in field):
                    matched = True
                    expected_val = "Cryptographic integrity verified"
                    rule_name = "REQUIRED_DOCUMENT"
                elif agent_name == "UDYAM_AGENT" and ("udyam" in field or "msme" in field):
                    matched = True
                    expected_val = "Valid MSME Udyam registration"
                    rule_name = "UDYAM_REGISTRATION"
                elif agent_name == "ENTITY_RESOLUTION_AGENT" and ("entity" in field or "sanction" in field or "bidder" in field):
                    matched = True
                    expected_val = "Clean sanctions and entity verification"
                    rule_name = "ENTITY_VERIFICATION"

                if matched:
                    source_p = getattr(be, "source_page", None) if getattr(be, "source_page", None) is not None else getattr(be, "page_number", None)
                    items.append(
                        StructuredEvidenceItem(
                            source_document=getattr(be, "source_document", None),
                            page_number=int(source_p) if source_p is not None and int(source_p) > 0 else None,
                            field=getattr(be, "field", None),
                            detected_value=getattr(be, "value", None),
                            normalized_value=getattr(be, "value", None),
                            expected_value=expected_val,
                            requirement=rule_name,
                            evidence_text=getattr(be, "source_text", None) or getattr(be, "text_snippet", None),
                            reference=getattr(be, "source_document", None) or getattr(be, "document_id", None),
                            confidence=float(be.confidence) if getattr(be, "confidence", None) is not None else None,
                            evidence_id=str(be.evidence_id) if getattr(be, "evidence_id", None) else None,
                            document_id=str(be.document_id) if getattr(be, "document_id", None) else None,
                        )
                    )

        # 3. If still empty, check if agent_evidence was a dict (e.g. from local fallback or n8n)
        if not items and isinstance(agent_evidence, dict) and agent_evidence:
            raw_anoms = agent_evidence.get("anomalies") or agent_evidence.get("integrity_issues")
            if isinstance(raw_anoms, list) and raw_anoms:
                for idx, a in enumerate(raw_anoms):
                    if isinstance(a, dict):
                        p_val = a.get("page_number")
                        items.append(
                            StructuredEvidenceItem(
                                evidence_id=a.get("anomaly_id") or f"FORENSIC-{idx+1:03d}",
                                field=a.get("anomaly_type") or a.get("type") or "document_integrity",
                                detected_value=a.get("description") or a.get("issue") or a.get("reason"),
                                requirement="DOCUMENT_AUTHENTICITY",
                                source_document=a.get("source_document") or agent_evidence.get("source_document"),
                                page_number=int(p_val) if p_val is not None and int(p_val) > 0 else None,
                                confidence=a.get("confidence") if a.get("confidence") is not None else agent_evidence.get("confidence"),
                                document_id=a.get("document_id") or agent_evidence.get("document_id"),
                            )
                        )
            elif "source_document" in agent_evidence or "detected_value" in agent_evidence:
                try:
                    items.append(StructuredEvidenceItem.model_validate(agent_evidence))
                except Exception:
                    pass
            else:
                for k, v in agent_evidence.items():
                    if k in ("extracted_text", "raw_data", "tampering_detected"):
                        continue
                    items.append(
                        StructuredEvidenceItem(
                            field=k,
                            detected_value=v,
                            source_document=None,
                            page_number=None,
                        )
                    )

        return items


    def _calculate_risk_assessment(
        self,
        deduped_results: List[N8nAgentResult],
        requirements_eval: List[RequirementEvaluation],
        n8n_risk_score: Optional[float],
        failed_checks: List[str],
        critical_errors: List[str],
    ) -> VerificationRiskAssessment:
        """
        Computes an explainable, deterministic risk profile with explicit weights and thresholds.
        """
        score = 0.0
        reasons: List[str] = []
        signals: Dict[str, Any] = {}
        critical_flags: List[str] = []

        # 1. Evaluate Critical Risk Conditions (Section 6)
        for ag in deduped_results:
            name = ag.agent
            issues_joined = " ".join(ag.issues + ag.findings + ag.errors)

            # Document forgery indicators
            if name == "DOCUMENT_FORENSICS_AGENT" and any(p.search(issues_joined) for p in CRITICAL_FORGERY_PATTERNS):
                flag = "Critical: Document forgery / tampering indicator detected."
                if flag not in critical_flags:
                    critical_flags.append(flag)
                    score += 50.0

            # Entity mismatch
            if name == "ENTITY_RESOLUTION_AGENT" and any(p.search(issues_joined) for p in CRITICAL_ENTITY_PATTERNS):
                flag = "Critical: Entity legal identity or director mismatch detected."
                if flag not in critical_flags:
                    critical_flags.append(flag)
                    score += 45.0

            # Statutory invalidity / cancellation
            if name in {"GST_AGENT", "PAN_AGENT", "UDYAM_AGENT"} and any(p.search(issues_joined) for p in CRITICAL_STATUTORY_PATTERNS):
                flag = f"Critical: Conflicting or cancelled statutory registration detected by {name}."
                if flag not in critical_flags:
                    critical_flags.append(flag)
                    score += 40.0

            # Major financial distress
            if name == "FINANCIAL_AGENT" and any(p.search(issues_joined) for p in CRITICAL_FINANCIAL_PATTERNS):
                flag = "Critical: Major financial statement inconsistency or insolvency indicator detected."
                if flag not in critical_flags:
                    critical_flags.append(flag)
                    score += 35.0

        # Mandatory requirement failure raises risk
        if failed_checks or any(r.mandatory and r.decision == RequirementComplianceEnum.NON_COMPLIANT for r in requirements_eval):
            reason_msg = "One or more mandatory tender requirements failed compliance."
            if reason_msg not in reasons:
                reasons.append(reason_msg)
            score += 30.0


        # 2. Evaluate Explicit Component Agent Signals (Section 5)
        for ag in deduped_results:
            name = ag.agent
            st = ag.status.upper()
            rl = ag.risk_level.upper()
            agent_score = 0.0

            if st in NEGATIVE_STATUSES or st == "ERROR":
                agent_score += 25.0
            elif st in PARTIAL_STATUSES or rl == "MEDIUM":
                agent_score += 10.0
            elif st in {"NOT_EXECUTED", "UNKNOWN"}:
                # Missing data must not be treated as zero risk!
                agent_score += 15.0

            if rl in {"HIGH", "CRITICAL"}:
                agent_score += 20.0

            signals[name] = {
                "status": st,
                "risk_level": rl,
                "risk_contribution": agent_score,
                "issues": ag.issues,
            }
            score += agent_score

        # Combine with n8n provided risk score if higher
        n8n_val = float(n8n_risk_score) if n8n_risk_score is not None else 0.0
        final_score = min(100.0, max(n8n_val, score))

        # Determine explicit risk category (Section 5)
        if critical_flags or final_score >= 80.0 or critical_errors:
            level = RiskLevelEnum.CRITICAL
            reasons.append("High-severity risk flags or critical agent failures triggered.")
        elif final_score >= 60.0 or failed_checks:
            level = RiskLevelEnum.HIGH
            reasons.append("Elevated risk due to compliance violations or multiple agent issues.")
        elif final_score >= 30.0 or any(ag.status in PARTIAL_STATUSES for ag in deduped_results):
            level = RiskLevelEnum.MEDIUM
            reasons.append("Moderate risk with advisory warnings or conditional verifications.")
        elif all(ag.status in {"NOT_EXECUTED", "UNKNOWN"} for ag in deduped_results):
            level = RiskLevelEnum.UNKNOWN
            reasons.append("Risk could not be assessed due to lack of agent execution data.")
        else:
            level = RiskLevelEnum.LOW
            reasons.append("All statutory, financial, and integrity verifications indicate low risk.")

        reasons.extend(critical_flags)

        return VerificationRiskAssessment(
            level=level,
            score=round(final_score, 2),
            reasons=reasons,
            signals=signals,
            critical_flags=critical_flags,
        )

    def _generate_decision_explanation(
        self,
        decision: VerificationDecisionEnum,
        overall_compliance: Optional[OverallComplianceEnum],
        requirements_eval: List[RequirementEvaluation],
        deduped_results: List[N8nAgentResult],
        failed_checks: List[str],
        critical_errors: List[str],
        warnings: List[str],
        inconclusive_checks: List[str],
        compliance_policy: Optional[VerificationCompliancePolicy] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Deterministically generates a human-readable explanation and structured factors
        for the final verification decision without any probabilistic models or LLM calls.
        """
        explanation = ""
        decision_factors: List[Dict[str, Any]] = []

        if decision == VerificationDecisionEnum.QUALIFIED:
            mandatory_reqs = [r for r in requirements_eval if r.mandatory]
            if mandatory_reqs:
                explanation = (
                    f"Bidder is qualified because all {len(mandatory_reqs)} mandatory tender requirements "
                    f"were successfully verified. No mandatory requirements failed or remain unresolved."
                )
            else:
                explanation = (
                    "Bidder is qualified because all mandatory tender requirements were successfully verified. "
                    "No mandatory requirements failed or remain unresolved."
                )
            for req in mandatory_reqs:
                decision_factors.append({
                    "type": "PASSED_REQUIREMENT",
                    "requirement_id": req.requirement_id,
                    "rule": req.rule,
                    "mandatory": req.mandatory,
                    "status": req.status or "PASS",
                    "reason": req.reason,
                    "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in (req.evidence or [])],
                })

        elif decision == VerificationDecisionEnum.NOT_QUALIFIED:
            # 1. Check for failed mandatory requirements
            failed_mandatory = [
                r for r in requirements_eval
                if r.mandatory and (r.status == "FAIL" or r.decision == RequirementComplianceEnum.NON_COMPLIANT)
            ]
            if not failed_mandatory:
                failed_mandatory = [
                    r for r in requirements_eval
                    if r.status == "FAIL" or r.decision == RequirementComplianceEnum.NON_COMPLIANT
                ]

            req_clauses = []
            for req in failed_mandatory:
                rule_name = req.rule or req.requirement_id
                val_clause = ""
                ev_clause = ""

                ev = req.evidence[0] if (req.evidence and len(req.evidence) > 0) else None
                if ev and ev.detected_value is not None and ev.expected_value is not None:
                    field_label = (ev.field or "value").replace("_", " ")
                    if "turnover" in field_label.lower():
                        val_clause = f"Detected {field_label} was {ev.detected_value} against the required minimum of {ev.expected_value}."
                    else:
                        val_clause = f"Detected {field_label} was {ev.detected_value} against the required {ev.expected_value}."
                elif req.reason:
                    val_clause = req.reason.rstrip(".") + "."
                else:
                    val_clause = "Requirement criteria was not satisfied."

                if ev and ev.source_document:
                    page_str = f", page {ev.page_number}" if ev.page_number is not None else ""
                    ev_clause = f" Evidence: {ev.source_document}{page_str}."

                clause = f"the mandatory {rule_name} requirement failed. {val_clause}{ev_clause}".strip()
                req_clauses.append(clause)

                decision_factors.append({
                    "type": "FAILED_REQUIREMENT",
                    "requirement_id": req.requirement_id,
                    "rule": req.rule,
                    "mandatory": req.mandatory,
                    "status": "FAIL",
                    "reason": req.reason,
                    "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in (req.evidence or [])],
                })

            if len(req_clauses) == 1:
                explanation = f"Bidder is not qualified because {req_clauses[0]}"
            elif len(req_clauses) > 1:
                explanation = (
                    f"Bidder is not qualified because multiple mandatory requirements failed: "
                    + " ".join(f"({i+1}) {c}" for i, c in enumerate(req_clauses))
                )
            else:
                # Check critical agents or forensics
                doc_forensics = next((ag for ag in deduped_results if ag.agent == "DOCUMENT_FORENSICS_AGENT"), None)
                if doc_forensics and (doc_forensics.status.upper() in NEGATIVE_STATUSES or doc_forensics.normalized_status == "FAILED"):
                    explanation = "Bidder is not qualified because DOCUMENT_FORENSICS_AGENT detected a document authenticity failure."
                    decision_factors.append({
                        "type": "CRITICAL_AGENT_CONDITION",
                        "agent_id": "DOCUMENT_FORENSICS_AGENT",
                        "status": "FAILED",
                        "reason": doc_forensics.reason or "Document authenticity failure",
                        "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in (doc_forensics.evidence or [])] if isinstance(doc_forensics.evidence, list) else [],
                    })
                else:
                    failed_agents = [ag for ag in deduped_results if ag.status.upper() in NEGATIVE_STATUSES or ag.normalized_status == "FAILED"]
                    if failed_agents:
                        first_ag = failed_agents[0]
                        ag_reason = first_ag.reason or ("; ".join(first_ag.issues) if first_ag.issues else "verification criteria not met")
                        ev = first_ag.evidence[0] if (isinstance(first_ag.evidence, list) and len(first_ag.evidence) > 0) else None
                        ev_str = f" Evidence: {ev.source_document}" if ev and ev.source_document else ""
                        if ev and ev.page_number is not None:
                            ev_str += f", page {ev.page_number}."
                        elif ev_str:
                            ev_str += "."
                        explanation = f"Bidder is not qualified because {first_ag.agent} failed verification: {ag_reason}.{ev_str}".strip()
                        for fa in failed_agents:
                            decision_factors.append({
                                "type": "CRITICAL_AGENT_CONDITION",
                                "agent_id": fa.agent_id or fa.agent,
                                "status": "FAILED",
                                "reason": fa.reason,
                                "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in (fa.evidence or [])] if isinstance(fa.evidence, list) else [],
                            })
                    else:
                        explanation = f"Bidder is not qualified because {failed_checks[0] if failed_checks else 'mandatory compliance criteria failed.'}"

        elif decision == VerificationDecisionEnum.MANUAL_REVIEW:
            # 1. Document Forensics check
            doc_forensics = next((ag for ag in deduped_results if ag.agent == "DOCUMENT_FORENSICS_AGENT"), None)
            has_forensics_anomaly = False
            if doc_forensics:
                df_issues = " ".join(doc_forensics.issues or []).lower()
                df_st = (doc_forensics.status or "").upper()
                if (
                    "anomaly" in df_issues
                    or "tamper" in df_issues
                    or "unresolved" in df_issues
                    or df_st in UNVERIFIED_STATUSES
                    or doc_forensics.normalized_status == "UNRESOLVED"
                ):
                    has_forensics_anomaly = True

            forensic_review_findings = [
                f for f in (compliance_policy.review_findings if compliance_policy else [])
                if f.finding_type == "FORENSIC_ANOMALY"
            ]
            if forensic_review_findings:
                has_forensics_anomaly = True

            cross_review_findings = [
                f for f in (compliance_policy.review_findings if compliance_policy else [])
                if f.finding_type == "CROSS_VERIFICATION_INCONSISTENCY"
            ]

            # Check unresolved requirements
            unresolved_reqs = [
                r for r in requirements_eval
                if r.mandatory and (r.status == "UNRESOLVED" or r.decision in {RequirementComplianceEnum.UNVERIFIED, RequirementComplianceEnum.PARTIALLY_COMPLIANT})
            ]
            if not unresolved_reqs:
                unresolved_reqs = [
                    r for r in requirements_eval
                    if r.status == "UNRESOLVED" or r.decision in {RequirementComplianceEnum.UNVERIFIED, RequirementComplianceEnum.PARTIALLY_COMPLIANT}
                ]

            if has_forensics_anomaly and not unresolved_reqs:
                f_desc = forensic_review_findings[0].description if forensic_review_findings else "Suspicious document indicator requires manual review."
                explanation = f"Manual review is required because DOCUMENT_FORENSICS_AGENT detected an unresolved document authenticity anomaly. {f_desc}".strip()
                decision_factors.append({
                    "type": "UNRESOLVED_AGENT_CONDITION",
                    "agent_id": "DOCUMENT_FORENSICS_AGENT",
                    "status": "UNRESOLVED",
                    "reason": doc_forensics.reason if (doc_forensics and doc_forensics.reason) else f_desc,
                    "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in (doc_forensics.evidence or [])] if (doc_forensics and isinstance(doc_forensics.evidence, list)) else [],
                })
            elif unresolved_reqs:
                unres_clauses = []
                for req in unresolved_reqs:
                    rule_name = req.rule or req.requirement_id
                    ev = req.evidence[0] if (req.evidence and len(req.evidence) > 0) else None
                    if ev and ev.source_document:
                        page_str = f", page {ev.page_number}" if ev.page_number is not None else ""
                        ev_str = f" from the submitted evidence ({ev.source_document}{page_str})"
                    elif ev and ev.detected_value:
                        ev_str = " from the submitted evidence"
                    else:
                        ev_str = " because verification evidence was insufficient"

                    clause = f"the mandatory {rule_name} requirement could not be conclusively verified{ev_str}"
                    unres_clauses.append(clause)

                    decision_factors.append({
                        "type": "UNRESOLVED_REQUIREMENT",
                        "requirement_id": req.requirement_id,
                        "rule": req.rule,
                        "mandatory": req.mandatory,
                        "status": "UNRESOLVED",
                        "reason": req.reason,
                        "evidence": [e.model_dump() if hasattr(e, "model_dump") else e for e in (req.evidence or [])],
                    })

                if len(unres_clauses) == 1:
                    explanation = f"Manual review is required because {unres_clauses[0]}."
                elif len(unres_clauses) > 1:
                    explanation = (
                        f"Manual review is required because multiple mandatory requirements could not be conclusively verified: "
                        + " ".join(f"({i+1}) {c}." for i, c in enumerate(unres_clauses))
                    )
            elif cross_review_findings:
                cf = cross_review_findings[0]
                field_label = cf.source.upper()
                explanation = f"Manual review is required because {field_label} values differ across submitted documents."
                decision_factors.append({
                    "type": "CROSS_VERIFICATION_INCONSISTENCY",
                    "field": cf.source,
                    "status": "INCONSISTENT",
                    "reason": cf.description,
                })
            elif has_forensics_anomaly:
                explanation = "Manual review is required because DOCUMENT_FORENSICS_AGENT detected an unresolved document authenticity anomaly."
            else:
                reason_msg = critical_errors[0] if critical_errors else (inconclusive_checks[0] if inconclusive_checks else "one or more verification checks require manual verification.")
                explanation = f"Manual review is required because {reason_msg}"

        elif decision == VerificationDecisionEnum.CONDITIONALLY_QUALIFIED:
            explanation = (
                "Bidder is conditionally qualified. All mandatory requirements were satisfied, "
                "but review items or warning flags require confirmation."
            )
        else:
            explanation = f"Verification completed with verdict: {decision.value}."

        return explanation, decision_factors

    def _build_confidence_breakdown(
        self,
        overall_confidence: Optional[float],
        known_confidences: List[float],
        deduped_results: List[N8nAgentResult],
        requirements_eval: List[RequirementEvaluation],
    ) -> VerificationConfidenceBreakdown:
        """
        Builds a transparent, auditable breakdown of the existing confidence calculation.
        Exposes contributing agents, requirements, unresolved conditions, and the arithmetic mean formula.
        """
        agent_confidence_items: List[AgentConfidenceItem] = []
        for ag in deduped_results:
            ag_id = ag.agent_id or ag.agent
            agent_confidence_items.append(
                AgentConfidenceItem(
                    agent_id=ag_id,
                    confidence=ag.confidence,
                    status=ag.status or ag.normalized_status or "UNKNOWN",
                )
            )

        req_confidence_items: List[RequirementConfidenceItem] = []
        for req in requirements_eval:
            status_val = req.status or (
                "PASS" if req.decision == RequirementComplianceEnum.COMPLIANT
                else ("FAIL" if req.decision == RequirementComplianceEnum.NON_COMPLIANT else "UNRESOLVED")
            )
            req_confidence_items.append(
                RequirementConfidenceItem(
                    requirement_id=req.requirement_id,
                    rule=req.rule,
                    confidence=req.confidence,
                    status=status_val,
                )
            )

        unresolved_items: List[UnresolvedConfidenceItem] = []

        # 1. Unresolved or partially verified requirements
        for req in requirements_eval:
            is_unresolved = (
                req.status == "UNRESOLVED"
                or req.decision in {RequirementComplianceEnum.UNVERIFIED, RequirementComplianceEnum.PARTIALLY_COMPLIANT}
            )
            if is_unresolved:
                unresolved_items.append(
                    UnresolvedConfidenceItem(
                        type="REQUIREMENT",
                        requirement_id=req.requirement_id,
                        rule=req.rule,
                        agent_id=req.agent,
                        status=req.status or "UNRESOLVED",
                        confidence=req.confidence,
                        reason=req.reason or "Requirement could not be conclusively verified from submitted evidence.",
                    )
                )

        # 2. Unresolved, erroneous, or non-executed agents
        unresolved_agent_statuses = {
            "UNRESOLVED", "ERROR", "NOT_EXECUTED", "INCONCLUSIVE",
            "NOT_VERIFIED", "WARNING", "REVIEW", "NOT_APPLICABLE",
        }
        for ag in deduped_results:
            st = (ag.status or "").upper()
            norm_st = (ag.normalized_status or "").upper()
            if st in unresolved_agent_statuses or norm_st in {"UNRESOLVED", "ERROR", "NOT_APPLICABLE"}:
                unresolved_items.append(
                    UnresolvedConfidenceItem(
                        type="AGENT",
                        agent_id=ag.agent_id or ag.agent,
                        status=ag.status or "UNRESOLVED",
                        confidence=ag.confidence,
                        reason=ag.reason or ("; ".join(ag.issues) if ag.issues else "Agent check inconclusive or omitted."),
                    )
                )

        return VerificationConfidenceBreakdown(
            overall_confidence=overall_confidence,
            method="arithmetic_mean",
            formula="round(sum(known_confidences) / len(known_confidences), 2)",
            inputs=known_confidences,
            calculated_confidence=overall_confidence,
            agent_confidence=agent_confidence_items,
            requirement_confidence=req_confidence_items,
            unresolved_items=unresolved_items,
        )

    def _build_cross_verification(
        self,
        payload: Optional[N8nVerificationPayload],
        deduped_results: List[N8nAgentResult],
        requirements_eval: List[RequirementEvaluation],
        bidder_name: str,
    ) -> VerificationCrossVerification:
        """
        Builds a deterministic cross-verification comparison across existing evidence records.
        Compares identifiers (GSTIN, PAN, Udyam, Legal Name) and metrics (Turnover, Experience)
        across multiple submitted documents and evaluation findings without altering decisions.
        """
        class Candidate:
            def __init__(self, val: Any, source_doc: Optional[str], page: Optional[int], ev_id: Optional[str]):
                self.val = val
                self.source_doc = source_doc
                self.page = page
                self.ev_id = ev_id

        candidates_by_field: Dict[str, List[Candidate]] = {
            "gstin": [],
            "pan": [],
            "udyam_registration": [],
            "bidder_name": [],
            "annual_turnover": [],
            "years_of_experience": [],
        }
        seen_keys: Set[Tuple[str, str, Optional[int], Optional[str], str]] = set()

        def add_candidate(field_name: str, val: Any, source_doc: Optional[str], page: Optional[int], ev_id: Optional[str]):
            if val is None or val == "":
                return
            fn = str(field_name).strip().lower()
            canon_field: Optional[str] = None
            if any(k in fn for k in ("gstin", "gst_number", "gst_no", "gst_reg")) or fn == "gst":
                canon_field = "gstin"
            elif any(k in fn for k in ("pan_number", "pan_card", "pan_no")) or fn == "pan":
                canon_field = "pan"
            elif any(k in fn for k in ("udyam", "msme")):
                canon_field = "udyam_registration"
            elif any(k in fn for k in ("turnover", "annual_turnover", "average_turnover")):
                canon_field = "annual_turnover"
            elif any(k in fn for k in ("experience", "work_period", "project_period")):
                canon_field = "years_of_experience"
            elif any(k in fn for k in ("bidder_name", "company_name", "legal_name", "entity_name")):
                canon_field = "bidder_name"

            if not canon_field:
                return

            key = (canon_field, (source_doc or "").strip(), page, (ev_id or "").strip(), str(val).strip())
            if key in seen_keys:
                return
            seen_keys.add(key)
            candidates_by_field[canon_field].append(Candidate(val, source_doc, page, ev_id))

        # 1. From payload.bidder_evidence
        if payload and payload.bidder_evidence:
            for be in payload.bidder_evidence:
                source_p = getattr(be, "page_number", None) if getattr(be, "page_number", None) is not None else getattr(be, "source_page", None)
                add_candidate(be.field, be.value, getattr(be, "source_document", None), source_p, getattr(be, "evidence_id", None))

        # 2. From requirements_eval evidence
        for req in requirements_eval:
            for ev in (req.evidence or []):
                val = ev.detected_value if ev.detected_value is not None else ev.normalized_value
                add_candidate(ev.field or req.rule or "", val, ev.source_document, ev.page_number, ev.evidence_id)

        # 3. From agent results evidence
        for ag in deduped_results:
            if isinstance(ag.evidence, list):
                for ev in ag.evidence:
                    val = ev.detected_value if ev.detected_value is not None else ev.normalized_value
                    add_candidate(ev.field or "", val, ev.source_document, ev.page_number, ev.evidence_id)
            elif isinstance(ag.evidence, dict):
                s_doc = ag.evidence.get("source_document")
                p_num = ag.evidence.get("page_number") or ag.evidence.get("source_page")
                e_id = ag.evidence.get("evidence_id")
                for k, v in ag.evidence.items():
                    if k in ("source_document", "page_number", "source_page", "evidence_id", "raw_data", "extracted_text"):
                        continue
                    add_candidate(k, v, s_doc, p_num, e_id)

        # 4. From ENTITY_RESOLUTION_AGENT output
        for ag in deduped_results:
            if ag.agent == "ENTITY_RESOLUTION_AGENT" and isinstance(ag.evidence, dict):
                for k in ("normalized_name", "legal_name", "entity_name", "resolved_name"):
                    if ag.evidence.get(k):
                        add_candidate("bidder_name", ag.evidence[k], source_doc="ENTITY_RESOLUTION_AGENT", page=None, ev_id=None)

        def norm_str(v: Any) -> str:
            return str(v).strip().upper()

        def norm_name(v: Any) -> str:
            s = re.sub(r"[^\w\s]", "", str(v).lower())
            return " ".join(s.split())

        def parse_turnover(v: Any) -> Optional[float]:
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).lower().replace("₹", "").replace("inr", "").replace("rs", "").replace(",", "").strip()
            if "crore" in s or "cr" in s:
                matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", s)
                if matches:
                    return float(matches[0]) * 10000000.0
            if "lakh" in s or "lac" in s:
                matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", s)
                if matches:
                    return float(matches[0]) * 100000.0
            matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", s)
            if matches:
                return float(matches[0])
            return None

        def parse_experience(v: Any) -> Optional[float]:
            if isinstance(v, (int, float)):
                return float(v)
            s = str(v).lower().strip()
            matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)", s)
            if matches:
                return float(matches[0])
            return None

        checks: List[CrossVerificationCheckItem] = []

        field_configs = [
            ("GSTIN_CROSS_DOCUMENT", "gstin", "GSTIN"),
            ("PAN_CROSS_DOCUMENT", "pan", "PAN"),
            ("UDYAM_CROSS_DOCUMENT", "udyam_registration", "Udyam registration"),
            ("LEGAL_NAME_CROSS_DOCUMENT", "bidder_name", "Legal entity name"),
            ("TURNOVER_CROSS_DOCUMENT", "annual_turnover", "Turnover"),
            ("EXPERIENCE_CROSS_DOCUMENT", "years_of_experience", "Experience duration"),
        ]

        for check_id, field_name, display_name in field_configs:
            cands = candidates_by_field.get(field_name, [])
            if not cands:
                continue

            values_list = [
                CrossVerificationValueItem(
                    source_document=c.source_doc,
                    page_number=c.page,
                    value=c.val,
                    evidence_id=c.ev_id,
                )
                for c in cands
            ]

            if len(cands) < 2:
                status = "UNRESOLVED"
                reason = f"Insufficient multi-source evidence to cross-verify {display_name} across documents."
            else:
                if field_name in ("gstin", "pan"):
                    normed = [norm_str(c.val) for c in cands]
                    if len(set(normed)) == 1:
                        status = "CONSISTENT"
                        reason = f"{display_name} matches across submitted documents."
                    else:
                        status = "INCONSISTENT"
                        reason = f"{display_name} values differ across submitted documents: {cands[0].val} vs {cands[1].val}."
                elif field_name == "udyam_registration":
                    normed = [norm_str(c.val).replace("-", "").replace(" ", "") for c in cands]
                    if len(set(normed)) == 1:
                        status = "CONSISTENT"
                        reason = f"{display_name} matches across submitted documents."
                    else:
                        status = "INCONSISTENT"
                        reason = f"{display_name} values differ across submitted documents: {cands[0].val} vs {cands[1].val}."
                elif field_name == "bidder_name":
                    normed = [norm_name(c.val) for c in cands]
                    if len(set(normed)) == 1:
                        status = "CONSISTENT"
                        reason = f"{display_name} matches across submitted documents."
                    else:
                        status = "INCONSISTENT"
                        reason = f"{display_name} discrepancy detected across submitted documents: '{cands[0].val}' vs '{cands[1].val}'."
                elif field_name == "annual_turnover":
                    nums = [parse_turnover(c.val) for c in cands]
                    if all(n is not None for n in nums):
                        first_n = nums[0]
                        if all(abs(n - first_n) < 1.0 for n in nums):
                            status = "CONSISTENT"
                            reason = "Turnover values are consistent across submitted documents."
                        else:
                            status = "INCONSISTENT"
                            reason = f"Turnover discrepancy detected across submitted documents: {cands[0].val} vs {cands[1].val}."
                    else:
                        normed = [norm_name(c.val) for c in cands]
                        if len(set(normed)) == 1:
                            status = "CONSISTENT"
                            reason = "Turnover values are consistent across submitted documents."
                        else:
                            status = "INCONSISTENT"
                            reason = f"Turnover discrepancy detected across submitted documents: {cands[0].val} vs {cands[1].val}."
                elif field_name == "years_of_experience":
                    nums = [parse_experience(c.val) for c in cands]
                    if all(n is not None for n in nums):
                        first_n = nums[0]
                        if all(abs(n - first_n) < 0.01 for n in nums):
                            status = "CONSISTENT"
                            reason = "Experience duration is consistent across submitted documents."
                        else:
                            status = "INCONSISTENT"
                            reason = f"Experience duration discrepancy detected across submitted documents: {cands[0].val} vs {cands[1].val}."
                    else:
                        normed = [norm_name(c.val) for c in cands]
                        if len(set(normed)) == 1:
                            status = "CONSISTENT"
                            reason = "Experience duration is consistent across submitted documents."
                        else:
                            status = "INCONSISTENT"
                            reason = f"Experience duration discrepancy detected across submitted documents: {cands[0].val} vs {cands[1].val}."
                else:
                    status = "UNRESOLVED"
                    reason = f"Unable to deterministically cross-verify {display_name}."

            checks.append(
                CrossVerificationCheckItem(
                    check_id=check_id,
                    field=field_name,
                    status=status,
                    values=values_list,
                    reason=reason,
                )
            )

        if any(c.status == "INCONSISTENT" for c in checks):
            overall_status = "INCONSISTENT"
        elif any(c.status == "CONSISTENT" for c in checks):
            overall_status = "CONSISTENT"
        else:
            overall_status = "UNRESOLVED"

        return VerificationCrossVerification(
            overall_status=overall_status,
            checks=checks,
        )

    def _classify_forensic_issue(self, issue_str: str) -> Tuple[str, str]:
        s = issue_str.lower()
        if any(k in s for k in ("forg", "tamper", "alter", "manipulat", "fraud")):
            return "TAMPERING_INDICATOR", "HIGH"
        if any(k in s for k in ("duplicate", "hash collision", "identical sha")):
            return "HASH_COLLISION", "HIGH"
        if any(k in s for k in ("corrupt", "unreadable", "readability")):
            return "FILE_CORRUPTION", "HIGH"
        if any(k in s for k in ("mime", "format", "unsupported format")):
            return "FORMAT_VIOLATION", "HIGH"
        if any(k in s for k in ("type mismatch", "classified as")):
            return "CONTENT_TYPE_MISMATCH", "MEDIUM"
        if any(k in s for k in ("metadata", "modification date", "creation date", "timestamp")):
            return "METADATA_INCONSISTENCY", "MEDIUM"
        if any(k in s for k in ("ocr", "text is empty", "short")):
            return "TEXT_DENSITY_ANOMALY", "LOW"
        return "FORENSIC_ANOMALY", "MEDIUM"

    def _build_document_forensics(
        self,
        payload: Optional[N8nVerificationPayload],
        deduped_results: List[N8nAgentResult],
        requirements_eval: List[RequirementEvaluation],
    ) -> VerificationDocumentForensics:
        """
        Builds a structured, transparent document forensics report from DOCUMENT_FORENSICS_AGENT findings,
        preserving anomalies, provenance (source_document, document_id, page_number), confidence,
        and severity without altering qualification decisions.
        """
        doc_agent = next((ag for ag in deduped_results if ag.agent == "DOCUMENT_FORENSICS_AGENT"), None)

        if not doc_agent:
            return VerificationDocumentForensics(
                overall_status="UNRESOLVED",
                overall_risk="UNKNOWN",
                documents=[],
                summary="DOCUMENT_FORENSICS_AGENT was not executed or not included in results.",
            )

        agent_status = (doc_agent.status or doc_agent.normalized_status or "UNKNOWN").upper()
        if agent_status in {"NOT_EXECUTED", "ERROR", "NOT_APPLICABLE"}:
            return VerificationDocumentForensics(
                overall_status="UNRESOLVED",
                overall_risk="UNKNOWN",
                documents=[],
                summary=doc_agent.reason or "DOCUMENT_FORENSICS_AGENT execution was inconclusive or encountered an error.",
            )

        anomalies: List[ForensicAnomalyItem] = []
        seen_anomaly_keys: Set[Tuple[str, Optional[str], Optional[str]]] = set()

        raw_evidence = None
        if isinstance(getattr(doc_agent, "execution_metadata", None), dict):
            raw_evidence = doc_agent.execution_metadata.get("raw_evidence")
        if not raw_evidence and isinstance(doc_agent.evidence, dict):
            raw_evidence = doc_agent.evidence

        # 1. Inspect structured anomalies in raw_evidence or doc_agent.evidence if provided as dict
        if isinstance(raw_evidence, dict):
            raw_anomalies = raw_evidence.get("anomalies") or raw_evidence.get("integrity_issues")
            if isinstance(raw_anomalies, list):
                for idx, item in enumerate(raw_anomalies):
                    if isinstance(item, dict):
                        anom_id = item.get("anomaly_id") or f"FORENSIC-{idx+1:03d}"
                        anom_type = item.get("anomaly_type") or item.get("type") or "FORENSIC_ANOMALY"
                        sev = item.get("severity") or "MEDIUM"
                        conf = item.get("confidence") if item.get("confidence") is not None else doc_agent.confidence
                        desc = item.get("description") or item.get("issue") or item.get("reason") or "Forensic anomaly detected"
                        src_doc = item.get("source_document") or raw_evidence.get("source_document")
                        doc_id = item.get("document_id") or raw_evidence.get("document_id")
                        p_num = item.get("page_number")
                        aff_field = item.get("affected_field")
                        ev_dict = item.get("evidence") or {}

                        key = (anom_type, src_doc, desc)
                        if key not in seen_anomaly_keys:
                            seen_anomaly_keys.add(key)
                            anomalies.append(
                                ForensicAnomalyItem(
                                    anomaly_id=anom_id,
                                    anomaly_type=anom_type,
                                    severity=sev,
                                    confidence=conf,
                                    description=desc,
                                    source_document=src_doc,
                                    document_id=doc_id,
                                    page_number=p_num,
                                    affected_field=aff_field,
                                    evidence=ev_dict if isinstance(ev_dict, dict) else {},
                                )
                            )

        # 2. Inspect structured items in doc_agent.evidence if provided as list
        elif isinstance(doc_agent.evidence, list):
            for idx, item in enumerate(doc_agent.evidence):
                if isinstance(item, StructuredEvidenceItem):
                    anom_field = (item.field or "").upper()
                    if any(k in anom_field for k in ("ANOMALY", "TAMPER", "COLLISION", "CORRUPT", "INCONSISTENCY", "MISMATCH", "DENSITY")):
                        anom_id = item.evidence_id or f"FORENSIC-{len(anomalies)+1:03d}"
                        desc = str(item.detected_value or item.evidence_text or "Forensic anomaly detected")
                        anom_type, sev = self._classify_forensic_issue(f"{anom_field} {desc}")
                        key = (anom_type, item.source_document, desc)
                        if key not in seen_anomaly_keys:
                            seen_anomaly_keys.add(key)
                            anomalies.append(
                                ForensicAnomalyItem(
                                    anomaly_id=anom_id,
                                    anomaly_type=item.field or anom_type,
                                    severity=sev,
                                    confidence=item.confidence if item.confidence is not None else doc_agent.confidence,
                                    description=desc,
                                    source_document=item.source_document,
                                    document_id=item.document_id,
                                    page_number=item.page_number,
                                    affected_field=item.field,
                                    evidence={"evidence_id": item.evidence_id} if item.evidence_id else {},
                                )
                            )
                elif isinstance(item, dict):
                    anom_id = item.get("anomaly_id") or f"FORENSIC-{idx+1:03d}"
                    anom_type = item.get("anomaly_type") or item.get("type") or "FORENSIC_ANOMALY"
                    sev = item.get("severity") or "MEDIUM"
                    conf = item.get("confidence") if item.get("confidence") is not None else doc_agent.confidence
                    desc = item.get("description") or item.get("issue") or item.get("reason") or "Forensic anomaly detected"
                    src_doc = item.get("source_document")
                    doc_id = item.get("document_id")
                    p_num = item.get("page_number")
                    aff_field = item.get("affected_field")
                    ev_dict = item.get("evidence") or {}

                    key = (anom_type, src_doc, desc)
                    if key not in seen_anomaly_keys:
                        seen_anomaly_keys.add(key)
                        anomalies.append(
                            ForensicAnomalyItem(
                                anomaly_id=anom_id,
                                anomaly_type=anom_type,
                                severity=sev,
                                confidence=conf,
                                description=desc,
                                source_document=src_doc,
                                document_id=doc_id,
                                page_number=p_num,
                                affected_field=aff_field,
                                evidence=ev_dict if isinstance(ev_dict, dict) else {},
                            )
                        )

        # 3. Inspect issues and errors from doc_agent
        issue_strings = list(doc_agent.issues) + list(doc_agent.errors)
        for idx, issue in enumerate(issue_strings):
            if not issue or not isinstance(issue, str):
                continue
            anom_type, sev = self._classify_forensic_issue(issue)
            doc_id_match = re.search(r"Document\s+['\"]?([A-Za-z0-9_\-]+)['\"]?", issue, re.IGNORECASE)
            doc_id = doc_id_match.group(1) if doc_id_match else None

            file_match = re.search(r"([A-Za-z0-9_\-]+\.(?:pdf|jpeg|jpg|png))", issue, re.IGNORECASE)
            file_name = file_match.group(1) if file_match else None

            key = (anom_type, file_name, issue)
            if key not in seen_anomaly_keys:
                seen_anomaly_keys.add(key)
                anomalies.append(
                    ForensicAnomalyItem(
                        anomaly_id=f"FORENSIC-{len(anomalies)+1:03d}",
                        anomaly_type=anom_type,
                        severity=sev,
                        confidence=doc_agent.confidence,
                        description=issue,
                        source_document=file_name,
                        document_id=doc_id,
                        page_number=None,
                        affected_field="document_integrity",
                        evidence={"raw_issue": issue},
                    )
                )

        # 3. Assemble document-level results
        doc_results: List[ForensicDocumentResult] = []
        if payload and payload.documents:
            for doc in payload.documents:
                doc_anoms = [
                    a for a in anomalies
                    if (a.document_id and a.document_id == doc.document_id)
                    or (a.source_document and doc.file_name and a.source_document.lower() == doc.file_name.lower())
                ]
                if doc_anoms:
                    has_high = any(a.severity in ("HIGH", "CRITICAL") for a in doc_anoms)
                    st = "ANOMALY" if (has_high or agent_status in ("FAIL", "FAILED", "NOT_VERIFIED")) else "SUSPICIOUS"
                    rk = "HIGH" if has_high else "MEDIUM"
                else:
                    if agent_status in ("FAIL", "FAILED", "NOT_VERIFIED"):
                        st = "SUSPICIOUS"
                        rk = "MEDIUM"
                    else:
                        st = "CLEAN"
                        rk = "LOW"

                doc_results.append(
                    ForensicDocumentResult(
                        document_id=doc.document_id,
                        source_document=doc.file_name,
                        status=st,
                        risk_level=rk,
                        confidence=doc_agent.confidence,
                        sha256=doc.sha256,
                        anomalies=doc_anoms,
                    )
                )
        else:
            if anomalies:
                grouped: Dict[str, List[ForensicAnomalyItem]] = {}
                for a in anomalies:
                    g_key = a.source_document or a.document_id or "submitted_document.pdf"
                    grouped.setdefault(g_key, []).append(a)
                for g_key, g_anoms in grouped.items():
                    has_high = any(a.severity in ("HIGH", "CRITICAL") for a in g_anoms)
                    st = "ANOMALY" if (has_high or agent_status in ("FAIL", "FAILED", "NOT_VERIFIED")) else "SUSPICIOUS"
                    rk = "HIGH" if has_high else "MEDIUM"
                    doc_results.append(
                        ForensicDocumentResult(
                            document_id=g_anoms[0].document_id if g_anoms[0].document_id else None,
                            source_document=g_anoms[0].source_document if g_anoms[0].source_document else g_key,
                            status=st,
                            risk_level=rk,
                            confidence=doc_agent.confidence,
                            anomalies=g_anoms,
                        )
                    )
            else:
                src_doc = None
                doc_id = None
                if isinstance(raw_evidence, dict):
                    src_doc = raw_evidence.get("source_document")
                    doc_id = raw_evidence.get("document_id")
                if not src_doc and doc_agent.source_documents:
                    src_doc = doc_agent.source_documents[0]
                if not src_doc and isinstance(doc_agent.evidence, list) and doc_agent.evidence:
                    first_ev = doc_agent.evidence[0]
                    src_doc = getattr(first_ev, "source_document", None)
                    doc_id = getattr(first_ev, "document_id", None)
                if not src_doc:
                    src_doc = "submitted_document.pdf"

                doc_results.append(
                    ForensicDocumentResult(
                        document_id=doc_id or "DOC-001",
                        source_document=src_doc,
                        status="CLEAN" if agent_status in ("PASS", "VERIFIED", "QUALIFIED") else "UNRESOLVED",
                        risk_level="LOW" if agent_status in ("PASS", "VERIFIED", "QUALIFIED") else "MEDIUM",
                        confidence=doc_agent.confidence,
                        anomalies=[],
                    )
                )

        # 4. Overall status and risk
        if any(d.status == "ANOMALY" for d in doc_results) or any(a.severity in ("HIGH", "CRITICAL") for a in anomalies):
            overall_status = "ANOMALY"
            overall_risk = "HIGH"
            summary = f"Forensic analysis detected {len(anomalies)} critical document anomalies or tampering indicators."
        elif any(d.status == "SUSPICIOUS" for d in doc_results) or len(anomalies) > 0:
            overall_status = "SUSPICIOUS"
            overall_risk = "MEDIUM"
            summary = f"Forensic analysis detected {len(anomalies)} suspicious document indicators requiring review."
        elif agent_status in ("PASS", "VERIFIED", "QUALIFIED"):
            overall_status = "CLEAN"
            overall_risk = "LOW"
            summary = "All evaluated documents passed cryptographic, metadata, and structural integrity checks."
        else:
            overall_status = "UNRESOLVED"
            overall_risk = "UNKNOWN"
            summary = "Document forensics status could not be conclusively determined."

        return VerificationDocumentForensics(
            overall_status=overall_status,
            overall_risk=overall_risk,
            documents=doc_results,
            summary=summary,
        )

    def _evaluate_compliance_policy(
        self,
        requirements_eval: List[RequirementEvaluation],
        deduped_results: List[N8nAgentResult],
        cross_verification: Optional[VerificationCrossVerification] = None,
        document_forensics: Optional[VerificationDocumentForensics] = None,
        warnings: Optional[List[str]] = None,
        failed_checks: Optional[List[str]] = None,
        critical_errors: Optional[List[str]] = None,
        inconclusive_checks: Optional[List[str]] = None,
        existing_decision: Optional[VerificationDecisionEnum] = None,
    ) -> VerificationCompliancePolicy:
        """
        Phase 22.7: Deterministic Compliance Policy for Cross-Verification and Forensics.
        Interprets existing verification findings across mandatory requirements,
        forensic anomalies, and cross-verification checks to determine the policy outcome.

        Precedence rules:
        1. Mandatory requirement FAIL -> NOT_QUALIFIED (Blocking)
        2. Critical/High forensic anomaly -> MANUAL_REVIEW (Review)
        3. Mandatory requirement UNRESOLVED -> MANUAL_REVIEW (Review)
        4. Cross-verification INCONSISTENT -> MANUAL_REVIEW (Review)
        5. Other warnings -> Warnings only
        6. Clean -> QUALIFIED
        """
        blocking_findings: List[PolicyFindingItem] = []
        review_findings: List[PolicyFindingItem] = []
        policy_warnings: List[str] = list(warnings or [])
        applied_rules: List[AppliedPolicyRule] = []

        # 1. Mandatory Requirement Failures (Precedence 1: Blocking -> NOT_QUALIFIED)
        for req in requirements_eval:
            req_id = req.rule or req.requirement_id
            if req.mandatory and (req.status == "FAIL" or req.decision == RequirementComplianceEnum.NON_COMPLIANT):
                finding = PolicyFindingItem(
                    finding_id=f"BLOCKING-REQ-{req.requirement_id or req.rule}",
                    finding_type="MANDATORY_REQUIREMENT_FAILURE",
                    severity="CRITICAL",
                    source=req_id,
                    description=f"Mandatory requirement '{req_id}' failed: {req.reason or 'criteria not satisfied'}.",
                )
                blocking_findings.append(finding)
                applied_rules.append(
                    AppliedPolicyRule(
                        rule_id="MANDATORY_REQUIREMENT_FAILURE",
                        trigger=req_id,
                        action="NOT_QUALIFIED",
                        reason=f"Mandatory requirement '{req_id}' failed: {req.reason or 'criteria not satisfied'}.",
                    )
                )

        # Also check critical agent failures
        for ag in deduped_results:
            st = (ag.status or "").upper()
            norm_st = getattr(ag, "normalized_status", None)
            if ag.agent in CRITICAL_AGENTS and (st in NEGATIVE_STATUSES or norm_st == "FAILED"):
                ag_already_blocked = any(b.source == ag.agent for b in blocking_findings)
                if not ag_already_blocked:
                    finding = PolicyFindingItem(
                        finding_id=f"BLOCKING-AGENT-{ag.agent}",
                        finding_type="CRITICAL_AGENT_FAILURE",
                        severity="CRITICAL",
                        source=ag.agent,
                        description=f"Critical verification agent '{ag.agent}' failed: {ag.reason or '; '.join(ag.issues) or 'execution failed'}.",
                    )
                    blocking_findings.append(finding)
                    applied_rules.append(
                        AppliedPolicyRule(
                            rule_id="CRITICAL_AGENT_FAILURE",
                            trigger=ag.agent,
                            action="NOT_QUALIFIED",
                            reason=f"Critical verification agent '{ag.agent}' failed: {ag.reason or '; '.join(ag.issues) or 'execution failed'}.",
                        )
                    )

        if failed_checks:
            for fc in failed_checks:
                if not any(fc in b.description for b in blocking_findings):
                    blocking_findings.append(
                        PolicyFindingItem(
                            finding_id=f"BLOCKING-CHECK-{len(blocking_findings)+1}",
                            finding_type="COMPLIANCE_CHECK_FAILURE",
                            severity="CRITICAL",
                            source="FAILED_CHECKS",
                            description=f"Compliance check failed: {fc}",
                        )
                    )

        # 2. Document Forensics Anomalies (Precedence 2: Review -> MANUAL_REVIEW)
        # Policy Section 6:
        # CRITICAL / HIGH tampering or forgery indicator -> MANUAL_REVIEW by default
        # File corruption/format violation that prevents reliable verification -> MANUAL_REVIEW
        # MEDIUM/LOW anomaly -> WARNING unless an existing rule already makes it blocking.
        # Phrasing: "Suspicious document indicator requires manual review: {description}"
        if document_forensics:
            forensic_anomalies: List[ForensicAnomalyItem] = []
            for doc in (document_forensics.documents or []):
                for a in (doc.anomalies or []):
                    forensic_anomalies.append(a)

            for anom in forensic_anomalies:
                sev = (anom.severity or "MEDIUM").upper()
                anom_type = (anom.anomaly_type or "").upper()
                is_high_or_crit = sev in ("HIGH", "CRITICAL") or any(
                    k in anom_type for k in ("TAMPER", "CORRUPT", "FORGERY", "COLLISION", "FORMAT_VIOLATION")
                )

                if is_high_or_crit:
                    review_desc = f"Suspicious document indicator requires manual review: {anom.description}"
                    review_findings.append(
                        PolicyFindingItem(
                            finding_id=f"REVIEW-FORENSIC-{anom.anomaly_id}",
                            finding_type="FORENSIC_ANOMALY",
                            severity=sev,
                            source=anom.source_document or "DOCUMENT_FORENSICS",
                            description=review_desc,
                        )
                    )
                    applied_rules.append(
                        AppliedPolicyRule(
                            rule_id="FORENSIC_ANOMALY_REVIEW",
                            trigger=anom.anomaly_id or anom.source_document or "DOCUMENT_FORENSICS",
                            action="MANUAL_REVIEW",
                            reason=review_desc,
                        )
                    )
                else:
                    warn_msg = f"Forensic advisory ({sev}): {anom.description}"
                    if warn_msg not in policy_warnings:
                        policy_warnings.append(warn_msg)

        # 3. Mandatory Requirement UNRESOLVED (Precedence 3: Review -> MANUAL_REVIEW)
        # Policy Section 4:
        # A mandatory requirement with status = UNRESOLVED must NOT be treated as FAIL.
        # It should create a review finding.
        for req in requirements_eval:
            req_id = req.rule or req.requirement_id
            if req.mandatory and (
                (req.status == "UNRESOLVED" and req.decision != RequirementComplianceEnum.PARTIALLY_COMPLIANT)
                or req.decision == RequirementComplianceEnum.UNVERIFIED
            ):
                unres_desc = f"Mandatory requirement '{req_id}' could not be conclusively verified and requires manual review."
                review_findings.append(
                    PolicyFindingItem(
                        finding_id=f"REVIEW-REQ-{req.requirement_id or req.rule}",
                        finding_type="MANDATORY_REQUIREMENT_UNRESOLVED",
                        severity="MEDIUM",
                        source=req_id,
                        description=unres_desc,
                    )
                )
                applied_rules.append(
                    AppliedPolicyRule(
                        rule_id="MANDATORY_REQUIREMENT_UNRESOLVED",
                        trigger=req_id,
                        action="MANUAL_REVIEW",
                        reason=f"Mandatory requirement '{req_id}' is unresolved: {req.reason or 'insufficient evidence'}.",
                    )
                )

        # Check agents with review or unverified statuses
        for ag in deduped_results:
            st = (ag.status or "").upper()
            norm_st = getattr(ag, "normalized_status", None)
            if st in {"REVIEW", "UNVERIFIED", "INCONCLUSIVE", "MANUAL_REVIEW"} or (st not in PARTIAL_STATUSES and norm_st == "UNRESOLVED"):
                ag_already_reviewed = any(r.source == ag.agent for r in review_findings)
                if not ag_already_reviewed:
                    review_findings.append(
                        PolicyFindingItem(
                            finding_id=f"REVIEW-AGENT-{ag.agent}",
                            finding_type="AGENT_REVIEW_REQUIRED",
                            severity="MEDIUM",
                            source=ag.agent,
                            description=f"Verification agent '{ag.agent}' requires manual review: {ag.reason or '; '.join(ag.issues) or 'inconclusive verification'}.",
                        )
                    )
                    applied_rules.append(
                        AppliedPolicyRule(
                            rule_id="AGENT_REVIEW_REQUIRED",
                            trigger=ag.agent,
                            action="MANUAL_REVIEW",
                            reason=f"Verification agent '{ag.agent}' requires manual review: {ag.reason or '; '.join(ag.issues) or 'inconclusive verification'}.",
                        )
                    )

        if inconclusive_checks:
            for ic in inconclusive_checks:
                review_findings.append(
                    PolicyFindingItem(
                        finding_id=f"REVIEW-CHECK-{len(review_findings)+1}",
                        finding_type="INCONCLUSIVE_CHECK",
                        severity="MEDIUM",
                        source="INCONCLUSIVE_CHECKS",
                        description=f"Inconclusive verification check: {ic}",
                    )
                )

        # 4. Cross-Verification Inconsistency (Precedence 4: Review -> MANUAL_REVIEW)
        # Policy Section 5:
        # For each check with status = INCONSISTENT -> classify as MANUAL_REVIEW
        # Default policy: INCONSISTENT -> MANUAL_REVIEW
        # Status = UNRESOLVED -> does not automatically disqualify or trigger manual review (remains warning/advisory).
        if cross_verification and cross_verification.checks:
            for check in cross_verification.checks:
                chk_st = (check.status or "").upper()
                if chk_st == "INCONSISTENT":
                    cross_desc = f"Cross-document discrepancy detected for {check.field}: {check.reason or 'Values differ across submitted documents.'}"
                    review_findings.append(
                        PolicyFindingItem(
                            finding_id=f"REVIEW-CROSS-{check.check_id}",
                            finding_type="CROSS_VERIFICATION_INCONSISTENCY",
                            severity="HIGH",
                            source=check.field,
                            description=cross_desc,
                        )
                    )
                    applied_rules.append(
                        AppliedPolicyRule(
                            rule_id="CROSS_VERIFICATION_INCONSISTENCY",
                            trigger=check.check_id or check.field,
                            action="MANUAL_REVIEW",
                            reason=f"{check.field.upper()} values differ across submitted documents: {check.reason or 'Inconsistency found.'}",
                        )
                    )
                elif chk_st == "UNRESOLVED":
                    warn_msg = f"Cross-verification check '{check.field}' unresolved: {check.reason or 'Second document missing'}"
                    if warn_msg not in policy_warnings:
                        policy_warnings.append(warn_msg)

        # 5. Resolve Final Status by Deterministic Precedence
        if blocking_findings:
            final_status = "NOT_QUALIFIED"
        elif review_findings:
            final_status = "MANUAL_REVIEW"
        elif existing_decision == VerificationDecisionEnum.NOT_QUALIFIED:
            final_status = "NOT_QUALIFIED"
        elif existing_decision == VerificationDecisionEnum.MANUAL_REVIEW:
            final_status = "MANUAL_REVIEW"
        else:
            final_status = "QUALIFIED"
            applied_rules.append(
                AppliedPolicyRule(
                    rule_id="ALL_MANDATORY_REQUIREMENTS_PASSED",
                    trigger="ALL_REQUIREMENTS",
                    action="QUALIFIED",
                    reason="All mandatory tender requirements and verification checks successfully passed.",
                )
            )

        return VerificationCompliancePolicy(
            final_status=final_status,
            blocking_findings=blocking_findings,
            review_findings=review_findings,
            warnings=policy_warnings,
            applied_rules=applied_rules,
        )

    def _build_document_similarity(
        self,
        payload: Optional[N8nVerificationPayload] = None,
        requirements_eval: Optional[List[RequirementEvaluation]] = None,
        documents: Optional[List[Any]] = None,
        bidder_evidence: Optional[List[Any]] = None,
    ) -> VerificationDocumentSimilarity:
        """
        Builds a deterministic document similarity and duplicate detection assessment (Phase 22.8)
        across extracted document texts and cryptographic hashes.
        Strictly informational: does not alter qualification verdicts or risk scores.
        """
        doc_list = list(documents) if documents else []
        ev_list = list(bidder_evidence) if bidder_evidence else []

        if payload and getattr(payload, "documents", None):
            doc_list.extend(payload.documents)
        if payload and getattr(payload, "bidder_evidence", None):
            ev_list.extend(payload.bidder_evidence)

        if requirements_eval:
            for req in requirements_eval:
                for ev in (req.evidence or []):
                    ev_list.append(ev)

        return document_similarity_service.analyze_similarity(
            payload=payload,
            documents=doc_list if doc_list else None,
            bidder_evidence=ev_list if ev_list else None,
        )


verification_aggregator = VerificationResultAggregator()
