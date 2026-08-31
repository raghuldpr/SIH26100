import dataclasses
import logging
import os
from typing import List, Optional, Tuple, Union
from fastapi import UploadFile

from app.config import settings
from app.core.exceptions import BadRequestException
from app.core.storage import sanitize_filename

logger = logging.getLogger("app.core.validation")

# Magic byte signatures for supported file types
MAGIC_SIGNATURES = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}

# Extension to expected MIME type mapping
EXTENSION_MIME_MAP = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

MIME_EXTENSION_MAP = {
    "application/pdf": [".pdf"],
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
}


@dataclasses.dataclass
class ValidatedFile:
    """Encapsulates validated and sanitized file metadata and binary content."""

    content: bytes
    filename: str
    original_filename: str
    extension: str
    mime_type: str
    file_size: int


def detect_magic_mime_type(content: bytes) -> Optional[str]:
    """
    Inspects binary payload leading bytes against known magic signatures.
    Returns detected MIME type if recognized, or None.
    """
    if not content:
        return None

    # Check PNG signature (exact 8-byte sequence)
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"

    # Check JPEG signature (SOI marker FF D8 FF)
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"

    # Check PDF signature (%PDF- at the very start of the file)
    stripped_head = content[:32].lstrip(b"\r\n\t \x00")
    if stripped_head.startswith(b"%PDF-"):
        return "application/pdf"

    return None



def inspect_file_integrity(content: bytes, mime_type: str) -> None:
    """
    Performs structural sanity checks to catch obviously corrupt or truncated payloads.
    Raises BadRequestException if structural verification fails.
    """
    file_len = len(content)

    if mime_type == "application/pdf":
        if file_len < 30:
            raise BadRequestException(
                message="Invalid file format: PDF file is truncated or corrupted."
            )
        # Verify valid PDF header at the beginning
        if not content.startswith(b"%PDF-"):
            # If not at offset 0, ensure it appears near start
            idx = content[:1024].find(b"%PDF-")
            if idx == -1:
                raise BadRequestException(
                    message="Invalid file format: File header does not match a valid PDF document."
                )

    elif mime_type == "image/jpeg":
        if file_len < 10:
            raise BadRequestException(
                message="Invalid file format: JPEG image is truncated or corrupted."
            )
        if not content.startswith(b"\xff\xd8\xff"):
            raise BadRequestException(
                message="Invalid file format: File header does not match a valid JPEG image."
            )

    elif mime_type == "image/png":
        if file_len < 24:
            raise BadRequestException(
                message="Invalid file format: PNG image is truncated or corrupted."
            )
        if not content.startswith(b"\x89PNG\r\n\x1a\n"):
            raise BadRequestException(
                message="Invalid file format: File header does not match a valid PNG image."
            )


def validate_file_content(
    content: bytes,
    filename: Optional[str],
    allowed_mime_types: Optional[List[str]] = None,
    max_size_mb: Optional[int] = None,
) -> ValidatedFile:
    """
    Synchronously validates a raw byte payload and filename for size, extension,
    magic byte signature, and structural integrity.
    """
    if allowed_mime_types is None:
        allowed_mime_types = settings.ALLOWED_DOCUMENT_MIME_TYPES
    if max_size_mb is None:
        max_size_mb = settings.MAX_UPLOAD_SIZE_MB

    max_size_bytes = max_size_mb * 1024 * 1024
    file_size = len(content)

    # 1. Reject empty files
    if file_size == 0:
        raise BadRequestException(message="Uploaded file is empty.")

    # 2. Reject oversized files
    if file_size > max_size_bytes:
        raise BadRequestException(
            message=f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum limit of {max_size_mb}MB."
        )

    # 3. Filename sanitization and path traversal prevention
    raw_name = filename or "document.pdf"
    clean_name = sanitize_filename(raw_name)
    _, ext = os.path.splitext(clean_name.lower())

    if not ext:
        raise BadRequestException(
            message="Uploaded file is missing a valid file extension (e.g., .pdf, .jpg, .png)."
        )

    allowed_exts = set(settings.ALLOWED_DOCUMENT_EXTENSIONS)
    if ext not in allowed_exts:
        raise BadRequestException(
            message=f"Unsupported file extension '{ext}'. Allowed extensions: {', '.join(sorted(allowed_exts))}"
        )

    # 4. Inspect magic bytes for true MIME type (do not trust client Content-Type)
    detected_mime = detect_magic_mime_type(content)
    if not detected_mime:
        raise BadRequestException(
            message="Invalid file format: File header does not match a valid PDF document or supported image format."
        )

    if detected_mime not in allowed_mime_types:
        raise BadRequestException(
            message=f"Unsupported file format '{detected_mime}'. Allowed types: {', '.join(allowed_mime_types)}"
        )

    # 5. Verify extension compatibility with verified MIME type
    expected_extensions = MIME_EXTENSION_MAP.get(detected_mime, [])
    if ext not in expected_extensions:
        raise BadRequestException(
            message=f"File extension '{ext}' does not match detected file content format '{detected_mime}'."
        )

    # 6. Basic structural integrity check
    inspect_file_integrity(content, detected_mime)

    return ValidatedFile(
        content=content,
        filename=clean_name,
        original_filename=raw_name,
        extension=ext,
        mime_type=detected_mime,
        file_size=file_size,
    )


async def validate_single_upload_file(
    file: UploadFile,
    allowed_mime_types: Optional[List[str]] = None,
    max_size_mb: Optional[int] = None,
) -> ValidatedFile:
    """
    Validates an incoming FastAPI UploadFile instance.
    Reads file stream and performs complete security, MIME, and size checks.
    """
    if file is None:
        raise BadRequestException(message="No file uploaded.")

    content = await file.read()
    return validate_file_content(
        content=content,
        filename=file.filename,
        allowed_mime_types=allowed_mime_types,
        max_size_mb=max_size_mb,
    )


async def validate_multiple_upload_files(
    files: List[UploadFile],
    max_files: Optional[int] = None,
    allowed_mime_types: Optional[List[str]] = None,
    max_size_mb: Optional[int] = None,
) -> List[ValidatedFile]:
    """
    Validates a list of UploadFile instances for batch uploads.
    Enforces maximum file count per request and validates each file individually.
    """
    if not files:
        raise BadRequestException(message="No files provided for upload.")

    limit = max_files or settings.MAX_UPLOAD_FILES_PER_REQUEST
    if len(files) > limit:
        raise BadRequestException(
            message=f"Too many files uploaded in single request ({len(files)}). Maximum allowed is {limit}."
        )

    validated_results: List[ValidatedFile] = []
    for idx, f in enumerate(files):
        try:
            val_file = await validate_single_upload_file(
                file=f,
                allowed_mime_types=allowed_mime_types,
                max_size_mb=max_size_mb,
            )
            validated_results.append(val_file)
        except BadRequestException as exc:
            logger.warning(f"Validation failed for batch file #{idx + 1} ({f.filename}): {exc.message}")
            raise BadRequestException(
                message=f"File #{idx + 1} ('{f.filename or 'unnamed'}') validation failed: {exc.message}"
            )

    return validated_results
