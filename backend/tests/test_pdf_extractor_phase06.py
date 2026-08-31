import io
import fitz  # PyMuPDF
import pytest

from app.schemas.processing import ExtractionResult, PageExtractionResult
from app.services.document_processor import DocumentProcessor, document_processor
from app.services.pdf_extractor import PDFExtractor, pdf_extractor


def create_text_pdf(pages_text: list[str]) -> bytes:
    """Helper to generate an in-memory multi-page PDF with real embedded text using PyMuPDF."""
    doc = fitz.open()
    for text in pages_text:
        page = doc.new_page()
        # Insert text block at coordinate (50, 72)
        page.insert_text(fitz.Point(50, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_image_only_pdf() -> bytes:
    """Helper to generate a PDF page containing only an image and no text."""
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    # Create a simple 10x10 pixmap and insert it
    pix = fitz.Pixmap(fitz.csRGB, (0, 0, 10, 10), False)
    pix.set_rect(pix.irect, (255, 0, 0))  # red box
    page.insert_image(fitz.Rect(50, 50, 200, 200), pixmap=pix)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# 1. Multi-page Text-based PDF Extraction

def test_extract_text_pdf_multipage():
    """Test extracting structured text from a multi-page PDF."""
    p1 = "Tender Number: GEM/2026/B/890123\nProcurement Scope: Server Infrastructure for Data Center."
    p2 = "Eligibility Criteria: Minimum 3 years prior experience in Government Cloud deployments."
    p3 = "Financial Terms: EMD of INR 50,000 required. Turnover certificate mandatory."

    pdf_bytes = create_text_pdf([p1, p2, p3])
    result: ExtractionResult = pdf_extractor.extract(pdf_bytes, filename="tender_rfp.pdf")

    assert result.is_corrupted is False
    assert result.error_message is None
    assert result.page_count == 3
    assert result.requires_ocr is False

    # Page 1 validation
    assert len(result.pages) == 3
    assert result.pages[0].page_number == 1
    assert "GEM/2026/B/890123" in result.pages[0].text
    assert result.pages[0].has_text is True
    assert result.pages[0].requires_ocr is False

    # Page 2 validation
    assert result.pages[1].page_number == 2
    assert "Eligibility Criteria" in result.pages[1].text

    # Page 3 validation
    assert result.pages[2].page_number == 3
    assert "Financial Terms" in result.pages[2].text

    # Aggregated full text
    assert "GEM/2026/B/890123" in result.text
    assert "Financial Terms" in result.text


# 2. Scanned / Image-only PDF Detection

def test_detect_image_only_pdf_requires_ocr():
    """Test that a PDF with only images and no embedded text is detected as requiring OCR."""
    pdf_bytes = create_image_only_pdf()
    result: ExtractionResult = pdf_extractor.extract(pdf_bytes, filename="scanned_cert.pdf")

    assert result.is_corrupted is False
    assert result.page_count == 1
    assert result.requires_ocr is True
    assert result.pages[0].has_text is False
    assert result.pages[0].requires_ocr is True
    assert result.pages[0].images_count >= 1


# 3. Corrupt & Malformed PDF Handling

def test_extract_empty_pdf_bytes_handled_safely():
    """Test passing empty byte stream returns corrupt status without crashing."""
    result = pdf_extractor.extract(b"", filename="empty.pdf")
    assert result.is_corrupted is True
    assert result.page_count == 0
    assert "empty" in result.error_message.lower()


def test_extract_corrupt_pdf_handled_safely():
    """Test passing garbage bytes returns corrupt result without raising an uncaught exception."""
    garbage = b"NOT_A_VALID_PDF_HEADER_12345_CORRUPT_BYTES"
    result = pdf_extractor.extract(garbage, filename="corrupt.pdf")
    assert result.is_corrupted is True
    assert result.page_count == 0
    assert result.error_message is not None


# 4. DocumentProcessor Unified Routing

def test_document_processor_routes_pdf():
    """Test DocumentProcessor successfully handles PDF text extraction."""
    pdf_bytes = create_text_pdf(["Company Name: ABC Infotech\nGSTIN: 27AAAAA0000A1Z5"])
    result = document_processor.process_document(pdf_bytes, mime_type="application/pdf", filename="gst.pdf")

    assert result.is_corrupted is False
    assert result.requires_ocr is False
    assert "27AAAAA0000A1Z5" in result.text


def test_document_processor_routes_image_to_ocr():
    """Test DocumentProcessor flags image documents (JPEG, PNG) as requiring OCR."""
    # JPEG magic bytes
    fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\xff\xd9"
    result_jpeg = document_processor.process_document(fake_jpeg, mime_type="image/jpeg", filename="pan.jpg")

    assert result_jpeg.is_corrupted is False
    assert result_jpeg.requires_ocr is True
    assert result_jpeg.page_count == 1

    # PNG magic bytes
    fake_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    result_png = document_processor.process_document(fake_png, mime_type="image/png", filename="sign.png")

    assert result_png.is_corrupted is False
    assert result_png.requires_ocr is True


def test_document_processor_unsupported_format():
    """Test DocumentProcessor flags unsupported format cleanly."""
    unknown_binary = b"\x00\x01\x02\x03\x04\x05"
    result = document_processor.process_document(unknown_binary, mime_type="application/octet-stream", filename="blob.bin")
    assert result.is_corrupted is True
    assert "unsupported" in result.error_message.lower()
