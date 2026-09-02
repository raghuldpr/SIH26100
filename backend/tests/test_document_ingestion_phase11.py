"""
Phase 11.1 — Document Ingestion and Validation Test Suite
Tests validation, MIME/magic byte inspection, SHA-256 cryptographic calculation,
file integrity, path traversal prevention, and error responses for PDF, DOCX, XLSX, and images.
"""
import hashlib
import io
import os
import sys
import unittest
import zipfile
from unittest.mock import MagicMock, patch

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if "sqlalchemy" not in sys.modules:
    import types

    class DummyType(type):
        def __getitem__(cls, item):
            return cls
        def __getattr__(cls, item):
            return DummyClass()
        def __call__(cls, *args, **kwargs):
            return super().__call__(*args, **kwargs)
            
    class DummyClass(metaclass=DummyType):
        def __init__(self, *args, **kwargs):
            pass
        def __call__(self, *args, **kwargs):
            return self
        def __getattr__(self, item):
            return self

    class AutoModule(types.ModuleType):
        def __init__(self, name):
            super().__init__(name)
            self.__path__ = []
        def __getattr__(self, name):
            if name == "create_engine":
                return lambda *a, **kw: DummyClass()
            if name == "text":
                return lambda *a, **kw: DummyClass()
            if name == "mapped_column":
                return lambda *a, **kw: None
            if name == "relationship":
                return lambda *a, **kw: None
            if name == "declarative_base":
                return lambda *a, **kw: DummyClass
            if name == "sessionmaker":
                return lambda *a, **kw: DummyClass
            return DummyClass

    sa_mod = AutoModule("sqlalchemy")
    sa_orm = AutoModule("sqlalchemy.orm")
    sa_dialects = AutoModule("sqlalchemy.dialects")
    sa_pg = AutoModule("sqlalchemy.dialects.postgresql")
    sa_types = AutoModule("sqlalchemy.types")
    
    sa_mod.orm = sa_orm
    sa_mod.dialects = sa_dialects
    sa_mod.types = sa_types
    
    sys.modules["sqlalchemy"] = sa_mod
    sys.modules["sqlalchemy.orm"] = sa_orm
    sys.modules["sqlalchemy.dialects"] = sa_dialects
    sys.modules["sqlalchemy.dialects.postgresql"] = sa_pg
    sys.modules["sqlalchemy.types"] = sa_types

for mod in ["supabase", "fitz", "pdfplumber"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

from app.config import settings
from app.core.exceptions import BadRequestException
from app.core.storage import (
    generate_bidder_storage_path,
    generate_tender_storage_path,
    sanitize_filename,
    validate_storage_path,
)
from app.core.validation import (
    calculate_sha256,
    detect_magic_mime_type,
    inspect_file_integrity,
    validate_file_content,
    ValidatedFile,
)
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus
from app.schemas.document import DocumentResponse


def create_valid_pdf_bytes() -> bytes:
    """Generates minimal valid PDF bytes."""
    return b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def create_valid_docx_bytes() -> bytes:
    """Generates minimal valid DOCX (OpenXML ZIP) bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        zf.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships></Relationships>')
        zf.writestr("word/document.xml", '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Tender Specification</w:t></w:r></w:p></w:body></w:document>')
    return buf.getvalue()


def create_valid_xlsx_bytes() -> bytes:
    """Generates minimal valid XLSX (OpenXML ZIP) bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')
        zf.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships></Relationships>')
        zf.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"></workbook>')
        zf.writestr("xl/worksheets/sheet1.xml", '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"></worksheet>')
    return buf.getvalue()


def create_valid_jpeg_bytes() -> bytes:
    """Generates minimal valid JPEG bytes."""
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9"


def create_valid_png_bytes() -> bytes:
    """Generates minimal valid PNG bytes."""
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"


class TestDocumentValidationPhase11(unittest.TestCase):
    """Unit tests for Phase 11 document validation and ingestion rules."""

    def test_calculate_sha256(self):
        """Verifies deterministic SHA-256 calculation."""
        payload = b"Sample Procurement Document Content"
        expected = hashlib.sha256(payload).hexdigest()
        self.assertEqual(calculate_sha256(payload), expected)
        self.assertEqual(len(calculate_sha256(payload)), 64)

    def test_valid_pdf_validation(self):
        """Verifies that a valid PDF file is accepted with correct MIME and SHA-256."""
        pdf_bytes = create_valid_pdf_bytes()
        val_file = validate_file_content(
            content=pdf_bytes,
            filename="tender_rfp_2026.pdf",
        )
        self.assertIsInstance(val_file, ValidatedFile)
        self.assertEqual(val_file.mime_type, "application/pdf")
        self.assertEqual(val_file.extension, ".pdf")
        self.assertEqual(val_file.filename, "tender_rfp_2026.pdf")
        self.assertEqual(val_file.file_size, len(pdf_bytes))
        self.assertEqual(val_file.sha256, hashlib.sha256(pdf_bytes).hexdigest())

    def test_valid_docx_validation(self):
        """Verifies that a valid DOCX file is accepted with correct OpenXML MIME and SHA-256."""
        docx_bytes = create_valid_docx_bytes()
        val_file = validate_file_content(
            content=docx_bytes,
            filename="Tender_Scope_Document.docx",
        )
        self.assertIsInstance(val_file, ValidatedFile)
        self.assertEqual(
            val_file.mime_type,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(val_file.extension, ".docx")
        self.assertEqual(val_file.filename, "Tender_Scope_Document.docx")
        self.assertEqual(val_file.sha256, hashlib.sha256(docx_bytes).hexdigest())

    def test_valid_xlsx_validation(self):
        """Verifies that a valid XLSX file is accepted with correct Spreadsheet MIME and SHA-256."""
        xlsx_bytes = create_valid_xlsx_bytes()
        val_file = validate_file_content(
            content=xlsx_bytes,
            filename="Financial_Schedule_BOQ.xlsx",
        )
        self.assertIsInstance(val_file, ValidatedFile)
        self.assertEqual(
            val_file.mime_type,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(val_file.extension, ".xlsx")
        self.assertEqual(val_file.filename, "Financial_Schedule_BOQ.xlsx")
        self.assertEqual(val_file.sha256, hashlib.sha256(xlsx_bytes).hexdigest())

    def test_valid_images_validation(self):
        """Verifies that JPEG and PNG images for OCR are validated correctly."""
        jpeg_bytes = create_valid_jpeg_bytes()
        val_jpeg = validate_file_content(jpeg_bytes, "gst_cert.jpg")
        self.assertEqual(val_jpeg.mime_type, "image/jpeg")

        png_bytes = create_valid_png_bytes()
        val_png = validate_file_content(png_bytes, "pan_card.png")
        self.assertEqual(val_png.mime_type, "image/png")

    def test_unsupported_file_type_extension(self):
        """Verifies rejection of unsupported file extensions (e.g. .exe, .sh, .bat)."""
        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(b"echo 'malicious payload'", "script.sh")
        self.assertIn("Unsupported file extension", ctx.exception.message)

        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(b"MZ\x90\x00", "payload.exe")
        self.assertIn("Unsupported file extension", ctx.exception.message)

    def test_oversized_file_rejection(self):
        """Verifies rejection of payloads exceeding MAX_UPLOAD_SIZE_MB."""
        large_payload = b"%PDF-" + b"0" * (1024 * 1024 * 2)  # 2MB
        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(
                content=large_payload,
                filename="huge_file.pdf",
                max_size_mb=1,  # limit to 1MB
            )
        self.assertIn("exceeds maximum limit", ctx.exception.message)

    def test_empty_file_rejection(self):
        """Verifies rejection of 0-byte empty file uploads."""
        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(b"", "empty.pdf")
        self.assertIn("Uploaded file is empty", ctx.exception.message)

    def test_unsafe_filename_sanitization(self):
        """Verifies that path traversal characters and unsafe names are sanitized safely."""
        # Path traversal sequences
        sanitized = sanitize_filename("../../../etc/passwd.pdf")
        self.assertEqual(sanitized, "passwd.pdf")

        # Windows path traversal
        sanitized_win = sanitize_filename("..\\..\\Windows\\System32\\config.pdf")
        self.assertEqual(sanitized_win, "config.pdf")

        # Null bytes and control characters
        sanitized_ctrl = sanitize_filename("safe\x00file\x1f_test.docx")
        self.assertEqual(sanitized_ctrl, "safefile_test.docx")

        # Double dots
        sanitized_dots = sanitize_filename("tender...final..version.xlsx")
        self.assertEqual(sanitized_dots, "tender.final.version.xlsx")

        # Storage path traversal validation
        with self.assertRaises(BadRequestException):
            validate_storage_path("../unsafe/path/doc.pdf")

    def test_malformed_pdf_rejection(self):
        """Verifies that corrupt or truncated PDFs are rejected."""
        # PDF with missing header
        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(b"Random unformatted text without header", "corrupt.pdf")
        self.assertIn("Invalid file format", ctx.exception.message)

        # Truncated PDF (< 30 bytes)
        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(b"%PDF-1.4", "truncated.pdf")
        self.assertIn("truncated or corrupted", ctx.exception.message)

    def test_malformed_docx_rejection(self):
        """Verifies that corrupt DOCX files are rejected."""
        # Corrupted ZIP header pretending to be docx
        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(b"PK\x03\x04corrupted_payload_non_zip_stream", "bad.docx")
        self.assertIn("Invalid file format", ctx.exception.message)

        # Valid ZIP file but missing word/ structure (e.g. random zip renamed to .docx)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("test.txt", "hello world")
        fake_docx = buf.getvalue()

        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(fake_docx, "fake.docx")
        self.assertIn("Invalid file format", ctx.exception.message)

    def test_malformed_xlsx_rejection(self):
        """Verifies that corrupt XLSX files are rejected."""
        # Valid ZIP but missing xl/ structure (e.g. zip renamed to .xlsx)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("test.txt", "hello world")
        fake_xlsx = buf.getvalue()

        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(fake_xlsx, "fake.xlsx")
        self.assertIn("Invalid file format", ctx.exception.message)

    def test_extension_mime_mismatch_rejection(self):
        """Verifies that a valid PDF with .docx extension is rejected due to mismatch."""
        pdf_bytes = create_valid_pdf_bytes()
        with self.assertRaises(BadRequestException) as ctx:
            validate_file_content(pdf_bytes, "actually_a_pdf.docx")
        self.assertIn("does not match detected file content format", ctx.exception.message)

    def test_storage_path_generation_never_exposes_filesystem(self):
        """Verifies that generated storage paths are relative virtual object keys, not local filesystem paths."""
        tender_id = "123e4567-e89b-12d3-a456-426614174000"
        t_path = generate_tender_storage_path(tender_id, "rfp_document.pdf")
        self.assertTrue(t_path.startswith(f"tenders/{tender_id}/"))
        self.assertNotIn("C:", t_path)
        self.assertNotIn("\\", t_path)
        self.assertNotIn("..", t_path)

        bidder_id = "987e6543-e89b-12d3-a456-426614174999"
        b_path = generate_bidder_storage_path(bidder_id, DocumentType.GST, "gst_cert.png")
        self.assertTrue(b_path.startswith(f"bidders/{bidder_id}/GST/"))
        self.assertNotIn("C:", b_path)
        self.assertNotIn("\\", b_path)

    def test_processing_status_enum_values(self):
        """Verifies that ProcessingStatus enum includes project status conventions."""
        self.assertEqual(ProcessingStatus.NOT_PROCESSED.value, "NOT_PROCESSED")
        self.assertEqual(ProcessingStatus.PROCESSING.value, "PROCESSING")
        self.assertEqual(ProcessingStatus.PROCESSED.value, "PROCESSED")
        self.assertEqual(ProcessingStatus.EXTRACTED.value, "EXTRACTED")
        self.assertEqual(ProcessingStatus.OCR_REQUIRED.value, "OCR_REQUIRED")
        self.assertEqual(ProcessingStatus.OCR_COMPLETED.value, "OCR_COMPLETED")
        self.assertEqual(ProcessingStatus.PARTIALLY_EXTRACTED.value, "PARTIALLY_EXTRACTED")
        self.assertEqual(ProcessingStatus.FAILED.value, "FAILED")

    def test_document_response_schema_sha256(self):
        """Verifies that DocumentResponse Pydantic schema serializes sha256 checksum."""
        import uuid
        doc_dict = {
            "id": uuid.uuid4(),
            "original_filename": "tender.docx",
            "document_type": DocumentType.TENDER,
            "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "file_size": 1024,
            "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "storage_path": "tenders/123/file.docx",
            "status": DocumentStatus.ACTIVE,
            "processing_status": ProcessingStatus.NOT_PROCESSED,
        }
        resp = DocumentResponse.model_validate(doc_dict)
        self.assertEqual(resp.sha256, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(resp.original_filename, "tender.docx")


if __name__ == "__main__":
    unittest.main()
