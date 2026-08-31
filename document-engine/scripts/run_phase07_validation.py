import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
import pymupdf

# Configure path so document-engine app is importable
doc_engine_root = Path(__file__).resolve().parent.parent
if str(doc_engine_root) not in sys.path:
    sys.path.insert(0, str(doc_engine_root))

from app.services.document_service import process_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("phase07_validation")


def create_pan_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic PAN card PDF."""
    path = fixtures_dir / "SYNTHETIC_PAN_CARD.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=250)
    text = (
        "INCOME TAX DEPARTMENT\n"
        "GOVT. OF INDIA\n"
        "Permanent Account Number Card\n\n"
        "ABCDE1234F\n\n"
        "Name: RAJESH SHARMA\n"
        "Father's Name: MANOHAR SHARMA\n"
        "Date of Birth: 22/04/1982\n"
    )
    page.insert_text((30, 40), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def create_gst_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic GST registration certificate PDF with a table."""
    path = fixtures_dir / "SYNTHETIC_GST_REGISTRATION.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "Form GST REG-06\n"
        "Government of India\n"
        "Registration Certificate\n\n"
        "Registration Number (GSTIN): 27ABCDE1234F1Z5\n"
        "Legal Name: APEX GLOBAL TECHNOLOGIES PRIVATE LIMITED\n"
        "Trade Name: APEX TECH\n"
        "Status: Active\n"
        "Central Goods and Services Tax Act, 2017\n"
    )
    page.insert_text((50, 60), text, fontsize=12)

    # Draw table
    page.draw_rect(pymupdf.Rect(50, 220, 520, 320))
    page.draw_line(pymupdf.Point(50, 260), pymupdf.Point(520, 260))
    page.draw_line(pymupdf.Point(260, 220), pymupdf.Point(260, 320))
    page.insert_text((60, 245), "Principal Place of Business", fontsize=10)
    page.insert_text((270, 245), "Registered Address", fontsize=10)
    page.insert_text((60, 290), "Sector 5, Salt Lake", fontsize=10)
    page.insert_text((270, 290), "Kolkata, West Bengal", fontsize=10)

    doc.save(str(path))
    doc.close()
    return path


def create_udyam_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic Udyam MSME certificate PDF."""
    path = fixtures_dir / "SYNTHETIC_UDYAM_CERTIFICATE.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "UDYAM REGISTRATION CERTIFICATE\n\n"
        "UDYAM REGISTRATION NUMBER: UDYAM-MH-01-0098765\n\n"
        "NAME OF ENTERPRISE: RELIABLE NETWORKS PVT LTD\n"
        "TYPE OF ENTERPRISE: SMALL ENTERPRISE\n"
        "MAJOR ACTIVITY: SERVICES\n"
        "MINISTRY OF MICRO, SMALL AND MEDIUM ENTERPRISES\n"
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def create_financial_statement_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic multi-page Financial Statement PDF with a table."""
    path = fixtures_dir / "SYNTHETIC_FINANCIAL_STATEMENT.pdf"
    doc = pymupdf.open()

    # Page 1: Auditor's Report
    page1 = doc.new_page(width=595, height=842)
    p1_text = (
        "INDEPENDENT AUDITOR'S REPORT\n\n"
        "To the Members of Apex Global Technologies Private Limited\n\n"
        "Report on the Audit of the Financial Statements\n"
        "FY: 2024-25\n"
        "UDIN: 24123456AAAAAA1234\n"
        "Annual Turnover: INR 45,00,00,000\n"
        "Net Profit: INR 5,20,00,000\n"
    )
    page1.insert_text((50, 80), p1_text, fontsize=12)

    # Page 2: Balance Sheet with table
    page2 = doc.new_page(width=595, height=842)
    p2_text = "Balance Sheet as at 31st March 2025\n(All amounts in INR Crores)"
    page2.insert_text((50, 60), p2_text, fontsize=12)

    page2.draw_rect(pymupdf.Rect(50, 120, 520, 240))
    page2.draw_line(pymupdf.Point(50, 160), pymupdf.Point(520, 160))
    page2.draw_line(pymupdf.Point(320, 120), pymupdf.Point(320, 240))
    page2.insert_text((60, 145), "Financial Indicator", fontsize=11)
    page2.insert_text((330, 145), "Amount (INR)", fontsize=11)
    page2.insert_text((60, 195), "Annual Revenue", fontsize=11)
    page2.insert_text((330, 195), "450000000", fontsize=11)

    doc.save(str(path))
    doc.close()
    return path


def create_experience_cert_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic Work Completion / Experience Certificate PDF."""
    path = fixtures_dir / "SYNTHETIC_EXPERIENCE_CERTIFICATE.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "WORK COMPLETION CERTIFICATE\n\n"
        "Issued by: National Thermal Power Corporation Limited (NTPC)\n\n"
        "This is to certify that M/s Apex Global Technologies Private Limited has satisfactorily completed\n"
        "execution of work for 'Enterprise Cloud Network Setup'.\n\n"
        "Contract Value: Rs. 1,20,00,000\n"
        "Date of Completion: 15-Jan-2024\n"
        "Work Order No: NTPC/PO/2022/450\n"
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def create_oem_authorization_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic OEM Authorization / MAF PDF."""
    path = fixtures_dir / "SYNTHETIC_OEM_AUTHORIZATION.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "MANUFACTURER'S AUTHORIZATION FORM (MAF)\n\n"
        "Dated: 20-08-2026\n\n"
        "We, Cisco Systems India Pvt Ltd, who are official manufacturer of 'Networking Equipment',\n"
        "do hereby authorize Apex Global Technologies Private Limited to submit a bid against Tender GEM/2026/B/998877.\n"
        "We confirm warranty support and supply guarantee as an Original Equipment Manufacturer.\n"
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def create_mii_declaration_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic Make in India Declaration PDF."""
    path = fixtures_dir / "SYNTHETIC_MII_DECLARATION.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    text = (
        "MAKE IN INDIA LOCAL CONTENT DECLARATION\n\n"
        "Dated: 10-09-2026\n\n"
        "In terms of Public Procurement (Preference to Make in India) Order,\n"
        "we hereby certify that M/s Apex Global Technologies Private Limited is a Class-I Local Supplier.\n\n"
        "Percentage of local content: 72.5%\n"
        "Country of Origin: India\n"
        "Location of value addition: Pune, Maharashtra\n"
    )
    page.insert_text((50, 80), text, fontsize=12)
    doc.save(str(path))
    doc.close()
    return path


def create_tender_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic multi-page GeM Tender PDF with a schedule table."""
    path = fixtures_dir / "SYNTHETIC_GEM_TENDER.pdf"
    doc = pymupdf.open()

    # Page 1: Tender Overview
    page1 = doc.new_page(width=595, height=842)
    p1_text = (
        "GeM Bid Document\n\n"
        "Bid Number: GEM/2026/B/887766\n"
        "Ministry/State Name: Ministry of Power\n"
        "Department: Central Power Research Institute\n"
        "Notice Inviting Tender for Procurement of Enterprise Core Switches\n"
        "Bid End Date / Time: 25-09-2026 15:00:00\n"
        "Estimated Bid Value: INR 75,00,000\n"
    )
    page1.insert_text((50, 80), p1_text, fontsize=12)

    # Page 2: Schedule Table
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 60), "Schedule of Requirements", fontsize=12)
    page2.draw_rect(pymupdf.Rect(50, 100, 520, 220))
    page2.draw_line(pymupdf.Point(50, 140), pymupdf.Point(520, 140))
    page2.draw_line(pymupdf.Point(280, 100), pymupdf.Point(280, 220))
    page2.insert_text((60, 125), "Item Specification", fontsize=10)
    page2.insert_text((290, 125), "Quantity", fontsize=10)
    page2.insert_text((60, 175), "48-Port Managed Switch", fontsize=10)
    page2.insert_text((290, 175), "10 Units", fontsize=10)

    doc.save(str(path))
    doc.close()
    return path


def create_scanned_pdf_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic scanned PDF (pure raster image, no digital text)."""
    path = fixtures_dir / "SYNTHETIC_SCANNED_DOC.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    img = np.ones((1200, 900, 3), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "Government of India Registration Certificate",
        (80, 160),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Registration Number (GSTIN): 27ABCDE1234F1Z5",
        (80, 240),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Legal Name: APEX GLOBAL TECHNOLOGIES PRIVATE LIMITED",
        (80, 310),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Central Goods and Services Tax Act, 2017",
        (80, 380),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    _, buffer = cv2.imencode(".png", img)
    page.insert_image(pymupdf.Rect(50, 50, 545, 792), stream=buffer.tobytes())

    doc.save(str(path))
    doc.close()
    return path


def create_poor_quality_scan_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic low-contrast, faded scan PDF."""
    path = fixtures_dir / "SYNTHETIC_POOR_QUALITY_SCAN.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    # Low contrast scan: light gray background (210) and dark gray text (40)
    img = np.ones((1200, 900, 3), dtype=np.uint8) * 210
    cv2.putText(
        img,
        "INCOME TAX DEPARTMENT",
        (80, 180),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (40, 40, 40),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Permanent Account Number Card",
        (80, 260),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (40, 40, 40),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "ABCDE1234F",
        (80, 340),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (40, 40, 40),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "Name: SURESH MENON",
        (80, 420),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (40, 40, 40),
        2,
        cv2.LINE_AA,
    )

    _, buffer = cv2.imencode(".png", img)
    page.insert_image(page.rect, stream=buffer.tobytes())

    doc.save(str(path))
    doc.close()
    return path


def create_rotated_page_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic rotated/skewed page scan."""
    path = fixtures_dir / "SYNTHETIC_ROTATED_SCAN.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    img = np.ones((1200, 900, 3), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "UDYAM REGISTRATION CERTIFICATE",
        (80, 200),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "UDYAM REGISTRATION NUMBER: UDYAM-MH-01-0098765",
        (80, 280),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        img,
        "MINISTRY OF MICRO, SMALL AND MEDIUM ENTERPRISES",
        (80, 360),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 0),
        2,
        cv2.LINE_AA,
    )
    # Rotate by 8.5 degrees
    center = (450, 600)
    rot_mat = cv2.getRotationMatrix2D(center, 8.5, 1.0)
    skewed = cv2.warpAffine(img, rot_mat, (900, 1200), borderValue=(255, 255, 255))

    _, buffer = cv2.imencode(".png", skewed)
    page.insert_image(pymupdf.Rect(50, 50, 545, 792), stream=buffer.tobytes())

    doc.save(str(path))
    doc.close()
    return path


def create_hybrid_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic PDF containing both native digital text and an image."""
    path = fixtures_dir / "SYNTHETIC_HYBRID_DOC.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    text = (
        "MAKE IN INDIA DECLARATION\n"
        "Class-I Local Supplier Certification\n"
        "Percentage of local content: 68.0%\n"
        "Country of Origin: India\n"
    )
    page.insert_text((50, 60), text, fontsize=12)

    # Insert an illustrative logo/stamp
    logo = np.zeros((150, 150, 3), dtype=np.uint8)
    cv2.circle(logo, (75, 75), 60, (0, 120, 255), -1)
    _, buffer = cv2.imencode(".png", logo)
    page.insert_image(pymupdf.Rect(50, 200, 200, 350), stream=buffer.tobytes())

    doc.save(str(path))
    doc.close()
    return path


def create_invalid_file_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic invalid binary file."""
    path = fixtures_dir / "SYNTHETIC_INVALID_FILE.exe"
    with open(path, "wb") as f:
        f.write(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00")
    return path


def create_empty_file_fixture(fixtures_dir: Path) -> Path:
    """Creates a synthetic 0-byte empty file."""
    path = fixtures_dir / "SYNTHETIC_EMPTY_DOC.pdf"
    with open(path, "wb") as f:
        pass
    return path


def run_validation() -> List[Dict[str, Any]]:
    """Runs end-to-end validation across all document categories and edge cases."""
    with tempfile.TemporaryDirectory(prefix="sih_val_") as tmp_dir:
        fixtures_dir = Path(tmp_dir)

        test_cases = [
            ("PAN", create_pan_fixture(fixtures_dir)),
            ("GST", create_gst_fixture(fixtures_dir)),
            ("UDYAM", create_udyam_fixture(fixtures_dir)),
            ("FINANCIAL_STATEMENT", create_financial_statement_fixture(fixtures_dir)),
            ("EXPERIENCE_CERTIFICATE", create_experience_cert_fixture(fixtures_dir)),
            ("OEM_AUTHORIZATION", create_oem_authorization_fixture(fixtures_dir)),
            ("MII_DECLARATION", create_mii_declaration_fixture(fixtures_dir)),
            ("TENDER", create_tender_fixture(fixtures_dir)),
            ("GST", create_scanned_pdf_fixture(fixtures_dir)),
            ("PAN", create_poor_quality_scan_fixture(fixtures_dir)),
            ("UDYAM", create_rotated_page_fixture(fixtures_dir)),
            ("MII_DECLARATION", create_hybrid_fixture(fixtures_dir)),
            ("UNKNOWN", create_invalid_file_fixture(fixtures_dir)),
            ("UNKNOWN", create_empty_file_fixture(fixtures_dir)),
        ]

        report_entries: List[Dict[str, Any]] = []

        logger.info(f"Beginning validation against {len(test_cases)} synthetic test fixtures...")

        for expected_type, fixture_path in test_cases:
            filename = fixture_path.name
            logger.info(f"Processing '{filename}' (Expected: {expected_type})...")

            # Execute pipeline
            result = process_document(fixture_path, filename=filename)

            # Determine fields extracted
            fields_extracted = [k for k, v in result.data.items() if v is not None]

            entry = {
                "filename": filename,
                "expected_type": expected_type,
                "detected_type": result.document_type,
                "classification_confidence": result.classification_confidence,
                "ocr_used": result.extraction.ocr_used,
                "pages": result.pages,
                "tables_detected": len(result.tables),
                "fields_extracted": fields_extracted,
                "processing_status": result.processing.status,
            }
            report_entries.append(entry)

        # Save test report
        report_path = doc_engine_root / "phase07_validation_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_entries, f, indent=2)

        logger.info(f"Validation complete! Report generated at: {report_path}")
        return report_entries


if __name__ == "__main__":
    entries = run_validation()
    print(json.dumps(entries, indent=2))
