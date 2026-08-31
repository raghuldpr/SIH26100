import pytest
from app.schemas.classification import ClassificationResult
from app.services.document_classifier import RuleBasedDocumentClassifier, document_classifier


# 1. PAN Classification Tests

def test_classify_pan_document():
    """Test classification of Indian Income Tax PAN card text."""
    pan_text = """
    INCOME TAX DEPARTMENT
    GOVT. OF INDIA
    Permanent Account Number
    ABCDE1234F
    Name: SURESH KUMAR
    Father's Name: RAMESH KUMAR
    Date of Birth: 15/08/1985
    """
    result: ClassificationResult = document_classifier.classify(pan_text, filename="pan_card.pdf")

    assert result.document_type == "PAN"
    assert result.confidence >= 0.85
    assert len(result.matched_signals) >= 2
    assert any("Permanent Account Number" in s or "PAN regex" in s for s in result.matched_signals)


# 2. GST Classification Tests

def test_classify_gst_document():
    """Test classification of GST Registration Certificate."""
    gst_text = """
    Government of India
    Form GST REG-06
    Registration Certificate
    Registration Number (GSTIN): 27ABCDE1234F1Z5
    Legal Name: TECHSERVE SOLUTIONS PRIVATE LIMITED
    Principal Place of Business: Plot 45, MIDC Industrial Area, Pune, Maharashtra
    Date of Liability: 01/07/2017
    Taxpayer Type: Regular
    """
    result: ClassificationResult = document_classifier.classify(gst_text, filename="gst_certificate.pdf")

    assert result.document_type == "GST"
    assert result.confidence >= 0.90
    assert any("GSTIN" in s or "Goods and Services Tax" in s or "GST REG" in s for s in result.matched_signals)


# 3. UDYAM (MSME) Classification Tests

def test_classify_udyam_document():
    """Test classification of MSME Udyam Registration Certificate."""
    udyam_text = """
    MINISTRY OF MICRO, SMALL AND MEDIUM ENTERPRISES
    UDYAM REGISTRATION CERTIFICATE
    UDYAM REGISTRATION NUMBER: UDYAM-MH-01-0012345
    NAME OF ENTERPRISE: INNOVATIVE DIGITAL SYSTEMS
    TYPE OF ENTERPRISE: MICRO
    MAJOR ACTIVITY: SERVICES
    NATIONAL INDUSTRY CLASSIFICATION (NIC) CODE: 62011 - Writing of software
    """
    result: ClassificationResult = document_classifier.classify(udyam_text, filename="msme_udyam.pdf")

    assert result.document_type == "UDYAM"
    assert result.confidence >= 0.90
    assert any("Udyam" in s or "UDYAM-" in s for s in result.matched_signals)


# 4. Financial Statement Classification Tests

def test_classify_financial_statement():
    """Test classification of Audited Balance Sheet & Profit and Loss."""
    fin_text = """
    INDEPENDENT AUDITOR'S REPORT
    To the Members of Alpha Tech Private Limited
    Balance Sheet as at 31st March 2025
    Statement of Profit and Loss for the year ended March 31, 2025
    Annual Turnover: INR 12,45,00,000
    UDIN: 24123456AAAAAA1234
    For S.R. Batliboi & Associates
    Chartered Accountants
    CA Membership No: 123456
    """
    result: ClassificationResult = document_classifier.classify(fin_text, filename="audited_financials.pdf")

    assert result.document_type == "FINANCIAL_STATEMENT"
    assert result.confidence >= 0.85
    assert any("balance sheet" in s.lower() or "profit and loss" in s.lower() or "auditor" in s.lower() for s in result.matched_signals)


# 5. Experience Certificate Classification Tests

def test_classify_experience_certificate():
    """Test classification of Past Work Completion / Experience Certificate."""
    exp_text = """
    WORK COMPLETION CERTIFICATE
    This is to certify that M/s Global Networks India Pvt Ltd has satisfactorily completed
    the execution of work for 'Installation of Campus Wide Wi-Fi Network' under
    Purchase Order / Work Order No: PO/2023/8899.
    Total Contract Value Executed: Rs. 85,00,000.
    Client Certificate issued for tender eligibility.
    """
    result: ClassificationResult = document_classifier.classify(exp_text, filename="work_order_completion.pdf")

    assert result.document_type == "EXPERIENCE_CERTIFICATE"
    assert result.confidence >= 0.80
    assert any("completion" in s.lower() or "work order" in s.lower() or "certificate" in s.lower() for s in result.matched_signals)


# 6. OEM Authorization (MAF) Classification Tests

def test_classify_oem_authorization():
    """Test classification of Manufacturer Authorization Form (MAF)."""
    oem_text = """
    MANUFACTURER'S AUTHORIZATION FORM (MAF)
    To: The Procurement Officer, National Informatics Centre
    Subject: OEM Authorization Letter for GeM Bid No: GEM/2026/B/100200
    We, Dell Technologies India Pvt Ltd, who are official and original equipment manufacturers (OEM)
    of Enterprise Server Hardware, do hereby authorize M/s Prime Infotech to submit a bid.
    """
    result: ClassificationResult = document_classifier.classify(oem_text, filename="dell_maf.pdf")

    assert result.document_type == "OEM_AUTHORIZATION"
    assert result.confidence >= 0.85
    assert any("manufacturer" in s.lower() or "oem" in s.lower() or "authorize" in s.lower() for s in result.matched_signals)


# 7. Make in India (MII) Declaration Classification Tests

def test_classify_mii_declaration():
    """Test classification of Make in India (MII) Local Content Declaration."""
    mii_text = """
    SELF-DECLARATION UNDER PREFERENCE TO MAKE IN INDIA (PPP-MII) ORDER
    In line with Government Public Procurement (Preference to Make in India) Order,
    We hereby certify that we are a 'Class-I Local Supplier'.
    The local content percentage for the offered products is 68.5%.
    Local Content Declaration Certificate.
    """
    result: ClassificationResult = document_classifier.classify(mii_text, filename="mii_declaration.pdf")

    assert result.document_type == "MII_DECLARATION"
    assert result.confidence >= 0.85
    assert any("make in india" in s.lower() or "class-i local supplier" in s.lower() or "local content" in s.lower() for s in result.matched_signals)



# 8. Tender RFP Classification Tests

def test_classify_tender_document():
    """Test classification of official Tender RFP / Notice Inviting Tender."""
    tender_text = """
    NOTICE INVITING TENDER (NIT)
    Request for Proposal (RFP) for Procurement of Cloud Data Center Servers
    Tender Inviting Authority: Ministry of Electronics and Information Technology
    GeM Bid Number: GEM/2026/B/987654
    Earnest Money Deposit (EMD): INR 2,00,000
    Bid Submission Deadline: 25th September 2026, 15:00 hrs
    Two Bid System: Technical Bid and Financial Bid
    """
    result: ClassificationResult = document_classifier.classify(tender_text, filename="tender_rfp.pdf")

    assert result.document_type == "TENDER"
    assert result.confidence >= 0.85
    assert any("Notice Inviting Tender" in s or "Request for Proposal" in s or "GeM Bid" in s for s in result.matched_signals)


# 9. OTHER (Unrelated / Ambiguous / Empty) Classification Tests

def test_classify_unrelated_text_as_other():
    """Test that general non-compliance text is classified as OTHER without false positives."""
    unrelated_text = """
    Weekly Team Meeting Agenda:
    1. Review quarterly marketing KPIs
    2. Discuss office cafeteria menu updates
    3. Plan team building retreat in Goa
    """
    result: ClassificationResult = document_classifier.classify(unrelated_text, filename="notes.txt")

    assert result.document_type == "OTHER"
    assert result.confidence <= 0.40


def test_classify_empty_text_as_other():
    """Test that empty string input returns OTHER cleanly."""
    result: ClassificationResult = document_classifier.classify("", filename="empty.pdf")

    assert result.document_type == "OTHER"
    assert result.confidence == 0.10
    assert len(result.matched_signals) == 0


def test_classifier_explainability():
    """Test that classification result contains an informative human-readable explanation."""
    result = document_classifier.classify("Permanent Account Number: ABCDE1234F Income Tax Department")
    assert result.explanation is not None
    assert "PAN" in result.explanation
    assert isinstance(result.scores, dict)
