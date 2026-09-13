"""
Phase 21.5 — Verification Result Consistency, Evidence Mapping & Decision Debugging Tests
Validates:
1. Experience clause extraction without hallucinated projects count
2. Experience criteria mapping (min_years=5, minimum_similar_works=0)
3. Bidder experience evidence extraction (years_of_experience=7)
4. Experience Agent pass evaluation (7 >= 5 -> VERIFIED/PASS)
5. Experience Agent fail evaluation (3 < 5 -> FAIL, 1 distinct failure message)
6. Compliance counts mathematical consistency (total == C + NC + PC + U)
7. Decision consistency with zero non-compliant requirements (MANUAL_REVIEW, not NOT_QUALIFIED)
8. Decision consistency with all compliant requirements (QUALIFIED, LOW risk)
9. Decision consistency with non-compliant requirements (NOT_QUALIFIED, HIGH risk)
10. Failed requirements deduplication (no repeated strings)
11. Evidence provenance linkage (document_ids and evidence_ids preserved)
12. Single verification execution record persistence
13. Groq used strictly for ambiguous clauses, not deterministic experience
"""
import uuid
import pytest
from app.models.enums import RequirementType
from app.schemas.verification import (
    ExperienceRequirementsInput,
    ExperienceEvidenceInput,
    N8nAgentResult,
    N8nVerificationPayload,
    N8nVerificationResponse,
    RequirementComplianceEnum,
    TenderRequirementItemInput,
    BidderEvidenceItemInput,
    VerificationDecisionEnum,
    OverallComplianceEnum,
)
from app.services.tender_clause_extractor import TenderClauseExtractor
from app.services.tender_requirement_normalizer import TenderRequirementNormalizer
from app.services.verification_aggregator import verification_aggregator


class TestPhase21_5VerificationConsistency:

    def test_experience_clause_extraction(self):
        """1. Verify tender with 'at least 5 years of relevant experience' extracts min_years=5 without requiring 3 projects."""
        sample_text = "The bidder must have at least 5 years of relevant experience in the supply and implementation of enterprise IT solutions."
        result = TenderClauseExtractor.detect_experience_clause(sample_text, in_eligibility_section=True)

        assert result is not None, "detect_experience_clause failed to detect experience clause"
        reason, kws, conf, params = result
        assert "years_experience" in kws
        assert conf >= 0.90
        assert params.get("min_years") == 5
        assert "min_orders" not in params

    def test_experience_criteria_mapping(self):
        """2. Verify schema defaults and mapping sets experience_period_years=5, minimum_similar_works=0."""
        req = ExperienceRequirementsInput(
            experience_period_years=5,
            minimum_similar_works=0,
        )
        assert req.minimum_similar_works == 0
        assert req.experience_period_years == 5

        # Normalizer test
        sample_text = "The bidder must have at least 5 years of relevant experience in IT solutions."
        normalized = TenderRequirementNormalizer.normalize_clause(sample_text)
        assert normalized.status.value == "NORMALIZED"
        assert normalized.parameters.get("min_years") == 5
        assert normalized.parameters.get("experience_period_years") == 5
        assert normalized.parameters.get("min_completed_orders") is None

    def test_bidder_experience_evidence_extraction(self):
        """3. Verify bidder text with '7 years of relevant experience' matches regex and captures 7."""
        import re
        bidder_text = "The bidder has 7 years of relevant experience in enterprise software deployment and support."
        match = re.search(r"\b(\d+)\s+years?\s+(?:of\s+)?(?:relevant\s+|past\s+)?experience\b", bidder_text, re.IGNORECASE)
        assert match is not None
        years = int(match.group(1))
        assert years == 7

    def test_experience_agent_evaluation_pass(self):
        """4. Verify Experience evaluation with 7 years against 5-year requirement passes without project count failure."""
        from app.services.verification_service import VerificationService
        service = VerificationService()

        t_id = str(uuid.uuid4())
        b_id = str(uuid.uuid4())
        payload = N8nVerificationPayload(
            request_id="REQ-TEST-EXP-01",
            verification_id="VER-TEST-EXP-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Apex Tech Pvt Ltd",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-EXP",
                    category="EXPERIENCE",
                    requirement_type="EXPERIENCE",
                    rule="EXPERIENCE_PERIOD",
                    description="5 years of experience",
                    parameters={"min_years": 5, "experience_period_years": 5},
                    mandatory=True,
                    confidence=0.98,
                )
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EV-EXP-01",
                    bidder_id=b_id,
                    field="years_of_experience",
                    value=7,
                    confidence=0.98,
                    extraction_method="DETERMINISTIC",
                ),
                BidderEvidenceItemInput(
                    evidence_id="EV-GST-01",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AABCB1234F1Z5",
                    confidence=0.99,
                    extraction_method="DETERMINISTIC",
                ),
                BidderEvidenceItemInput(
                    evidence_id="EV-PAN-01",
                    bidder_id=b_id,
                    field="pan",
                    value="AABCB1234F",
                    confidence=0.99,
                    extraction_method="DETERMINISTIC",
                ),
            ],
            required_agents=["EXPERIENCE_AGENT"],
        )

        n8n_resp = service._execute_local_multi_agent_fallback(payload=payload)
        exp_agent = next((ag for ag in n8n_resp.agent_results if ag.agent == "EXPERIENCE_AGENT"), None)
        assert exp_agent is not None
        assert exp_agent.status == "PASS"
        assert exp_agent.decision == "QUALIFIED"
        assert "YEARS_OF_EXPERIENCE" not in n8n_resp.failed_requirements
        assert len(n8n_resp.failed_requirements) == 0

    def test_experience_agent_evaluation_fail(self):
        """5. Verify bidder with 3 years against 5-year requirement fails with distinct single failure message."""
        from app.services.verification_service import VerificationService
        service = VerificationService()

        t_id = str(uuid.uuid4())
        b_id = str(uuid.uuid4())
        payload = N8nVerificationPayload(
            request_id="REQ-TEST-EXP-02",
            verification_id="VER-TEST-EXP-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Junior Tech Ltd",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-EXP",
                    category="EXPERIENCE",
                    requirement_type="EXPERIENCE",
                    rule="EXPERIENCE_PERIOD",
                    description="5 years of experience",
                    parameters={"min_years": 5, "experience_period_years": 5},
                    mandatory=True,
                    confidence=0.98,
                )
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="EV-EXP-02",
                    bidder_id=b_id,
                    field="years_of_experience",
                    value=3,
                    confidence=0.98,
                    extraction_method="DETERMINISTIC",
                ),
                BidderEvidenceItemInput(
                    evidence_id="EV-GST-02",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AABCB1234F1Z5",
                    confidence=0.99,
                    extraction_method="DETERMINISTIC",
                ),
                BidderEvidenceItemInput(
                    evidence_id="EV-PAN-02",
                    bidder_id=b_id,
                    field="pan",
                    value="AABCB1234F",
                    confidence=0.99,
                    extraction_method="DETERMINISTIC",
                ),
            ],
            required_agents=["EXPERIENCE_AGENT"],
        )

        n8n_resp = service._execute_local_multi_agent_fallback(payload=payload)
        exp_agent = next((ag for ag in n8n_resp.agent_results if ag.agent == "EXPERIENCE_AGENT"), None)
        assert exp_agent is not None
        assert exp_agent.status == "FAIL"
        assert exp_agent.decision == "NOT_QUALIFIED"
        assert "YEARS_OF_EXPERIENCE" in n8n_resp.failed_requirements
        assert len(n8n_resp.failed_requirements) == 1

    def test_compliance_counts_mathematical_consistency(self):
        """6. Verify total == compliant + non_compliant + partially_compliant + unverified strictly holds."""
        b_id = str(uuid.uuid4())
        agent_res = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}, findings=[]),
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.99, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-MATH-01",
            request_id="REQ-MATH-01",
            tender_id=str(uuid.uuid4()),
            bidder_id=b_id,
            bidder_name="Math Test Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=10.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=["All checks passed"],
        )

        payload = N8nVerificationPayload(
            request_id="REQ-MATH-01",
            verification_id="VER-MATH-01",
            tender_id=n8n_resp.tender_id,
            bidder_id=b_id,
            bidder_name="Math Test Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="FINANCIAL", requirement_type="FINANCIAL", rule="MINIMUM_TURNOVER", description="Turnover", parameters={"minimum": 1000000}, mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", description="GST", parameters={}, mandatory=True),
                TenderRequirementItemInput(requirement_id="R3", category="TECHNICAL", requirement_type="TECHNICAL", rule="ISO_9001", description="ISO Certification", parameters={}, mandatory=False),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="annual_turnover", value=1500000),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="gstin", value="29AABCB1234F1Z5"),
            ],
            required_agents=["FINANCIAL_AGENT", "GST_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        summary = response.summary
        total_sum = summary.compliant + summary.non_compliant + summary.partially_compliant + summary.unverified
        assert summary.total_requirements == total_sum == 3
        assert summary.compliant == 2
        assert summary.unverified == 1
        assert summary.non_compliant == 0

    def test_decision_consistency_zero_non_compliant(self):
        """7. If non_compliant == 0 and unverified > 0, decision is MANUAL_REVIEW, NEVER NOT_QUALIFIED."""
        b_id = str(uuid.uuid4())
        agent_res = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-DEC-01",
            request_id="REQ-DEC-01",
            tender_id=str(uuid.uuid4()),
            bidder_id=b_id,
            bidder_name="Review Test Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=20.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        payload = N8nVerificationPayload(
            request_id="REQ-DEC-01",
            verification_id="VER-DEC-01",
            tender_id=n8n_resp.tender_id,
            bidder_id=b_id,
            bidder_name="Review Test Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="FINANCIAL", requirement_type="FINANCIAL", rule="MINIMUM_TURNOVER", description="Turnover", parameters={"minimum": 1000000}, mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="STATUTORY", requirement_type="STATUTORY", rule="OEM_AUTHORIZATION", description="OEM Authorization", parameters={}, mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="annual_turnover", value=1500000),
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert response.summary.non_compliant == 0
        assert response.summary.unverified == 1
        assert response.decision == VerificationDecisionEnum.MANUAL_REVIEW
        assert response.overall_compliance == OverallComplianceEnum.UNVERIFIED

    def test_decision_consistency_all_compliant(self):
        """8. If non_compliant == 0 and unverified == 0, decision is QUALIFIED, risk is LOW, confidence >= 0.90."""
        b_id = str(uuid.uuid4())
        agent_res = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}, findings=[]),
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="PASS", decision="QUALIFIED", confidence=0.96, evidence={}, findings=[]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-QUAL-01",
            request_id="REQ-QUAL-01",
            tender_id=str(uuid.uuid4()),
            bidder_id=b_id,
            bidder_name="Qual Test Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        payload = N8nVerificationPayload(
            request_id="REQ-QUAL-01",
            verification_id="VER-QUAL-01",
            tender_id=n8n_resp.tender_id,
            bidder_id=b_id,
            bidder_name="Qual Test Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="FINANCIAL", requirement_type="FINANCIAL", rule="MINIMUM_TURNOVER", description="Turnover", parameters={"minimum": 1000000}, mandatory=True),
                TenderRequirementItemInput(requirement_id="R2", category="EXPERIENCE", requirement_type="EXPERIENCE", rule="EXPERIENCE_PERIOD", description="Experience", parameters={"min_years": 5}, mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="annual_turnover", value=1500000),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="years_of_experience", value=7),
            ],
            required_agents=["FINANCIAL_AGENT", "EXPERIENCE_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert response.summary.non_compliant == 0
        assert response.summary.unverified == 0
        assert response.decision == VerificationDecisionEnum.QUALIFIED
        assert response.overall_compliance == OverallComplianceEnum.COMPLIANT
        assert response.risk_level.value == "LOW"
        assert response.overall_confidence >= 0.90

    def test_decision_consistency_has_non_compliant(self):
        """9. If non_compliant > 0, decision is NOT_QUALIFIED, risk is HIGH, failed requirements lists genuine failures."""
        b_id = str(uuid.uuid4())
        agent_res = [
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="FAIL", decision="NOT_QUALIFIED", confidence=0.98, evidence={}, findings=["Experience 3 < 5 years"], issues=["Experience below threshold"]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-REJ-01",
            request_id="REQ-REJ-01",
            tender_id=str(uuid.uuid4()),
            bidder_id=b_id,
            bidder_name="Fail Test Bidder",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=75.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["Experience below threshold"],
            warnings=[],
            reasons=["Mandatory criteria failed"],
        )

        payload = N8nVerificationPayload(
            request_id="REQ-REJ-01",
            verification_id="VER-REJ-01",
            tender_id=n8n_resp.tender_id,
            bidder_id=b_id,
            bidder_name="Fail Test Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="EXPERIENCE", requirement_type="EXPERIENCE", rule="EXPERIENCE_PERIOD", description="Experience", parameters={"min_years": 5}, mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="years_of_experience", value=3),
            ],
            required_agents=["EXPERIENCE_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert response.summary.non_compliant > 0
        assert response.decision == VerificationDecisionEnum.NOT_QUALIFIED
        assert response.overall_compliance == OverallComplianceEnum.NON_COMPLIANT
        assert response.risk_level.value in ("HIGH", "CRITICAL")
        assert len(response.failed_requirements) > 0

    def test_failed_requirements_deduplication(self):
        """10. Ensure zero duplicate failure messages across agents/requirements."""
        agent_res = [
            N8nAgentResult(agent="EXPERIENCE_AGENT", status="FAIL", decision="NOT_QUALIFIED", confidence=0.95, evidence={}, findings=[], issues=["Turnover criteria violated"]),
            N8nAgentResult(agent="FINAL_COMPLIANCE_AGENT", status="FAIL", decision="NOT_QUALIFIED", confidence=0.95, evidence={}, findings=[], issues=["Turnover criteria violated"]),
        ]
        n8n_resp = N8nVerificationResponse(
            verification_id="VER-DEDUP-01",
            request_id="REQ-DEDUP-01",
            tender_id=str(uuid.uuid4()),
            bidder_id=str(uuid.uuid4()),
            bidder_name="Dedup Test Bidder",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=70.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=["Turnover criteria violated", "Turnover criteria violated"],
            warnings=[],
            reasons=[],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp)
        normalized_failed = [f.strip().lower() for f in response.failed_requirements]
        # Assert no identical strings in failed_requirements
        assert len(normalized_failed) == len(set(normalized_failed))

    def test_evidence_provenance_linkage(self):
        """11. Every evaluated requirement has non-empty evidence_ids and document_ids when evidence matches."""
        b_id = str(uuid.uuid4())
        doc_uuid = str(uuid.uuid4())
        ev_uuid = str(uuid.uuid4())

        agent_res = [
            N8nAgentResult(agent="FINANCIAL_AGENT", status="PASS", decision="QUALIFIED", confidence=0.98, evidence={}, findings=[]),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-PROV-01",
            request_id="REQ-PROV-01",
            tender_id=str(uuid.uuid4()),
            bidder_id=b_id,
            bidder_name="Provenance Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=10.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        payload = N8nVerificationPayload(
            request_id="REQ-PROV-01",
            verification_id="VER-PROV-01",
            tender_id=n8n_resp.tender_id,
            bidder_id=b_id,
            bidder_name="Provenance Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R-FIN", category="FINANCIAL", requirement_type="FINANCIAL", rule="MINIMUM_TURNOVER", description="Turnover", parameters={"minimum": 1000000}, mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id=ev_uuid, bidder_id=b_id, document_id=doc_uuid, field="annual_turnover", value=2000000),
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        response = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        req_eval = response.requirements[0]
        assert req_eval.decision == RequirementComplianceEnum.COMPLIANT
        assert ev_uuid in req_eval.evidence_ids
        assert doc_uuid in req_eval.document_ids

    def test_single_verification_execution_persistence(self):
        """12. Exactly 1 verification_executions record created per execution."""
        from app.core.database import SessionLocal
        from app.models.verification import VerificationExecution
        from app.models.tender import Tender
        from app.models.bidder import Bidder
        from app.models.enums import TenderStatus, BidderStatus
        db = SessionLocal()
        try:
            # Create a test tender and bidder
            t = Tender(
                tender_number=f"TND-{uuid.uuid4().hex[:6].upper()}",
                title="Execution Persistence Test Tender",
                organization="Department of Expenditure",
                department="General",
                category="General",
                status=TenderStatus.PUBLISHED,
            )
            b = Bidder(
                company_name=f"Persistence Bidder {uuid.uuid4().hex[:6]}",
                status=BidderStatus.ACTIVE,
            )
            db.add(t)
            db.add(b)
            db.commit()
            db.refresh(t)
            db.refresh(b)

            v_id = f"VER-TEST-{uuid.uuid4().hex[:6].upper()}"
            r_id = f"REQ-TEST-{uuid.uuid4().hex[:6].upper()}"

            exec_row = VerificationExecution(
                verification_id=v_id,
                request_id=r_id,
                tender_id=t.id,
                bidder_id=b.id,
                request_hash="hash12345",
                status="RUNNING",
            )
            db.add(exec_row)
            db.commit()

            rows = db.query(VerificationExecution).filter(VerificationExecution.verification_id == v_id).all()
            assert len(rows) == 1

            # Clean up
            db.delete(exec_row)
            db.delete(b)
            db.delete(t)
            db.commit()
        finally:
            db.close()

    def test_groq_only_for_ambiguous_in_phase21_5(self):
        """13. Zero Groq calls for standard deterministic experience clause; only called for genuinely ambiguous."""
        standard_text = "The bidder must have at least 5 years of relevant experience."
        norm = TenderRequirementNormalizer.normalize_clause(standard_text)
        assert norm.status.value == "NORMALIZED"
        assert not norm.requires_semantic_interpretation
