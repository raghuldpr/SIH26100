import pytest

from app.services.structured_extractor import (
    StructuredExtractor,
    extract_structured_data,
)


def test_extract_gst_fields():
    """Verify structured field extraction from GST registration certificate."""
    gst_text = """
    Government of India
    Registration Certificate
    Registration Number (GSTIN): 27ABCDE1234F1Z5
    Legal Name: ACME GLOBAL INFOTECH PRIVATE LIMITED
    Trade Name: ACME INFOTECH
    Status: Active
    """
    result = extract_structured_data(gst_text, doc_type="GST")
    assert result.document_type == "GST"
    assert result.data["gstin"] == "27ABCDE1234F1Z5"
    assert result.data["legal_name"] == "ACME GLOBAL INFOTECH PRIVATE LIMITED"
    assert result.data["company_name"] == "ACME INFOTECH"
    assert result.data["status"] == "Active"

    assert result.field_confidence["gstin"] == 0.99
    assert result.field_confidence["legal_name"] >= 0.90
    assert result.field_confidence["company_name"] >= 0.90


def test_extract_pan_fields():
    """Verify structured field extraction from PAN document."""
    pan_text = """
    INCOME TAX DEPARTMENT
    GOVT. OF INDIA
    Permanent Account Number Card
    ABCDE1234F
    Name: RAMESH KUMAR
    Father's Name: SURESH KUMAR
    Date of Birth: 15/08/1985
    """
    result = extract_structured_data(pan_text, doc_type="PAN")
    assert result.document_type == "PAN"
    assert result.data["pan"] == "ABCDE1234F"
    assert result.data["name"] == "RAMESH KUMAR"

    assert result.field_confidence["pan"] == 0.99
    assert result.field_confidence["name"] >= 0.85


def test_extract_udyam_fields():
    """Verify structured field extraction from UDYAM certificate."""
    udyam_text = """
    UDYAM REGISTRATION CERTIFICATE
    UDYAM REGISTRATION NUMBER: UDYAM-MH-01-0012345
    NAME OF ENTERPRISE: PRIME NETWORKS
    TYPE OF ENTERPRISE: MICRO
    MAJOR ACTIVITY: SERVICES
    """
    result = extract_structured_data(udyam_text, doc_type="UDYAM")
    assert result.document_type == "UDYAM"
    assert result.data["udyam_number"] == "UDYAM-MH-01-0012345"
    assert result.data["enterprise_name"] == "PRIME NETWORKS"
    assert result.data["enterprise_type"] == "MICRO"

    assert result.field_confidence["udyam_number"] == 0.99
    assert result.field_confidence["enterprise_type"] >= 0.90


def test_extract_financial_statement_fields():
    """Verify structured field extraction from Financial Statement / Audit report."""
    fin_text = """
    INDEPENDENT AUDITOR'S REPORT
    To the Members of Apex Solutions Ltd.
    Balance Sheet as at 31st March 2025
    Statement of Profit and Loss for the year ended March 31, 2025
    FY: 2024-25
    Annual Turnover: INR 15,00,00,000
    Net Profit: INR 1,50,00,000
    """
    result = extract_structured_data(fin_text, doc_type="FINANCIAL_STATEMENT")
    assert result.document_type == "FINANCIAL_STATEMENT"
    assert result.data["company_name"] == "Apex Solutions Ltd."
    assert result.data["financial_year"] == "2024-25"
    assert result.data["revenue"] == 150000000
    assert result.data["profit"] == 15000000
    assert result.data["statement_type"] == "Balance Sheet"

    assert result.field_confidence["financial_year"] >= 0.85
    assert result.field_confidence["revenue"] >= 0.85


def test_extract_experience_certificate_fields():
    """Verify structured field extraction from Work Completion / Experience Certificate."""
    exp_text = """
    WORK COMPLETION CERTIFICATE
    Issued by: Department of Information Technology, Govt of Karnataka
    This is to certify that M/s Global Networks India Pvt Ltd has satisfactorily completed
    execution of work for 'Campus Wi-Fi Infrastructure Setup'.
    Contract Value: Rs. 85,00,000
    Date of Completion: 30-Nov-2023
    """
    result = extract_structured_data(exp_text, doc_type="EXPERIENCE_CERTIFICATE")
    assert result.document_type == "EXPERIENCE_CERTIFICATE"
    assert result.data["company_name"] == "Global Networks India Pvt Ltd"
    assert "Department of Information Technology" in result.data["client_name"]
    assert "Campus Wi-Fi" in result.data["project_name"]
    assert result.data["project_value"] == 8500000
    assert result.data["completion_date"] == "30-Nov-2023"


def test_extract_oem_authorization_fields():
    """Verify structured field extraction from Manufacturer Authorization Form (MAF)."""
    oem_text = """
    MANUFACTURER'S AUTHORIZATION FORM (MAF)
    Dated: 12-08-2026
    We, Dell Technologies India Pvt Ltd, who are official manufacturer of 'Server Hardware',
    do hereby authorize Prime Infotech to submit a bid against Tender Ref: GEM/2026/B/100200.
    """
    result = extract_structured_data(oem_text, doc_type="OEM_AUTHORIZATION")
    assert result.document_type == "OEM_AUTHORIZATION"
    assert result.data["oem_name"] == "Dell Technologies India Pvt Ltd"
    assert result.data["authorized_bidder"] == "Prime Infotech"
    assert result.data["authorization_date"] == "12-08-2026"
    assert "Server Hardware" in result.data["product"]


def test_extract_mii_declaration_fields():
    """Verify structured field extraction from Make in India Declaration."""
    mii_text = """
    MAKE IN INDIA SELF-CERTIFICATION
    Dated: 05-09-2026
    We certify that M/s Bharat Heavy Electricals is a Class-I Local Supplier.
    Percentage of local content: 65.5%
    Country of Origin: India
    """
    result = extract_structured_data(mii_text, doc_type="MII_DECLARATION")
    assert result.document_type == "MII_DECLARATION"
    assert result.data["bidder_name"] == "Bharat Heavy Electricals"
    assert result.data["local_content_percentage"] == 65.5
    assert result.data["country_of_origin"] == "India"
    assert result.data["declaration_date"] == "05-09-2026"


def test_extract_tender_fields():
    """Verify structured field extraction from GeM Tender Document."""
    tender_text = """
    GeM Bid Document
    Bid Number: GEM/2026/B/100200
    Ministry/State Name: Ministry of Electronics and Information Technology
    Notice Inviting Tender for Procurement of High-End Core Switches
    Bid End Date / Time: 15-09-2026 18:00:00
    Estimated Bid Value: INR 50,00,000
    """
    result = extract_structured_data(tender_text, doc_type="TENDER")
    assert result.document_type == "TENDER"
    assert result.data["tender_reference"] == "GEM/2026/B/100200"
    assert "Ministry of Electronics" in result.data["issuing_organization"]
    assert "High-End Core Switches" in result.data["title"]
    assert "15-09-2026" in result.data["bid_deadline"]
    assert result.data["estimated_value"] == 5000000


def test_missing_fields_return_null_without_hallucination():
    """Verify that unextractable or missing fields return None rather than invented values."""
    sparse_gst = "Registration Number (GSTIN): 27ABCDE1234F1Z5"
    result = extract_structured_data(sparse_gst, doc_type="GST")
    assert result.data["gstin"] == "27ABCDE1234F1Z5"
    assert result.data["legal_name"] is None
    assert result.data["company_name"] is None
    assert "legal_name" not in result.field_confidence


def test_automatic_classification_dispatch():
    """Verify omitting doc_type automatically triggers classification and structured extraction."""
    udyam_text = """
    UDYAM REGISTRATION CERTIFICATE
    UDYAM REGISTRATION NUMBER: UDYAM-DL-01-9988776
    NAME OF ENTERPRISE: HINDUSTAN HARDWARE
    TYPE OF ENTERPRISE: SMALL ENTERPRISE
    """
    result = extract_structured_data(udyam_text)
    assert result.document_type == "UDYAM"
    assert result.data["udyam_number"] == "UDYAM-DL-01-9988776"
    assert result.data["enterprise_name"] == "HINDUSTAN HARDWARE"
    assert result.data["enterprise_type"] == "SMALL"
