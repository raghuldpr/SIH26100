"""
Phase 11.5 — Document Content Normalization Test Suite
Tests whitespace/linebreak cleanup, Unicode normalization, Indian currency standardization,
Indian numbering format conversion, date normalization, table normalization,
and preservation of raw source text alongside page and section metadata.
"""
import os
import sys
import unittest

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# If running in environment where heavy DB/OCR libraries are not installed in global site-packages, provide typed mock stubs
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

for mod in ["supabase", "fitz", "pdfplumber", "cv2", "numpy"]:
    if mod not in sys.modules:
        from unittest.mock import MagicMock
        sys.modules[mod] = MagicMock()

from app.schemas.normalized_content import (
    NormalizedCurrency,
    NormalizedDate,
    NormalizedDocument,
    NormalizedNumber,
    NormalizedPage,
    NormalizedTable,
)
from app.schemas.processing import ExtractionResult, PageExtractionResult, TableData
from app.services.content_normalizer import (
    DocumentContentNormalizer,
    format_indian_number,
    format_standard_number,
)


class TestContentNormalizationPhase11(unittest.TestCase):
    """Unit tests for Phase 11.5 Document Content Normalization subsystem."""

    def setUp(self):
        self.normalizer = DocumentContentNormalizer()

    # -------------------------------------------------------------------------
    # 1. INR VALUES & CURRENCY NORMALIZATION
    # -------------------------------------------------------------------------
    def test_inr_currency_normalization(self):
        """
        Verifies diverse representations of INR monetary values map to consistent
        internal numerical amounts and canonical formatted strings:
        - ₹5 crore
        - ₹5,00,00,000
        - INR 50,000,000
        - Rs. 50 Lakhs
        - ₹ 1.5 Cr
        """
        samples = [
            ("₹5 crore", 50000000.0, "INR 50,000,000"),
            ("₹5,00,00,000", 50000000.0, "INR 50,000,000"),
            ("INR 50,000,000", 50000000.0, "INR 50,000,000"),
            ("Rs. 50 Lakhs", 5000000.0, "INR 5,000,000"),
            ("₹ 1.5 Cr", 15000000.0, "INR 15,000,000"),
            ("Rs 25,000", 25000.0, "INR 25,000"),
            ("INR 10,000.50", 10000.50, "INR 10,000.50"),
        ]

        for raw_expr, expected_val, expected_canon in samples:
            text = f"The bidder must provide a bank guarantee of {raw_expr} as earnest money."
            currencies = self.normalizer.extract_currencies(text)
            self.assertGreaterEqual(len(currencies), 1, f"Failed to detect currency in: '{text}'")
            matched = currencies[0]
            self.assertEqual(matched.amount, expected_val, f"Amount mismatch for '{raw_expr}'")
            self.assertEqual(matched.formatted, expected_canon, f"Canonical format mismatch for '{raw_expr}'")
            self.assertEqual(matched.currency, "INR")

    # -------------------------------------------------------------------------
    # 2. INDIAN NUMBERING FORMAT CONVERSION
    # -------------------------------------------------------------------------
    def test_indian_numbering_formats(self):
        """Verifies conversion between standard numbers and the Indian numbering grouping system."""
        self.assertEqual(format_indian_number(50000000), "5,00,00,000")
        self.assertEqual(format_indian_number(1500000), "15,00,000")
        self.assertEqual(format_indian_number(250000), "2,50,000")
        self.assertEqual(format_indian_number(50000), "50,000")
        self.assertEqual(format_indian_number(500), "500")

        self.assertEqual(format_standard_number(50000000), "50,000,000")
        self.assertEqual(format_standard_number(1500000), "1,500,000")

        # Extraction from text
        text = "Supplied 5,00,00,000 units in batch A and 1,500,000 units in batch B."
        numbers = self.normalizer.extract_numbers(text)
        self.assertEqual(len(numbers), 2)
        self.assertEqual(numbers[0].value, 50000000)
        self.assertEqual(numbers[0].formatted_indian, "5,00,00,000")
        self.assertEqual(numbers[1].value, 1500000)
        self.assertEqual(numbers[1].formatted_standard, "1,500,000")

    # -------------------------------------------------------------------------
    # 3. DATE NORMALIZATION
    # -------------------------------------------------------------------------
    def test_date_normalization(self):
        """Verifies diverse tender date representations normalize into standard ISO 8601 YYYY-MM-DD."""
        date_samples = [
            ("Bid submission ends on 15/08/2026 at 17:00 hrs.", "2026-08-15"),
            ("Notice published on 15-08-2026.", "2026-08-15"),
            ("Tender opening date: 2026-08-15.", "2026-08-15"),
            ("Pre-bid meeting on 15th August 2026 in Conference Hall.", "2026-08-15"),
            ("Technical evaluation starting August 15, 2026.", "2026-08-15"),
            ("Validity up to 15-Aug-2026.", "2026-08-15"),
            ("Deadline is 31/12/2025.", "2025-12-31"),
        ]

        for text, expected_iso in date_samples:
            dates = self.normalizer.extract_dates(text)
            self.assertGreaterEqual(len(dates), 1, f"Failed to extract date from '{text}'")
            self.assertEqual(dates[0].iso_date, expected_iso, f"ISO date mismatch for '{text}'")

    # -------------------------------------------------------------------------
    # 4. WHITESPACE & LINE-BREAK NORMALIZATION
    # -------------------------------------------------------------------------
    def test_whitespace_and_linebreak_cleanup(self):
        """
        Verifies line break cleanup:
        - Repairing words split across hyphenated linebreaks (e.g. 'submis-\nsion')
        - Collapsing excessive tabs/spaces
        - Collapsing 3+ newlines to double newline
        """
        raw_text = (
            "This   is   a    tender   document.\n\n\n\n"
            "All submis-\n"
            "sion files must be   verified with certifi-\n"
            "cate of experience.\r\n\r\n"
            "End of section."
        )
        cleaned = self.normalizer.normalize_whitespace_and_linebreaks(raw_text)

        self.assertNotIn("   ", cleaned)
        self.assertNotIn("\n\n\n", cleaned)
        self.assertIn("submission", cleaned)
        self.assertIn("certificate", cleaned)
        self.assertNotIn("submis-\n", cleaned)
        self.assertNotIn("certifi-\n", cleaned)

    # -------------------------------------------------------------------------
    # 5. UNICODE NORMALIZATION
    # -------------------------------------------------------------------------
    def test_unicode_normalization(self):
        """
        Verifies Unicode normalization:
        - Smart quotes (“ ” ‘ ’) -> ASCII (\" \')
        - Em-dash (—) and en-dash (–) -> standard hyphen (-)
        - Ellipsis (…) -> ...
        - Non-breaking spaces (\u00a0, \u200b) -> ASCII space
        - Rupee symbol (₹) preserved
        """
        raw_unicode = '“Tender Notice” – “Clause 1.2”—‘Scope’… Fee is ₹500\u00a0only.\u200b'
        cleaned = self.normalizer.normalize_unicode(raw_unicode)

        self.assertIn('"Tender Notice"', cleaned)
        self.assertIn("'Scope'", cleaned)
        self.assertIn("...", cleaned)
        self.assertIn("₹500 only.", cleaned)
        self.assertNotIn("\u00a0", cleaned)
        self.assertNotIn("\u200b", cleaned)

    # -------------------------------------------------------------------------
    # 6. TABLE NORMALIZATION
    # -------------------------------------------------------------------------
    def test_table_normalization(self):
        """Verifies table normalization into cleaned cell matrix and structured records dict."""
        raw_table = TableData(
            page_number=1,
            headers=["  Item No.  ", " Description\n ", " Amount (INR) "],
            rows=[
                [" 1 ", " Server  Hardware ", " ₹ 5,00,000 "],
                [" 2 ", " Annual\u00a0Maintenance ", " ₹ 1,50,000 "],
            ],
            row_count=2,
            col_count=3,
        )

        norm_tbl: NormalizedTable = self.normalizer.normalize_table(raw_table, table_index=1)
        self.assertEqual(norm_tbl.table_index, 1)
        self.assertEqual(norm_tbl.headers, ["Item No.", "Description", "Amount (INR)"])
        self.assertEqual(len(norm_tbl.rows), 2)
        self.assertEqual(norm_tbl.rows[0], ["1", "Server Hardware", "₹ 5,00,000"])

        # Check records dict mapping
        self.assertEqual(len(norm_tbl.records), 2)
        self.assertEqual(norm_tbl.records[0]["Item No."], "1")
        self.assertEqual(norm_tbl.records[0]["Description"], "Server Hardware")
        self.assertEqual(norm_tbl.records[1]["Description"], "Annual Maintenance")

    # -------------------------------------------------------------------------
    # 7. WHOLE DOCUMENT NORMALIZATION & SOURCE PRESERVATION
    # -------------------------------------------------------------------------
    def test_whole_document_normalization_preserves_raw_source(self):
        """
        Verifies that DocumentContentNormalizer.normalize_document:
        - Retains 100% untouched raw_text
        - Generates clean normalized_text
        - Preserves 1-indexed page boundaries and section headers
        - Extracts structured currencies, dates, numbers, and tables globally and per-page.
        """
        raw_page1 = (
            "SECTION 1: ELIGIBILITY CRITERIA\n\n"
            "The bidder must have an average annual turnover of at least ₹5 crore.\n"
            "Pre-bid meeting date: 15/08/2026.\n"
        )
        raw_page2 = (
            "SECTION 2: MANDATORY REQUIREMENTS\n\n"
            "Security deposit is INR 50,00,000.\n"
            "Submission deadline: August 30, 2026.\n"
        )
        full_raw = f"{raw_page1}\n\n{raw_page2}"

        extraction_result = ExtractionResult(
            document_id="123e4567-e89b-12d3-a456-426614174000",
            format="PDF",
            status="EXTRACTED",
            page_count=2,
            text=full_raw,
            pages=[
                PageExtractionResult(
                    page_number=1,
                    section_heading="SECTION 1: ELIGIBILITY CRITERIA",
                    text=raw_page1,
                    has_text=True,
                ),
                PageExtractionResult(
                    page_number=2,
                    section_heading="SECTION 2: MANDATORY REQUIREMENTS",
                    text=raw_page2,
                    has_text=True,
                ),
            ],
            requires_ocr=False,
            tables=[],
        )

        norm_doc: NormalizedDocument = self.normalizer.normalize_document(
            extraction_result=extraction_result,
            document_id="123e4567-e89b-12d3-a456-426614174000",
        )

        # 1. Verify original raw_text is completely preserved
        self.assertEqual(norm_doc.raw_text, full_raw)
        self.assertEqual(norm_doc.document_id, "123e4567-e89b-12d3-a456-426614174000")
        self.assertEqual(norm_doc.page_count, 2)

        # 2. Verify Page 1
        p1 = norm_doc.pages[0]
        self.assertEqual(p1.page_number, 1)
        self.assertEqual(p1.section, "SECTION 1: ELIGIBILITY CRITERIA")
        self.assertEqual(p1.raw_text, raw_page1)
        self.assertGreaterEqual(len(p1.currencies), 1)
        self.assertEqual(p1.currencies[0].amount, 50000000.0)
        self.assertGreaterEqual(len(p1.dates), 1)
        self.assertEqual(p1.dates[0].iso_date, "2026-08-15")

        # 3. Verify Page 2
        p2 = norm_doc.pages[1]
        self.assertEqual(p2.page_number, 2)
        self.assertEqual(p2.section, "SECTION 2: MANDATORY REQUIREMENTS")
        self.assertGreaterEqual(len(p2.currencies), 1)
        self.assertEqual(p2.currencies[0].amount, 5000000.0)
        self.assertGreaterEqual(len(p2.dates), 1)
        self.assertEqual(p2.dates[0].iso_date, "2026-08-30")

        # 4. Verify Document-level extracted entities
        self.assertEqual(len(norm_doc.currencies), 2)
        self.assertEqual(len(norm_doc.dates), 2)


if __name__ == "__main__":
    unittest.main()
