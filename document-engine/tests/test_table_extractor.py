import hashlib
import io
from pathlib import Path
import pytest
import pymupdf
from fastapi.testclient import TestClient
from starlette import status

from app.core.exceptions import (
    DocumentNotFoundException,
    EmptyPDFException,
    HTTP_422_STATUS,
    UnsupportedDocumentException,
)
from app.extractors.table_extractor import TableExtractor, extract_tables_from_pdf
from app.main import app

client = TestClient(app)


@pytest.fixture
def create_pdf_with_table(tmp_path):
    """Creates a digital PDF with vector grid lines and cell text representing a table."""

    def _create() -> Path:
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)  # A4

        # Draw title text outside table
        page.insert_text((50, 60), "FINANCIAL DISCLOSURE STATEMENT", fontsize=14)

        # Draw a 2x2 table grid with explicit vector lines
        # Row 1 (header): y=100 to y=140
        # Row 2 (data):   y=140 to y=180
        # Col 1: x=50 to x=250
        # Col 2: x=250 to x=450

        # Horizontal lines
        page.draw_line((50, 100), (450, 100), width=1.0)
        page.draw_line((50, 140), (450, 140), width=1.0)
        page.draw_line((50, 180), (450, 180), width=1.0)

        # Vertical lines
        page.draw_line((50, 100), (50, 180), width=1.0)
        page.draw_line((250, 100), (250, 180), width=1.0)
        page.draw_line((450, 100), (450, 180), width=1.0)

        # Cell texts
        page.insert_text((60, 125), "Description", fontsize=11)
        page.insert_text((260, 125), "Amount", fontsize=11)
        page.insert_text((60, 165), "Annual Turnover", fontsize=11)
        page.insert_text((260, 165), "2500000", fontsize=11)

        pdf_path = tmp_path / "table_sample.pdf"
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    return _create


@pytest.fixture
def create_text_only_pdf(tmp_path):
    """Creates a digital PDF with paragraphs of text but no tables."""

    def _create() -> Path:
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        page.insert_text(
            (50, 80),
            "This is a standard text narrative document without any tabular grids.\n"
            "All compliance terms and conditions are documented in plain text sentences.\n"
            "Section 1.1: General terms and guidelines for bidder participation in GeM.",
            fontsize=12,
        )
        pdf_path = tmp_path / "text_only.pdf"
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    return _create


@pytest.fixture
def create_scanned_pdf(tmp_path):
    """Creates a synthetic scanned PDF containing only an embedded image with no digital text."""

    def _create() -> Path:
        import cv2
        import numpy as np

        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)

        # Create a synthetic scan image
        img = np.full((300, 400, 3), 230, dtype=np.uint8)
        _, enc = cv2.imencode(".png", img)

        img_rect = pymupdf.Rect(50, 100, 450, 600)
        page.insert_image(img_rect, stream=enc.tobytes())

        pdf_path = tmp_path / "scanned_doc.pdf"
        doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    return _create


def test_extract_table_from_digital_pdf(create_pdf_with_table):
    """Verify detection, extraction, and row structure from a digital PDF with vector grid lines."""
    pdf_path = create_pdf_with_table()

    result = TableExtractor.extract(pdf_path)

    assert result.extraction_method == "pdfplumber"
    assert result.total_tables >= 1
    assert result.is_scanned_pdf is False
    assert result.requires_ocr is False
    assert 1 in result.pages_with_tables

    tbl = result.tables[0]
    assert tbl.page == 1
    assert tbl.table_index == 0
    assert tbl.num_rows == 2
    assert tbl.num_cols == 2
    assert tbl.rows[0] == ["Description", "Amount"]
    assert tbl.rows[1] == ["Annual Turnover", "2500000"]


def test_normalize_table_and_padding():
    """Verify table normalization handles None values, whitespace, and irregular row lengths."""
    raw_table = [
        ["  Header A  ", "Header B", None],
        ["Row 1 Col 1", "  Row 1 Col 2  "],  # Missing third column
        [None, "Row 2 Col 2", "Row 2 Col 3"],
    ]

    normalized = TableExtractor.normalize_table(raw_table)
    assert normalized is not None
    rows, num_rows, num_cols = normalized

    assert num_rows == 3
    assert num_cols == 3

    assert rows[0] == ["Header A", "Header B", ""]
    assert rows[1] == ["Row 1 Col 1", "Row 1 Col 2", ""]  # Padded
    assert rows[2] == ["", "Row 2 Col 2", "Row 2 Col 3"]


def test_normalize_empty_table():
    """Verify degenerate empty tables return None."""
    assert TableExtractor.normalize_table([]) is None
    assert TableExtractor.normalize_table([[], []]) is None
    assert TableExtractor.normalize_table([[None, "  "], ["", None]]) is None


def test_clean_cell_whitespace_handling():
    """Verify cell cleaner handles newlines, None, and excessive whitespace."""
    assert TableExtractor.clean_cell(None) == ""
    assert TableExtractor.clean_cell("   hello world   ") == "hello world"
    assert TableExtractor.clean_cell("line 1  \n   line 2  ") == "line 1\nline 2"
    assert TableExtractor.clean_cell(12345) == "12345"


def test_pdf_without_tables_returns_empty_list(create_text_only_pdf):
    """Verify documents without tables do not crash and return empty table list."""
    pdf_path = create_text_only_pdf()

    result = TableExtractor.extract(pdf_path)

    assert result.extraction_method == "pdfplumber"
    assert result.total_tables == 0
    assert result.tables == []
    assert result.pages_with_tables == []
    assert result.is_scanned_pdf is False
    assert result.requires_ocr is False


def test_scanned_pdf_flags_ocr_required(create_scanned_pdf):
    """Verify scanned PDFs lacking native digital text are flagged as requiring OCR."""
    pdf_path = create_scanned_pdf()

    result = TableExtractor.extract(pdf_path)

    assert result.extraction_method == "pdfplumber"
    assert result.total_tables == 0
    assert result.tables == []
    assert result.is_scanned_pdf is True
    assert result.requires_ocr is True


def test_convenience_helper(create_pdf_with_table):
    """Verify extract_tables_from_pdf convenience wrapper works identically."""
    pdf_path = create_pdf_with_table()
    result = extract_tables_from_pdf(pdf_path)
    assert result.total_tables >= 1


def test_file_immutability(create_pdf_with_table):
    """Verify source PDF is strictly unmodified during table extraction."""
    pdf_path = create_pdf_with_table()

    with open(pdf_path, "rb") as f:
        hash_before = hashlib.sha256(f.read()).hexdigest()
    size_before = pdf_path.stat().st_size

    _ = TableExtractor.extract(pdf_path)

    with open(pdf_path, "rb") as f:
        hash_after = hashlib.sha256(f.read()).hexdigest()
    size_after = pdf_path.stat().st_size

    assert hash_before == hash_after
    assert size_before == size_after


def test_non_existent_pdf_raises(tmp_path):
    """Verify missing file raises DocumentNotFoundException."""
    missing = tmp_path / "missing.pdf"
    with pytest.raises(DocumentNotFoundException) as exc_info:
        TableExtractor.extract(missing)
    assert exc_info.value.code == "DOCUMENT_NOT_FOUND"


def test_empty_pdf_raises(tmp_path):
    """Verify 0-byte file raises EmptyPDFException."""
    empty = tmp_path / "empty.pdf"
    empty.write_bytes(b"")
    with pytest.raises(EmptyPDFException) as exc_info:
        TableExtractor.extract(empty)
    assert exc_info.value.code == "EMPTY_PDF"


# =========================================================================
# API Endpoint Tests: POST /api/v1/extract/tables
# =========================================================================

def test_api_extract_tables_success(create_pdf_with_table):
    """Verify POST /api/v1/extract/tables returns 200 and matches TableExtractionResult schema."""
    pdf_path = create_pdf_with_table()

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        response = client.post("/api/v1/extract/tables", files=files)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["extraction_method"] == "pdfplumber"
    assert data["total_tables"] >= 1
    assert len(data["tables"]) >= 1
    assert data["tables"][0]["rows"][0] == ["Description", "Amount"]
    assert data["tables"][0]["rows"][1] == ["Annual Turnover", "2500000"]


def test_api_extract_tables_scanned_pdf(create_scanned_pdf):
    """Verify POST /api/v1/extract/tables on scanned document returns requires_ocr: True."""
    pdf_path = create_scanned_pdf()

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        response = client.post("/api/v1/extract/tables", files=files)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["is_scanned_pdf"] is True
    assert data["requires_ocr"] is True
    assert data["total_tables"] == 0
    assert data["tables"] == []


def test_api_extract_tables_invalid_extension():
    """Verify non-.pdf upload is rejected with 415 Unsupported Media Type."""
    fake_file = io.BytesIO(b"not a pdf")
    files = {"file": ("data.csv", fake_file, "text/csv")}

    response = client.post("/api/v1/extract/tables", files=files)
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNSUPPORTED_DOCUMENT_TYPE"


def test_api_extract_tables_empty_file():
    """Verify empty file upload returns unprocessable error."""
    empty_file = io.BytesIO(b"")
    files = {"file": ("empty.pdf", empty_file, "application/pdf")}

    response = client.post("/api/v1/extract/tables", files=files)
    assert response.status_code == HTTP_422_STATUS
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMPTY_PDF"
