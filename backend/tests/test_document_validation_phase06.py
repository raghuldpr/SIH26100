import io
import pytest
from fastapi import UploadFile

from app.core.exceptions import BadRequestException
from app.core.validation import (
    detect_magic_mime_type,
    validate_file_content,
    validate_multiple_upload_files,
    validate_single_upload_file,
)


def generate_valid_pdf(title: str = "Test PDF") -> bytes:
    """Generates a valid PDF byte sequence with header, body, and EOF."""
    return (
        f"%PDF-1.4\n1 0 obj\n<< /Title ({title}) >>\nendobj\n"
        f"xref\n0 2\n0000000000 65535 f \n0000000010 00000 n \n"
        f"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n70\n%%EOF\n"
    ).encode("utf-8")


def generate_valid_jpeg() -> bytes:
    """Generates a valid JPEG byte sequence with SOI, APP0, and EOI."""
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\xff\xd9"


def generate_valid_png() -> bytes:
    """Generates a valid PNG byte sequence with signature and IHDR/IEND chunks."""
    return (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )


# 1. Valid PDF, JPEG, PNG Validation Tests

def test_validate_valid_pdf_content():
    """Verify valid PDF content passes validation and detects application/pdf."""
    pdf_bytes = generate_valid_pdf("GeM Bid Document")
    val_file = validate_file_content(pdf_bytes, filename="technical_bid.pdf")

    assert val_file.mime_type == "application/pdf"
    assert val_file.extension == ".pdf"
    assert val_file.filename == "technical_bid.pdf"
    assert val_file.file_size == len(pdf_bytes)


def test_validate_valid_jpeg_content():
    """Verify valid JPEG content passes validation for .jpg and .jpeg extensions."""
    jpeg_bytes = generate_valid_jpeg()

    val_jpg = validate_file_content(jpeg_bytes, filename="pan_card_photo.jpg")
    assert val_jpg.mime_type == "image/jpeg"
    assert val_jpg.extension == ".jpg"

    val_jpeg = validate_file_content(jpeg_bytes, filename="director_signature.jpeg")
    assert val_jpeg.mime_type == "image/jpeg"
    assert val_jpeg.extension == ".jpeg"


def test_validate_valid_png_content():
    """Verify valid PNG content passes validation and detects image/png."""
    png_bytes = generate_valid_png()
    val_png = validate_file_content(png_bytes, filename="company_seal.png")

    assert val_png.mime_type == "image/png"
    assert val_png.extension == ".png"
    assert val_png.filename == "company_seal.png"


# 2. Magic Byte Detection Tests

def test_detect_magic_mime_types():
    """Verify detect_magic_mime_type accurately determines types from binary headers."""
    assert detect_magic_mime_type(generate_valid_pdf()) == "application/pdf"
    assert detect_magic_mime_type(generate_valid_jpeg()) == "image/jpeg"
    assert detect_magic_mime_type(generate_valid_png()) == "image/png"
    assert detect_magic_mime_type(b"MZ\x90\x00\x03\x00\x00\x00") is None
    assert detect_magic_mime_type(b"PK\x03\x04\x14\x00\x06\x00") is None
    assert detect_magic_mime_type(b"") is None


# 3. Unsupported Types & Extensions

def test_reject_unsupported_extensions():
    """Verify unsupported file extensions are rejected."""
    with pytest.raises(BadRequestException, match="Unsupported file extension"):
        validate_file_content(generate_valid_pdf(), filename="script.sh")

    with pytest.raises(BadRequestException, match="Unsupported file extension"):
        validate_file_content(generate_valid_pdf(), filename="executable.exe")

    with pytest.raises(BadRequestException, match="Unsupported file extension"):
        validate_file_content(generate_valid_pdf(), filename="archive.zip")


def test_reject_missing_extension():
    """Verify filenames without extensions are rejected."""
    with pytest.raises(BadRequestException, match="missing a valid file extension"):
        validate_file_content(generate_valid_pdf(), filename="document_without_ext")


# 4. Spoofed Content-Type and Mismatches

def test_reject_spoofed_pdf_with_text():
    """Verify text file named .pdf is rejected despite client naming."""
    fake_pdf = b"Hello, this is a plain text file pretending to be a PDF."
    with pytest.raises(BadRequestException, match="Invalid file format"):
        validate_file_content(fake_pdf, filename="fake.pdf")


def test_reject_extension_and_content_mismatch():
    """Verify PNG bytes disguised under .pdf extension are rejected."""
    png_bytes = generate_valid_png()
    with pytest.raises(BadRequestException, match="does not match"):
        validate_file_content(png_bytes, filename="sneaky_file.pdf")


# 5. Oversized and Empty Files

def test_reject_empty_file():
    """Verify 0-byte file is rejected."""
    with pytest.raises(BadRequestException, match="empty"):
        validate_file_content(b"", filename="empty.pdf")


def test_reject_oversized_file():
    """Verify files larger than max_size_mb are rejected."""
    oversized = b"%PDF-" + b"0" * (11 * 1024 * 1024)
    with pytest.raises(BadRequestException, match="exceeds"):
        validate_file_content(oversized, filename="large.pdf", max_size_mb=10)


# 6. Malformed & Corrupted Payloads

def test_reject_corrupt_truncated_pdf():
    """Verify PDF smaller than minimum structure length is rejected."""
    with pytest.raises(BadRequestException, match="truncated or corrupted"):
        validate_file_content(b"%PDF-1.4\nshort", filename="corrupt.pdf")


def test_reject_corrupt_truncated_jpeg():
    """Verify JPEG smaller than minimum header size is rejected."""
    with pytest.raises(BadRequestException, match="truncated or corrupted"):
        validate_file_content(b"\xff\xd8\xff\xe0", filename="corrupt.jpg")


def test_reject_corrupt_truncated_png():
    """Verify PNG with broken header is rejected."""
    with pytest.raises(BadRequestException, match="truncated or corrupted"):
        validate_file_content(b"\x89PNG\r\n\x1a\nshort", filename="corrupt.png")


# 7. Path Traversal & Filename Sanitization

def test_sanitize_dangerous_filenames():
    """Verify path traversal sequences in filenames are sanitized."""
    pdf_bytes = generate_valid_pdf()
    val_file = validate_file_content(pdf_bytes, filename="../../var/log/system.pdf")
    assert val_file.filename == "system.pdf"
    assert "/" not in val_file.filename
    assert ".." not in val_file.filename


# 8. Async FastAPI UploadFile Integration

@pytest.mark.anyio
async def test_validate_single_upload_file_async():
    """Test validate_single_upload_file with FastAPI UploadFile instance."""
    pdf_bytes = generate_valid_pdf("RFP Notice")
    upload_file = UploadFile(
        file=io.BytesIO(pdf_bytes),
        filename="rfp_notice.pdf",
        headers={"content-type": "application/pdf"},
    )
    val_file = await validate_single_upload_file(upload_file)
    assert val_file.mime_type == "application/pdf"
    assert val_file.filename == "rfp_notice.pdf"


# 9. Batch Multiple Files Upload Validation

@pytest.mark.anyio
async def test_validate_multiple_upload_files_success():
    """Test validating a batch of valid mixed PDF, JPEG, and PNG files."""
    files = [
        UploadFile(
            file=io.BytesIO(generate_valid_pdf("Doc 1")),
            filename="tender_doc.pdf",
        ),
        UploadFile(
            file=io.BytesIO(generate_valid_jpeg()),
            filename="pan_card.jpg",
        ),
        UploadFile(
            file=io.BytesIO(generate_valid_png()),
            filename="gst_certificate.png",
        ),
    ]

    validated_list = await validate_multiple_upload_files(files, max_files=10)
    assert len(validated_list) == 3
    assert validated_list[0].mime_type == "application/pdf"
    assert validated_list[1].mime_type == "image/jpeg"
    assert validated_list[2].mime_type == "image/png"


@pytest.mark.anyio
async def test_validate_multiple_upload_files_exceeding_max_limit():
    """Test batch upload exceeding max_files limit is rejected."""
    files = [
        UploadFile(
            file=io.BytesIO(generate_valid_pdf(f"Doc {i}")),
            filename=f"doc_{i}.pdf",
        )
        for i in range(5)
    ]

    with pytest.raises(BadRequestException, match="Too many files"):
        await validate_multiple_upload_files(files, max_files=3)


@pytest.mark.anyio
async def test_validate_multiple_upload_files_empty_list():
    """Test empty batch is rejected."""
    with pytest.raises(BadRequestException, match="No files provided"):
        await validate_multiple_upload_files([])


@pytest.mark.anyio
async def test_validate_multiple_upload_files_partial_failure():
    """Test batch with one invalid file fails and identifies the failing file."""
    files = [
        UploadFile(
            file=io.BytesIO(generate_valid_pdf("Valid Doc")),
            filename="valid_doc.pdf",
        ),
        UploadFile(
            file=io.BytesIO(b"Not a valid file"),
            filename="corrupt.pdf",
        ),
    ]

    with pytest.raises(BadRequestException, match="File #2"):
        await validate_multiple_upload_files(files)
