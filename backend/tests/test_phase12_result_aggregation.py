"""
SIH-26100 — Phase 12.6 Test Suite
tests/test_phase12_result_aggregation.py

Verifies:
n8n Agent Results
       ↓
Result Validation
       ↓
Agent Result Aggregation
       ↓
Requirement-Level Compliance
       ↓
Overall Compliance Decision
       ↓
Risk Assessment
       ↓
Final Verification Result
       ↓
FastAPI
"""
import asyncio
import io
import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from uuid import UUID

import pytest
from pydantic import ValidationError

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.schemas.verification import (
    DEFAULT_VERIFICATION_AGENTS,
    AgentStatusEnum,
    BidderEvidenceItemInput,
    DocumentForensicInput,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    OverallComplianceEnum,
    RequirementComplianceEnum,
    RequirementEvaluation,
    RiskLevelEnum,
    TenderRequirementItemInput,
    VerificationComplianceSummary,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationRiskAssessment,
    VerificationStatusEnum,
    VerificationTriggerRequest,
)
from app.services.verification_aggregator import (
    VerificationResultAggregator,
    verification_aggregator,
)


class TestPhase12ResultAggregation(unittest.TestCase):
    """
    Phase 12.6 Result Aggregation, Final Compliance & Risk Decision Test Suite.
    Tests 1 to 20 validating requirement-level compliance, deterministic aggregation rules,
    explainable risk assessments, confidence handling, provenance, and security.
    """

    def setUp(self):
        self.aggregator = VerificationResultAggregator()
        self.tender_id = uuid.uuid4()
        self.bidder_id = uuid.uuid4()

    def _build_mock_payload(
        self,
        requirements: list[TenderRequirementItemInput] = None,
        evidence: list[BidderEvidenceItemInput] = None,
    ) -> N8nVerificationPayload:
        if requirements is None:
            requirements = [
                TenderRequirementItemInput(
                    requirement_id=str(uuid.uuid4()),
                    category="FINANCIAL",
                    requirement_type="FINANCIAL",
                    rule="MINIMUM_TURNOVER",
                    description="Minimum turnover ₹10 Cr",
                    mandatory=True,
                    parameters={"minimum": 100000000.0},
                    source_page=2,
                    source_section="Financial Eligibility",
                    source_text="Average annual turnover of Rs 10 Crore",
                )
            ]
        if evidence is None:
            evidence = [
                BidderEvidenceItemInput(
                    evidence_id=str(uuid.uuid4()),
                    bidder_id=str(self.bidder_id),
                    document_id=str(uuid.uuid4()),
                    document_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    field="turnover",
                    value={"amount": 120000000.0},
                    source_page=1,
                    source_text="Annual Turnover: ₹12,00,00,000",
                    confidence=0.96,
                )
            ]

        return N8nVerificationPayload(
            request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
            verification_id=f"VER-{uuid.uuid4().hex[:8].upper()}",
            tender_id=str(self.tender_id),
            bidder_id=str(self.bidder_id),
            bidder_name="Apex Teleinfra Private Limited",
            required_agents=["FINANCIAL_AGENT", "GST_AGENT"],
            tender_requirements=requirements,
            bidder_evidence=evidence,
        )

    def _build_n8n_response(
        self,
        agent_results: list[N8nAgentResult],
        risk_score: float = 10.0,
        risk_level: str = "LOW",
        decision: str = "QUALIFIED",
    ) -> N8nVerificationResponse:
        return N8nVerificationResponse(
            verification_id=f"VER-{uuid.uuid4().hex[:8].upper()}",
            request_id=f"REQ-{uuid.uuid4().hex[:8].upper()}",
            tender_id=str(self.tender_id),
            bidder_id=str(self.bidder_id),
            bidder_name="Apex Teleinfra Private Limited",
            status="COMPLETED",
            decision=decision,
            risk_score=risk_score,
            risk_level=risk_level,
            agent_results=agent_results,
            failed_requirements=[],
            warnings=[],
            missing_documents=[],
            reasons=["All evaluation criteria processed."],
        )

    # -------------------------------------------------------------------------
    # Test 1: All requirements compliant → COMPLIANT
    # -------------------------------------------------------------------------
    def test_01_all_requirements_compliant_yields_compliant(self):
        """Test 1: When all requirements meet criteria with passing agents, overall verdict is COMPLIANT."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.96, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.overall_compliance, OverallComplianceEnum.COMPLIANT)
        self.assertEqual(resp.decision, VerificationDecisionEnum.QUALIFIED)
        self.assertEqual(len(resp.requirements), 1)
        self.assertEqual(resp.requirements[0].decision, RequirementComplianceEnum.COMPLIANT)
        self.assertEqual(resp.summary.compliant, 1)
        self.assertEqual(resp.summary.non_compliant, 0)

    # -------------------------------------------------------------------------
    # Test 2: Mandatory requirement failed → NON_COMPLIANT
    # -------------------------------------------------------------------------
    def test_02_mandatory_requirement_failed_yields_non_compliant(self):
        """Test 2: When any mandatory requirement fails, overall compliance must be NON_COMPLIANT."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="FAIL",
                confidence=0.95,
                issues=["Turnover ₹8 Cr is below mandatory threshold of ₹10 Cr"],
                risk_level="HIGH",
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents, risk_score=65.0, risk_level="HIGH")

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.overall_compliance, OverallComplianceEnum.NON_COMPLIANT)
        self.assertEqual(resp.decision, VerificationDecisionEnum.NOT_QUALIFIED)
        self.assertEqual(resp.requirements[0].decision, RequirementComplianceEnum.NON_COMPLIANT)
        self.assertEqual(resp.summary.non_compliant, 1)
        self.assertTrue(any("failed" in r.lower() for r in resp.reasons))

    # -------------------------------------------------------------------------
    # Test 3: Mandatory requirement unverified → UNVERIFIED
    # -------------------------------------------------------------------------
    def test_03_mandatory_requirement_unverified_yields_unverified(self):
        """Test 3: When responsible agent encounters error, requirement and overall decision are UNVERIFIED."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="ERROR",
                confidence=0.0,
                errors=["Service timeout during MCA balance sheet fetch"],
                risk_level="HIGH",
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.overall_compliance, OverallComplianceEnum.UNVERIFIED)
        self.assertEqual(resp.decision, VerificationDecisionEnum.MANUAL_REVIEW)
        self.assertEqual(resp.requirements[0].decision, RequirementComplianceEnum.UNVERIFIED)
        self.assertEqual(resp.summary.unverified, 1)

    # -------------------------------------------------------------------------
    # Test 4: Partial compliance → PARTIALLY_COMPLIANT
    # -------------------------------------------------------------------------
    def test_04_partial_compliance_yields_partially_compliant(self):
        """Test 4: Warning flags or review items on requirements evaluate to PARTIALLY_COMPLIANT."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="PARTIAL",
                confidence=0.75,
                issues=["Provisional financials submitted; audited statement pending"],
                risk_level="MEDIUM",
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.overall_compliance, OverallComplianceEnum.PARTIALLY_COMPLIANT)
        self.assertEqual(resp.decision, VerificationDecisionEnum.CONDITIONALLY_QUALIFIED)
        self.assertEqual(resp.requirements[0].decision, RequirementComplianceEnum.PARTIALLY_COMPLIANT)
        self.assertEqual(resp.summary.partially_compliant, 1)

    # -------------------------------------------------------------------------
    # Test 5: Missing evidence → UNVERIFIED
    # -------------------------------------------------------------------------
    def test_05_missing_evidence_yields_unverified_never_compliant(self):
        """Test 5: Invariant - If supporting evidence is missing, requirement is UNVERIFIED, never COMPLIANT."""
        # Empty evidence list
        payload = self._build_mock_payload(evidence=[])
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.requirements[0].decision, RequirementComplianceEnum.UNVERIFIED)
        self.assertNotEqual(resp.requirements[0].decision, RequirementComplianceEnum.COMPLIANT)
        self.assertEqual(resp.overall_compliance, OverallComplianceEnum.UNVERIFIED)
        self.assertIn("No relevant evidence", resp.requirements[0].reason)

    # -------------------------------------------------------------------------
    # Test 6: Agent error → requirement not falsely passed
    # -------------------------------------------------------------------------
    def test_06_agent_error_does_not_falsely_pass(self):
        """Test 6: Agent failure or timeout must never silently convert to COMPLIANT."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="ERROR",
                errors=["Connection reset by peer"],
                risk_level="HIGH",
            ),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertNotEqual(resp.requirements[0].decision, RequirementComplianceEnum.COMPLIANT)
        self.assertEqual(resp.requirements[0].decision, RequirementComplianceEnum.UNVERIFIED)

    # -------------------------------------------------------------------------
    # Test 7: Malformed agent response rejected
    # -------------------------------------------------------------------------
    def test_07_malformed_agent_response_rejected(self):
        """Test 7: Malformed agent objects (e.g. invalid confidence) are rejected without crashing."""
        payload = self._build_mock_payload()
        # Raw dict with invalid confidence > 1.0
        malformed_agent_results = [
            {
                "agent": "MALFORMED_AGENT",
                "status": "PASS",
                "confidence": 5.5,  # Invalid: must be <= 1.0
            },
            {
                "agent": "FINANCIAL_AGENT",
                "status": "PASS",
                "confidence": 0.95,
            },
            {
                "agent": "GST_AGENT",
                "status": "PASS",
                "confidence": 0.98,
            },
        ]
        n8n_resp = self._build_n8n_response(agent_results=[])
        n8n_resp.agent_results = malformed_agent_results  # assign raw list of dicts

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # The malformed agent with confidence 5.5 must be filtered out
        agent_names = [a.agent for a in resp.agent_results]
        self.assertNotIn("MALFORMED_AGENT", agent_names)
        self.assertIn("FINANCIAL_AGENT", agent_names)

    # -------------------------------------------------------------------------
    # Test 8: Risk LOW
    # -------------------------------------------------------------------------
    def test_08_risk_low_evaluation(self):
        """Test 8: Clear checks with no discrepancies evaluate to LOW risk."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.99, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents, risk_score=5.0)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.risk.level, RiskLevelEnum.LOW)
        self.assertLess(resp.risk.score, 30.0)

    # -------------------------------------------------------------------------
    # Test 9: Risk MEDIUM
    # -------------------------------------------------------------------------
    def test_09_risk_medium_evaluation(self):
        """Test 9: Advisory warnings or moderate scores produce MEDIUM risk."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="WARNING",
                issues=["Minor working capital delay observed"],
                risk_level="MEDIUM",
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.95, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents, risk_score=35.0)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.risk.level, RiskLevelEnum.MEDIUM)
        self.assertGreaterEqual(resp.risk.score, 30.0)
        self.assertLess(resp.risk.score, 60.0)

    # -------------------------------------------------------------------------
    # Test 10: Risk HIGH
    # -------------------------------------------------------------------------
    def test_10_risk_high_evaluation(self):
        """Test 10: Requirement violations or elevated scores produce HIGH risk."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="FAIL",
                issues=["Minimum turnover requirement unmet"],
                risk_level="HIGH",
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.90, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents, risk_score=65.0)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.risk.level, RiskLevelEnum.HIGH)
        self.assertGreaterEqual(resp.risk.score, 60.0)

    # -------------------------------------------------------------------------
    # Test 11: Critical risk condition
    # -------------------------------------------------------------------------
    def test_11_critical_risk_condition_triggers_critical(self):
        """Test 11: Document forgery indicator triggers CRITICAL risk condition."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.95, risk_level="LOW"),
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="FAIL",
                issues=["Critical: Forgery detected in CA certificate seal and digital signature alteration"],
                risk_level="CRITICAL",
            ),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.risk.level, RiskLevelEnum.CRITICAL)
        self.assertTrue(any("forgery" in f.lower() for f in resp.risk.critical_flags))

    # -------------------------------------------------------------------------
    # Test 12: Entity mismatch
    # -------------------------------------------------------------------------
    def test_12_entity_mismatch_triggers_critical_flag(self):
        """Test 12: Entity Resolution agent mismatch raises entity conflict critical risk."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="ENTITY_RESOLUTION_AGENT",
                status="FAIL",
                issues=["Entity mismatch between bidder registration name and PAN card holder"],
                risk_level="CRITICAL",
            ),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp.risk.level, RiskLevelEnum.CRITICAL)
        self.assertTrue(any("mismatch" in f.lower() for f in resp.risk.critical_flags))

    # -------------------------------------------------------------------------
    # Test 13: Document-forensics failure
    # -------------------------------------------------------------------------
    def test_13_document_forensics_failure_handling(self):
        """Test 13: Forensic tampering findings directly elevate risk and trigger explainable flags."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="FAIL",
                issues=["Tampered PDF metadata: modified timestamp precedes creation timestamp"],
                risk_level="HIGH",
            ),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertIn("DOCUMENT_FORENSICS_AGENT", resp.risk.signals)
        self.assertGreaterEqual(resp.risk.score, 50.0)

    # -------------------------------------------------------------------------
    # Test 14: Confidence preservation
    # -------------------------------------------------------------------------
    def test_14_confidence_preservation(self):
        """Test 14: Known confidence scores are strictly preserved and calculated."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.88, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.92, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        fin_eval = next(r for r in resp.requirements if r.rule == "MINIMUM_TURNOVER")
        self.assertEqual(fin_eval.confidence, 0.88)
        self.assertIsNotNone(resp.overall_confidence)

    # -------------------------------------------------------------------------
    # Test 15: Missing confidence
    # -------------------------------------------------------------------------
    def test_15_missing_confidence_handled_as_null(self):
        """Test 15: Invariant - Missing confidence is represented as None/null without crashing."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=None, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=None, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertIsNone(resp.overall_confidence)
        self.assertIsNone(resp.requirements[0].confidence)

    # -------------------------------------------------------------------------
    # Test 16: Evidence traceability
    # -------------------------------------------------------------------------
    def test_16_evidence_traceability_survives(self):
        """Test 16: Correlated evidence IDs and document IDs are retained in requirement evaluations."""
        ev_id = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        ev = BidderEvidenceItemInput(
            evidence_id=ev_id,
            bidder_id=str(self.bidder_id),
            document_id=doc_id,
            document_hash="hash123",
            field="turnover",
            value={"amount": 150000000.0},
            source_page=4,
            source_text="FY25 Turnover ₹15 Cr",
            confidence=0.99,
        )
        payload = self._build_mock_payload(evidence=[ev])
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.95, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        req_eval = resp.requirements[0]
        self.assertIn(ev_id, req_eval.evidence_ids)
        self.assertIn(doc_id, req_eval.document_ids)

    # -------------------------------------------------------------------------
    # Test 17: Requirement traceability
    # -------------------------------------------------------------------------
    def test_17_requirement_traceability_survives(self):
        """Test 17: Source page, section, text, and description survive in the requirement evaluation."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.95, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        req_eval = resp.requirements[0]
        self.assertEqual(req_eval.source_page, 2)
        self.assertEqual(req_eval.source_section, "Financial Eligibility")
        self.assertIn("Average annual turnover", req_eval.source_text)

    # -------------------------------------------------------------------------
    # Test 18: Deterministic aggregation
    # -------------------------------------------------------------------------
    def test_18_deterministic_aggregation_consistency(self):
        """Test 18: Aggregation outputs identical results across repeated executions on identical inputs."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.95, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp1 = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        resp2 = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        self.assertEqual(resp1.overall_compliance, resp2.overall_compliance)
        self.assertEqual(resp1.decision, resp2.decision)
        self.assertEqual(resp1.risk.level, resp2.risk.level)
        self.assertEqual(resp1.risk.score, resp2.risk.score)
        self.assertEqual(resp1.summary.model_dump(), resp2.summary.model_dump())

    # -------------------------------------------------------------------------
    # Test 19: No Groq calls during aggregation
    # -------------------------------------------------------------------------
    def test_19_no_groq_calls_during_aggregation(self):
        """Test 19: Invariant - Aggregation logic executes with zero Groq LLM calls."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.95, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        with patch("groq.Groq") as mock_groq:
            resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
            mock_groq.assert_not_called()

    # -------------------------------------------------------------------------
    # Test 20: No secrets exposed in final response
    # -------------------------------------------------------------------------
    def test_20_no_secrets_exposed_in_final_response(self):
        """Test 20: Serialized response contains zero API keys, postgres URLs, or secret tokens."""
        payload = self._build_mock_payload()
        agents = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", confidence=0.95, risk_level="LOW"),
            N8nAgentResult(agent="GST_AGENT", status="PASS", confidence=0.98, risk_level="LOW"),
        ]
        n8n_resp = self._build_n8n_response(agent_results=agents)

        resp = self.aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        serialized = resp.model_dump_json()

        forbidden_patterns = ["postgresql://", "gsk_", "Bearer ey", "webhook_secret", "password"]
        for pattern in forbidden_patterns:
            self.assertNotIn(pattern, serialized)


if __name__ == "__main__":
    unittest.main()
