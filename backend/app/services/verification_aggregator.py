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
    AgentStatusEnum,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    OverallComplianceEnum,
    RequirementComplianceEnum,
    RequirementEvaluation,
    RiskLevelEnum,
    VerificationComplianceSummary,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationRiskAssessment,
    VerificationStatusEnum,
)

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

POSITIVE_STATUSES: Set[str] = {"PASS", "VERIFIED", "QUALIFIED"}
NEGATIVE_STATUSES: Set[str] = {"FAIL", "FAILED", "NOT_VERIFIED", "NOT_QUALIFIED"}
PARTIAL_STATUSES: Set[str] = {"PARTIAL", "WARNING", "REVIEW", "CONDITIONALLY_QUALIFIED"}
ERROR_STATUSES: Set[str] = {"ERROR", "NOT_EXECUTED", "INCONCLUSIVE", "SKIPPED", "UNKNOWN"}

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

            name = (agent_obj.agent_name or agent_obj.agent or "").strip().upper()
            if not name:
                continue
            if name in seen_agents:
                logger.warning(f"[aggregator-dedup] Duplicate result for agent '{name}' ignored to prevent double-counting.")
                continue
            seen_agents.add(name)

            # Preserve metadata & IDs onto result
            enriched_agent = agent_obj.model_copy()
            enriched_agent.agent = name
            enriched_agent.agent_name = name
            enriched_agent.verification_id = verification_id
            enriched_agent.tender_id = str(t_uuid)
            enriched_agent.bidder_id = str(b_uuid)
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
                    agent_name=norm_name,
                    status="NOT_EXECUTED",
                    verification_id=verification_id,
                    tender_id=str(t_uuid),
                    bidder_id=str(b_uuid),
                    confidence=0.0,
                    evidence={},
                    issues=[f"Required agent '{norm_name}' was not executed or returned no results."],
                    findings=[f"Required agent '{norm_name}' was not executed or returned no results."],
                    errors=[f"Required agent '{norm_name}' was not executed or returned no results."],
                    risk_level="HIGH",
                    reason="Required agent was not executed or omitted from workflow output.",
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
            if msg and msg not in failed_checks:
                failed_checks.append(msg)
        for w in n8n_resp.warnings:
            if w and w not in warnings:
                warnings.append(str(w))

        # Check agent-level outcomes
        for ag in deduped_results:
            st = ag.status.upper()
            ag_name = ag.agent
            is_critical = ag_name in CRITICAL_AGENTS

            if st in NEGATIVE_STATUSES:
                detail = f"{ag_name} failed: {'; '.join(ag.issues)}" if ag.issues else f"{ag_name} failed verification."
                failed_checks.append(detail)
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
            reasons=reasons,
            failed_requirements=failed_checks,
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

        # Invariant: If mandatory evidence is missing -> UNVERIFIED (Never COMPLIANT)
        if not correlated_evidence:
            decision = RequirementComplianceEnum.UNVERIFIED
            reason = f"No relevant evidence provided for requirement '{req.rule}'."
            findings.append("Missing required supporting documentation or evidence.")
            return RequirementEvaluation(
                requirement_id=str(req.requirement_id),
                rule=req.rule,
                description=req.description,
                mandatory=req.mandatory,
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

        return RequirementEvaluation(
            requirement_id=str(req.requirement_id),
            rule=req.rule,
            description=req.description,
            mandatory=req.mandatory,
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
        if "FORENSIC" in t or "FORGERY" in r or "INTEGRITY" in r or "TAMPER" in r:
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
        if "experience" in t or "similar_work" in r:
            if "experience" in field or "work" in field or "project" in field:
                return True
        if "gst" in r and "gst" in field:
            return True
        if "pan" in r and "pan" in field:
            return True
        if ("udyam" in r or "msme" in r) and ("udyam" in field or "msme" in field):
            return True
        # If generic matching
        if field in r or r in field:
            return True
        return False

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


verification_aggregator = VerificationResultAggregator()
