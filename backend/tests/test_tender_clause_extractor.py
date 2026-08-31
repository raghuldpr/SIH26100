import pytest
from app.models.enums import RequirementType
from app.services.tender_clause_extractor import (
    TenderClauseExtractor,
    extract_clauses,
    extract_clauses_from_text,
    tender_clause_extractor,
)


def test_turnover_clause_extraction():
    """
    Verify prompt example:
    Input: 'Average annual turnover shall not be less than Rs. 15 lakhs during the preceding three years.'
    Expected: candidate_type=FINANCIAL, detection_reason='turnover + monetary threshold + period', confidence >= 0.95
    """
    text = "Average annual turnover shall not be less than Rs. 15 lakhs during the preceding three years."
    result = extract_clauses_from_text(text, page=12)

    assert result.total_candidates >= 1
    candidate = result.candidates[0]

    assert candidate.page == 12
    assert candidate.candidate_type == RequirementType.FINANCIAL.value
    assert candidate.detection_reason == "turnover + monetary threshold + period"
    assert candidate.confidence >= 0.95
    assert candidate.is_mandatory is True
    assert candidate.parameters.get("minimum_amount") == 1500000.0
    assert candidate.parameters.get("period_years") == 3
    assert candidate.parameters.get("currency") == "INR"


def test_crore_turnover_clause_extraction():
    """Verify crore turnover parsing and section context."""
    page_content = {
        "page_number": 5,
        "text": (
            "SECTION II: ELIGIBILITY CRITERIA\n"
            "The Bidder must have a minimum average annual turnover of Rs. 4.50 Crores "
            "during the last three financial years (2022-23, 2023-24, 2024-25)."
        ),
    }
    result = extract_clauses([page_content])

    assert result.total_candidates == 1
    cand = result.candidates[0]
    assert cand.candidate_type == "FINANCIAL"
    assert cand.section == "Eligibility Criteria"
    assert cand.parameters.get("minimum_amount") == 45000000.0
    assert cand.parameters.get("period_years") == 3


def test_experience_clause_extraction():
    """Verify past experience and similar works requirement extraction."""
    text = (
        "SECTION III: QUALIFICATION REQUIREMENTS\n"
        "The bidder must have at least 3 years of past experience in executing "
        "similar works for Central or State Government departments."
    )
    result = extract_clauses_from_text(text, page=8)

    assert result.total_candidates == 1
    cand = result.candidates[0]
    assert cand.candidate_type == RequirementType.EXPERIENCE.value
    assert "past experience" in cand.detection_reason
    assert cand.confidence >= 0.90
    assert cand.parameters.get("min_years") == 3
    assert cand.is_mandatory is True


def test_oem_clause_extraction():
    """Verify Manufacturer Authorization Form (MAF) / OEM requirement extraction."""
    text = (
        "ELIGIBILITY CONDITIONS\n"
        "In case the bidder is not an OEM, a valid Manufacturer Authorization Form (MAF) "
        "from the OEM must be submitted along with the bid."
    )
    result = extract_clauses_from_text(text, page=14)

    assert result.total_candidates == 1
    cand = result.candidates[0]
    assert cand.candidate_type == RequirementType.OEM.value
    assert cand.detection_reason == "oem authorization requirement"
    assert cand.confidence >= 0.95
    assert cand.is_mandatory is True
    assert cand.parameters.get("required") is True


def test_statutory_clause_extraction():
    """Verify GST and PAN statutory registration clause extraction."""
    text = (
        "MANDATORY DOCUMENTS TO BE SUBMITTED\n"
        "The bidder must possess a valid GSTIN registration certificate and PAN card "
        "issued by the competent authority."
    )
    result = extract_clauses_from_text(text, page=3)

    assert result.total_candidates >= 1
    cand = result.candidates[0]
    assert cand.candidate_type == RequirementType.STATUTORY.value
    assert cand.detection_reason == "statutory tax/registration requirement"
    assert cand.confidence >= 0.90
    assert "GST" in cand.parameters.get("statutory_ids", [])
    assert "PAN" in cand.parameters.get("statutory_ids", [])


def test_document_requirement_clause_extraction():
    """Verify mandatory affidavit, undertaking, or non-blacklisting clause extraction."""
    text = (
        "CHECKLIST FOR BIDDERS\n"
        "The bidder must submit a notarized non-blacklisting affidavit on a Rs. 100 non-judicial "
        "stamp paper confirming that the firm has not been debarred by any Government agency."
    )
    result = extract_clauses_from_text(text, page=7)

    assert result.total_candidates >= 1
    cand = result.candidates[0]
    assert cand.candidate_type == RequirementType.DOCUMENT.value
    assert cand.detection_reason == "mandatory document / undertaking submission"
    assert cand.confidence >= 0.90
    assert cand.is_mandatory is True
    assert any(d in cand.parameters.get("required_documents", []) for d in ("affidavit", "non_blacklisting"))


def test_exemption_clause_extraction():
    """Verify startup and MSE exemption rule extraction."""
    text = (
        "SECTION 4: POLICY EXEMPTIONS AND RELAXATIONS\n"
        "Relaxation of Norms for Startups and MSEs: Prior turnover and prior experience criteria "
        "are relaxed for DPIIT recognized Startups and Micro & Small Enterprises."
    )
    result = extract_clauses_from_text(text, page=18)

    assert result.total_candidates == 1
    cand = result.candidates[0]
    assert cand.candidate_type == RequirementType.EXEMPTION.value
    assert cand.detection_reason == "statutory exemption / relaxation clause"
    assert cand.confidence >= 0.95
    assert cand.is_mandatory is False
    assert "STARTUP" in cand.parameters.get("applies_to", [])
    assert "MSE" in cand.parameters.get("applies_to", [])
    assert "TURNOVER" in cand.parameters.get("target_rules", [])
    assert "EXPERIENCE" in cand.parameters.get("target_rules", [])


def test_mii_local_content_clause_extraction():
    """Verify Make in India local content percentage extraction."""
    text = (
        "PREFERENCE TO MAKE IN INDIA\n"
        "Minimum 50% local content requirement: Only Class-I Local Suppliers shall be eligible "
        "to participate in this tender."
    )
    result = extract_clauses_from_text(text, page=9)

    assert result.total_candidates == 1
    cand = result.candidates[0]
    assert cand.candidate_type == RequirementType.MII.value
    assert cand.detection_reason == "make in india local content requirement"
    assert cand.confidence >= 0.95
    assert cand.parameters.get("minimum_local_content_pct") == 50.0


def test_irrelevant_text_does_not_produce_false_positives():
    """
    Verify that general narrative, boilerplate headers, or incidental mentions
    without requirement markers are NOT falsely detected as requirements.
    """
    irrelevant_passages = [
        "Page 12 of 45 | Government e-Marketplace | GeM Bid Number: GEM/2026/B/12345",
        "The Ministry of Defence invites tenders for general administrative support.",
        "The Department was founded in 1985 to promote scientific research.",
        "Table of Contents\n1. Introduction\n2. Scope\n3. Contact Details",
        "All queries may be directed to the procurement helpdesk at helpdesk@gov.in.",
        "Prices quoted must be inclusive of all taxes, duties, and transport expenses.",
    ]

    for passage in irrelevant_passages:
        res = extract_clauses_from_text(passage, page=1)
        assert res.total_candidates == 0, f"False positive detected on: {passage}"


def test_multiple_requirements_on_one_page_with_section_tracking():
    """Verify extracting multiple discrete criteria across a single page with section inheritance."""
    page_text = (
        "SECTION III: MINIMUM ELIGIBILITY CRITERIA\n"
        "1. Average annual financial turnover shall not be less than Rs. 50 lakhs during the last three years.\n"
        "2. Bidder must have at least 2 years of past experience executing similar government works.\n"
        "3. In case of non-OEM bidders, an OEM Authorization Form must be furnished.\n"
        "4. Bidder must submit copy of valid GST registration and PAN card.\n"
        "5. Startups and MSEs are exempted from prior turnover criteria.\n"
    )

    result = extract_clauses_from_text(page_text, page=6)

    # All 5 distinct requirements should be extracted
    assert result.total_candidates == 5
    assert "Eligibility Criteria" in result.sections_detected

    # Verify each candidate inherited the section
    for cand in result.candidates:
        assert cand.page == 6
        assert cand.section == "Eligibility Criteria"

    # Verify type-based filtering helper
    fin_candidates = result.by_type("FINANCIAL")
    assert len(fin_candidates) == 1
    assert fin_candidates[0].parameters.get("minimum_amount") == 5000000.0

    exp_candidates = result.by_type("EXPERIENCE")
    assert len(exp_candidates) == 1
    assert exp_candidates[0].parameters.get("min_years") == 2

    oem_candidates = result.by_type("OEM")
    assert len(oem_candidates) == 1

    stat_candidates = result.by_type("STATUTORY")
    assert len(stat_candidates) == 1

    # Verify mandatory vs exemption filtering helpers
    mandatory_clauses = result.mandatory_only()
    assert len(mandatory_clauses) == 4

    exemption_clauses = result.exemptions_only()
    assert len(exemption_clauses) == 1
    assert exemption_clauses[0].candidate_type == RequirementType.EXEMPTION.value
