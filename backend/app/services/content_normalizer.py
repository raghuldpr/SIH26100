import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple, Union

from app.schemas.normalized_content import (
    NormalizedCurrency,
    NormalizedDate,
    NormalizedDocument,
    NormalizedNumber,
    NormalizedPage,
    NormalizedTable,
)
from app.schemas.processing import ExtractionResult, TableData

logger = logging.getLogger("app.services.content_normalizer")

# Month string to integer mapping
MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def format_indian_number(num: Union[int, float]) -> str:
    """
    Formats a numeric value using the Indian numbering system grouping.
    e.g. 50000000 -> '5,00,00,000', 1500000 -> '15,00,000', 50000 -> '50,000'.
    """
    if isinstance(num, float) and not num.is_integer():
        int_part = str(int(num))
        dec_part = f".{str(round(num, 4)).split('.', 1)[1]}"
    else:
        int_part = str(int(round(num)))
        dec_part = ""

    if len(int_part) <= 3:
        return int_part + dec_part

    last_three = int_part[-3:]
    remaining = int_part[:-3]
    groups: List[str] = []
    while len(remaining) > 2:
        groups.insert(0, remaining[-2:])
        remaining = remaining[:-2]
    if remaining:
        groups.insert(0, remaining)
    groups.append(last_three)
    return ",".join(groups) + dec_part


def format_standard_number(num: Union[int, float]) -> str:
    """Formats numeric value with standard Western 3-digit comma grouping."""
    if isinstance(num, float) and not num.is_integer():
        return f"{num:,.2f}"
    return f"{int(round(num)):,}"


class DocumentContentNormalizer:
    """
    Deterministic Document Content Normalization Engine for SIH-26100 (Phase 11.5).
    Performs Unicode normalization, whitespace deduplication, hyphenated line-break cleanup,
    standardized currency/date/number parsing, and table normalization while preserving
    original raw source text and 1-indexed page/section traceability.
    """

    # Matches Indian & International currency representations:
    # ₹5 crore, ₹5,00,00,000, INR 50,000,000, Rs. 50 Lakhs, Rs 15,00,000, 50k, 1.5 Cr
    CURRENCY_REGEX = re.compile(
        r"(?:(₹|Rs\.?|INR)\s*)?(\d+(?:,\d+)*(?:\.\d+)?)\s*(crores?|cr|lakhs?|lacs?|lac|thousand|k|million|m)?\b",
        re.IGNORECASE,
    )

    # Date regex patterns:
    DATE_PATTERNS = [
        # 1. DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
        (
            re.compile(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b"),
            lambda m: (int(m.group(3)), int(m.group(2)), int(m.group(1))),
        ),
        # 2. YYYY-MM-DD (ISO)
        (
            re.compile(r"\b(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})\b"),
            lambda m: (int(m.group(1)), int(m.group(2)), int(m.group(3))),
        ),
        # 3. 15th August 2026, 15 Aug 2026, 15-Aug-2026
        (
            re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?[\s\-]+([A-Za-z]+)[\s\-]+(\d{4})\b", re.IGNORECASE),
            lambda m: (int(m.group(3)), MONTH_MAP.get(m.group(2).lower()[:3], 0), int(m.group(1))),
        ),
        # 4. August 15, 2026, Aug 15 2026
        (
            re.compile(r"\b([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?[\s,]+(\d{4})\b", re.IGNORECASE),
            lambda m: (int(m.group(3)), MONTH_MAP.get(m.group(1).lower()[:3], 0), int(m.group(2))),
        ),
    ]

    def normalize_unicode(self, text: str) -> str:
        """
        Normalizes Unicode characters into standard compatibility NFKC form.
        Converts smart quotes, typographic dashes, non-breaking spaces,
        and zero-width characters to standard ASCII equivalents while preserving ₹.
        """
        if not text:
            return ""

        # NFKC compatibility decomposition
        norm = unicodedata.normalize("NFKC", text)

        # Smart quotes and apostrophes
        norm = norm.replace("“", '"').replace("”", '"').replace("„", '"').replace("‟", '"')
        norm = norm.replace("‘", "'").replace("’", "'").replace("‚", "'").replace("‛", "'").replace("`", "'")

        # Typographic dashes and bars
        norm = norm.replace("—", "-").replace("–", "-").replace("―", "-").replace("‒", "-")

        # Ellipsis
        norm = norm.replace("…", "...")

        # Non-breaking and zero-width spaces
        for sp in ("\u00a0", "\u200b", "\u200c", "\u200d", "\ufeff", "\u2007", "\u2009", "\u202f", "\u2001", "\u2002", "\u2003"):
            norm = norm.replace(sp, " ")

        return norm

    def normalize_whitespace_and_linebreaks(self, text: str) -> str:
        """
        Cleans up line breaks, collapses multiple consecutive spaces/tabs,
        repairs hyphenated word breaks split across lines, and standardizes paragraph gaps.
        """
        if not text:
            return ""

        # 1. Normalize carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Repair hyphenated line breaks (e.g. 'submis-\nsion' -> 'submission')
        text = re.sub(r"(\b[a-zA-Z]{2,})-\n\s*([a-zA-Z]{2,}\b)", r"\1\2", text)

        # 3. Strip spaces around line breaks
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n[ \t]+", "\n", text)

        # 4. Collapse repeated horizontal spaces and tabs into a single space
        text = re.sub(r"[ \t]+", " ", text)

        # 5. Collapse 3 or more consecutive newlines into 2 (standard paragraph break)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def normalize_text(self, text: str) -> str:
        """Applies full Unicode and whitespace/line-break normalization pipeline."""
        if not text:
            return ""
        norm_unicode = self.normalize_unicode(text)
        return self.normalize_whitespace_and_linebreaks(norm_unicode)

    def extract_currencies(self, text: str) -> List[NormalizedCurrency]:
        """
        Deterministically extracts and normalizes all monetary expressions
        (INR, ₹, Rs., Lakhs, Crores, Million, etc.) into canonical INR values.
        """
        if not text:
            return []

        results: List[NormalizedCurrency] = []
        seen_spans = set()

        for m in self.CURRENCY_REGEX.finditer(text):
            raw_match = m.group(0).strip()
            sym = (m.group(1) or "").strip()
            num_str = m.group(2)
            unit_str = (m.group(3) or "").lower()

            if not num_str:
                continue

            has_sym = bool(sym)
            has_unit = bool(unit_str)

            # Must have either a currency indicator or an explicit unit (e.g. crore, lakh)
            if not (has_sym or has_unit):
                continue

            try:
                num_val = float(num_str.replace(",", "").strip())
            except ValueError:
                continue

            # Filter standalone years (e.g. 2024, 2025) unless currency symbol is explicit
            if not has_sym and not has_unit and 1900 <= num_val <= 2100:
                continue

            # Determine multiplier
            if "crore" in unit_str or "cr" in unit_str:
                multiplier = 10000000.0
                unit_label = "crore"
            elif "lakh" in unit_str or "lac" in unit_str:
                multiplier = 100000.0
                unit_label = "lakh"
            elif "million" in unit_str or unit_str == "m":
                multiplier = 1000000.0
                unit_label = "million"
            elif "thousand" in unit_str or unit_str == "k":
                multiplier = 1000.0
                unit_label = "thousand"
            else:
                multiplier = 1.0
                unit_label = None

            amount = round(num_val * multiplier, 2)
            formatted_canonical = f"INR {format_standard_number(amount)}"

            span = (m.start(), m.end())
            if span not in seen_spans:
                seen_spans.add(span)
                results.append(
                    NormalizedCurrency(
                        raw=raw_match,
                        amount=amount,
                        currency="INR",
                        formatted=formatted_canonical,
                        unit=unit_label,
                    )
                )

        return results

    def extract_dates(self, text: str) -> List[NormalizedDate]:
        """
        Deterministically extracts and normalizes dates from diverse formats
        into canonical ISO 8601 YYYY-MM-DD.
        """
        if not text:
            return []

        results: List[NormalizedDate] = []
        seen_raw = set()

        for pattern, parse_fn in self.DATE_PATTERNS:
            for m in pattern.finditer(text):
                raw_match = m.group(0).strip()
                if raw_match in seen_raw:
                    continue

                try:
                    year, month, day = parse_fn(m)
                    # Validate date boundaries
                    if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                        iso_str = f"{year:04d}-{month:02d}-{day:02d}"
                        seen_raw.add(raw_match)
                        results.append(
                            NormalizedDate(
                                raw=raw_match,
                                iso_date=iso_str,
                                year=year,
                                month=month,
                                day=day,
                            )
                        )
                except Exception:
                    continue

        return results

    def extract_numbers(self, text: str) -> List[NormalizedNumber]:
        """
        Extracts formatted numbers (including Indian and Western comma groupings).
        """
        if not text:
            return []

        # Matches numbers formatted with commas or decimals (e.g. 5,00,00,000 or 50,000,000)
        pattern = re.compile(r"\b(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?)\b")
        results: List[NormalizedNumber] = []
        seen = set()

        for m in pattern.finditer(text):
            raw_str = m.group(1).strip()
            if raw_str in seen:
                continue

            # Must contain a comma or decimal to be a formatted number
            if "," not in raw_str and "." not in raw_str:
                continue

            try:
                clean_num = float(raw_str.replace(",", ""))
                is_int = clean_num.is_integer()
                seen.add(raw_str)
                results.append(
                    NormalizedNumber(
                        raw=raw_str,
                        value=int(clean_num) if is_int else clean_num,
                        is_integer=is_int,
                        formatted_standard=format_standard_number(clean_num),
                        formatted_indian=format_indian_number(clean_num),
                    )
                )
            except ValueError:
                continue

        return results

    def normalize_table(self, table: TableData, table_index: int = 1) -> NormalizedTable:
        """
        Normalizes a raw extracted table by cleaning headers, stripping cells,
        and building structured row record mappings.
        """
        cleaned_headers = [self.normalize_text(h) for h in (table.headers or [])]
        cleaned_rows: List[List[str]] = []
        records: List[Dict[str, Any]] = []

        for row in (table.rows or []):
            cleaned_row = [self.normalize_text(str(cell) if cell is not None else "") for cell in row]
            if any(cleaned_row):
                cleaned_rows.append(cleaned_row)

                # Map to structured record dictionary
                if cleaned_headers:
                    rec: Dict[str, Any] = {}
                    for idx, h in enumerate(cleaned_headers):
                        rec[h or f"Column_{idx + 1}"] = cleaned_row[idx] if idx < len(cleaned_row) else ""
                    records.append(rec)

        col_count = max(len(cleaned_headers), max((len(r) for r in cleaned_rows), default=0))

        return NormalizedTable(
            table_index=table_index,
            page_number=table.page_number,
            sheet_name=table.sheet_name,
            headers=cleaned_headers,
            rows=cleaned_rows,
            records=records,
            row_count=len(cleaned_rows),
            col_count=col_count,
        )

    def normalize_document(
        self,
        extraction_result: ExtractionResult,
        document_id: Optional[str] = None,
    ) -> NormalizedDocument:
        """
        Main pipeline method: transforms a raw ExtractionResult into a NormalizedDocument,
        preserving untouched raw source text alongside normalized content, page references,
        and structured values.
        """
        raw_full_text = extraction_result.text or ""
        normalized_full_text = self.normalize_text(raw_full_text)

        # Process traceable pages / sheets
        traceable_pages = extraction_result.to_traceable_pages()
        normalized_pages: List[NormalizedPage] = []
        all_currencies: List[NormalizedCurrency] = []
        all_dates: List[NormalizedDate] = []
        all_numbers: List[NormalizedNumber] = []
        all_tables: List[NormalizedTable] = []

        for idx, page_dict in enumerate(traceable_pages):
            page_num = page_dict.get("page_number", idx + 1)
            section = page_dict.get("section")
            page_raw = page_dict.get("text", "")
            page_norm = self.normalize_text(page_raw)

            # Extract structured items for this page
            page_currencies = self.extract_currencies(page_norm)
            page_dates = self.extract_dates(page_norm)
            page_numbers = self.extract_numbers(page_norm)

            # Process tables for this page
            raw_tables = page_dict.get("tables", [])
            page_tables: List[NormalizedTable] = []
            for t_idx, raw_t in enumerate(raw_tables):
                t_obj = TableData(**raw_t) if isinstance(raw_t, dict) else raw_t
                norm_tbl = self.normalize_table(t_obj, table_index=len(all_tables) + t_idx + 1)
                page_tables.append(norm_tbl)
                all_tables.append(norm_tbl)

            all_currencies.extend(page_currencies)
            all_dates.extend(page_dates)
            all_numbers.extend(page_numbers)

            normalized_pages.append(
                NormalizedPage(
                    page_number=page_num,
                    section=section,
                    raw_text=page_raw,
                    normalized_text=page_norm,
                    tables=page_tables,
                    currencies=page_currencies,
                    dates=page_dates,
                    numbers=page_numbers,
                )
            )

        # Global deduplication of currencies and dates across document
        unique_currencies: List[NormalizedCurrency] = []
        seen_curr = set()
        for c in all_currencies:
            key = (c.raw, c.amount)
            if key not in seen_curr:
                seen_curr.add(key)
                unique_currencies.append(c)

        unique_dates: List[NormalizedDate] = []
        seen_dates = set()
        for d in all_dates:
            if d.raw not in seen_dates:
                seen_dates.add(d.raw)
                unique_dates.append(d)

        unique_numbers: List[NormalizedNumber] = []
        seen_nums = set()
        for n in all_numbers:
            if n.raw not in seen_nums:
                seen_nums.add(n.raw)
                unique_numbers.append(n)

        # If document has top-level tables that were not in pages
        if not all_tables and extraction_result.tables:
            for t_idx, t in enumerate(extraction_result.tables):
                all_tables.append(self.normalize_table(t, table_index=t_idx + 1))

        return NormalizedDocument(
            document_id=document_id or extraction_result.document_id,
            format=extraction_result.format,
            raw_text=raw_full_text,
            normalized_text=normalized_full_text,
            page_count=len(normalized_pages) if normalized_pages else extraction_result.page_count,
            pages=normalized_pages,
            tables=all_tables,
            currencies=unique_currencies,
            dates=unique_dates,
            numbers=unique_numbers,
            sections=[{"page_number": p.page_number, "section": p.section} for p in normalized_pages if p.section],
            metadata=extraction_result.metadata,
        )


# Default singleton instance
content_normalizer = DocumentContentNormalizer()
