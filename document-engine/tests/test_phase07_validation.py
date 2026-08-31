import json
from pathlib import Path
import pytest

from scripts.run_phase07_validation import (
    create_pan_fixture,
    create_gst_fixture,
    create_udyam_fixture,
    create_financial_statement_fixture,
    create_experience_cert_fixture,
    create_oem_authorization_fixture,
    create_mii_declaration_fixture,
    create_tender_fixture,
    create_scanned_pdf_fixture,
    create_poor_quality_scan_fixture,
    create_rotated_page_fixture,
    create_hybrid_fixture,
    create_invalid_file_fixture,
    create_empty_file_fixture,
)
from app.services.document_service import process_document


def test_validation_pan(tmp_path: Path):
    """Synthetic PAN document validation."""
    fixture = create_pan_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "PAN"
    assert res.classification_confidence >= 0.85
    assert res.extraction.ocr_used is False
    assert res.data["pan"] == "ABCDE1234F"
    assert res.data["name"] == "RAJESH SHARMA"
    assert res.processing.status == "completed"


def test_validation_gst(tmp_path: Path):
    """Synthetic GST document validation with table."""
    fixture = create_gst_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "GST"
    assert res.classification_confidence >= 0.85
    assert res.extraction.ocr_used is False
    assert res.data["gstin"] == "27ABCDE1234F1Z5"
    assert res.data["legal_name"] == "APEX GLOBAL TECHNOLOGIES PRIVATE LIMITED"
    assert len(res.tables) >= 1
    assert res.processing.status == "completed"


def test_validation_udyam(tmp_path: Path):
    """Synthetic UDYAM MSME certificate validation."""
    fixture = create_udyam_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "UDYAM"
    assert res.classification_confidence >= 0.85
    assert res.extraction.ocr_used is False
    assert res.data["udyam_number"] == "UDYAM-MH-01-0098765"
    assert res.data["enterprise_type"] == "SMALL"
    assert res.processing.status == "completed"


def test_validation_financial_statement(tmp_path: Path):
    """Synthetic multi-page Financial Statement validation with table."""
    fixture = create_financial_statement_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "FINANCIAL_STATEMENT"
    assert res.classification_confidence >= 0.85
    assert res.pages == 2
    assert res.extraction.ocr_used is False
    assert res.data["financial_year"] == "2024-25"
    assert res.data["revenue"] == 450000000
    assert len(res.tables) >= 1
    assert res.processing.status == "completed"


def test_validation_experience_certificate(tmp_path: Path):
    """Synthetic Work Completion / Experience Certificate validation."""
    fixture = create_experience_cert_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "EXPERIENCE_CERTIFICATE"
    assert res.classification_confidence >= 0.85
    assert res.data["company_name"] == "Apex Global Technologies Private Limited"
    assert res.data["project_value"] == 12000000
    assert res.data["completion_date"] == "15-Jan-2024"
    assert res.processing.status == "completed"


def test_validation_oem_authorization(tmp_path: Path):
    """Synthetic OEM Authorization Form validation."""
    fixture = create_oem_authorization_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "OEM_AUTHORIZATION"
    assert res.classification_confidence >= 0.85
    assert res.data["oem_name"] == "Cisco Systems India Pvt Ltd"
    assert res.data["authorized_bidder"] == "Apex Global Technologies Private Limited"
    assert res.data["authorization_date"] == "20-08-2026"
    assert res.processing.status == "completed"


def test_validation_mii_declaration(tmp_path: Path):
    """Synthetic Make in India Declaration validation."""
    fixture = create_mii_declaration_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "MII_DECLARATION"
    assert res.classification_confidence >= 0.85
    assert res.data["bidder_name"] == "Apex Global Technologies Private Limited"
    assert res.data["local_content_percentage"] == 72.5
    assert res.data["country_of_origin"] == "India"
    assert res.processing.status == "completed"


def test_validation_tender(tmp_path: Path):
    """Synthetic multi-page GeM Tender validation with schedule table."""
    fixture = create_tender_fixture(tmp_path)
    res = process_document(fixture)
    assert res.document_type == "TENDER"
    assert res.classification_confidence >= 0.85
    assert res.pages == 2
    assert res.data["tender_reference"] == "GEM/2026/B/887766"
    assert res.data["estimated_value"] == 7500000
    assert len(res.tables) >= 1
    assert res.processing.status == "completed"


def test_validation_scanned_pdf(tmp_path: Path):
    """Synthetic scanned document triggers page rendering and OCR."""
    fixture = create_scanned_pdf_fixture(tmp_path)
    res = process_document(fixture)
    assert res.extraction.ocr_used is True
    assert res.extraction.method == "ocr"
    assert res.pages == 1
    assert res.processing.status == "completed"


def test_validation_poor_quality_scan(tmp_path: Path):
    """Synthetic noisy, low-contrast scan triggers OCR pipeline."""
    fixture = create_poor_quality_scan_fixture(tmp_path)
    res = process_document(fixture)
    assert res.extraction.ocr_used is True
    assert res.pages == 1
    assert res.processing.status == "completed"


def test_validation_rotated_page(tmp_path: Path):
    """Synthetic rotated/skewed page scan triggers OCR pipeline."""
    fixture = create_rotated_page_fixture(tmp_path)
    res = process_document(fixture)
    assert res.extraction.ocr_used is True
    assert res.pages == 1
    assert res.processing.status == "completed"


def test_validation_hybrid_document(tmp_path: Path):
    """Synthetic hybrid document containing both text and image."""
    fixture = create_hybrid_fixture(tmp_path)
    res = process_document(fixture)
    # Native text present, so native extraction is retained
    assert res.extraction.ocr_used is False
    assert res.document_type == "MII_DECLARATION"
    assert res.data["local_content_percentage"] == 68.0
    assert res.processing.status == "completed"


def test_validation_invalid_file(tmp_path: Path):
    """Synthetic invalid non-document binary fails cleanly."""
    fixture = create_invalid_file_fixture(tmp_path)
    res = process_document(fixture)
    assert res.processing.status == "failed"
    assert res.document_type == "UNKNOWN"


def test_validation_empty_file(tmp_path: Path):
    """Synthetic empty 0-byte document fails cleanly."""
    fixture = create_empty_file_fixture(tmp_path)
    res = process_document(fixture)
    assert res.processing.status == "failed"
    assert res.document_type == "UNKNOWN"
