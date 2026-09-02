import unittest
from uuid import uuid4

from app.models.enums import RequirementType
from app.schemas.tender_section import DetectedTenderSection, SectionType
from app.schemas.tender_requirement_normalizer import NormalizationStatus
from app.services.tender_clause_extractor import (
    TenderClauseExtractor,
    extract_clauses,
    extract_clauses_from_text,
    extract_clauses_from_sections,
)
from app.services.tender_requirement_normalizer import (
    TenderRequirementNormalizer,
    normalize_clause,
    normalize_candidates,
    normalize_sections,
)


class TestDeterministicRequirementExtractionPhase11(unittest.TestCase):
    """
    Unit tests for SIH-26100 Phase 11.7:
    Deterministic Requirement Extraction & Clause Segmentation.
    """

    def setUp(self):
        self.doc_id = str(uuid4())

    def test_01_minimum_turnover(self):
        """Verify deterministic extraction and normalization of minimum turnover."""
        text = "The bidder must have a minimum turnover of ₹5 crore in the preceding financial year."
        result = extract_clauses_from_text(text, page=2)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.FINANCIAL.value)
        self.assertEqual(norm.rule, "MINIMUM_TURNOVER")
        self.assertEqual(norm.parameters.get("minimum"), 50000000.0)
        self.assertEqual(norm.parameters.get("currency"), "INR")
        self.assertTrue(norm.mandatory)

    def test_02_average_annual_turnover(self):
        """Verify deterministic extraction and normalization of average annual turnover over period."""
        text = "Minimum average annual turnover shall not be less than Rs. 15 lakhs during the preceding three years."
        result = extract_clauses_from_text(text, page=12)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.FINANCIAL.value)
        self.assertEqual(norm.rule, "AVERAGE_TURNOVER")
        self.assertEqual(norm.parameters.get("minimum"), 1500000.0)
        self.assertEqual(norm.parameters.get("period"), 3)
        self.assertEqual(norm.parameters.get("period_unit"), "YEARS")
        self.assertEqual(norm.parameters.get("currency"), "INR")

    def test_03_emd_amount_and_percentage(self):
        """Verify fixed EMD and percentage EMD deterministic extraction."""
        # Fixed EMD
        text_fixed = "Earnest Money Deposit (EMD): ₹5,00,000 to be submitted along with technical bid."
        res_fixed = extract_clauses_from_text(text_fixed, page=4)
        self.assertGreaterEqual(res_fixed.total_candidates, 1)
        norm_fixed = normalize_clause(res_fixed.candidates[0])
        self.assertEqual(norm_fixed.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm_fixed.type, RequirementType.FINANCIAL.value)
        self.assertEqual(norm_fixed.rule, "EMD_REQUIREMENT")
        self.assertEqual(norm_fixed.parameters.get("amount"), 500000.0)

        # Percentage EMD
        text_pct = "Bidder shall submit EMD of 2% of the estimated contract value."
        res_pct = extract_clauses_from_text(text_pct, page=4)
        self.assertGreaterEqual(res_pct.total_candidates, 1)
        norm_pct = normalize_clause(res_pct.candidates[0])
        self.assertEqual(norm_pct.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm_pct.parameters.get("percentage"), 2.0)

    def test_04_performance_security_percentage(self):
        """Verify performance security percentage deterministic extraction."""
        text = "Performance Security: 5% of contract value to be furnished within 15 days of LoA."
        result = extract_clauses_from_text(text, page=9)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.FINANCIAL.value)
        self.assertEqual(norm.rule, "PERFORMANCE_SECURITY")
        self.assertEqual(norm.parameters.get("percentage"), 5.0)

    def test_05_estimated_tender_value(self):
        """Verify estimated tender value extraction."""
        text = "Estimated Tender Value: INR 5,00,00,000 (Rupees Five Crore only)."
        result = extract_clauses_from_text(text, page=1)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.FINANCIAL.value)
        self.assertEqual(norm.rule, "ESTIMATED_TENDER_VALUE")
        self.assertEqual(norm.parameters.get("estimated_value"), 50000000.0)

    def test_06_experience_project_count(self):
        """Verify completed project count deterministic extraction."""
        text = "The bidder must have successfully completed at least 3 similar works for Government bodies."
        result = extract_clauses_from_text(text, page=6)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.EXPERIENCE.value)
        self.assertEqual(norm.rule, "COMPLETED_PROJECTS")
        self.assertEqual(norm.parameters.get("min_completed_orders"), 3)
        self.assertEqual(norm.parameters.get("scope"), "SIMILAR_WORK")

    def test_07_experience_duration(self):
        """Verify experience duration (years) deterministic extraction."""
        text = "Bidder must possess minimum 5 years of past experience in highway maintenance."
        result = extract_clauses_from_text(text, page=7)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.EXPERIENCE.value)
        self.assertEqual(norm.parameters.get("min_years"), 5)
        self.assertEqual(norm.parameters.get("period_unit"), "YEARS")

    def test_08_mandatory_document_requirement(self):
        """Verify mandatory document & affidavit deterministic extraction."""
        text = "Bidder must submit a non-blacklisting affidavit on non-judicial stamp paper."
        result = extract_clauses_from_text(text, page=11)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.DOCUMENT.value)
        self.assertEqual(norm.rule, "REQUIRED_DOCUMENT")
        self.assertEqual(norm.parameters.get("document_type"), "NON_BLACKLISTING_AFFIDAVIT")
        self.assertTrue(norm.parameters.get("notarized"))

    def test_09_gst_and_pan_statutory_requirement(self):
        """Verify statutory GST and PAN requirement extraction."""
        text = "Bidder must possess valid GSTIN and PAN registrations in India."
        result = extract_clauses_from_text(text, page=3)
        self.assertGreaterEqual(result.total_candidates, 1)

        norm = normalize_clause(result.candidates[0])
        self.assertEqual(norm.status, NormalizationStatus.NORMALIZED)
        self.assertEqual(norm.type, RequirementType.STATUTORY.value)
        self.assertEqual(norm.rule, "GST_AND_PAN_REGISTRATION")
        self.assertEqual(norm.parameters.get("statutory_documents"), ["GSTIN", "PAN"])

    def test_10_multi_page_requirement_traceability(self):
        """Verify multi-page span preservation across bounded sections."""
        section = DetectedTenderSection(
            section_id="sec_eligibility_001",
            name="Eligibility Criteria",
            section_type=SectionType.ELIGIBILITY_CRITERIA,
            document_id=self.doc_id,
            page_start=3,
            page_end=5,
            source_reference="Section 3, Pages 3-5",
            text="The bidder must have average annual turnover of Rs 2 crore during the last 3 years.",
        )
        norm_res = normalize_sections([section], document_id=self.doc_id)
        self.assertGreaterEqual(norm_res.total_evaluated, 1)

        req = norm_res.requirements[0]
        self.assertEqual(req.page_start, 3)
        self.assertEqual(req.page_end, 5)
        self.assertEqual(req.section_id, "sec_eligibility_001")
        self.assertEqual(req.document_id, self.doc_id)
        self.assertEqual(req.source_section, "Eligibility Criteria")

    def test_11_compound_sentence_clause_segmentation(self):
        """Verify compound sentence segmentation separating multiple distinct requirements."""
        text = "Bidder must have GST registration and minimum annual turnover of ₹5 crore and submit audited financial statements."
        clauses = TenderClauseExtractor.split_into_clauses(text)
        self.assertGreaterEqual(len(clauses), 2)

        candidates = extract_clauses_from_text(text, page=2)
        # Should extract GST, turnover, and/or audited statements independently
        types_found = [c.candidate_type for c in candidates.candidates]
        self.assertIn(RequirementType.STATUTORY.value, types_found)
        self.assertIn(RequirementType.FINANCIAL.value, types_found)

    def test_12_ambiguous_semantic_clause_not_guessed(self):
        """Verify that vague/non-quantified clauses are NOT guessed and marked as AMBIGUOUS with semantic flag and no artificial confidence."""
        ambiguous_text = "Bidder should have sound financial standing and good market reputation."
        norm = normalize_clause(ambiguous_text, page=8, section="General Requirements")

        self.assertEqual(norm.status, NormalizationStatus.AMBIGUOUS)
        self.assertTrue(norm.requires_semantic_interpretation)
        self.assertIsNone(norm.confidence)
        self.assertIsNotNone(norm.ambiguity_reason)
        self.assertEqual(norm.source_text, ambiguous_text)
        # Verify no artificial monetary threshold was guessed
        self.assertNotIn("minimum", norm.parameters)
        self.assertNotIn("amount", norm.parameters)

    def test_13_page_and_source_traceability(self):
        """Verify source evidence and traceability metadata are preserved."""
        raw_text = "Average annual turnover shall not be less than Rs. 50 lakhs over preceding 3 financial years."
        res = extract_clauses_from_text(raw_text, page=14, default_section="Financial Qualifications")
        cand = res.candidates[0]
        self.assertEqual(cand.page, 14)
        self.assertEqual(cand.extraction_method, "deterministic")

        norm = normalize_clause(cand)
        self.assertEqual(norm.source_page, 14)
        self.assertEqual(norm.source_text, raw_text)
        self.assertEqual(norm.resolution_method, "DETERMINISTIC")
        self.assertFalse(norm.requires_semantic_interpretation)

    def test_14_section_association(self):
        """Verify end-to-end integration from DetectedTenderSection into NormalizedRequirements."""
        sec_technical = DetectedTenderSection(
            section_id="sec_tech_002",
            name="Technical Specifications",
            section_type=SectionType.TECHNICAL_REQUIREMENTS,
            document_id=self.doc_id,
            page_start=10,
            page_end=12,
            source_reference="Section 4, Pages 10-12",
            text="Bidder must possess valid ISO 9001 and ISO 27001 certifications.",
        )
        norm_res = normalize_sections([sec_technical], document_id=self.doc_id)
        self.assertEqual(norm_res.normalized_count, 1)
        req = norm_res.requirements[0]
        self.assertEqual(req.type, RequirementType.TECHNICAL.value)
        self.assertEqual(req.rule, "QUALITY_CERTIFICATION")
        self.assertIn("ISO 9001", req.parameters.get("certifications", []))
        self.assertEqual(req.section_id, "sec_tech_002")


if __name__ == "__main__":
    unittest.main()
