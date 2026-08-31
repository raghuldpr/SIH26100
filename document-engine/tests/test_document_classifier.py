import pytest

from app.classifiers.document_classifier import (
    DocumentClassifier,
    classify_text,
)


def test_classify_pan_document():
    """Verify PAN card / letter detection with PAN number format and departmental titles."""
    pan_text = """
    INCOME TAX DEPARTMENT
    GOVT. OF INDIA
    Permanent Account Number Card
    ABCDE1234F
    Name: RAMESH KUMAR
    Father's Name: SURESH KUMAR
    Date of Birth: 15/08/1985
    """
    result = classify_text(pan_text)
    assert result.document_type == "PAN"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("permanent account number" in ind.lower() or "pan" in ind.lower() for ind in result.matched_indicators)


def test_classify_gst_document():
    """Verify GST registration certificate detection with GSTIN format and statutory phrases."""
    gst_text = """
    Form GST REG-06
    Government of India
    Registration Certificate
    Registration Number (GSTIN): 27ABCDE1234F1Z5
    Legal Name: ACME GLOBAL INFOTECH PRIVATE LIMITED
    Trade Name: ACME INFOTECH
    Central Goods and Services Tax Act, 2017
    State Goods and Services Tax Act, 2017
    Date of Liability: 01/07/2017
    """
    result = classify_text(gst_text)
    assert result.document_type == "GST"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("goods and services tax" in ind.lower() or "gstin" in ind.lower() for ind in result.matched_indicators)


def test_classify_udyam_document():
    """Verify UDYAM MSME registration certificate detection."""
    udyam_text = """
    UDYAM REGISTRATION CERTIFICATE
    UDYAM REGISTRATION NUMBER: UDYAM-MH-01-0012345
    NAME OF ENTERPRISE: PRIME NETWORKS
    TYPE OF ENTERPRISE: MICRO ENTERPRISE
    MAJOR ACTIVITY: SERVICES
    MINISTRY OF MICRO, SMALL AND MEDIUM ENTERPRISES
    """
    result = classify_text(udyam_text)
    assert result.document_type == "UDYAM"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("udyam registration certificate" in ind.lower() or "udyam" in ind.lower() for ind in result.matched_indicators)


def test_classify_financial_statement():
    """Verify financial statement and audited balance sheet detection with UDIN."""
    financial_text = """
    INDEPENDENT AUDITOR'S REPORT
    To the Members of Apex Solutions Ltd.
    Balance Sheet as at 31st March 2025
    Statement of Profit and Loss for the year ended March 31, 2025
    UDIN: 24123456AAAAAA1234
    For Chartered Accountants
    Annual Turnover: INR 15,00,00,000
    Current Assets and Current Liabilities
    """
    result = classify_text(financial_text)
    assert result.document_type == "FINANCIAL_STATEMENT"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("balance sheet" in ind.lower() or "auditor" in ind.lower() or "udin" in ind.lower() for ind in result.matched_indicators)


def test_classify_experience_certificate():
    """Verify work completion / experience certificate detection."""
    exp_text = """
    WORK COMPLETION CERTIFICATE
    This is to certify that M/s Global Networks India Pvt Ltd has satisfactorily completed
    the execution of work for 'Campus Wi-Fi Infrastructure Setup'.
    Purchase Order No: PO/2023/8899
    Work Order Date: 12-Jan-2023
    Contract Value: Rs. 85,00,000
    Date of Completion: 30-Nov-2023
    Performance Certificate: Performance has been found satisfactory.
    """
    result = classify_text(exp_text)
    assert result.document_type == "EXPERIENCE_CERTIFICATE"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("work completion certificate" in ind.lower() or "satisfactorily completed" in ind.lower() for ind in result.matched_indicators)


def test_classify_oem_authorization():
    """Verify Manufacturer Authorization Form (MAF) detection."""
    oem_text = """
    MANUFACTURER'S AUTHORIZATION FORM (MAF)
    To: The Purchase Officer, GeM Portal
    We, Dell Technologies India Pvt Ltd, who are official manufacturer of Server Hardware,
    do hereby authorize Prime Infotech to submit a bid against Tender Ref: GEM/2026/B/100200.
    As an authorized partner, they are authorized to negotiate and conclude the contract.
    Original Equipment Manufacturer guarantee and warranty is supported.
    """
    result = classify_text(oem_text)
    assert result.document_type == "OEM_AUTHORIZATION"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("manufacturer" in ind.lower() or "authorization" in ind.lower() for ind in result.matched_indicators)


def test_classify_mii_declaration():
    """Verify Make in India / Local Content self-declaration detection."""
    mii_text = """
    SELF-CERTIFICATION / MII DECLARATION
    In compliance with Public Procurement (Preference to Make in India) Order,
    we hereby certify that we are a Class-I Local Supplier.
    Percentage of local content: 65%
    Country of Origin: India
    Location of Value Addition: Bengaluru, Karnataka
    """
    result = classify_text(mii_text)
    assert result.document_type == "MII_DECLARATION"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("make in india" in ind.lower() or "local content" in ind.lower() or "class-i local supplier" in ind.lower() for ind in result.matched_indicators)


def test_classify_tender_document():
    """Verify GeM Bid document and tender notice detection."""
    tender_text = """
    GeM Bid Document
    Bid Number: GEM/2026/B/100200
    Notice Inviting Tender for Procurement of High Performance Routers
    Bid End Date / Time: 15-09-2026 18:00:00
    Bid Opening Date / Time: 15-09-2026 18:30:00
    Earnest Money Deposit (EMD) Amount: 50,000 INR
    Consignee/Reporting Officer details included in Schedule.
    """
    result = classify_text(tender_text)
    assert result.document_type == "TENDER"
    assert result.confidence >= 0.85
    assert result.confidence < 1.0
    assert any("gem" in ind.lower() or "bid document" in ind.lower() for ind in result.matched_indicators)


def test_classify_unknown_empty_text():
    """Verify empty or whitespace string returns UNKNOWN with 0.0 confidence."""
    result = classify_text("")
    assert result.document_type == "UNKNOWN"
    assert result.confidence == 0.0
    assert result.matched_indicators == []

    result_spaces = classify_text("   \n\n\t  ")
    assert result_spaces.document_type == "UNKNOWN"
    assert result_spaces.confidence == 0.0


def test_classify_unknown_unrelated_text():
    """Verify non-procurement arbitrary text returns UNKNOWN."""
    recipe_text = """
    Chocolate Chip Cookies Recipe
    Ingredients: 2 cups flour, 1 cup butter, 1 cup brown sugar, 2 eggs, 1 tsp vanilla extract,
    1 cup semi-sweet chocolate chips. Bake at 350 degrees Fahrenheit for 12 minutes until golden brown.
    """
    result = classify_text(recipe_text)
    assert result.document_type == "UNKNOWN"
    assert result.confidence == 0.0


def test_single_keyword_never_claims_100_percent():
    """Verify a single matched keyword does not produce 100% or overly high certainty."""
    single_keyword_text = "The company recorded annual turnover during the recent quarterly review."
    result = classify_text(single_keyword_text)
    # Even if it matches financial statement or remains below threshold, confidence must never be 1.0
    assert result.confidence < 0.65


def test_ocr_noisy_spacing_tolerant():
    """Verify classifier correctly handles spaced OCR noise (e.g. 'G S T I N')."""
    noisy_gst_text = """
    Government of India
    Registration Certificate under Goods and Services Tax
    G S T I N : 27ABCDE1234F1Z5
    Taxpayer Details
    """
    result = classify_text(noisy_gst_text)
    assert result.document_type == "GST"
    assert result.confidence >= 0.80
