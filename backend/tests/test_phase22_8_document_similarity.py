"""
Test Suite: Phase 22.8 - Deterministic Document Similarity and Duplicate Detection
Verifies:
1. Identical SHA-256 values -> EXACT_DUPLICATE.
2. Different hashes but identical normalized text -> HIGH_SIMILARITY or equivalent deterministic result.
3. Highly similar documents -> expected similarity classification.
4. Low similarity documents -> LOW_SIMILARITY.
5. Only one document -> INSUFFICIENT_REFERENCE_CORPUS.
6. Empty extracted text -> INSUFFICIENT_REFERENCE_CORPUS or appropriate unresolved state.
7. Similarity calculation is deterministic.
8. Same inputs always produce the same score.
9. Document IDs are preserved.
10. Source document names are preserved.
11. Page numbers are preserved when actually available.
12. Missing page numbers remain null (never fabricated).
13. No plagiarism/fraud claim is generated from similarity alone.
14. Final decision is unchanged.
15. Risk score is unchanged.
16. Overall confidence is unchanged.
17. Compliance policy is unchanged.
18. Phase 22.1 invariants remain intact.
19. Phase 22.2 evidence remains intact.
20. Phase 22.3 decision explanation remains intact.
21. Phase 22.4 confidence breakdown remains intact.
22. Phase 22.5 cross-verification remains intact.
23. Phase 22.6 forensics remains intact.
24. Phase 22.7 compliance policy remains intact.
25. No LLM/Groq call is introduced.
26. Persistence and reconstruction via CRUD preserves document_similarity.
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
    DocumentForensicInput,
    N8nAgentResult,
    StructuredEvidenceItem,
    RequirementEvaluation,
    VerificationResponse,
    VerificationDecisionEnum,
    VerificationCrossVerification,
    VerificationDocumentForensics,
    VerificationDocumentSimilarity,
    DocumentSimilarityComparison,
    DocumentReference,
    VerificationCompliancePolicy,
)
from app.services.verification_aggregator import verification_aggregator
from app.services.document_similarity_service import (
    document_similarity_service,
    normalize_text,
    tokenize_text,
    calculate_jaccard_similarity,
    SIMILARITY_THRESHOLD_EXACT,
    SIMILARITY_THRESHOLD_HIGH,
    SIMILARITY_THRESHOLD_MODERATE,
)
from app.models.verification import VerificationExecution
from app.crud.crud_verification import crud_verification


class TestPhase22_8DocumentSimilarity:

    def test_01_identical_sha256_yields_exact_duplicate(self):
        """1. Identical SHA-256 values -> EXACT_DUPLICATE."""
        shared_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        doc_a = DocumentForensicInput(
            document_id="DOC-01",
            file_name="GST_Certificate_A.pdf",
            sha256=shared_hash,
            ocr_text="Standard GST registration certificate text payload",
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-02",
            file_name="GST_Certificate_B.pdf",
            sha256=shared_hash,
            ocr_text="Standard GST registration certificate text payload",
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])

        assert sim_res.overall_status == "EXACT_DUPLICATE"
        assert len(sim_res.comparisons) == 1
        comp = sim_res.comparisons[0]
        assert comp.comparison_type == "EXACT_DUPLICATE"
        assert comp.similarity_score == 1.0
        assert comp.status == "EXACT_DUPLICATE"
        assert comp.threshold == SIMILARITY_THRESHOLD_EXACT
        assert "identical SHA-256" in comp.reason

    def test_02_different_hashes_identical_normalized_text_yields_high_similarity(self):
        """2. Different hashes but identical normalized text -> HIGH_SIMILARITY."""
        # Different raw text formatting / hashes, but identical normalized tokens
        text_a = "Government of India \n Department of Expenditure \n Tender Agreement Form 2026."
        text_b = "government   of INDIA -- department of expenditure.. Tender Agreement Form 2026"

        doc_a = DocumentForensicInput(
            document_id="DOC-A",
            file_name="Agreement_ScanA.pdf",
            sha256="1111111111111111111111111111111111111111111111111111111111111111",
            ocr_text=text_a,
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-B",
            file_name="Agreement_ScanB.pdf",
            sha256="2222222222222222222222222222222222222222222222222222222222222222",
            ocr_text=text_b,
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])

        assert sim_res.overall_status == "SIMILARITY_FOUND"
        assert len(sim_res.comparisons) == 1
        comp = sim_res.comparisons[0]
        assert comp.comparison_type == "CONTENT_SIMILARITY"
        assert comp.similarity_score == 1.0
        assert comp.status == "HIGH_SIMILARITY"
        assert "identical normalized text" in comp.reason

    def test_03_highly_similar_documents_expected_similarity(self):
        """3. Highly similar documents (>= 80% token overlap) -> HIGH_SIMILARITY."""
        base_clause = (
            "The contractor shall execute the civil construction work in accordance with CPWD "
            "specifications volume one and volume two. All materials supplied must strictly comply with "
            "Bureau of Indian Standards IS 456 for reinforced concrete works."
        )
        variation = base_clause + " Additional engineer inspection required within 14 days."

        doc_a = DocumentForensicInput(
            document_id="DOC-TENDER",
            file_name="Tender_Specs.pdf",
            sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ocr_text=base_clause,
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-BIDDER",
            file_name="Bidder_Specs.pdf",
            sha256="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ocr_text=variation,
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])

        assert sim_res.overall_status == "SIMILARITY_FOUND"
        assert len(sim_res.comparisons) == 1
        comp = sim_res.comparisons[0]
        assert comp.status == "HIGH_SIMILARITY"
        assert comp.similarity_score >= SIMILARITY_THRESHOLD_HIGH
        assert comp.threshold == SIMILARITY_THRESHOLD_HIGH
        assert "highly similar normalized text" in comp.reason

    def test_04_low_similarity_documents_yields_low_similarity(self):
        """4. Low similarity documents (< 50% token overlap) -> LOW_SIMILARITY."""
        text_gst = "Goods and Services Tax Certificate registration legal name ABC Infra private limited Maharashtra."
        text_financial = "Independent Auditor Report financial year 2024 balance sheet revenue operations depreciation amortization."

        doc_a = DocumentForensicInput(
            document_id="DOC-GST",
            file_name="GST_Doc.pdf",
            sha256="3333333333333333333333333333333333333333333333333333333333333333",
            ocr_text=text_gst,
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-FIN",
            file_name="Audited_Balance_Sheet.pdf",
            sha256="4444444444444444444444444444444444444444444444444444444444444444",
            ocr_text=text_financial,
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])

        assert sim_res.overall_status == "NO_COMPARISON"
        assert len(sim_res.comparisons) == 1
        comp = sim_res.comparisons[0]
        assert comp.status == "LOW_SIMILARITY"
        assert comp.similarity_score < SIMILARITY_THRESHOLD_MODERATE
        assert "low content similarity" in comp.reason

    def test_05_only_one_document_yields_insufficient_reference_corpus(self):
        """5. Only one document -> INSUFFICIENT_REFERENCE_CORPUS."""
        doc = DocumentForensicInput(
            document_id="DOC-SOLO",
            file_name="Single_Document.pdf",
            sha256="5555555555555555555555555555555555555555555555555555555555555555",
            ocr_text="Solo document text content.",
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc])

        assert sim_res.overall_status == "INSUFFICIENT_REFERENCE_CORPUS"
        assert sim_res.comparisons == []
        assert "requires at least two comparable documents" in sim_res.reason

    def test_06_empty_extracted_text_yields_insufficient_reference_corpus(self):
        """6. Empty extracted text with distinct hashes -> INSUFFICIENT_REFERENCE_CORPUS."""
        doc_a = DocumentForensicInput(
            document_id="DOC-EMPTY-1",
            file_name="Empty_A.pdf",
            sha256="6666666666666666666666666666666666666666666666666666666666666666",
            ocr_text="",
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-EMPTY-2",
            file_name="Empty_B.pdf",
            sha256="7777777777777777777777777777777777777777777777777777777777777777",
            ocr_text="",
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])

        assert sim_res.overall_status == "INSUFFICIENT_REFERENCE_CORPUS"
        assert sim_res.comparisons == []
        assert "insufficient" in sim_res.reason.lower()

    def test_07_similarity_calculation_is_deterministic(self):
        """7. Similarity calculation is deterministic."""
        text_a = "Procurement of high voltage electrical transformers specifications ratings 220kV."
        text_b = "Procurement of electrical transformers technical specifications ratings 220kV."

        tok_a = tokenize_text(text_a)
        tok_b = tokenize_text(text_b)

        score_1 = calculate_jaccard_similarity(tok_a, tok_b)
        score_2 = calculate_jaccard_similarity(tok_a, tok_b)
        score_3 = calculate_jaccard_similarity(tok_a, tok_b)

        assert score_1 == score_2 == score_3
        assert isinstance(score_1, float)

    def test_08_same_inputs_always_produce_the_same_score(self):
        """8. Same inputs always produce the same score across multiple invocations."""
        doc_a = DocumentForensicInput(
            document_id="DOC-REPEAT-A",
            file_name="Repeat_A.pdf",
            ocr_text="Alpha Beta Gamma Delta Epsilon Zeta Eta Theta Iota Kappa",
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-REPEAT-B",
            file_name="Repeat_B.pdf",
            ocr_text="Alpha Beta Gamma Delta Epsilon Lambda Mu Nu Xi Omicron",
        )

        res_1 = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])
        res_2 = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])

        assert len(res_1.comparisons) == len(res_2.comparisons) == 1
        assert res_1.comparisons[0].similarity_score == res_2.comparisons[0].similarity_score
        assert res_1.comparisons[0].status == res_2.comparisons[0].status
        assert res_1.overall_status == res_2.overall_status

    def test_09_document_ids_are_preserved(self):
        """9. Document IDs are preserved in DocumentReference."""
        doc_a = DocumentForensicInput(
            document_id="DOC-ID-ALPHA",
            file_name="Alpha.pdf",
            ocr_text="Some document text for preservation testing.",
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-ID-BETA",
            file_name="Beta.pdf",
            ocr_text="Some document text for preservation testing.",
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])
        comp = sim_res.comparisons[0]

        assert comp.document_a.document_id == "DOC-ID-ALPHA"
        assert comp.document_b.document_id == "DOC-ID-BETA"

    def test_10_source_document_names_are_preserved(self):
        """10. Source document names are preserved in DocumentReference."""
        doc_a = DocumentForensicInput(
            document_id="D1",
            file_name="Official_Tender_Notice_Vol1.pdf",
            ocr_text="Unique official tender notice text.",
        )
        doc_b = DocumentForensicInput(
            document_id="D2",
            file_name="Bidder_Subcontractor_Affidavit.pdf",
            ocr_text="Unique bidder subcontractor affidavit text.",
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])
        comp = sim_res.comparisons[0]

        assert comp.document_a.source_document == "Official_Tender_Notice_Vol1.pdf"
        assert comp.document_b.source_document == "Bidder_Subcontractor_Affidavit.pdf"

    def test_11_page_numbers_preserved_when_available(self):
        """11. Page numbers are preserved when actually available from extraction structures."""
        doc_a = DocumentForensicInput(
            document_id="DOC-PAGE-A",
            file_name="Contract_A.pdf",
            extracted_data={
                "pages": [
                    {"page_number": 1, "text": "Cover page table of contents introduction."},
                    {"page_number": 3, "text": "Specific technical clause regarding foundation piles depth 25 meters."},
                ]
            },
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-PAGE-B",
            file_name="Contract_B.pdf",
            extracted_data={
                "pages": [
                    {"page_number": 2, "text": "Commercial terms payment milestones schedule."},
                    {"page_number": 5, "text": "Specific technical clause regarding foundation piles depth 25 meters."},
                ]
            },
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])
        comp = sim_res.comparisons[0]

        assert comp.document_a_page == 3
        assert comp.document_b_page == 5
        assert comp.document_a.page_number == 3
        assert comp.document_b.page_number == 5

    def test_12_missing_page_numbers_remain_null(self):
        """12. Missing page numbers remain null (never fabricated)."""
        doc_a = DocumentForensicInput(
            document_id="DOC-NOPAGE-A",
            file_name="NoPage_A.pdf",
            ocr_text="General unpaged document content string here.",
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-NOPAGE-B",
            file_name="NoPage_B.pdf",
            ocr_text="General unpaged document content string here too.",
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])
        comp = sim_res.comparisons[0]

        assert comp.document_a_page is None
        assert comp.document_b_page is None
        assert comp.document_a.page_number is None
        assert comp.document_b.page_number is None

    def test_13_no_plagiarism_or_fraud_claim_generated(self):
        """13. No plagiarism, fraud, or forgery claim is generated from similarity alone."""
        doc_a = DocumentForensicInput(
            document_id="DOC-SUSP-1",
            file_name="Suspicious_1.pdf",
            sha256="8888888888888888888888888888888888888888888888888888888888888888",
            ocr_text="Identical technical specifications word for word between bidders.",
        )
        doc_b = DocumentForensicInput(
            document_id="DOC-SUSP-2",
            file_name="Suspicious_2.pdf",
            sha256="8888888888888888888888888888888888888888888888888888888888888888",
            ocr_text="Identical technical specifications word for word between bidders.",
        )

        sim_res = document_similarity_service.analyze_similarity(documents=[doc_a, doc_b])

        res_dict = sim_res.model_dump()
        res_str = str(res_dict).lower()

        forbidden_terms = ["plagiar", "fraud", "forger", "stolen", "copied"]
        for term in forbidden_terms:
            assert term not in res_str, f"Forbidden non-neutral term '{term}' found in similarity output!"

    def test_14_final_decision_is_unchanged(self):
        """14. Final qualification decision is unchanged by document similarity."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        # Create two identical documents (EXACT_DUPLICATE)
        shared_hash = "9999999999999999999999999999999999999999999999999999999999999999"
        payload = N8nVerificationPayload(
            request_id="REQ-22-8-14",
            verification_id="VER-22-8-14",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Qualifying Bidder With Duplicates",
            tender_requirements=[
                TenderRequirementItemInput(
                    requirement_id="REQ-GST",
                    category="STATUTORY",
                    requirement_type="STATUTORY",
                    rule="GST_REGISTRATION",
                    mandatory=True,
                ),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(
                    evidence_id="E1",
                    bidder_id=b_id,
                    field="gstin",
                    value="27AAACB2929P1Z5",
                    source_document="GST_A.pdf",
                    document_hash=shared_hash,
                    page_number=1,
                )
            ],
            documents=[
                DocumentForensicInput(
                    document_id="D-1",
                    file_name="GST_A.pdf",
                    sha256=shared_hash,
                    ocr_text="GST registration 27AAACB2929P1Z5",
                ),
                DocumentForensicInput(
                    document_id="D-2",
                    file_name="GST_Copy.pdf",
                    sha256=shared_hash,
                    ocr_text="GST registration 27AAACB2929P1Z5",
                ),
            ],
            required_agents=["GST_AGENT", "DOCUMENT_FORENSICS_AGENT", "FINAL_COMPLIANCE_AGENT"],
        )

        agent_res = [
            N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.95),
            N8nAgentResult(agent="DOCUMENT_FORENSICS_AGENT", status="PASS", decision="QUALIFIED", confidence=0.90),
            N8nAgentResult(agent="FINAL_COMPLIANCE_AGENT", status="PASS", decision="QUALIFIED", confidence=0.92),
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-14",
            request_id="REQ-22-8-14",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Qualifying Bidder With Duplicates",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=10.0,
            risk_level="LOW",
            agent_results=agent_res,
            failed_requirements=[],
            warnings=[],
            reasons=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)

        # Decision MUST remain QUALIFIED despite exact duplicate documents (informational only)
        assert resp.decision == VerificationDecisionEnum.QUALIFIED
        assert resp.document_similarity is not None
        assert resp.document_similarity.overall_status == "EXACT_DUPLICATE"

    def test_15_risk_score_is_unchanged(self):
        """15. Risk score is not mutated by document similarity analysis."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Risk Test Bidder",
            documents=[
                DocumentForensicInput(document_id="D1", file_name="Doc1.pdf", ocr_text="Content"),
                DocumentForensicInput(document_id="D2", file_name="Doc2.pdf", ocr_text="Content"),
            ],
            required_agents=["GST_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-15",
            request_id="REQ-22-8-15",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Risk Test Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=24.5,
            risk_level="LOW",
            agent_results=[N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED")],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.risk_score == 24.5

    def test_16_overall_confidence_is_unchanged(self):
        """16. Overall confidence is not mutated by document similarity analysis."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-16",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Confidence Test Bidder",
            documents=[
                DocumentForensicInput(document_id="D1", file_name="Doc1.pdf", ocr_text="Same text"),
                DocumentForensicInput(document_id="D2", file_name="Doc2.pdf", ocr_text="Same text"),
            ],
            required_agents=["GST_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-16",
            request_id="REQ-22-8-16",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Confidence Test Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            overall_confidence=0.88,
            agent_results=[N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.88)],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.overall_confidence == 0.88

    def test_17_compliance_policy_is_unchanged(self):
        """17. Compliance policy evaluation from Phase 22.7 is untouched by similarity."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-17",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Policy Preserved Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="REQ-1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="DocA.pdf"),
            ],
            documents=[
                DocumentForensicInput(document_id="D1", file_name="DocA.pdf", ocr_text="High similarity text string"),
                DocumentForensicInput(document_id="D2", file_name="DocB.pdf", ocr_text="High similarity text string"),
            ],
            required_agents=["GST_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-17",
            request_id="REQ-22-8-17",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Policy Preserved Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            agent_results=[N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED")],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.compliance_policy is not None
        assert resp.compliance_policy.final_status == "QUALIFIED"

    def test_18_phase22_1_semantic_invariants_preserved(self):
        """18. Phase 22.1 semantic invariants (passed/failed/review requirements separation) remain intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-18",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Semantics Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="REQ-P", category="STATUTORY", requirement_type="STATUTORY", rule="PAN_VERIFICATION", mandatory=True),
            ],
            documents=[
                DocumentForensicInput(document_id="D1", file_name="D1.pdf", ocr_text="Text 1"),
                DocumentForensicInput(document_id="D2", file_name="D2.pdf", ocr_text="Text 2"),
            ],
            required_agents=["PAN_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-18",
            request_id="REQ-22-8-18",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Semantics Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            agent_results=[N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED")],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        for req_id in resp.passed_requirements:
            assert not req_id.endswith("_AGENT")
        assert not any(r.endswith("_AGENT") for r in resp.failed_requirements)

    def test_19_phase22_2_structured_evidence_preserved(self):
        """19. Phase 22.2 structured evidence provenance remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-19",
            verification_id="VER-22-8-19",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Evidence Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="FINANCIAL", requirement_type="FINANCIAL", rule="MINIMUM_TURNOVER", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="turnover", value="₹10 Cr", source_document="balance_sheet.pdf", page_number=4),
            ],
            required_agents=["FINANCIAL_AGENT"],
        )

        ev_item = StructuredEvidenceItem(
            field="turnover",
            detected_value="₹10 Cr",
            expected_value="₹5 Cr",
            source_document="balance_sheet.pdf",
            page_number=4,
        )

        agent_res = [
            N8nAgentResult(
                agent="FINANCIAL_AGENT",
                status="PASS",
                decision="QUALIFIED",
                evidence=[ev_item],
            )
        ]

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-19",
            request_id="REQ-22-8-19",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Evidence Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            agent_results=agent_res,
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.requirements is not None
        assert len(resp.requirements) >= 1
        ev = resp.requirements[0].evidence[0]
        assert ev.source_document == "balance_sheet.pdf"
        assert ev.page_number == 4
        assert ev.detected_value == "₹10 Cr"

    def test_20_phase22_3_decision_explanation_preserved(self):
        """20. Phase 22.3 deterministic decision explanation remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-20",
            verification_id="VER-22-8-20",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Explanation Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="gstin", value="29AAACB2929P1Z5", source_document="doc.pdf"),
            ],
            required_agents=["GST_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-20",
            request_id="REQ-22-8-20",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Explanation Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            agent_results=[N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED")],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.decision_explanation is not None
        assert "qualified" in resp.decision_explanation.lower()

    def test_21_phase22_4_confidence_breakdown_preserved(self):
        """21. Phase 22.4 confidence breakdown remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-21",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Confidence Bidder",
            required_agents=["GST_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-21",
            request_id="REQ-22-8-21",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Confidence Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            overall_confidence=0.92,
            agent_results=[N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED", confidence=0.92)],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.confidence_breakdown is not None
        assert resp.confidence_breakdown.overall_confidence == 0.92

    def test_22_phase22_5_cross_verification_preserved(self):
        """22. Phase 22.5 cross-verification comparison remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-22",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Cross Bidder",
            bidder_evidence=[
                BidderEvidenceItemInput(evidence_id="E1", bidder_id=b_id, field="pan", value="AAACB2929P", source_document="doc1.pdf"),
                BidderEvidenceItemInput(evidence_id="E2", bidder_id=b_id, field="pan", value="AAACB2929P", source_document="doc2.pdf"),
            ],
            required_agents=["PAN_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-22",
            request_id="REQ-22-8-22",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Cross Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            agent_results=[N8nAgentResult(agent="PAN_AGENT", status="PASS", decision="QUALIFIED")],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.cross_verification is not None
        assert resp.cross_verification.overall_status in ("CONSISTENT", "UNRESOLVED")

    def test_23_phase22_6_forensics_preserved(self):
        """23. Phase 22.6 document forensics assessment remains intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-23",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Forensics Bidder",
            documents=[
                DocumentForensicInput(document_id="D1", file_name="Clean.pdf", sha256="abc123hash", ocr_text="Text"),
                DocumentForensicInput(document_id="D2", file_name="Clean2.pdf", sha256="def456hash", ocr_text="Other"),
            ],
            required_agents=["DOCUMENT_FORENSICS_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-23",
            request_id="REQ-22-8-23",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Forensics Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            agent_results=[N8nAgentResult(agent="DOCUMENT_FORENSICS_AGENT", status="PASS", decision="QUALIFIED", confidence=0.96)],
            failed_requirements=[],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.document_forensics is not None
        assert resp.document_forensics.overall_status == "CLEAN"

    def test_24_phase22_7_compliance_policy_preserved(self):
        """24. Phase 22.7 compliance policy precedence rules remain intact."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-24",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Compliance Bidder",
            tender_requirements=[
                TenderRequirementItemInput(requirement_id="R1", category="STATUTORY", requirement_type="STATUTORY", rule="GST_REGISTRATION", mandatory=True),
            ],
            required_agents=["GST_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-24",
            request_id="REQ-22-8-24",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="Compliance Bidder",
            status="COMPLETED",
            decision="NOT_QUALIFIED",
            agent_results=[N8nAgentResult(agent="GST_AGENT", status="FAIL", decision="NOT_QUALIFIED", reason="GST missing")],
            failed_requirements=["GST_REGISTRATION"],
        )

        resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
        assert resp.compliance_policy is not None
        assert resp.compliance_policy.final_status == "NOT_QUALIFIED"
        assert len(resp.compliance_policy.blocking_findings) >= 1

    def test_25_no_llm_groq_call_introduced(self):
        """25. Zero LLM or Groq calls occur during document similarity analysis."""
        b_id = str(uuid.uuid4())
        t_id = str(uuid.uuid4())

        payload = N8nVerificationPayload(
            request_id="REQ-22-8-25",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="No LLM Sim Bidder",
            documents=[
                DocumentForensicInput(document_id="D1", file_name="Doc1.pdf", ocr_text="Standard tender clause for work."),
                DocumentForensicInput(document_id="D2", file_name="Doc2.pdf", ocr_text="Standard tender clause for work."),
            ],
            required_agents=["GST_AGENT"],
        )

        n8n_resp = N8nVerificationResponse(
            verification_id="VER-22-8-25",
            request_id="REQ-22-8-25",
            tender_id=t_id,
            bidder_id=b_id,
            bidder_name="No LLM Sim Bidder",
            status="COMPLETED",
            decision="QUALIFIED",
            agent_results=[N8nAgentResult(agent="GST_AGENT", status="PASS", decision="QUALIFIED")],
            failed_requirements=[],
        )

        with patch("app.services.ai_gateway.ai_gateway.analyze_ambiguous_clause") as mock_ai:
            resp = verification_aggregator.aggregate(n8n_resp=n8n_resp, payload=payload)
            mock_ai.assert_not_called()
            assert resp.document_similarity is not None
            assert resp.document_similarity.overall_status == "SIMILARITY_FOUND"

    def test_26_persistence_and_reconstruction_survives(self):
        """26. document_similarity survives aggregation -> persistence -> API reconstruction."""
        exec_id = uuid.uuid4()
        b_id = uuid.uuid4()
        t_id = uuid.uuid4()

        sim_data = VerificationDocumentSimilarity(
            overall_status="EXACT_DUPLICATE",
            comparisons=[
                DocumentSimilarityComparison(
                    comparison_id="SIM-001",
                    document_a=DocumentReference(document_id="DOC-1", source_document="GST_1.pdf", page_number=1),
                    document_b=DocumentReference(document_id="DOC-2", source_document="GST_2.pdf", page_number=1),
                    document_a_page=1,
                    document_b_page=1,
                    comparison_type="EXACT_DUPLICATE",
                    similarity_score=1.0,
                    threshold=1.0,
                    status="EXACT_DUPLICATE",
                    reason="Documents have identical SHA-256 content.",
                )
            ],
            reason="Exact duplicate document content detected based on cryptographic hash equality.",
        )

        raw_resp = {
            "document_similarity": sim_data.model_dump(),
        }

        execution = VerificationExecution(
            id=exec_id,
            verification_id="VER-22-8-26",
            request_id="REQ-22-8-26",
            tender_id=t_id,
            bidder_id=b_id,
            status="COMPLETED",
            decision="QUALIFIED",
            risk_score=5.0,
            risk_level="LOW",
            overall_confidence=0.95,
            compliance_summary={"document_similarity": sim_data.model_dump(), "raw_response": raw_resp},
            agent_results=[],
            requirements=[],
            reasons=["All checks passed."],
            warnings=[],
            inconclusive_checks=[],
            failed_requirements=[],
            missing_documents=[],
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        reconstructed = crud_verification.to_verification_response(execution)

        assert reconstructed.document_similarity is not None
        assert reconstructed.document_similarity.overall_status == "EXACT_DUPLICATE"
        assert len(reconstructed.document_similarity.comparisons) == 1
        c = reconstructed.document_similarity.comparisons[0]
        assert c.comparison_id == "SIM-001"
        assert c.status == "EXACT_DUPLICATE"
        assert c.similarity_score == 1.0
        assert c.document_a.source_document == "GST_1.pdf"
        assert c.document_b.source_document == "GST_2.pdf"
        assert c.document_a_page == 1
        assert c.document_b_page == 1
