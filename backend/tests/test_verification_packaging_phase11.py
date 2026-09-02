import json
import unittest
from uuid import UUID, uuid4

from app.models.enums import RequirementType
from app.schemas.packaged_output import (
    CanonicalDocumentOutput,
    PackagedRequirement,
    PackagedSection,
)
from app.schemas.processing import ExtractionResult
from app.schemas.tender_requirement_normalizer import (
    NormalizationStatus,
    NormalizedRequirement,
)
from app.schemas.tender_section import DetectedTenderSection, SectionType
from app.services.ai_gateway import AIGateway
from app.services.verification_packaging_service import (
    VerificationPackagingService,
    package_verification_output,
)


class TestVerificationPackagingPhase11(unittest.TestCase):
    """
    Unit tests for SIH-26100 Phase 11.9:
    Verification Output Packaging & Traceability Mapping.
    """

    def setUp(self):
        self.doc_id = str(uuid4())
        self.doc_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # -------------------------------------------------------------------------
    # 1. Complete Deterministic Tender Output Packaging
    # -------------------------------------------------------------------------
    def test_01_complete_deterministic_tender_output(self):
        """Verify packaging of purely deterministic requirements with full provenance."""
        sec = DetectedTenderSection(
            section_id="sec_elig_001",
            name="Eligibility Criteria",
            section_type=SectionType.ELIGIBILITY_CRITERIA,
            heading_raw="SECTION 2: ELIGIBILITY CRITERIA",
            document_id=self.doc_id,
            page_start=2,
            page_end=4,
            source_reference="Page 2-4 - SECTION 2: ELIGIBILITY CRITERIA",
            confidence=0.98,
        )

        req1 = NormalizedRequirement(
            status=NormalizationStatus.NORMALIZED,
            type="FINANCIAL",
            rule="AVERAGE_TURNOVER",
            description="Minimum average annual turnover of INR 50,000,000 across last 3 financial years",
            parameters={"minimum": 50000000.0, "currency": "INR", "period": 3, "period_unit": "YEARS", "operator": ">="},
            mandatory=True,
            confidence=0.98,
            source_page=2,
            page_start=2,
            page_end=3,
            section_id="sec_elig_001",
            source_section="Eligibility Criteria",
            document_id=self.doc_id,
            source_text="The minimum average annual turnover of the bidder shall be Rs. 5 Crore in the last 3 financial years.",
            resolution_method="DETERMINISTIC",
        )

        pkg = package_verification_output(
            document_id=self.doc_id,
            document_hash=self.doc_hash,
            document_type="TENDER",
            filename="GeM_Tender_2026_B_99182.pdf",
            file_size=1048576,
            mime_type="application/pdf",
            sections=[sec],
            requirements=[req1],
            total_pages=10,
        )

        self.assertIsInstance(pkg, CanonicalDocumentOutput)
        self.assertEqual(pkg.document.document_id, self.doc_id)
        self.assertEqual(pkg.document.document_hash, self.doc_hash)
        self.assertEqual(pkg.extraction_summary.total_requirements, 1)
        self.assertEqual(pkg.extraction_summary.deterministic_requirements, 1)
        self.assertEqual(pkg.extraction_summary.ai_resolved_requirements, 0)
        self.assertEqual(pkg.extraction_summary.ambiguous_requirements, 0)
        self.assertEqual(len(pkg.sections), 1)
        self.assertEqual(pkg.sections[0].section_id, "sec_elig_001")

        # Verify deterministic requirement does not contain AI metadata
        self.assertEqual(pkg.requirements[0].resolution.method, "DETERMINISTIC")
        self.assertEqual(pkg.requirements[0].resolution.status, "NORMALIZED")
        self.assertIsNone(pkg.requirements[0].traceability.ai_metadata)
        self.assertEqual(pkg.requirements[0].traceability.extraction_method, "deterministic")

    # -------------------------------------------------------------------------
    # 2. Mixed Deterministic + AI Resolved Requirements
    # -------------------------------------------------------------------------
    def test_02_mixed_deterministic_and_ai_requirements(self):
        """Verify summary calculation and segregated metadata for mixed deterministic and AI requirements."""
        req_det = NormalizedRequirement(
            status=NormalizationStatus.NORMALIZED,
            type="STATUTORY",
            rule="GST_REGISTRATION",
            description="Mandatory GST registration certificate",
            parameters={"registration_type": "GST", "mandatory": True},
            mandatory=True,
            confidence=0.99,
            source_page=1,
            document_id=self.doc_id,
            source_text="Bidder must submit copy of valid GST Registration Certificate.",
            resolution_method="DETERMINISTIC",
        )

        req_ai = NormalizedRequirement(
            status=NormalizationStatus.AI_RESOLVED,
            type="EXPERIENCE",
            rule="SIMILAR_WORK_EXPERIENCE",
            description="Proven experience in cloud modernization across 2 major government projects",
            parameters={"minimum_projects": 2, "scope": "CLOUD_MODERNIZATION"},
            mandatory=True,
            confidence=0.92,
            source_page=5,
            document_id=self.doc_id,
            source_text="Bidder should demonstrate execution of comparable cloud modernization assignments.",
            resolution_method="AI_GATEWAY",
            requires_semantic_interpretation=False,
            ai_confidence=0.92,
            escalation_reason="Subjective cloud modernization scope requires semantic resolution",
            model_metadata={
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "prompt_tokens": 160,
                "completion_tokens": 55,
                "total_tokens": 215,
                "latency_ms": 280.4,
            },
        )

        pkg = package_verification_output(
            document_id=self.doc_id,
            document_hash=self.doc_hash,
            requirements=[req_det, req_ai],
        )

        self.assertEqual(pkg.extraction_summary.total_requirements, 2)
        self.assertEqual(pkg.extraction_summary.deterministic_requirements, 1)
        self.assertEqual(pkg.extraction_summary.ai_resolved_requirements, 1)
        self.assertEqual(pkg.extraction_summary.ambiguous_requirements, 0)

        # Requirement 1 (Deterministic) -> No AI metadata
        self.assertIsNone(pkg.requirements[0].traceability.ai_metadata)
        self.assertEqual(pkg.requirements[0].resolution.method, "DETERMINISTIC")

        # Requirement 2 (AI-Resolved) -> AI metadata correctly propagated without secrets
        self.assertIsNotNone(pkg.requirements[1].traceability.ai_metadata)
        self.assertEqual(pkg.requirements[1].traceability.ai_metadata.provider, "groq")
        self.assertEqual(pkg.requirements[1].traceability.ai_metadata.model, "llama-3.3-70b-versatile")
        self.assertEqual(pkg.requirements[1].traceability.ai_metadata.prompt_tokens, 160)
        self.assertEqual(pkg.requirements[1].resolution.method, "AI_GATEWAY")

    # -------------------------------------------------------------------------
    # 3. Ambiguous & Unresolved Requirement Packaging
    # -------------------------------------------------------------------------
    def test_03_ambiguous_and_unresolved_requirement(self):
        """Ambiguous and unresolvable criteria retain explicit AMBIGUOUS/UNRESOLVED status and verbatim evidence."""
        req_amb = NormalizedRequirement(
            status=NormalizationStatus.AMBIGUOUS,
            type="EXPERIENCE",
            rule="PAST_EXPERIENCE",
            source_page=8,
            document_id=self.doc_id,
            source_text="Bidder should have satisfactory past performance records.",
            requires_semantic_interpretation=True,
            ambiguity_reason="Missing quantifiable duration or completed order count",
            confidence=None,
        )

        pkg = package_verification_output(
            document_id=self.doc_id,
            document_hash=self.doc_hash,
            requirements=[req_amb],
        )

        self.assertEqual(pkg.extraction_summary.total_requirements, 1)
        self.assertEqual(pkg.extraction_summary.ambiguous_requirements, 1)
        self.assertEqual(pkg.extraction_summary.deterministic_requirements, 0)

        res = pkg.requirements[0].resolution
        self.assertEqual(res.status, "AMBIGUOUS")
        self.assertEqual(res.method, "UNRESOLVED")
        self.assertIsNone(res.confidence)
        self.assertEqual(res.reason, "Missing quantifiable duration or completed order count")
        self.assertEqual(pkg.requirements[0].traceability.source_text, "Bidder should have satisfactory past performance records.")

    # -------------------------------------------------------------------------
    # 4. Multi-Page Requirement Preservation
    # -------------------------------------------------------------------------
    def test_04_multi_page_requirement_preservation(self):
        """Requirements spanning multiple pages retain page_start and page_end."""
        req_multi = NormalizedRequirement(
            status=NormalizationStatus.NORMALIZED,
            type="TECHNICAL",
            rule="QUALITY_CERTIFICATION",
            description="ISO 9001 and ISO 27001 certifications required",
            parameters={"certifications": ["ISO 9001", "ISO 27001"]},
            mandatory=True,
            confidence=0.96,
            source_page=12,
            page_start=12,
            page_end=14,
            section_id="sec_tech_004",
            source_section="Technical Specifications",
            document_id=self.doc_id,
            source_text="Bidder must hold valid ISO 9001 and ISO 27001 certificates on bid opening date.",
        )

        pkg = package_verification_output(requirements=[req_multi])
        trace = pkg.requirements[0].traceability

        self.assertEqual(trace.source_page, 12)
        self.assertEqual(trace.page_start, 12)
        self.assertEqual(trace.page_end, 14)
        self.assertEqual(trace.section_id, "sec_tech_004")

    # -------------------------------------------------------------------------
    # 5. Section Traceability Mapping
    # -------------------------------------------------------------------------
    def test_05_section_traceability_mapping(self):
        """Verify section metadata mapping and total section counts."""
        sec1 = DetectedTenderSection(
            section_id="sec_info_001",
            name="Tender Information",
            section_type=SectionType.TENDER_INFORMATION,
            page_start=1,
            page_end=2,
            source_reference="Page 1-2 - Tender Details",
            confidence=1.0,
        )
        sec2 = DetectedTenderSection(
            section_id="sec_fin_002",
            name="Financial Requirements",
            section_type=SectionType.FINANCIAL_REQUIREMENTS,
            page_start=3,
            page_end=6,
            source_reference="Page 3-6 - Financial Qualifications",
            confidence=0.95,
        )

        pkg = package_verification_output(sections=[sec1, sec2])

        self.assertEqual(len(pkg.sections), 2)
        self.assertEqual(pkg.traceability.total_sections, 2)
        self.assertEqual(pkg.sections[0].section_type, "TENDER_INFORMATION")
        self.assertEqual(pkg.sections[1].section_type, "FINANCIAL_REQUIREMENTS")

    # -------------------------------------------------------------------------
    # 6. Source Text Verbatim Preservation
    # -------------------------------------------------------------------------
    def test_06_source_text_verbatim_preservation(self):
        """Verbatim evidence excerpt is preserved without truncation or destructive mutation."""
        exact_text = "The EMD shall be submitted in the form of Bank Guarantee of ₹2,50,000/- from any scheduled commercial bank."
        req = NormalizedRequirement(
            status=NormalizationStatus.NORMALIZED,
            type="FINANCIAL",
            rule="EMD_REQUIREMENT",
            description="EMD requirement of INR 250,000",
            parameters={"amount": 250000.0, "currency": "INR"},
            source_text=exact_text,
            source_page=3,
        )

        pkg = package_verification_output(requirements=[req])
        self.assertEqual(pkg.requirements[0].traceability.source_text, exact_text)

    # -------------------------------------------------------------------------
    # 7. SHA-256 Digest Propagation
    # -------------------------------------------------------------------------
    def test_07_sha256_propagation(self):
        """SHA-256 digest propagates across document metadata and requirement traceability."""
        test_hash = "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
        req = NormalizedRequirement(
            status=NormalizationStatus.NORMALIZED,
            type="STATUTORY",
            rule="PAN_REQUIREMENT",
            source_text="Copy of PAN card to be enclosed.",
            source_page=1,
        )

        pkg = package_verification_output(
            document_hash=test_hash,
            requirements=[req],
        )

        self.assertEqual(pkg.document.document_hash, test_hash)
        self.assertEqual(pkg.traceability.document_hash, test_hash)
        self.assertEqual(pkg.requirements[0].traceability.document_hash, test_hash)

    # -------------------------------------------------------------------------
    # 8. Missing Page Information (Null Preservation)
    # -------------------------------------------------------------------------
    def test_08_missing_page_information_represented_as_null(self):
        """Missing or unidentifiable page numbers are represented as None rather than fabricated."""
        req = NormalizedRequirement(
            status=NormalizationStatus.NORMALIZED,
            type="STATUTORY",
            rule="PAN_REQUIREMENT",
            source_text="Valid PAN is required.",
            source_page=None,
            page_start=None,
            page_end=None,
        )

        pkg = package_verification_output(requirements=[req])
        trace = pkg.requirements[0].traceability

        self.assertIsNone(trace.source_page)
        self.assertIsNone(trace.page_start)
        self.assertIsNone(trace.page_end)

    # -------------------------------------------------------------------------
    # 9. Null Confidence Serialization
    # -------------------------------------------------------------------------
    def test_09_null_confidence_serialization(self):
        """Ambiguous clauses with confidence=None serialize cleanly to JSON null."""
        req = NormalizedRequirement(
            status=NormalizationStatus.AMBIGUOUS,
            type="EXPERIENCE",
            rule="PAST_EXPERIENCE",
            source_text="Bidder should have sound experience in this domain.",
            confidence=None,
        )

        pkg = package_verification_output(requirements=[req])
        pkg_json = pkg.model_dump_json()
        parsed = json.loads(pkg_json)

        self.assertIsNone(parsed["requirements"][0]["resolution"]["confidence"])

    # -------------------------------------------------------------------------
    # 10. UUID and Datetime Serialization
    # -------------------------------------------------------------------------
    def test_10_uuid_and_datetime_serialization(self):
        """UUID and datetime fields serialize to standard strings without errors."""
        doc_uuid = uuid4()
        pkg = package_verification_output(
            document_id=doc_uuid,
            document_hash=self.doc_hash,
        )

        pkg_dict = pkg.model_dump()
        self.assertEqual(pkg_dict["document"]["document_id"], str(doc_uuid))
        self.assertIn("processed_at", pkg_dict["traceability"])

        # JSON round-trip validation
        json_str = pkg.model_dump_json()
        self.assertIsInstance(json_str, str)
        reloaded = json.loads(json_str)
        self.assertEqual(reloaded["document"]["document_id"], str(doc_uuid))

    # -------------------------------------------------------------------------
    # 11. Idempotent Packaging
    # -------------------------------------------------------------------------
    def test_11_idempotent_packaging(self):
        """Packaging the same intelligence results twice yields identical deterministic structures."""
        req = NormalizedRequirement(
            status=NormalizationStatus.NORMALIZED,
            type="FINANCIAL",
            rule="EMD_REQUIREMENT",
            parameters={"amount": 100000.0, "currency": "INR"},
            source_text="EMD amount: INR 1,00,000",
            source_page=2,
        )

        pkg1 = package_verification_output(document_id=self.doc_id, requirements=[req])
        pkg2 = package_verification_output(document_id=self.doc_id, requirements=[req])

        self.assertEqual(pkg1.extraction_summary.model_dump(), pkg2.extraction_summary.model_dump())
        self.assertEqual(pkg1.requirements[0].parameters, pkg2.requirements[0].parameters)
        self.assertEqual(pkg1.requirements[0].requirement_id, pkg2.requirements[0].requirement_id)

    # -------------------------------------------------------------------------
    # 12. Grounded-Value Relational Regression Test (Step 16)
    # -------------------------------------------------------------------------
    def test_12_grounded_value_relational_percentage_validation(self):
        """
        Regression test for Step 16:
        Clause: 'Average annual turnover shall be at least 30% of the estimated tender value.'
        Groq returns percentage=30.0 and derived minimum=15000000 based on context estimated_value=50000000.
        Verifies that grounding validator ACCEPTS this valid mathematical derivation.
        """
        from app.schemas.ai_gateway import LLMClauseInterpretation

        clause_text = "Average annual turnover shall be at least 30% of the estimated tender value."
        known_context = {"estimated_value": 50000000.0, "currency": "INR"}

        # Case A: Valid derived value (30% of 50M = 15M)
        valid_interpretation = LLMClauseInterpretation(
            requirement_type="FINANCIAL",
            rule="AVERAGE_TURNOVER",
            description="Average annual turnover must be at least 30% of estimated tender value (INR 15,000,000)",
            parameters={"percentage": 30.0, "minimum": 15000000.0, "currency": "INR", "period": 3},
            is_mandatory=True,
            is_interpretable=True,
            interpretation_confidence=0.95,
            rationale="Derived 30% of estimated tender value of INR 50,000,000",
        )

        is_grounded, err = AIGateway.validate_grounding(valid_interpretation, clause_text, known_context)
        self.assertTrue(is_grounded, f"Valid derived percentage value was incorrectly rejected: {err}")

        # Case B: Genuinely invented/hallucinated number (e.g. 77M which is not 30% of 50M)
        hallucinated_interpretation = LLMClauseInterpretation(
            requirement_type="FINANCIAL",
            rule="AVERAGE_TURNOVER",
            description="Average annual turnover of INR 77,000,000",
            parameters={"minimum": 77000000.0, "currency": "INR"},
            is_mandatory=True,
            is_interpretable=True,
            interpretation_confidence=0.95,
            rationale="Hallucinated 77 million",
        )

        is_grounded_bad, err_bad = AIGateway.validate_grounding(hallucinated_interpretation, clause_text, known_context)
        self.assertFalse(is_grounded_bad, "Invented hallucinated number was not caught by grounding validator")
        self.assertIn("Hallucination detected", err_bad)


if __name__ == "__main__":
    unittest.main()
