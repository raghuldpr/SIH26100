import hashlib
import io
from pathlib import Path
import pytest
import pymupdf
from fastapi.testclient import TestClient
from starlette import status

from app.core.exceptions import (
    CorruptedPDFException,
    DocumentNotFoundException,
    EmptyPDFException,
    HTTP_422_STATUS,
    PasswordProtectedPDFException,
    UnsupportedDocumentException,
)
from app.extractors.pdf_extractor import PDFExtractor, extract_pdf_text
from app.main import app

client = TestClient(app)


@pytest.fixture
def create_sample_pdf(tmp_path):
    """Factory fixture for creating in-memory and disk test PDF documents."""

    def _create(pages_text: list[str], password: str = None) -> Path:
        doc = pymupdf.open()
        for text in pages_text:
            page = doc.new_page(width=595, height=842)  # A4 standard
            if text:
                page.insert_text((50, 72), text, fontsize=12)

        pdf_path = tmp_path / f"test_doc_{len(pages_text)}p.pdf"
        if password:
            doc.save(
                str(pdf_path),
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                user_pw=password,
                owner_pw=password + "_owner",
            )
        else:
            doc.save(str(pdf_path))
        doc.close()
        return pdf_path

    return _create


def test_extract_valid_multipage_pdf(create_sample_pdf):
    """Verify extraction preserves page numbers, text, character counts, and meaningful text flag."""
    page_1_content = "GEM PROCUREMENT PORTAL\nTender ID: GEM/2026/B/100500\nDepartment of Technology"
    page_2_content = "TECHNICAL SPECIFICATIONS\nItem: High Performance Computing Node\nQuantity: 50"

    pdf_path = create_sample_pdf([page_1_content, page_2_content])

    result = PDFExtractor.extract(pdf_path)

    assert result.extraction_method == "native_pdf"
    assert result.total_pages == 2
    assert len(result.pages) == 2
    assert result.has_meaningful_text is True

    # Page 1 checks
    assert result.pages[0].page_number == 1
    assert "GEM PROCUREMENT PORTAL" in result.pages[0].text
    assert result.pages[0].character_count == len(result.pages[0].text)

    # Page 2 checks
    assert result.pages[1].page_number == 2
    assert "TECHNICAL SPECIFICATIONS" in result.pages[1].text
    assert result.pages[1].character_count == len(result.pages[1].text)

    assert result.total_characters == result.pages[0].character_count + result.pages[1].character_count


def test_extract_pdf_with_empty_page(create_sample_pdf):
    """Verify handling of blank pages without failing."""
    pdf_path = create_sample_pdf(["Valid first page content with sufficient characters", ""])

    result = PDFExtractor.extract(pdf_path)

    assert result.total_pages == 2
    assert result.pages[0].page_number == 1
    assert result.pages[0].character_count > 0
    assert result.pages[1].page_number == 2
    assert result.pages[1].text.strip() == ""
    assert result.pages[1].character_count == 0


def test_extract_no_meaningful_text(create_sample_pdf):
    """Verify has_meaningful_text is False when content is only punctuation or whitespace."""
    pdf_path = create_sample_pdf(["...", "   \n\n  "])

    result = PDFExtractor.extract(pdf_path)

    assert result.total_pages == 2
    assert result.has_meaningful_text is False


def test_extract_convenience_helper(create_sample_pdf):
    """Verify the extract_pdf_text helper function functions identically."""
    pdf_path = create_sample_pdf(["Convenience function testing with ample text length."])
    result = extract_pdf_text(pdf_path)
    assert result.total_pages == 1
    assert result.has_meaningful_text is True


def test_file_immutability(create_sample_pdf):
    """Verify source PDF file is never modified or altered during extraction."""
    pdf_path = create_sample_pdf(["Immutability test content to ensure read-only processing."])

    # Record hash and size before extraction
    with open(pdf_path, "rb") as f:
        original_hash = hashlib.sha256(f.read()).hexdigest()
    original_size = pdf_path.stat().st_size

    # Run extraction
    _ = PDFExtractor.extract(pdf_path)

    # Verify post-extraction hash and size
    with open(pdf_path, "rb") as f:
        post_hash = hashlib.sha256(f.read()).hexdigest()
    post_size = pdf_path.stat().st_size

    assert original_hash == post_hash
    assert original_size == post_size


def test_extract_empty_file_fails(tmp_path):
    """Verify 0-byte file raises EmptyPDFException."""
    empty_file = tmp_path / "empty_doc.pdf"
    empty_file.write_bytes(b"")

    with pytest.raises(EmptyPDFException) as exc_info:
        PDFExtractor.extract(empty_file)

    assert exc_info.value.code == "EMPTY_PDF"


def test_extract_non_existent_file(tmp_path):
    """Verify non-existent file path raises DocumentNotFoundException."""
    missing_file = tmp_path / "does_not_exist.pdf"

    with pytest.raises(DocumentNotFoundException) as exc_info:
        PDFExtractor.extract(missing_file)

    assert exc_info.value.code == "DOCUMENT_NOT_FOUND"


def test_extract_fake_pdf_header_missing(tmp_path):
    """Verify non-PDF file disguised as .pdf raises UnsupportedDocumentException."""
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_text("This is simply a plain text file pretending to be a PDF.")

    with pytest.raises(UnsupportedDocumentException) as exc_info:
        PDFExtractor.extract(fake_pdf)

    assert exc_info.value.code == "UNSUPPORTED_DOCUMENT_TYPE"


def test_extract_corrupted_pdf_structure(tmp_path):
    """Verify corrupted PDF bytes with %PDF- header raises CorruptedPDFException."""
    corrupted_pdf = tmp_path / "corrupt.pdf"
    # Starts with %PDF- but contains invalid junk data
    corrupted_pdf.write_bytes(b"%PDF-1.7\nCorrupted content completely invalid binary string 1234567890")

    with pytest.raises(CorruptedPDFException) as exc_info:
        PDFExtractor.extract(corrupted_pdf)

    assert exc_info.value.code == "CORRUPTED_PDF"


def test_extract_encrypted_password_protected_pdf(create_sample_pdf):
    """Verify password protected PDF raises PasswordProtectedPDFException."""
    encrypted_path = create_sample_pdf(
        ["Secret and confidential government tender data."],
        password="ProtectedPassword999!",
    )

    with pytest.raises(PasswordProtectedPDFException) as exc_info:
        PDFExtractor.extract(encrypted_path)

    assert exc_info.value.code == "PASSWORD_PROTECTED_PDF"


# =========================================================================
# API Endpoint Tests: POST /api/v1/extract/pdf
# =========================================================================

def test_api_extract_pdf_success(create_sample_pdf):
    """Verify POST /api/v1/extract/pdf successfully extracts and returns expected schema."""
    pdf_path = create_sample_pdf([
        "Page 1: BID COMPLIANCE FORM\nVendor: Acme Systems Pvt Ltd",
        "Page 2: FINANCIAL TURNOVER\nAudited revenue for FY 2024-25",
    ])

    with open(pdf_path, "rb") as f:
        files = {"file": (pdf_path.name, f, "application/pdf")}
        response = client.post("/api/v1/extract/pdf", files=files)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["extraction_method"] == "native_pdf"
    assert data["total_pages"] == 2
    assert data["has_meaningful_text"] is True
    assert len(data["pages"]) == 2
    assert data["pages"][0]["page_number"] == 1
    assert "BID COMPLIANCE FORM" in data["pages"][0]["text"]
    assert data["pages"][1]["page_number"] == 2
    assert "FINANCIAL TURNOVER" in data["pages"][1]["text"]


def test_api_extract_pdf_invalid_extension():
    """Verify uploading a non-.pdf file returns 415 Unsupported Media Type."""
    fake_file = io.BytesIO(b"dummy text")
    files = {"file": ("document.docx", fake_file, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}

    response = client.post("/api/v1/extract/pdf", files=files)
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNSUPPORTED_DOCUMENT_TYPE"


def test_api_extract_pdf_disguised_file(tmp_path):
    """Verify uploading a non-PDF file with a .pdf extension returns 415."""
    disguised = io.BytesIO(b"Hello world, I am not a real PDF file at all.")
    files = {"file": ("disguised.pdf", disguised, "application/pdf")}

    response = client.post("/api/v1/extract/pdf", files=files)
    assert response.status_code == status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "UNSUPPORTED_DOCUMENT_TYPE"


def test_api_extract_empty_file():
    """Verify uploading an empty 0-byte file returns unprocessable error."""
    empty_file = io.BytesIO(b"")
    files = {"file": ("empty.pdf", empty_file, "application/pdf")}

    response = client.post("/api/v1/extract/pdf", files=files)
    assert response.status_code == HTTP_422_STATUS
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "EMPTY_PDF"
