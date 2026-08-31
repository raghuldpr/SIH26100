import io
import cv2
import fitz  # PyMuPDF
import numpy as np
import pytest

from app.schemas.ocr import OCRDocumentResult, OCRPageResult, OCRTextBox
from app.services.image_preprocessor import ImagePreprocessor, image_preprocessor
from app.services.ocr_pipeline import OCRPipeline, PaddleOCREngine, ocr_pipeline


def generate_synthetic_document_image(text_lines: list[str], rotate_angle: float = 0.0) -> bytes:
    """Generates a synthetic document image (PNG) containing rendered text lines."""
    # Create white canvas 1000x800
    img = np.full((1000, 800, 3), 255, dtype=np.uint8)

    # Draw text lines
    y_pos = 100
    for line in text_lines:
        cv2.putText(
            img,
            line,
            (60, y_pos),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            2,
            cv2.LINE_AA,
        )
        y_pos += 60

    # Optional rotation
    if rotate_angle != 0.0:
        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        rot_mat = cv2.getRotationMatrix2D(center, rotate_angle, 1.0)
        img = cv2.warpAffine(img, rot_mat, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    success, buffer = cv2.imencode(".png", img)
    assert success
    return buffer.tobytes()


def generate_scanned_pdf_with_images(pages_text: list[list[str]], include_blank_page: bool = False) -> bytes:
    """Generates a PDF containing rendered image pages to simulate scanned documents."""
    doc = fitz.open()

    for lines in pages_text:
        img_bytes = generate_synthetic_document_image(lines)
        page = doc.new_page(width=600, height=800)
        page.insert_image(fitz.Rect(0, 0, 600, 800), stream=img_bytes)

    if include_blank_page:
        # Insert a pure white blank page
        blank_img = np.full((800, 600, 3), 255, dtype=np.uint8)
        _, buf = cv2.imencode(".png", blank_img)
        page_blank = doc.new_page(width=600, height=800)
        page_blank.insert_image(fitz.Rect(0, 0, 600, 800), stream=buf.tobytes())

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# 1. ImagePreprocessor Tests

def test_image_preprocessor_resolution_normalization():
    """Test resizing very large and very small images."""
    preprocessor = ImagePreprocessor(max_dimension=2000, min_dimension=800)

    # Oversized image 4000x3000
    large_img = np.full((4000, 3000, 3), 200, dtype=np.uint8)
    norm_large = preprocessor.normalize_resolution(large_img)
    assert max(norm_large.shape[:2]) == 2000

    # Undersized image 300x400
    small_img = np.full((300, 400, 3), 200, dtype=np.uint8)
    norm_small = preprocessor.normalize_resolution(small_img)
    assert max(norm_small.shape[:2]) == 800


def test_image_preprocessor_blank_detection():
    """Test blank page detection on pure white and textured images."""
    preprocessor = ImagePreprocessor()

    # Pure white image
    blank_white = np.full((800, 600, 3), 255, dtype=np.uint8)
    assert preprocessor.is_blank_page(blank_white) is True

    # Image with drawn text
    text_img_bytes = generate_synthetic_document_image(["PAN Number: ABCDE1234F", "Name: Rajesh Kumar"])
    text_img = preprocessor.bytes_to_cv2(text_img_bytes)
    assert preprocessor.is_blank_page(text_img) is False


def test_image_preprocessor_deskew_and_clahe():
    """Test preprocessing applies deskew and contrast enhancement without errors."""
    preprocessor = ImagePreprocessor(enable_clahe=True, enable_deskew=True)
    img_bytes = generate_synthetic_document_image(
        ["Goods & Services Tax Registration Certificate", "State: Maharashtra"],
        rotate_angle=5.0,
    )
    img = preprocessor.bytes_to_cv2(img_bytes)
    assert img is not None

    preprocessed, rot_angle, is_blank = preprocessor.preprocess(img)
    assert is_blank is False
    assert len(preprocessed.shape) == 2  # Grayscale
    assert isinstance(rot_angle, float)


# 2. OCRPipeline Single Image Processing

def test_ocr_pipeline_process_image_success():
    """Test OCR processing on a single certificate image."""
    img_bytes = generate_synthetic_document_image([
        "Government of India - Income Tax Department",
        "Permanent Account Number: ABCDE1234F",
        "Name: TechServe Solutions Pvt Ltd",
    ])

    result: OCRDocumentResult = ocr_pipeline.process_image(img_bytes, filename="pan_scan.png")

    assert result.is_success is True
    assert result.page_count == 1
    assert len(result.pages) == 1
    assert result.execution_time_ms > 0

    page_res: OCRPageResult = result.pages[0]
    assert page_res.page_number == 1
    assert page_res.is_blank is False
    assert len(page_res.boxes) > 0
    assert page_res.avg_confidence >= 0.80


def test_ocr_pipeline_process_blank_image():
    """Test OCR processing on a blank image correctly sets is_blank=True."""
    blank_bytes = generate_synthetic_document_image([])  # 0 text
    result: OCRDocumentResult = ocr_pipeline.process_image(blank_bytes, filename="blank.png")

    assert result.is_success is True
    assert result.page_count == 1
    assert result.pages[0].is_blank is True
    assert result.pages[0].text == ""
    assert len(result.pages[0].boxes) == 0


# 3. OCRPipeline Scanned PDF Processing

def test_ocr_pipeline_process_scanned_multipage_pdf():
    """Test multi-page scanned PDF rendering and page-level OCR extraction."""
    p1 = ["Tender Reference: GEM/2026/T/9988", "Procurement of Medical Grade Oxygen Cylinders"]
    p2 = ["Technical Specifications: Type D Capacity 46.7 Liters", "Working Pressure: 150 kgf/cm2"]

    pdf_bytes = generate_scanned_pdf_with_images([p1, p2], include_blank_page=True)

    result: OCRDocumentResult = ocr_pipeline.process_scanned_pdf(pdf_bytes, dpi=150, filename="scanned_spec.pdf")

    assert result.is_success is True
    assert result.page_count == 3
    assert len(result.pages) == 3

    # Page 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].is_blank is False
    assert len(result.pages[0].boxes) > 0

    # Page 2
    assert result.pages[1].page_number == 2
    assert result.pages[1].is_blank is False

    # Page 3 (Blank)
    assert result.pages[2].page_number == 3
    assert result.pages[2].is_blank is True
    assert result.pages[2].text == ""


# 4. Error and Edge Case Handling

def test_ocr_pipeline_empty_bytes_handled_safely():
    """Test passing empty byte stream returns clean error without crashing."""
    result_img = ocr_pipeline.process_image(b"")
    assert result_img.is_success is False
    assert "empty" in result_img.error_message.lower()

    result_pdf = ocr_pipeline.process_scanned_pdf(b"")
    assert result_pdf.is_success is False
    assert "empty" in result_pdf.error_message.lower()


def test_ocr_pipeline_corrupt_pdf_handled_safely():
    """Test passing corrupt PDF bytes returns structured error without exception."""
    corrupt_bytes = b"CORRUPTED_PDF_NOT_HEADER_STREAM_998877"
    result = ocr_pipeline.process_scanned_pdf(corrupt_bytes, filename="corrupt.pdf")

    assert result.is_success is False
    assert result.error_message is not None
    assert result.page_count == 0


def test_ocr_pipeline_unified_router():
    """Test process_document routes PDF and image formats appropriately."""
    img_bytes = generate_synthetic_document_image(["UDYAM-MH-01-0012345"])
    res_img = ocr_pipeline.process_document(img_bytes, mime_type="image/png", filename="udyam.png")
    assert res_img.is_success is True
    assert res_img.page_count == 1

    pdf_bytes = generate_scanned_pdf_with_images([["Turnover Certificate: FY 2024-25"]])
    res_pdf = ocr_pipeline.process_document(pdf_bytes, mime_type="application/pdf", filename="turnover.pdf")
    assert res_pdf.is_success is True
    assert res_pdf.page_count == 1
