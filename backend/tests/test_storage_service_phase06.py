import io
import uuid
import pytest
from fastapi import UploadFile

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.storage import (
    SupabaseStorageService,
    generate_bidder_storage_path,
    generate_tender_storage_path,
    sanitize_filename,
    sanitize_path_segment,
    storage_service,
    validate_storage_path,
)
from app.models.enums import DocumentType


def test_sanitize_filename_traversal_prevention():
    """Verify filename sanitization removes paths, traversal sequences, and control chars."""
    assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe.pdf") == "cmd.exe.pdf"
    assert sanitize_filename("../../../secret.pdf") == "secret.pdf"
    assert sanitize_filename(".hidden_file.pdf") == "hidden_file.pdf"
    assert sanitize_filename("my tender file (draft #1) [final].pdf") == "my_tender_file__draft__1___final_.pdf"
    assert sanitize_filename("") != ""
    assert sanitize_filename(None) != ""


def test_sanitize_filename_length_and_extensions():
    """Verify long filenames are truncated while preserving extensions."""
    long_name = "a" * 300 + ".pdf"
    sanitized = sanitize_filename(long_name)
    assert len(sanitized) <= 255
    assert sanitized.endswith(".pdf")


def test_sanitize_path_segment():
    """Verify path segments are cleaned of invalid directory characters."""
    assert sanitize_path_segment("tender/123/../../") == "tender_123"
    assert sanitize_path_segment("PAN CARD & GST") == "PAN_CARD_GST"
    assert sanitize_path_segment("") == "default"



def test_validate_storage_path_security():
    """Verify invalid or malicious storage paths are rejected."""
    # Valid paths
    assert validate_storage_path("tenders/123/file.pdf") == "tenders/123/file.pdf"
    assert validate_storage_path("bidders/456/PAN/doc.pdf") == "bidders/456/PAN/doc.pdf"

    # Malicious paths
    with pytest.raises(BadRequestException):
        validate_storage_path("")

    with pytest.raises(BadRequestException):
        validate_storage_path("../../../etc/shadow")

    with pytest.raises(BadRequestException):
        validate_storage_path("/tenders/123/file.pdf")

    with pytest.raises(BadRequestException):
        validate_storage_path("./tenders/123/file.pdf")

    with pytest.raises(BadRequestException):
        validate_storage_path("C:\\Windows\\file.pdf")


def test_generate_tender_storage_path():
    """Verify tender storage path hierarchy: tenders/{tender_id}/{filename}."""
    tender_id = uuid.uuid4()
    path = generate_tender_storage_path(tender_id, "rfp_specification.pdf", unique_prefix=True)
    assert path.startswith(f"tenders/{tender_id}/")
    assert "rfp_specification.pdf" in path

    path_no_prefix = generate_tender_storage_path(tender_id, "rfp.pdf", unique_prefix=False)
    assert path_no_prefix == f"tenders/{tender_id}/rfp.pdf"


def test_generate_bidder_storage_path():
    """Verify bidder storage path hierarchy: bidders/{bidder_id}/{document_type}/{filename}."""
    bidder_id = uuid.uuid4()
    
    # Using DocumentType Enum
    path_pan = generate_bidder_storage_path(bidder_id, DocumentType.PAN, "pan_card.pdf")
    assert path_pan.startswith(f"bidders/{bidder_id}/PAN/")
    assert "pan_card.pdf" in path_pan

    # Using string document type
    path_gst = generate_bidder_storage_path(bidder_id, "GST", "gst_certificate.pdf", unique_prefix=False)
    assert path_gst == f"bidders/{bidder_id}/GST/gst_certificate.pdf"


def test_storage_service_upload_download_lifecycle():
    """Test uploading binary content, verifying existence, downloading, and deleting."""
    service = SupabaseStorageService(bucket="test-documents")
    test_path = f"tenders/{uuid.uuid4()}/test_document.pdf"
    test_content = b"%PDF-1.4\nTest PDF content for storage service verification\n%%EOF"

    # 1. Upload
    returned_path = service.upload(
        storage_path=test_path,
        file_content=test_content,
        mime_type="application/pdf",
    )
    assert returned_path == test_path

    # 2. Exists
    assert service.exists(test_path) is True
    assert service.exists("non_existent/path/file.pdf") is False

    # 3. Download
    downloaded_bytes = service.download(test_path)
    assert downloaded_bytes == test_content

    # 4. Signed URL
    signed_url = service.get_signed_url(test_path, expires_in=1800)
    assert signed_url is not None
    assert test_path in signed_url or "token" in signed_url

    # 5. Public URL
    public_url = service.get_public_url(test_path)
    assert public_url is not None
    assert test_path in public_url

    # 6. Delete
    delete_result = service.delete(test_path)
    assert delete_result is True
    assert service.exists(test_path) is False

    # 7. Download after deletion raises NotFoundException
    with pytest.raises(NotFoundException):
        service.download(test_path)


def test_storage_service_batch_delete():
    """Test batch deletion of multiple stored files."""
    service = SupabaseStorageService(bucket="test-documents")
    path1 = f"tenders/{uuid.uuid4()}/file1.pdf"
    path2 = f"tenders/{uuid.uuid4()}/file2.pdf"
    content = b"%PDF-1.4 mock content %%EOF"

    service.upload(path1, content)
    service.upload(path2, content)

    assert service.exists(path1) is True
    assert service.exists(path2) is True

    # Batch delete
    success = service.delete_batch([path1, path2])
    assert success is True
    assert service.exists(path1) is False
    assert service.exists(path2) is False


@pytest.mark.anyio
async def test_validate_upload_file_success():
    """Test valid PDF UploadFile passes validation."""
    service = storage_service
    pdf_bytes = b"%PDF-1.4\nValid PDF Header and Body\n%%EOF"
    upload_file = UploadFile(
        file=io.BytesIO(pdf_bytes),
        filename="valid_proposal.pdf",
        headers={"content-type": "application/pdf"},
    )

    content, mime, size = await service.validate_upload_file(upload_file)
    assert content == pdf_bytes
    assert mime == "application/pdf"
    assert size == len(pdf_bytes)


@pytest.mark.anyio
async def test_validate_upload_file_empty_failure():
    """Test empty UploadFile raises BadRequestException."""
    service = storage_service
    upload_file = UploadFile(
        file=io.BytesIO(b""),
        filename="empty.pdf",
        headers={"content-type": "application/pdf"},
    )
    with pytest.raises(BadRequestException, match="empty"):
        await service.validate_upload_file(upload_file)


@pytest.mark.anyio
async def test_validate_upload_file_oversized_failure():
    """Test oversized UploadFile raises BadRequestException."""
    service = storage_service
    large_bytes = b"%PDF-" + b"0" * (12 * 1024 * 1024)
    upload_file = UploadFile(
        file=io.BytesIO(large_bytes),
        filename="large.pdf",
        headers={"content-type": "application/pdf"},
    )
    with pytest.raises(BadRequestException, match="exceeds"):
        await service.validate_upload_file(upload_file, max_size_mb=10)


@pytest.mark.anyio
async def test_validate_upload_file_invalid_pdf_header():
    """Test non-PDF UploadFile pretending to be PDF is rejected."""
    service = storage_service
    txt_bytes = b"This is plain text without a %PDF- magic byte header."
    upload_file = UploadFile(
        file=io.BytesIO(txt_bytes),
        filename="fake.pdf",
        headers={"content-type": "application/pdf"},
    )
    with pytest.raises(BadRequestException, match="Invalid file format"):
        await service.validate_upload_file(upload_file)
