import cv2
import fitz
import numpy as np
import pytest

from app.schemas.entities import ExtractedEntity, StructuredDocumentOutput
from app.services.document_processing_pipeline import DocumentProcessingPipeline, processing_pipeline
from app.services.entity_extractor import DocumentEntityExtractor, entity_extractor


# 1. GST Entity Extraction Test

def test_extract_gst_entities():
    """Test extracting structured fields from GST Certificate text."""
    gst_text = """
    Government of India
    Form GST REG-06
    Registration Certificate
    Registration Number (GSTIN): 27ABCDE1234F1Z5
    Legal Name: TECHSERVE SOLUTIONS PRIVATE LIMITED
    Trade Name: TECHSERVE INDIA
    Principal Place of Business: Plot 45, MIDC Industrial Area, Pune, Maharashtra
    Date of Liability: 01/07/2017
    Taxpayer Type: Regular
    """
    entities = entity_extractor.extract("GST", gst_text, pages=[gst_text])

    assert "gstin" in entities
    assert entities["gstin"].value == "27ABCDE1234F1Z5"
    assert entities["gstin"].confidence == 0.99
    assert entities["gstin"].page == 1

    assert "company_name" in entities
    assert "TECHSERVE SOLUTIONS PRIVATE LIMITED" in entities["company_name"].value

    assert "registration_type" in entities
    assert "Regular" in entities["registration_type"].value


# 2. PAN Entity Extraction Test

def test_extract_pan_entities():
    """Test extracting structured fields from PAN card text."""
    pan_text = """
    INCOME TAX DEPARTMENT
    GOVT. OF INDIA
    Permanent Account Number: ABCDE1234F
    Name: SURESH KUMAR
    Father's Name: RAMESH KUMAR
    Date of Birth: 15/08/1985
    """
    entities = entity_extractor.extract("PAN", pan_text, pages=[pan_text])

    assert "pan_number" in entities
    assert entities["pan_number"].value == "ABCDE1234F"
    assert entities["pan_number"].confidence == 0.99

    assert "name" in entities
    assert entities["name"].value == "SURESH KUMAR"

    assert "father_name" in entities
    assert entities["father_name"].value == "RAMESH KUMAR"

    assert "dob" in entities
    assert entities["dob"].value == "15/08/1985"


# 3. UDYAM Entity Extraction Test

def test_extract_udyam_entities():
    """Test extracting structured fields from Udyam Certificate text."""
    udyam_text = """
    MINISTRY OF MICRO, SMALL AND MEDIUM ENTERPRISES
    UDYAM REGISTRATION CERTIFICATE
    UDYAM REGISTRATION NUMBER: UDYAM-MH-01-0012345
    NAME OF ENTERPRISE: INNOVATIVE DIGITAL SYSTEMS
    TYPE OF ENTERPRISE: MICRO
    MAJOR ACTIVITY: SERVICES
    """
    entities = entity_extractor.extract("UDYAM", udyam_text, pages=[udyam_text])

    assert "udyam_number" in entities
    assert entities["udyam_number"].value == "UDYAM-MH-01-0012345"

    assert "enterprise_name" in entities
    assert entities["enterprise_name"].value == "INNOVATIVE DIGITAL SYSTEMS"

    assert "enterprise_type" in entities
    assert entities["enterprise_type"].value == "MICRO"

    assert "major_activity" in entities
    assert entities["major_activity"].value == "SERVICES"


# 4. Financial Statement Entity Extraction Test

def test_extract_financial_entities():
    """Test extracting structured fields from Audited Financials."""
    fin_text = """
    INDEPENDENT AUDITOR'S REPORT
    To the Members of Alpha Tech Private Limited
    Balance Sheet as at 31st March 2025
    Statement of Profit and Loss for the year ended March 31, 2025
    Annual Turnover: INR 12,45,00,000
    UDIN: 24123456AAAAAA1234
    """
    entities = entity_extractor.extract("FINANCIAL_STATEMENT", fin_text, pages=[fin_text])

    assert "company_name" in entities
    assert "Alpha Tech Private Limited" in entities["company_name"].value

    assert "financial_year" in entities
    assert "March 31, 2025" in entities["financial_year"].value

    assert "udin" in entities
    assert entities["udin"].value == "24123456AAAAAA1234"

    assert "annual_turnover" in entities
    assert "12,45,00,000" in entities["annual_turnover"].value


# 5. Experience Certificate Entity Extraction Test

def test_extract_experience_entities():
    """Test extracting structured fields from Work Completion Certificate."""
    exp_text = """
    WORK COMPLETION CERTIFICATE
    This is to certify that M/s Global Networks India Pvt Ltd has satisfactorily completed
    the execution of work for 'Installation of Campus Wide Wi-Fi Network' under
    Purchase Order No: PO/2023/8899.
    Contract Value: Rs. 85,00,000
    Completion Date: 20-Dec-2024
    """
    entities = entity_extractor.extract("EXPERIENCE_CERTIFICATE", exp_text, pages=[exp_text])

    assert "company_name" in entities
    assert "Global Networks India Pvt Ltd" in entities["company_name"].value

    assert "work_description" in entities
    assert "Installation of Campus Wide Wi-Fi Network" in entities["work_description"].value

    assert "contract_value" in entities
    assert "85,00,000" in entities["contract_value"].value

    assert "completion_date" in entities
    assert "20-Dec-2024" in entities["completion_date"].value


# 6. OEM Authorization Entity Extraction Test

def test_extract_oem_entities():
    """Test extracting structured fields from Manufacturer Authorization Form (MAF)."""
    oem_text = """
    MANUFACTURER'S AUTHORIZATION FORM (MAF)
    We, Dell Technologies India Pvt Ltd, who are official manufacturers of Server Hardware,
    do hereby authorize M/s Prime Infotech to submit a bid
    against Tender Ref: GEM/2026/B/100200.
    """
    entities = entity_extractor.extract("OEM_AUTHORIZATION", oem_text, pages=[oem_text])

    assert "oem_name" in entities
    assert "Dell Technologies India Pvt Ltd" in entities["oem_name"].value

    assert "authorized_bidder" in entities
    assert "Prime Infotech" in entities["authorized_bidder"].value

    assert "tender_reference" in entities
    assert "GEM/2026/B/100200" in entities["tender_reference"].value


# 7. MII Declaration Entity Extraction Test

def test_extract_mii_entities():
    """Test extracting structured fields from Make in India declaration."""
    mii_text = """
    DECLARATION OF LOCAL CONTENT
    We, Bharat Electronics Solutions Pvt Ltd, hereby declare that
    we are a Class-I Local Supplier.
    The local content percentage is 68.5%.
    """
    entities = entity_extractor.extract("MII_DECLARATION", mii_text, pages=[mii_text])

    assert "company_name" in entities
    assert "Bharat Electronics Solutions Pvt Ltd" in entities["company_name"].value

    assert "local_content_percentage" in entities
    assert "68.5%" in entities["local_content_percentage"].value

    assert "supplier_class" in entities
    assert "Class-I Local Supplier" in entities["supplier_class"].value


# 8. Tender Entity Extraction Test

def test_extract_tender_entities():
    """Test extracting structured fields from Tender RFP text."""
    tender_text = """
    NOTICE INVITING TENDER
    Request for Proposal (RFP) for Procurement of Cloud Data Center Servers
    Tender Inviting Authority: Ministry of Electronics and Information Technology
    GeM Bid Number: GEM/2026/B/987654
    Earnest Money Deposit (EMD): INR 2,00,000
    Bid Submission Deadline: 25th September 2026
    """
    entities = entity_extractor.extract("TENDER", tender_text, pages=[tender_text])

    assert "tender_number" in entities
    assert entities["tender_number"].value == "GEM/2026/B/987654"

    assert "title" in entities
    assert "Procurement of Cloud Data Center Servers" in entities["title"].value

    assert "organization" in entities
    assert "Ministry of Electronics and Information Technology" in entities["organization"].value

    assert "submission_deadline" in entities
    assert "25th September 2026" in entities["submission_deadline"].value

    assert "emd_amount" in entities
    assert "INR 2,00,000" in entities["emd_amount"].value


# 9. OTHER and Missing Entities Handling

def test_extract_other_returns_empty_dict():
    """Test that OTHER document type returns empty entities dict without errors."""
    entities = entity_extractor.extract("OTHER", "Some arbitrary unclassified text.", pages=["Some arbitrary unclassified text."])
    assert entities == {}


def test_missing_entities_not_invented():
    """Test that missing fields in incomplete documents are omitted / not hallucinated."""
    partial_pan = "INCOME TAX DEPARTMENT Permanent Account Number: ABCDE1234F"
    entities = entity_extractor.extract("PAN", partial_pan, pages=[partial_pan])

    assert "pan_number" in entities
    assert entities["pan_number"].value == "ABCDE1234F"
    assert "father_name" not in entities
    assert "dob" not in entities


# 10. Full Processing Pipeline End-to-End Test

def test_processing_pipeline_end_to_end_pdf():
    """Test executing full pipeline on an in-memory PDF document."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        fitz.Point(50, 72),
        "Form GST REG-06\nRegistration Certificate\nGSTIN: 27ABCDE1234F1Z5\nLegal Name: TECHSERVE SOLUTIONS PRIVATE LIMITED\nTaxpayer Type: Regular",
        fontsize=12,
    )
    pdf_bytes = doc.tobytes()
    doc.close()

    result: StructuredDocumentOutput = processing_pipeline.process(
        file_bytes=pdf_bytes,
        filename="vendor_gst.pdf",
    )

    assert result.document_type == "GST"
    assert result.confidence >= 0.85
    assert result.is_scanned is False
    assert result.page_count == 1
    assert "gstin" in result.entities
    assert result.entities["gstin"].value == "27ABCDE1234F1Z5"
    assert result.entities["company_name"].value == "TECHSERVE SOLUTIONS PRIVATE LIMITED"
    assert result.processing_time_ms > 0
