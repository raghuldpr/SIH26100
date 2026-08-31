import pytest
from app.models.enums import RequirementType
from app.schemas.tender_clause import ClauseCandidate
from app.schemas.tender_requirement_normalizer import (
    NormalizationResult,
    NormalizationStatus,
    NormalizedRequirement,
)
from app.services.tender_requirement_normalizer import (
    TenderRequirementNormalizer,
    normalize_candidates,
    normalize_clause,
    normalize_indian_currency,
    normalize_time_expression,
    tender_requirement_normalizer,
)


def test_user_example_average_turnover_normalization():
    """
    Verify exact prompt example:
    Input: 'Average annual turnover shall not be less than Rs. 15 lakhs during the preceding three years.'
    Output:
    {
      "type": "FINANCIAL",
      "rule": "AVERAGE_TURNOVER",
      "parameters": {
        "minimum": 1500000,
        "currency": "INR",
        "period": 3,
        "period_unit": "YEARS"
      },
      "mandatory": true
    }
    """
    clause_text = "Average annual turnover shall not be less than Rs. 15 lakhs during the preceding three years."
    result = normalize_clause(clause_text, page=12, section="Eligibility Criteria")

    assert result.status == NormalizationStatus.NORMALIZED
    assert result.type == RequirementType.FINANCIAL.value
    assert result.rule == "AVERAGE_TURNOVER"
    assert result.mandatory is True
    assert result.parameters == {
        "minimum": 1500000,
        "currency": "INR",
        "period": 3,
        "period_unit": "YEARS",
    }
    assert result.source_page == 12
    assert result.source_section == "Eligibility Criteria"
    assert result.source_text == clause_text
    assert result.confidence >= 0.95


def test_indian_monetary_expressions_normalization():
    """
    Verify normalization of diverse Indian currency expressions into canonical INR integers:
    - ₹15 lakh
    - Rs. 15 lakh
    - INR 1,500,000
    - Rs 15,00,000
    - 15 Lakhs
    - Rs. 4.5 Crores
    - ₹ 50,000
    """
    test_cases = [
        ("₹15 lakh", 1500000),
        ("Rs. 15 lakh", 1500000),
        ("INR 1,500,000", 1500000),
        ("Rs 15,00,000", 1500000),
        ("15 Lakhs", 1500000),
        ("Rs. 4.50 Crores", 45000000),
        ("Rs 2.5 Cr", 25000000),
        ("₹ 50,000", 50000),
    ]

    for expr, expected in test_cases:
        actual = normalize_indian_currency(expr)
        assert actual == expected, f"Failed for expression '{expr}': expected {expected}, got {actual}"


def test_time_expressions_normalization():
    """
    Verify normalization of diverse Indian tender time expressions:
    - previous 3 years
    - preceding three years
    - last three financial years
    - past 5 years
    - last 6 months
    """
    test_cases = [
        ("previous 3 years", {"period": 3, "period_unit": "YEARS"}),
        ("preceding three years", {"period": 3, "period_unit": "YEARS"}),
        ("last three financial years", {"period": 3, "period_unit": "YEARS"}),
        ("during the past 5 financial years", {"period": 5, "period_unit": "YEARS"}),
        ("completed within last 6 months", {"period": 6, "period_unit": "MONTHS"}),
    ]

    for phrase, expected in test_cases:
        actual = normalize_time_expression(phrase)
        assert actual == expected, f"Failed for phrase '{phrase}': expected {expected}, got {actual}"


def test_minimum_turnover_normalization():
    """Verify non-average minimum annual turnover rule."""
    text = "The bidder must have a minimum annual turnover of ₹ 2.50 Crores."
    res = normalize_clause(text, page=4)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "FINANCIAL"
    assert res.rule == "MINIMUM_TURNOVER"
    assert res.parameters.get("minimum") == 25000000
    assert res.parameters.get("currency") == "INR"
    assert res.mandatory is True


def test_net_worth_normalization():
    """Verify net worth normalization with positive condition or amount."""
    text1 = "The bidder should have a positive net worth as on the end of the last financial year."
    res1 = normalize_clause(text1, page=3)
    assert res1.status == NormalizationStatus.NORMALIZED
    assert res1.type == "FINANCIAL"
    assert res1.rule == "NET_WORTH"
    assert res1.parameters.get("condition") == "POSITIVE"

    text2 = "Bidder must have a minimum net worth of Rs. 1 Crore."
    res2 = normalize_clause(text2, page=3)
    assert res2.status == NormalizationStatus.NORMALIZED
    assert res2.parameters.get("minimum") == 10000000


def test_similar_work_experience_normalization():
    """Verify similar work experience rule normalization."""
    text = "Bidder must have at least 3 years of experience in executing similar works for Central Government."
    res = normalize_clause(text, page=7)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "EXPERIENCE"
    assert res.rule == "SIMILAR_WORK_EXPERIENCE"
    assert res.parameters.get("scope") == "SIMILAR_WORK"
    assert res.parameters.get("min_years") == 3
    assert res.parameters.get("period_unit") == "YEARS"


def test_completed_projects_normalization():
    """Verify number of completed projects/contracts rule."""
    text = "Bidder must have completed at least 3 similar contracts in the last three years."
    res = normalize_clause(text, page=8)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "EXPERIENCE"
    assert res.rule == "COMPLETED_PROJECTS"
    assert res.parameters.get("min_completed_orders") == 3
    assert res.parameters.get("scope") == "SIMILAR_WORK"


def test_experience_period_normalization():
    """Verify generic experience period rule."""
    text = "The firm should have at least 5 years of experience in business operations."
    res = normalize_clause(text, page=5)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "EXPERIENCE"
    assert res.rule == "EXPERIENCE_PERIOD"
    assert res.parameters.get("min_years") == 5


def test_gst_and_pan_normalization():
    """Verify GST and PAN statutory registrations."""
    text = "Copy of valid GSTIN registration and PAN card must be submitted."
    res = normalize_clause(text, page=2)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "STATUTORY"
    assert res.rule == "GST_AND_PAN_REGISTRATION"
    assert "GSTIN" in res.parameters.get("statutory_documents", [])
    assert "PAN" in res.parameters.get("statutory_documents", [])


def test_statutory_licenses_epf_esi_normalization():
    """Verify EPF and ESI registration requirements."""
    text = "Bidder must have active EPF and ESI registration certificates."
    res = normalize_clause(text, page=2)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "STATUTORY"
    assert res.rule == "STATUTORY_LICENSE"
    assert "EPF" in res.parameters.get("licenses", [])
    assert "ESI" in res.parameters.get("licenses", [])


def test_oem_authorization_normalization():
    """Verify OEM authorization and MAF normalization."""
    text = "Non-OEM bidders must submit valid Manufacturer Authorization Form (MAF) from OEM."
    res = normalize_clause(text, page=10)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "OEM"
    assert res.rule == "OEM_AUTHORIZATION"
    assert res.parameters.get("authorization_type") == "MAF"
    assert res.parameters.get("required") is True


def test_mii_local_content_normalization():
    """Verify Make in India (MII) local content normalization."""
    text = "Minimum 50% local content requirement. Class-I Local Suppliers will be given purchase preference under MII policy."
    res = normalize_clause(text, page=11)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "MII"
    assert res.rule == "MII_LOCAL_CONTENT"
    assert res.parameters.get("minimum_local_content_pct") == 50.0
    assert res.parameters.get("supplier_class") == "CLASS_I"


def test_mse_conditions_normalization():
    """Verify MSE preference conditions."""
    text = "Public Procurement Policy for Micro and Small Enterprises (MSEs) Order 2012 shall be applicable."
    res = normalize_clause(text, page=14)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "MSE"
    assert res.rule == "MSE_PREFERENCE"
    assert res.parameters.get("target_group") == "MSE"


def test_startup_conditions_normalization():
    """Verify Startup qualification criteria."""
    text = "Entities recognized as Startups by DPIIT are invited to participate."
    res = normalize_clause(text, page=15)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "STARTUP"
    assert res.rule == "STARTUP_CRITERIA"
    assert res.parameters.get("target_group") == "STARTUP"


def test_required_certificates_affidavit_normalization():
    """Verify non-blacklisting affidavit / undertaking requirement."""
    text = "The bidder must submit a notarized non-blacklisting affidavit on Rs 100 stamp paper."
    res = normalize_clause(text, page=9)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "DOCUMENT"
    assert res.rule == "REQUIRED_DOCUMENT"
    assert res.parameters.get("document_type") == "NON_BLACKLISTING_AFFIDAVIT"
    assert res.parameters.get("notarized") is True


def test_explicit_exemptions_normalization():
    """Verify Startup and MSE turnover/experience exemption rule."""
    text = "Relaxation of Norms for Startups and MSEs: Prior turnover and prior experience criteria are relaxed."
    res = normalize_clause(text, page=16)

    assert res.status == NormalizationStatus.NORMALIZED
    assert res.type == "EXEMPTION"
    assert res.mandatory is False
    assert "STARTUP" in res.parameters.get("applies_to", [])
    assert "MSE" in res.parameters.get("applies_to", [])
    assert "AVERAGE_TURNOVER" in res.parameters.get("target_rules", [])


def test_ambiguous_clause_marking_without_guessing():
    """
    Verify that unquantified or vague clauses are explicitly marked as AMBIGUOUS
    rather than fabricating information or guessing.
    """
    # 1. Turnover mentioned without numeric amount
    amb_turnover = "Bidder must possess sound financial turnover as determined by the evaluation committee."
    res1 = normalize_clause(amb_turnover, page=6)
    assert res1.status == NormalizationStatus.AMBIGUOUS
    assert res1.ambiguity_reason is not None
    assert "monetary threshold" in res1.ambiguity_reason.lower()

    # 2. Experience mentioned without duration or count
    amb_exp = "Bidder must have past experience in government contracting."
    res2 = normalize_clause(amb_exp, page=7)
    assert res2.status == NormalizationStatus.AMBIGUOUS
    assert res2.ambiguity_reason is not None
    assert "duration" in res2.ambiguity_reason.lower() or "count" in res2.ambiguity_reason.lower()


def test_batch_candidates_normalization_and_db_schema_conversion():
    """Verify batch normalization across ClauseCandidate list and conversion to TenderRequirementCreate."""
    candidates = [
        ClauseCandidate(
            page=2,
            section="Eligibility Criteria",
            source_text="Average annual turnover shall not be less than Rs. 20 lakhs during the preceding three years.",
            candidate_type="FINANCIAL",
            detection_reason="turnover + monetary threshold + period",
            confidence=0.96,
        ),
        ClauseCandidate(
            page=2,
            section="Eligibility Criteria",
            source_text="Bidder must have past experience.",
            candidate_type="EXPERIENCE",
            detection_reason="vague experience",
            confidence=0.60,
        ),
    ]

    batch_res = normalize_candidates(candidates)
    assert batch_res.total_evaluated == 2
    assert batch_res.normalized_count == 1
    assert batch_res.ambiguous_count == 1

    normalized = batch_res.normalized_only()[0]
    assert normalized.rule == "AVERAGE_TURNOVER"
    assert normalized.parameters["minimum"] == 2000000

    # Test conversion to TenderRequirementCreate schema
    schema = normalized.to_tender_requirement_create()
    assert schema.requirement_type == "FINANCIAL"
    assert schema.rule == "AVERAGE_TURNOVER"
    assert schema.parameters["minimum"] == 2000000
    assert schema.source_page == 2
    assert schema.source_section == "Eligibility Criteria"

    # Test ambiguous cannot be converted to TenderRequirementCreate
    ambiguous = batch_res.ambiguous_only()[0]
    with pytest.raises(ValueError):
        ambiguous.to_tender_requirement_create()
