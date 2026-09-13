"""
Test Suite: Phase 22.6 - Expose Structured Document Forensics Results
Verifies:
1. Clean document produces structured forensic result (CLEAN, LOW, 0 anomalies).
2. Existing suspicious/anomaly finding is represented correctly (SUSPICIOUS or ANOMALY).
3. Severity is preserved.
4. Confidence is preserved from DOCUMENT_FORENSICS_AGENT.
5. Source document is preserved.
6. Document ID is preserved when available.
7. Page number is preserved when available.
8. Missing page number remains null (never fabricated).
9. Multiple anomalies are preserved.
10. No anomaly is fabricated when the existing forensic engine has no finding.
11. DOCUMENT_FORENSICS_AGENT remains connected to the forensic result.
12. Existing final decision is unchanged.
13. Existing risk score is unchanged.
14. Existing overall confidence is unchanged.
15. Phase 22.1 semantic invariants remain intact.
16. Phase 22.2 evidence remains intact.
17. Phase 22.3 decision explanation remains intact.
18. Phase 22.4 confidence breakdown remains intact.
19. Phase 22.5 cross-verification remains intact.
20. No LLM/Groq call is introduced.
21. Persistence and reconstruction via CRUD preserves document_forensics.
"""
from datetime import datetime, timezone
import uuid
import pytest
from unittest.mock import patch

from app.schemas.verification import (
    N8nVerificationResponse,
    N8nVerificationPayload,
    TenderRequirementItemInput,
    BidderEvidenceItemInput,
    N8nAgentResult,
    StructuredEvidenceItem,
    RequirementEvaluation,
    VerificationResponse,
    VerificationDecisionEnum,
    RequirementComplianceEnum,
    VerificationCrossVerification,
    VerificationDocumentForensics,
    ForensicDocumentResult,
    ForensicAnomalyItem,
)
from app.services.verification_aggregator import verification_aggregator
from app.models.verification import VerificationExecution
from app.crud.crud_verification import crud_verification


class TestPhase22_6DocumentForensics:

    def test_clean_document_produces_structured_forensic_result(self):
        """1. Clean document produces structured forensic result (CLEAN, LOW, 0 anomalies)."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-01",
            verification_id="VER-22-6-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Clean Bidder Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="GST_Certificate.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT", "GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.98,
                evidence={
                    "status": "PASS",
                    "source_document": "GST_Certificate.pdf",
                    "anomalies": [],
                },
            ),
            N8nAgentResult(
                agent="GST_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.95,
                evidence={"gstin": "29AAACB2929P1Z5"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-01",
            request_id="REQ-22-6-01",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Clean Bidder Ltd",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.5,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.document_forensics is not None
        assert resp.document_forensics.overall_status == "CLEAN"
        assert resp.document_forensics.overall_risk == "LOW"
        assert len(resp.document_forensics.documents) >= 1
        doc = resp.document_forensics.documents[0]
        assert doc.status == "CLEAN"
        assert doc.risk_level == "LOW"
        assert len(doc.anomalies) == 0
        assert doc.source_document == "GST_Certificate.pdf"

    def test_existing_suspicious_or_anomaly_finding_represented_correctly(self):
        """2. Existing suspicious/anomaly finding is represented correctly."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-02",
            verification_id="VER-22-6-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Suspicious Bidder Ltd",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.92,
                evidence={
                    "source_document": "Forged_GST.pdf",
                    "anomalies": [
                        {
                            "type": "TAMPERING_INDICATOR",
                            "severity": "CRITICAL",
                            "description": "Critical forgery pattern detected in PDF stream",
                            "source_document": "Forged_GST.pdf",
                        }
                    ],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-02",
            request_id="REQ-22-6-02",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Suspicious Bidder Ltd",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=85.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        assert resp.document_forensics is not None
        assert resp.document_forensics.overall_status == "ANOMALY"
        assert resp.document_forensics.overall_risk == "HIGH"
        assert len(resp.document_forensics.documents) == 1
        doc = resp.document_forensics.documents[0]
        assert doc.status == "ANOMALY"
        assert len(doc.anomalies) == 1
        assert doc.anomalies[0].anomaly_type == "TAMPERING_INDICATOR"

    def test_severity_is_preserved(self):
        """3. Severity is preserved."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-03",
            verification_id="VER-22-6-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 3",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="REVIEW",
                decision="MANUAL_REVIEW",
                confidence=0.85,
                evidence={
                    "source_document": "doc_mod.pdf",
                    "anomalies": [
                        {
                            "type": "METADATA_INCONSISTENCY",
                            "severity": "MEDIUM",
                            "description": "Modification date is older than creation date",
                        }
                    ],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-03",
            request_id="REQ-22-6-03",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 3",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=40.0,
            risk_level="MEDIUM",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        anomaly = resp.document_forensics.documents[0].anomalies[0]
        assert anomaly.severity == "MEDIUM"

    def test_confidence_is_preserved(self):
        """4. Confidence is preserved from DOCUMENT_FORENSICS_AGENT."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-04",
            verification_id="VER-22-6-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 4",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.945,
                evidence={
                    "source_document": "valid_cert.pdf",
                    "anomalies": [],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-04",
            request_id="REQ-22-6-04",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 4",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        doc = resp.document_forensics.documents[0]
        assert doc.confidence == 0.945

    def test_source_document_is_preserved(self):
        """5. Source document is preserved."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-05",
            verification_id="VER-22-6-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 5",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.90,
                evidence={
                    "source_document": "Turnover_Audited_2024.pdf",
                    "anomalies": [],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-05",
            request_id="REQ-22-6-05",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 5",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        doc = resp.document_forensics.documents[0]
        assert doc.source_document == "Turnover_Audited_2024.pdf"

    def test_document_id_is_preserved_when_available(self):
        """6. Document ID is preserved when available."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-06",
            verification_id="VER-22-6-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 6",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="REVIEW",
                decision="MANUAL_REVIEW",
                confidence=0.88,
                evidence={
                    "document_id": "DOC-9988",
                    "source_document": "Contract_Agreement.pdf",
                    "anomalies": [
                        {
                            "document_id": "DOC-9988",
                            "type": "TEXT_DENSITY_ANOMALY",
                            "severity": "LOW",
                            "description": "OCR text extraction yielded low character count",
                        }
                    ],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-06",
            request_id="REQ-22-6-06",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 6",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=15.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        doc = resp.document_forensics.documents[0]
        assert doc.document_id == "DOC-9988"
        assert doc.anomalies[0].document_id == "DOC-9988"

    def test_page_number_is_preserved_when_available(self):
        """7. Page number is preserved when available."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-07",
            verification_id="VER-22-6-07",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 7",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="REVIEW",
                decision="MANUAL_REVIEW",
                confidence=0.85,
                evidence={
                    "source_document": "MultiPageDoc.pdf",
                    "anomalies": [
                        {
                            "type": "METADATA_INCONSISTENCY",
                            "page_number": 3,
                            "severity": "MEDIUM",
                            "description": "Page 3 contains inconsistent font encoding",
                        }
                    ],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-07",
            request_id="REQ-22-6-07",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 7",
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=20.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        anomaly = resp.document_forensics.documents[0].anomalies[0]
        assert anomaly.page_number == 3

    def test_missing_page_number_remains_null(self):
        """8. Missing page number remains null (never fabricated)."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-08",
            verification_id="VER-22-6-08",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 8",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.90,
                evidence={
                    "source_document": "File_Hash_Dup.pdf",
                    "anomalies": [
                        {
                            "type": "HASH_COLLISION",
                            "severity": "HIGH",
                            "description": "Duplicate SHA256 checksum with another document",
                        }
                    ],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-08",
            request_id="REQ-22-6-08",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 8",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=50.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        anomaly = resp.document_forensics.documents[0].anomalies[0]
        assert anomaly.page_number is None

    def test_multiple_anomalies_are_preserved(self):
        """9. Multiple anomalies are preserved."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-09",
            verification_id="VER-22-6-09",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 9",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="FAIL",
                decision="NOT_QUALIFIED",
                confidence=0.93,
                evidence={
                    "source_document": "Corrupt_Doc.pdf",
                    "anomalies": [
                        {
                            "anomaly_id": "ANO-01",
                            "type": "FILE_CORRUPTION",
                            "severity": "HIGH",
                            "description": "PDF structure damaged or unreadable",
                        },
                        {
                            "anomaly_id": "ANO-02",
                            "type": "METADATA_INCONSISTENCY",
                            "severity": "MEDIUM",
                            "description": "Modification date is older than creation date",
                        },
                    ],
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-09",
            request_id="REQ-22-6-09",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 9",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            risk_score=75.0,
            risk_level="HIGH",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        doc = resp.document_forensics.documents[0]
        assert len(doc.anomalies) == 2
        types = [a.anomaly_type for a in doc.anomalies]
        assert "FILE_CORRUPTION" in types
        assert "METADATA_INCONSISTENCY" in types

    def test_no_anomaly_is_fabricated_when_no_finding(self):
        """10. No anomaly is fabricated when the existing forensic engine has no finding."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-10",
            verification_id="VER-22-6-10",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 10",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.97,
                evidence={
                    "source_document": "Standard_Document.pdf",
                    "status": "PASS",
                },
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-10",
            request_id="REQ-22-6-10",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 10",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=0.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        assert resp.document_forensics.overall_status == "CLEAN"
        assert resp.document_forensics.overall_risk == "LOW"
        assert len(resp.document_forensics.documents[0].anomalies) == 0

    def test_document_forensics_agent_remains_connected_to_result(self):
        """11. DOCUMENT_FORENSICS_AGENT remains connected to the forensic result."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-11",
            verification_id="VER-22-6-11",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 11",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.96,
                evidence={"source_document": "Verified_Doc.pdf"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-11",
            request_id="REQ-22-6-11",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 11",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        # Agent result exists and is preserved:
        forensic_agent = next((ag for ag in resp.agent_results if ag.agent == "DOCUMENT_FORENSICS_AGENT"), None)
        assert forensic_agent is not None
        assert forensic_agent.status == "PASS"

        # Forensic structure is connected:
        assert resp.document_forensics is not None
        assert len(resp.document_forensics.documents) == 1
        assert resp.document_forensics.documents[0].source_document == "Verified_Doc.pdf"
        assert resp.document_forensics.documents[0].confidence == forensic_agent.confidence

    def test_existing_final_decision_is_unchanged(self):
        """12. Existing final decision is unchanged despite forensic anomaly exposure."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-12",
            verification_id="VER-22-6-12",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 12",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="GST_Cert.pdf",
                    page_number=1,
                ),
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT", "GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.80,
                evidence={
                    "source_document": "Doc_With_Warning.pdf",
                    "anomalies": [{"type": "TEXT_DENSITY_ANOMALY", "description": "low density"}],
                },
            ),
            N8nAgentResult(
                agent="GST_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.95,
                evidence={"gstin": "29AAACB2929P1Z5"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-12",
            request_id="REQ-22-6-12",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 12",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        # Decision must remain QUALIFIED per Phase 22.6 constraint 6:
        assert resp.decision == VerificationDecisionEnum.QUALIFIED
        # Yet forensic anomaly is exposed:
        assert resp.document_forensics is not None
        assert len(resp.document_forensics.documents[0].anomalies) == 1

    def test_existing_risk_score_is_unchanged(self):
        """13. Existing risk score is unchanged."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-13",
            verification_id="VER-22-6-13",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 13",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.85,
                evidence={"source_document": "file.pdf", "anomalies": [{"type": "METADATA_INCONSISTENCY"}]},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-13",
            request_id="REQ-22-6-13",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 13",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=17.5,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.risk_score == 17.5
        assert resp.risk_level.value == "LOW"

    def test_existing_overall_confidence_is_unchanged(self):
        """14. Existing overall confidence is unchanged."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-14",
            verification_id="VER-22-6-14",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 14",
            tender_requirements=[],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.91,
                evidence={"source_document": "file.pdf"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-14",
            request_id="REQ-22-6-14",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Bidder 14",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.overall_confidence == 0.91

    def test_phase22_invariants_preserved(self):
        """
        15-19. Full suite integration check:
        - Phase 22.1 semantic invariants intact
        - Phase 22.2 structured evidence intact
        - Phase 22.3 decision explanation intact
        - Phase 22.4 confidence breakdown intact
        - Phase 22.5 cross-verification intact
        """
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-15",
            verification_id="VER-22-6-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Comprehensive Test Corp",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="GST_Certificate.pdf",
                    page_number=1,
                ),
                BidderEvidenceItemInput(
                    evidence_id="E2",
                    bidder_id=b_id,
                    field="gstin",
                    value="29AAACB2929P1Z5",
                    source_document="Company_Profile.pdf",
                    page_number=2,
                ),
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT", "GST_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.98,
                evidence={"source_document": "GST_Certificate.pdf"},
            ),
            N8nAgentResult(
                agent="GST_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.96,
                evidence={"gstin": "29AAACB2929P1Z5"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-15",
            request_id="REQ-22-6-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Comprehensive Test Corp",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=2.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # 15. Phase 22.1: Semantic separation
        assert "GST_AGENT" in resp.passed_agents
        assert "DOCUMENT_FORENSICS_AGENT" in resp.passed_agents
        assert "GST_REGISTRATION" in resp.passed_requirements
        assert not any(a.endswith("_AGENT") for a in resp.passed_requirements)

        # 16. Phase 22.2: Structured evidence
        assert len(resp.requirements[0].evidence) > 0
        assert resp.requirements[0].evidence[0].source_document == "GST_Certificate.pdf"

        # 17. Phase 22.3: Decision explanation
        assert resp.decision_explanation is not None
        assert "mandatory tender requirements were successfully verified" in resp.decision_explanation

        # 18. Phase 22.4: Confidence breakdown
        assert resp.confidence_breakdown is not None
        assert resp.confidence_breakdown.overall_confidence == resp.overall_confidence

        # 19. Phase 22.5: Cross-verification
        assert resp.cross_verification is not None
        assert resp.cross_verification.overall_status == "CONSISTENT"

        # Phase 22.6: Document Forensics
        assert resp.document_forensics is not None
        assert resp.document_forensics.overall_status == "CLEAN"

    def test_no_additional_llm_or_groq_call_introduced(self):
        """20. No LLM / Groq call is introduced."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-6-20",
            verification_id="VER-22-6-20",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Deterministic Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        agent_res = [
            N8nAgentResult(
                agent="DOCUMENT_FORENSICS_AGENT",
                status="PASS",
                decision="QUALIFIED",
                confidence=0.97,
                evidence={"source_document": "clean.pdf"},
            ),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-6-20",
            request_id="REQ-22-6-20",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Deterministic Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=1.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        with patch("app.services.ai_gateway.ai_gateway.analyze_ambiguous_clause") as mock_ai:
            resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
            mock_ai.assert_not_called()

        assert resp.document_forensics is not None

    def test_persistence_reconstruction_survives(self):
        """21. Persistence and reconstruction preserves document_forensics."""
        raw_forensics = {
            "overall_status": "SUSPICIOUS",
            "overall_risk": "MEDIUM",
            "documents": [
                {
                    "document_id": "DOC-771",
                    "source_document": "Financial_Statement.pdf",
                    "status": "SUSPICIOUS",
                    "risk_level": "MEDIUM",
                    "confidence": 0.88,
                    "sha256": "abcdef1234567890",
                    "anomalies": [
                        {
                            "anomaly_id": "ANO-01",
                            "anomaly_type": "METADATA_INCONSISTENCY",
                            "severity": "MEDIUM",
                            "confidence": 0.88,
                            "description": "Modification timestamp precedes creation timestamp",
                            "source_document": "Financial_Statement.pdf",
                            "document_id": "DOC-771",
                            "page_number": None,
                            "affected_field": "metadata.timestamps",
                            "evidence": {"mod": "2023", "create": "2024"},
                        }
                    ],
                }
            ],
            "summary": "1 document evaluated, 1 document has anomalies",
        }

        mock_execution = VerificationExecution(
            id=uuid.uuid4(),
            verification_id="VER-PERSIST-01",
            request_id="REQ-PERSIST-01",
            tender_id=uuid.uuid4(),
            bidder_id=uuid.uuid4(),
            status="COMPLETED",
            decision="MANUAL_REVIEW",
            risk_score=35.0,
            risk_level="MEDIUM",
            overall_confidence=0.88,
            agent_results=[
                {
                    "agent": "DOCUMENT_FORENSICS_AGENT",
                    "status": "REVIEW",
                    "decision": "MANUAL_REVIEW",
                    "confidence": 0.88,
                    "evidence": {"source_document": "Financial_Statement.pdf"},
                }
            ],
            requirements=[],
            compliance_summary={"document_forensics": raw_forensics},
            reasons=[],
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        resp = crud_verification.to_verification_response(mock_execution)

        assert resp.document_forensics is not None
        assert resp.document_forensics.overall_status == "SUSPICIOUS"
        assert resp.document_forensics.overall_risk == "MEDIUM"
        assert len(resp.document_forensics.documents) == 1
        doc = resp.document_forensics.documents[0]
        assert doc.document_id == "DOC-771"
        assert doc.source_document == "Financial_Statement.pdf"
        assert len(doc.anomalies) == 1
        assert doc.anomalies[0].anomaly_type == "METADATA_INCONSISTENCY"
        assert doc.anomalies[0].page_number is None
        assert doc.anomalies[0].severity == "MEDIUM"
