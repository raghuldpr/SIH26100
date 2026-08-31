import io
from pathlib import Path
import numpy as np
import cv2
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.document_service import DocumentService, process_document

client = TestClient(app)


@pytest.fixture
def sample_gst_pdf(tmp_path: Path) -> Path:
    """Generates a valid digital PDF with GST certificate contents and a simple table."""
    pdf_path = tmp_path / "GST_Certificate.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4

    text = """
    Government of India
    Form GST REG-06
    Registration Certificate
    Registration Number (GSTIN): 27ABCDE1234F1Z5
    Legal Name: ACME GLOBAL INFOTECH PRIVATE LIMITED
    Trade Name: ACME INFOTECH
    Status: Active
    Central Goods and Services Tax Act, 2017
    """
    page.insert_text((50, 80), text, fontsize=12)

    # Draw simple table lines
    page.draw_rect(pymupdf.Rect(50, 250, 500, 350))
    page.draw_line(pymupdf.Point(50, 290), pymupdf.Point(500, 290))
    page.draw_line(pymupdf.Point(250, 250), pymupdf.Point(250, 350))
    page.insert_text((60, 275), "Particulars", fontsize=11)
    page.insert_text((260, 275), "Details", fontsize=11)
    page.insert_text((60, 320), "Jurisdiction", fontsize=11)
    page.insert_text((260, 320), "Ward 105, Mumbai", fontsize=11)

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.fixture
def sample_image_file(tmp_path: Path) -> Path:
    """Generates a valid PNG image for image processing."""
    img_path = tmp_path / "receipt.png"
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "GSTIN: 27ABCDE1234F1Z5",
        (50, 150),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (0, 0, 0),
        2,
    )
    cv2.putText(
        img,
        "Registration Certificate",
        (50, 220),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2,
    )
    cv2.imwrite(str(img_path), img)
    return img_path


@pytest.fixture
def sample_scanned_pdf(tmp_path: Path) -> Path:
    """Generates a PDF containing only an image (no native text), simulating a scanned PDF."""
    pdf_path = tmp_path / "scanned_doc.pdf"
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    # Insert an image into the page
    img = np.ones((600, 400, 3), dtype=np.uint8) * 255
    cv2.putText(
        img,
        "Permanent Account Number",
        (30, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 0, 0),
        2,
    )
    _, buffer = cv2.imencode(".png", img)
    page.insert_image(pymupdf.Rect(50, 50, 450, 650), stream=buffer.tobytes())

    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


# =============================================================================
# Pipeline Unit Tests
# =============================================================================

def test_process_native_pdf_document(sample_gst_pdf: Path):
    """Verify end-to-end processing of native digital PDF."""
    result = process_document(sample_gst_pdf, filename="GST_Certificate.pdf")

    assert result.document_id is not None
    assert result.filename == "GST_Certificate.pdf"
    assert result.document_type == "GST"
    assert result.classification_confidence >= 0.85
    assert result.pages == 1

    # Native extraction checks
    assert result.extraction.method == "native_pdf"
    assert result.extraction.ocr_used is False
    assert "27ABCDE1234F1Z5" in result.extraction.text
    assert len(result.extraction.pages) == 1
    assert result.extraction.pages[0].page_number == 1

    # Structured data checks
    assert result.data["gstin"] == "27ABCDE1234F1Z5"
    assert result.data["legal_name"] == "ACME GLOBAL INFOTECH PRIVATE LIMITED"
    assert result.data["company_name"] == "ACME INFOTECH"
    assert result.data["status"] == "Active"

    # Processing metadata
    assert result.processing.status == "completed"
    assert result.processing.processing_time_ms >= 0


def test_process_image_document(sample_image_file: Path):
    """Verify end-to-end processing of image document via OCR pipeline."""
    result = process_document(sample_image_file, filename="receipt.png")

    assert result.document_id is not None
    assert result.filename == "receipt.png"
    assert result.pages == 1

    # Image triggers OCR
    assert result.extraction.method == "ocr"
    assert result.extraction.ocr_used is True
    assert result.processing.status == "completed"
    assert result.processing.processing_time_ms >= 0


def test_process_scanned_pdf_triggers_ocr(sample_scanned_pdf: Path):
    """Verify that a scanned PDF without digital text triggers page rasterization and OCR."""
    result = process_document(sample_scanned_pdf, filename="scanned_doc.pdf")

    assert result.document_id is not None
    assert result.filename == "scanned_doc.pdf"
    assert result.pages == 1

    # Scanned PDF without text triggers OCR fallback
    assert result.extraction.method == "ocr"
    assert result.extraction.ocr_used is True
    assert result.processing.status == "completed"


def test_process_non_existent_file_clean_failure():
    """Verify that a missing file returns a clean failure object without crashing."""
    result = process_document("non_existent_file_xyz.pdf")

    assert result.document_id is not None
    assert result.document_type == "UNKNOWN"
    assert result.pages == 0
    assert result.processing.status == "failed"
    assert result.processing.error_code == "FileNotFoundError"
    assert "not found" in result.processing.message.lower()


# =============================================================================
# API Endpoint Integration Tests
# =============================================================================

def test_api_process_document_endpoint_success(sample_gst_pdf: Path):
    """Verify POST /api/v1/documents/process successfully processes uploaded PDF."""
    with open(sample_gst_pdf, "rb") as f:
        response = client.post(
            "/api/v1/documents/process",
            files={"file": ("GST_Certificate.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["filename"] == "GST_Certificate.pdf"
    assert data["document_type"] == "GST"
    assert data["classification_confidence"] >= 0.85
    assert data["pages"] == 1
    assert data["extraction"]["method"] == "native_pdf"
    assert data["extraction"]["ocr_used"] is False
    assert data["data"]["gstin"] == "27ABCDE1234F1Z5"
    assert data["processing"]["status"] == "completed"
    assert data["processing"]["processing_time_ms"] >= 0


def test_api_process_document_unsupported_extension():
    """Verify POST /api/v1/documents/process rejects unsupported file extensions."""
    response = client.post(
        "/api/v1/documents/process",
        files={"file": ("script.exe", b"MZbinaryexecutable", "application/octet-stream")},
    )
    assert response.status_code == 415
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNSUPPORTED_DOCUMENT_TYPE"


def test_api_process_document_empty_file():
    """Verify POST /api/v1/documents/process rejects empty 0-byte file."""
    response = client.post(
        "/api/v1/documents/process",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMPTY_PDF"
