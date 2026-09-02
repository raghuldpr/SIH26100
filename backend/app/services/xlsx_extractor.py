import io
import logging
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.processing import (
    TableData,
    XlsxCell,
    XlsxExtractionResult,
    XlsxTable,
    XlsxWorksheet,
)

logger = logging.getLogger("app.services.xlsx_extractor")

# OpenXML SpreadsheetML XML Namespaces
NAMESPACES = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
}


def col_letter_to_index(col_str: str) -> int:
    """Converts Excel column letter (e.g. 'A' -> 0, 'B' -> 1, 'Z' -> 25, 'AA' -> 26)."""
    idx = 0
    for char in col_str.upper():
        if "A" <= char <= "Z":
            idx = idx * 26 + (ord(char) - ord("A") + 1)
    return max(0, idx - 1)


class XLSXExtractor:
    """
    Deterministic XLSX spreadsheet and BOQ tabular extractor.
    Parses OpenXML SpreadsheetML packages, shared strings tables,
    cell coordinates, typed numeric/text values, and structured worksheet tables.
    """

    def _parse_shared_strings(self, zf: zipfile.ZipFile) -> List[str]:
        """Parses xl/sharedStrings.xml into a string index list."""
        if "xl/sharedStrings.xml" not in zf.namelist():
            return []

        shared_strings: List[str] = []
        try:
            xml_bytes = zf.read("xl/sharedStrings.xml")
            root = ET.fromstring(xml_bytes)
            for si in root.iter():
                tag = si.tag.split("}")[-1] if "}" in si.tag else si.tag
                if tag == "si":
                    # Collect all <t> within this <si>
                    t_parts: List[str] = []
                    for child in si.iter():
                        c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                        if c_tag == "t" and child.text:
                            t_parts.append(child.text)
                    shared_strings.append("".join(t_parts))
        except Exception as e:
            logger.debug(f"Failed to parse xl/sharedStrings.xml: {e}")
        return shared_strings

    def _parse_workbook_sheets(self, zf: zipfile.ZipFile) -> List[Tuple[str, str]]:
        """
        Parses xl/workbook.xml and relationships to retrieve sheet names and their file paths in order.
        Returns list of (sheet_name, zip_path).
        """
        sheets_info: List[Tuple[str, str]] = []
        if "xl/workbook.xml" not in zf.namelist():
            # Fallback: find all sheet*.xml files in xl/worksheets/
            sheet_files = [f for f in zf.namelist() if f.startswith("xl/worksheets/sheet") and f.endswith(".xml")]
            for idx, f in enumerate(sorted(sheet_files)):
                sheets_info.append((f"Sheet{idx + 1}", f))
            return sheets_info

        # 1. Parse relationship map (rId -> target)
        rel_map: Dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in zf.namelist():
            try:
                rels_xml = zf.read("xl/_rels/workbook.xml.rels")
                root_rels = ET.fromstring(rels_xml)
                for rel in root_rels.iter():
                    if rel.tag.endswith("Relationship"):
                        r_id = rel.attrib.get("Id")
                        target = rel.attrib.get("Target", "")
                        if r_id and target:
                            # Normalize target path relative to xl/
                            if not target.startswith("xl/"):
                                if target.startswith("/"):
                                    target = target.lstrip("/")
                                elif target.startswith("worksheets/"):
                                    target = f"xl/{target}"
                                else:
                                    target = f"xl/worksheets/{target}"
                            rel_map[r_id] = target
            except Exception as e:
                logger.debug(f"Failed to parse xl/_rels/workbook.xml.rels: {e}")

        # 2. Parse workbook.xml sheets
        try:
            wb_xml = zf.read("xl/workbook.xml")
            root_wb = ET.fromstring(wb_xml)
            for elem in root_wb.iter():
                if elem.tag.endswith("sheet"):
                    s_name = elem.attrib.get("name", "Sheet")
                    # r:id attribute
                    r_id = None
                    for k, v in elem.attrib.items():
                        if k.endswith("id") or k == "id":
                            r_id = v
                            break

                    target_file = rel_map.get(r_id, "") if r_id else ""
                    if not target_file:
                        target_file = f"xl/worksheets/sheet{len(sheets_info) + 1}.xml"

                    sheets_info.append((s_name, target_file))
        except Exception as e:
            logger.debug(f"Failed to parse xl/workbook.xml: {e}")

        # Fallback if empty
        if not sheets_info:
            sheet_files = [f for f in zf.namelist() if f.startswith("xl/worksheets/sheet") and f.endswith(".xml")]
            for idx, f in enumerate(sorted(sheet_files)):
                sheets_info.append((f"Sheet{idx + 1}", f))

        return sheets_info

    def _parse_worksheet_grid(
        self,
        xml_bytes: bytes,
        shared_strings: List[str],
        sheet_name: str,
        sheet_index: int,
    ) -> XlsxWorksheet:
        """Parses raw worksheet XML into a 2D grid matrix of rows and columns."""
        root = ET.fromstring(xml_bytes)

        # Dictionary of row_idx -> dict of col_idx -> value
        grid_data: Dict[int, Dict[int, Any]] = {}
        max_row = 0
        max_col = 0

        for row_elem in root.iter():
            if row_elem.tag.endswith("row"):
                r_num_str = row_elem.attrib.get("r")
                row_idx = int(r_num_str) - 1 if (r_num_str and r_num_str.isdigit()) else max_row

                if row_idx not in grid_data:
                    grid_data[row_idx] = {}
                max_row = max(max_row, row_idx + 1)

                curr_col_idx = 0
                for cell_elem in row_elem.iter():
                    if cell_elem.tag.endswith("c"):
                        cell_ref = cell_elem.attrib.get("r", "")
                        cell_type = cell_elem.attrib.get("t", "n")  # default number

                        if cell_ref:
                            # Extract column letters (e.g. 'A1' -> 'A')
                            col_letters = "".join(filter(str.isalpha, cell_ref))
                            col_idx = col_letter_to_index(col_letters) if col_letters else curr_col_idx
                        else:
                            col_idx = curr_col_idx

                        max_col = max(max_col, col_idx + 1)
                        curr_col_idx = col_idx + 1

                        # Extract cell value
                        val_elem = None
                        for child in cell_elem:
                            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                            if tag == "v":
                                val_elem = child
                                break
                            elif tag == "is":  # inline string
                                for sub in child.iter():
                                    if sub.tag.endswith("t") and sub.text:
                                        val_elem = sub
                                        break

                        cell_val: Any = None
                        if val_elem is not None and val_elem.text is not None:
                            raw_val = val_elem.text.strip()
                            if cell_type == "s" and raw_val.isdigit():
                                s_idx = int(raw_val)
                                cell_val = shared_strings[s_idx] if s_idx < len(shared_strings) else raw_val
                            elif cell_type == "b":
                                cell_val = raw_val == "1"
                            elif cell_type == "e":
                                cell_val = f"ERROR:{raw_val}"
                            else:
                                # Try numeric conversion
                                try:
                                    if "." in raw_val:
                                        cell_val = float(raw_val)
                                    else:
                                        cell_val = int(raw_val)
                                except ValueError:
                                    cell_val = raw_val

                        if cell_val is not None and str(cell_val).strip():
                            grid_data[row_idx][col_idx] = cell_val

        # Convert grid dictionary into 2D row array, trimming empty outer margins
        matrix: List[List[Optional[Any]]] = []
        for r in range(max_row):
            if r in grid_data and grid_data[r]:
                row_vals = [grid_data[r].get(c, None) for c in range(max_col)]
                # Check if row has any non-null content
                if any(v is not None for v in row_vals):
                    matrix.append(row_vals)

        # Build table metadata
        headers: List[str] = []
        if matrix:
            headers = [str(cell) if cell is not None else f"Column_{idx + 1}" for idx, cell in enumerate(matrix[0])]

        table_obj = XlsxTable(
            table_name=f"{sheet_name}_Table",
            sheet_name=sheet_name,
            headers=headers,
            rows=matrix,
            row_count=len(matrix),
            col_count=max_col,
        )

        # Build clean textual representation
        text_lines: List[str] = [f"=== SHEET: {sheet_name} ==="]
        for row in matrix:
            row_str = " | ".join(str(c) if c is not None else "" for c in row).strip()
            if row_str:
                text_lines.append(row_str)

        return XlsxWorksheet(
            sheet_index=sheet_index,
            sheet_name=sheet_name,
            row_count=len(matrix),
            col_count=max_col,
            rows=matrix,
            tables=[table_obj] if matrix else [],
            text_summary="\n".join(text_lines),
        )

    def extract(self, file_bytes: bytes, filename: Optional[str] = None) -> XlsxExtractionResult:
        """
        Deterministically extracts structured worksheets, rows, cells, and BOQ tables
        from an XLSX binary payload.
        """
        if not file_bytes:
            return XlsxExtractionResult(
                status="FAILED",
                is_corrupted=True,
                error_message="Empty XLSX byte stream provided.",
            )

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                # 1. Verify ZIP archive integrity
                if zf.testzip() is not None:
                    return XlsxExtractionResult(
                        status="FAILED",
                        is_corrupted=True,
                        error_message="XLSX ZIP archive is corrupted or contains damaged components.",
                    )

                # 2. Parse shared strings table
                shared_strings = self._parse_shared_strings(zf)

                # 3. Discover worksheets
                sheets_info = self._parse_workbook_sheets(zf)
                if not sheets_info:
                    return XlsxExtractionResult(
                        status="FAILED",
                        is_corrupted=True,
                        error_message="Invalid XLSX: no worksheets found in workbook.",
                    )

                worksheets: List[XlsxWorksheet] = []
                all_tables: List[TableData] = []
                full_text_fragments: List[str] = []
                total_rows = 0
                total_cells = 0

                for idx, (s_name, s_path) in enumerate(sheets_info):
                    sheet_num = idx + 1
                    if s_path in zf.namelist():
                        sheet_xml = zf.read(s_path)
                        ws = self._parse_worksheet_grid(
                            xml_bytes=sheet_xml,
                            shared_strings=shared_strings,
                            sheet_name=s_name,
                            sheet_index=sheet_num,
                        )
                        worksheets.append(ws)
                        total_rows += ws.row_count

                        # Count populated cells
                        for row in ws.rows:
                            total_cells += sum(1 for c in row if c is not None)

                        if ws.text_summary:
                            full_text_fragments.append(ws.text_summary)

                        # Map to TableData for unified table extraction representation
                        if ws.rows:
                            str_rows = [
                                [str(cell) if cell is not None else None for cell in row]
                                for row in ws.rows
                            ]
                            all_tables.append(
                                TableData(
                                    sheet_name=s_name,
                                    table_index=sheet_num,
                                    headers=[str(h) for h in str_rows[0]] if str_rows else [],
                                    rows=str_rows,
                                    row_count=len(str_rows),
                                    col_count=ws.col_count,
                                )
                            )

                combined_text = "\n\n".join(full_text_fragments)

                return XlsxExtractionResult(
                    format="XLSX",
                    status="EXTRACTED",
                    sheet_count=len(worksheets),
                    sheet_names=[ws.sheet_name for ws in worksheets],
                    sheets=worksheets,
                    total_rows=total_rows,
                    total_cells=total_cells,
                    text=combined_text,
                    tables=all_tables,
                    metadata={},
                    is_corrupted=False,
                    error_message=None,
                )

        except Exception as exc:
            logger.error(f"XLSX extraction error for '{filename or 'unknown'}': {exc}", exc_info=True)
            return XlsxExtractionResult(
                format="XLSX",
                status="FAILED",
                is_corrupted=True,
                error_message=f"XLSX extraction failure: {str(exc)}",
            )


# Default singleton instance
xlsx_extractor = XLSXExtractor()
