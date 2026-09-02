"""
Phase 11.3 — Deterministic Document Extraction Test Suite
Tests deterministic extraction across PDF, DOCX, and XLSX formats with source traceability,
heading hierarchies, worksheet ranges, tabular layouts, metadata, and error handling.
"""
import io
import os
import sys
import unittest
import zipfile
from unittest.mock import MagicMock

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# If running in environment where heavy DB/OCR libraries are not installed, provide typed mock stubs
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

from app.schemas.processing import (
    DocxExtractionResult,
    DocxParagraph,
    DocxSection,
    DocxTable,
    ExtractionResult,
    PageExtractionResult,
    TableData,
    XlsxExtractionResult,
    XlsxTable,
    XlsxWorksheet,
)
from app.services.docx_extractor import DOCXExtractor
from app.services.document_processor import DocumentProcessor
from app.services.pdf_extractor import PDFExtractor
from app.services.xlsx_extractor import XLSXExtractor, col_letter_to_index


def build_test_docx_bytes() -> bytes:
    """Builds a well-formed DOCX in-memory test fixture with headings, paragraphs, and a table."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '</Types>',
        )
        # docProps/core.xml (Metadata)
        zf.writestr(
            "docProps/core.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">'
            '<dc:title>GeM Procurement Tender Notice</dc:title>'
            '<dc:creator>Procurement Officer Division A</dc:creator>'
            '<dc:description>Annual Maintenance and Hardware Supply Tender</dc:description>'
            '</cp:coreProperties>',
        )
        # word/document.xml (Content)
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '  <w:p>'
            '    <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '    <w:r><w:t>SECTION 1: ELIGIBILITY CRITERIA</w:t></w:r>'
            '  </w:p>'
            '  <w:p>'
            '    <w:r><w:t>The bidder must have an average annual turnover of at least INR 50 Lakhs.</w:t></w:r>'
            '  </w:p>'
            '  <w:p>'
            '    <w:r><w:t>The bidder shall possess at least 3 years of past experience in similar works.</w:t></w:r>'
            '  </w:p>'
            '  <w:p>'
            '    <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>'
            '    <w:r><w:t>SECTION 2: MANDATORY DOCUMENTS SCHEDULE</w:t></w:r>'
            '  </w:p>'
            '  <w:tbl>'
            '    <w:tr>'
            '      <w:tc><w:p><w:r><w:t>Document Name</w:t></w:r></w:p></w:tc>'
            '      <w:tc><w:p><w:r><w:t>Mandatory</w:t></w:r></w:p></w:tc>'
            '      <w:tc><w:p><w:r><w:t>Issuing Authority</w:t></w:r></w:p></w:tc>'
            '    </w:tr>'
            '    <w:tr>'
            '      <w:tc><w:p><w:r><w:t>GST Registration Certificate</w:t></w:r></w:p></w:tc>'
            '      <w:tc><w:p><w:r><w:t>Yes</w:t></w:r></w:p></w:tc>'
            '      <w:tc><w:p><w:r><w:t>GSTN / Govt. of India</w:t></w:r></w:p></w:tc>'
            '    </w:tr>'
            '    <w:tr>'
            '      <w:tc><w:p><w:r><w:t>PAN Card</w:t></w:r></w:p></w:tc>'
            '      <w:tc><w:p><w:r><w:t>Yes</w:t></w:r></w:p></w:tc>'
            '      <w:tc><w:p><w:r><w:t>Income Tax Department</w:t></w:r></w:p></w:tc>'
            '    </w:tr>'
            '  </w:tbl>'
            '</w:body>'
            '</w:document>'
        )
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


def build_test_xlsx_bytes() -> bytes:
    """Builds a multi-sheet XLSX in-memory test fixture with shared strings and tabular grid."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # [Content_Types].xml
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '</Types>',
        )
        # xl/workbook.xml (2 sheets: BOQ_Schedule and Financial_Summary)
        zf.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets>'
            '  <sheet name="BOQ_Schedule" sheetId="1" r:id="rId1"/>'
            '  <sheet name="Financial_Summary" sheetId="2" r:id="rId2"/>'
            '</sheets>'
            '</workbook>',
        )
        # xl/_rels/workbook.xml.rels
        zf.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
            '</Relationships>',
        )
        # xl/sharedStrings.xml
        shared_strings = [
            "Item Code", "Description", "Quantity", "Unit Rate (INR)", "Total (INR)",
            "IT-HW-001", "Rack Server Dual Xeon", "5", "250000", "1250000",
            "IT-SW-002", "Linux Enterprise OS License", "10", "45000", "450000",
            "Financial Metric", "Value",
            "Base Estimate", "GST @ 18%", "Grand Total",
        ]
        sst_items = "".join(f"<si><t>{s}</t></si>" for s in shared_strings)
        zf.writestr(
            "xl/sharedStrings.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">{sst_items}</sst>',
        )
        # xl/worksheets/sheet1.xml (BOQ items)
        sheet1_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '  <row r="1">'
            '    <c r="A1" t="s"><v>0</v></c>'
            '    <c r="B1" t="s"><v>1</v></c>'
            '    <c r="C1" t="s"><v>2</v></c>'
            '    <c r="D1" t="s"><v>3</v></c>'
            '    <c r="E1" t="s"><v>4</v></c>'
            '  </row>'
            '  <row r="2">'
            '    <c r="A2" t="s"><v>5</v></c>'
            '    <c r="B2" t="s"><v>6</v></c>'
            '    <c r="C2"><v>5</v></c>'
            '    <c r="D2"><v>250000</v></c>'
            '    <c r="E2"><v>1250000</v></c>'
            '  </row>'
            '  <row r="3">'
            '    <c r="A3" t="s"><v>10</v></c>'
            '    <c r="B3" t="s"><v>11</v></c>'
            '    <c r="C3"><v>10</v></c>'
            '    <c r="D3"><v>45000</v></c>'
            '    <c r="E3"><v>450000</v></c>'
            '  </row>'
            '</sheetData>'
            '</worksheet>'
        )
        zf.writestr("xl/worksheets/sheet1.xml", sheet1_xml)

        # xl/worksheets/sheet2.xml (Financial Summary)
        sheet2_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>'
            '  <row r="1">'
            '    <c r="A1" t="s"><v>15</v></c>'
            '    <c r="B1" t="s"><v>16</v></c>'
            '  </row>'
            '  <row r="2">'
            '    <c r="A2" t="s"><v>17</v></c>'
            '    <c r="B2"><v>1700000</v></c>'
            '  </row>'
            '  <row r="3">'
            '    <c r="A3" t="s"><v>18</v></c>'
            '    <c r="B3"><v>306000</v></c>'
            '  </row>'
            '  <row r="4">'
            '    <c r="A4" t="s"><v>19</v></c>'
            '    <c r="B4"><v>2006000</v></c>'
            '  </row>'
            '</sheetData>'
            '</worksheet>'
        )
        zf.writestr("xl/worksheets/sheet2.xml", sheet2_xml)
    return buf.getvalue()


class TestDeterministicExtractionPhase11(unittest.TestCase):
    """Unit tests for Phase 11.3 deterministic extraction across PDF, DOCX, and XLSX."""

    def setUp(self):
        self.docx_extractor = DOCXExtractor()
        self.xlsx_extractor = XLSXExtractor()
        self.doc_processor = DocumentProcessor(
            docx_ext=self.docx_extractor,
            xlsx_ext=self.xlsx_extractor,
        )

    # -------------------------------------------------------------------------
    # DOCX EXTRACTION TESTS
    # -------------------------------------------------------------------------
    def test_docx_extraction_success(self):
        """Verifies full DOCX deterministic extraction of paragraphs, headings, tables, and sections."""
        docx_bytes = build_test_docx_bytes()
        res: DocxExtractionResult = self.docx_extractor.extract(docx_bytes, filename="tender.docx")

        self.assertEqual(res.format, "DOCX")
        self.assertEqual(res.status, "EXTRACTED")
        self.assertFalse(res.is_corrupted)
        self.assertIsNone(res.error_message)

        # Paragraphs & Headings verification
        self.assertGreaterEqual(res.paragraph_count, 4)
        headings = [p for p in res.paragraphs if p.is_heading]
        self.assertGreaterEqual(len(headings), 2)
        self.assertEqual(headings[0].text, "SECTION 1: ELIGIBILITY CRITERIA")
        self.assertEqual(headings[0].heading_level, 1)

        # Table extraction verification
        self.assertEqual(res.table_count, 1)
        table = res.tables[0]
        self.assertEqual(table.row_count, 3)
        self.assertEqual(table.col_count, 3)
        self.assertEqual(table.headers, ["Document Name", "Mandatory", "Issuing Authority"])
        self.assertIn("GST Registration Certificate", table.rows[1][0])

        # Metadata extraction
        self.assertEqual(res.metadata.get("title"), "GeM Procurement Tender Notice")
        self.assertEqual(res.metadata.get("creator"), "Procurement Officer Division A")

        # Section boundaries verification
        self.assertGreaterEqual(len(res.sections), 2)
        self.assertEqual(res.sections[0].heading, "SECTION 1: ELIGIBILITY CRITERIA")
        self.assertIn("average annual turnover of at least INR 50 Lakhs", res.sections[0].text)

    def test_docx_corrupt_payload(self):
        """Verifies that corrupted DOCX files return controlled error without raising exceptions."""
        res = self.docx_extractor.extract(b"Not a valid docx zip payload", "corrupt.docx")
        self.assertEqual(res.status, "FAILED")
        self.assertTrue(res.is_corrupted)
        self.assertIsNotNone(res.error_message)

    def test_docx_missing_document_xml(self):
        """Verifies that a valid ZIP lacking word/document.xml fails gracefully."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("test.txt", "dummy content")
        bad_docx = buf.getvalue()

        res = self.docx_extractor.extract(bad_docx, "missing_xml.docx")
        self.assertEqual(res.status, "FAILED")
        self.assertTrue(res.is_corrupted)
        self.assertIn("missing main word/document.xml", res.error_message)

    # -------------------------------------------------------------------------
    # XLSX EXTRACTION TESTS
    # -------------------------------------------------------------------------
    def test_xlsx_extraction_success(self):
        """Verifies full XLSX deterministic extraction of worksheets, rows, coordinates, and tables."""
        xlsx_bytes = build_test_xlsx_bytes()
        res: XlsxExtractionResult = self.xlsx_extractor.extract(xlsx_bytes, filename="boq.xlsx")

        self.assertEqual(res.format, "XLSX")
        self.assertEqual(res.status, "EXTRACTED")
        self.assertFalse(res.is_corrupted)
        self.assertIsNone(res.error_message)

        # Worksheet verification
        self.assertEqual(res.sheet_count, 2)
        self.assertEqual(res.sheet_names, ["BOQ_Schedule", "Financial_Summary"])

        # Sheet 1 verification (BOQ_Schedule)
        sheet1 = res.sheets[0]
        self.assertEqual(sheet1.sheet_name, "BOQ_Schedule")
        self.assertEqual(sheet1.row_count, 3)
        self.assertEqual(sheet1.col_count, 5)
        self.assertEqual(sheet1.tables[0].headers, ["Item Code", "Description", "Quantity", "Unit Rate (INR)", "Total (INR)"])
        self.assertEqual(sheet1.rows[1][0], "IT-HW-001")
        self.assertEqual(sheet1.rows[1][1], "Rack Server Dual Xeon")

        # Sheet 2 verification (Financial_Summary)
        sheet2 = res.sheets[1]
        self.assertEqual(sheet2.sheet_name, "Financial_Summary")
        self.assertEqual(sheet2.row_count, 4)
        self.assertEqual(sheet2.rows[1][0], "Base Estimate")
        self.assertEqual(sheet2.rows[1][1], 1700000)

        # Unified TableData verification
        self.assertEqual(len(res.tables), 2)
        self.assertEqual(res.tables[0].sheet_name, "BOQ_Schedule")
        self.assertEqual(res.tables[1].sheet_name, "Financial_Summary")

    def test_xlsx_col_letter_to_index(self):
        """Verifies Excel column letter to index helper."""
        self.assertEqual(col_letter_to_index("A"), 0)
        self.assertEqual(col_letter_to_index("B"), 1)
        self.assertEqual(col_letter_to_index("Z"), 25)
        self.assertEqual(col_letter_to_index("AA"), 26)
        self.assertEqual(col_letter_to_index("AB"), 27)

    def test_xlsx_corrupt_payload(self):
        """Verifies that corrupted XLSX files return controlled error without raising exceptions."""
        res = self.xlsx_extractor.extract(b"Not a valid xlsx zip payload", "corrupt.xlsx")
        self.assertEqual(res.status, "FAILED")
        self.assertTrue(res.is_corrupted)
        self.assertIsNotNone(res.error_message)

    # -------------------------------------------------------------------------
    # MULTI-FORMAT DOCUMENT PROCESSOR ROUTING & TRACEABILITY
    # -------------------------------------------------------------------------
    def test_document_processor_routing_docx(self):
        """Verifies DocumentProcessor correctly routes DOCX and provides traceable sections."""
        docx_bytes = build_test_docx_bytes()
        unified_res: ExtractionResult = self.doc_processor.process_document(
            file_bytes=docx_bytes,
            filename="tender.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(unified_res.format, "DOCX")
        self.assertEqual(unified_res.status, "EXTRACTED")
        self.assertIsNotNone(unified_res.docx_data)

        # Test to_traceable_pages() method
        traceable = unified_res.to_traceable_pages()
        self.assertIsInstance(traceable, list)
        self.assertGreaterEqual(len(traceable), 2)
        self.assertEqual(traceable[0]["page_number"], 1)
        self.assertIn("SECTION 1: ELIGIBILITY CRITERIA", traceable[0]["section"])

    def test_document_processor_routing_xlsx(self):
        """Verifies DocumentProcessor correctly routes XLSX and provides traceable sheet pages."""
        xlsx_bytes = build_test_xlsx_bytes()
        unified_res: ExtractionResult = self.doc_processor.process_document(
            file_bytes=xlsx_bytes,
            filename="boq.xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(unified_res.format, "XLSX")
        self.assertEqual(unified_res.status, "EXTRACTED")
        self.assertIsNotNone(unified_res.xlsx_data)

        # Test to_traceable_pages() method
        traceable = unified_res.to_traceable_pages()
        self.assertEqual(len(traceable), 2)
        self.assertEqual(traceable[0]["page_number"], 1)
        self.assertEqual(traceable[0]["section"], "Sheet: BOQ_Schedule")
        self.assertEqual(traceable[1]["page_number"], 2)
        self.assertEqual(traceable[1]["section"], "Sheet: Financial_Summary")

    def test_document_processor_routing_image(self):
        """Verifies DocumentProcessor marks image files as OCR_REQUIRED."""
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00\xff\xd9"
        res: ExtractionResult = self.doc_processor.process_document(
            file_bytes=jpeg_bytes,
            filename="cert.jpg",
            mime_type="image/jpeg",
            enable_ocr=False,
        )
        self.assertEqual(res.format, "IMAGE")
        self.assertEqual(res.status, "OCR_REQUIRED")
        self.assertTrue(res.requires_ocr)

    def test_document_processor_empty_file(self):
        """Verifies DocumentProcessor handles empty byte stream gracefully."""
        res: ExtractionResult = self.doc_processor.process_document(b"", "empty.pdf")
        self.assertEqual(res.status, "FAILED")
        self.assertTrue(res.is_corrupted)
        self.assertIn("Empty file byte stream", res.error_message)


if __name__ == "__main__":
    unittest.main()
