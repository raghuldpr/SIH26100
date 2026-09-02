import io
import logging
import os
import re
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.processing import (
    DocxExtractionResult,
    DocxParagraph,
    DocxSection,
    DocxTable,
    TableData,
)

logger = logging.getLogger("app.services.docx_extractor")

# OpenXML XML Namespaces
NAMESPACES = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "dcterms": "http://purl.org/dc/terms/",
}


class DOCXExtractor:
    """
    Deterministic DOCX text and document structure extractor.
    Parses OpenXML WordprocessingML packages using secure XML stream parsing,
    preserving paragraph hierarchy, heading levels, tabular data, and metadata.
    """

    def _extract_text_from_node(self, node: ET.Element) -> str:
        """Extracts text fragments from all text runs (<w:t>) in an XML subtree."""
        texts: List[str] = []
        for elem in node.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "t" and elem.text:
                texts.append(elem.text)
            elif tag == "tab":
                texts.append("\t")
            elif tag in ("br", "cr"):
                texts.append("\n")
        return "".join(texts).strip()

    def _extract_metadata(self, zf: zipfile.ZipFile) -> Dict[str, Any]:
        """Extracts core Dublin Core and OpenXML document properties."""
        metadata: Dict[str, Any] = {}
        if "docProps/core.xml" in zf.namelist():
            try:
                core_xml = zf.read("docProps/core.xml")
                root = ET.fromstring(core_xml)
                for child in root:
                    tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if child.text and child.text.strip():
                        metadata[tag_name] = child.text.strip()
            except Exception as e:
                logger.debug(f"Failed to parse docProps/core.xml: {e}")
        return metadata

    def extract(self, file_bytes: bytes, filename: Optional[str] = None) -> DocxExtractionResult:
        """
        Deterministically extracts structured paragraphs, headings, tables,
        and sections from a DOCX binary payload.
        """
        if not file_bytes:
            return DocxExtractionResult(
                status="FAILED",
                is_corrupted=True,
                error_message="Empty DOCX byte stream provided.",
            )

        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
                # 1. Verify ZIP archive integrity
                if zf.testzip() is not None:
                    return DocxExtractionResult(
                        status="FAILED",
                        is_corrupted=True,
                        error_message="DOCX ZIP archive is corrupted or contains damaged components.",
                    )

                namelist = zf.namelist()
                if "word/document.xml" not in namelist:
                    return DocxExtractionResult(
                        status="FAILED",
                        is_corrupted=True,
                        error_message="Invalid DOCX: missing main word/document.xml payload.",
                    )

                # 2. Extract metadata
                metadata = self._extract_metadata(zf)

                # 3. Parse main document XML
                doc_xml_bytes = zf.read("word/document.xml")
                root = ET.fromstring(doc_xml_bytes)

                # Find <w:body>
                body = root.find("w:body", NAMESPACES)
                if body is None:
                    # Fallback if namespace prefix resolution differs
                    for child in root:
                        if child.tag.endswith("body"):
                            body = child
                            break

                if body is None:
                    return DocxExtractionResult(
                        status="EXTRACTED",
                        paragraph_count=0,
                        table_count=0,
                        text="",
                        paragraphs=[],
                        tables=[],
                        sections=[],
                        metadata=metadata,
                        is_corrupted=False,
                    )

                paragraphs: List[DocxParagraph] = []
                tables: List[DocxTable] = []
                sections: List[DocxSection] = []
                full_text_fragments: List[str] = []

                current_section_heading: Optional[str] = None
                current_section_paras: List[DocxParagraph] = []
                section_counter = 1
                para_counter = 0
                table_counter = 0

                for element in body:
                    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

                    if tag == "p":
                        para_text = self._extract_text_from_node(element)
                        if not para_text:
                            continue

                        # Inspect paragraph properties for styles and headings
                        p_style = None
                        is_heading = False
                        heading_level = None

                        p_pr = element.find("w:pPr", NAMESPACES)
                        if p_pr is not None:
                            style_elem = p_pr.find("w:pStyle", NAMESPACES)
                            if style_elem is not None:
                                for k, v in style_elem.attrib.items():
                                    if k.endswith("val") or k == "val":
                                        p_style = v
                                        break

                        if p_style:
                            style_lower = p_style.lower()
                            if "heading" in style_lower or "title" in style_lower or "header" in style_lower:
                                is_heading = True
                                level_match = re.search(r"\d+", style_lower)
                                heading_level = int(level_match.group(0)) if level_match else 1
                        else:
                            # Heuristic check for capitalized section headings in text
                            if len(para_text) < 120 and (
                                para_text.isupper()
                                or re.match(r"^(?:SECTION|PART|CHAPTER|CLAUSE|ANNEXURE|ELIGIBILITY|SCOPE|TERMS)", para_text, re.IGNORECASE)
                            ):
                                is_heading = True
                                heading_level = 1

                        p_obj = DocxParagraph(
                            index=para_counter,
                            text=para_text,
                            style=p_style,
                            is_heading=is_heading,
                            heading_level=heading_level,
                        )
                        paragraphs.append(p_obj)
                        full_text_fragments.append(para_text)
                        para_counter += 1

                        # Section boundary handling
                        if is_heading:
                            if current_section_paras:
                                sec_text = "\n".join(p.text for p in current_section_paras)
                                sections.append(
                                    DocxSection(
                                        section_index=section_counter,
                                        heading=current_section_heading,
                                        text=sec_text,
                                        paragraph_count=len(current_section_paras),
                                    )
                                )
                                section_counter += 1
                                current_section_paras = []
                            current_section_heading = para_text

                        current_section_paras.append(p_obj)

                    elif tag == "tbl":
                        table_counter += 1
                        table_rows: List[List[Optional[str]]] = []

                        for row_elem in element:
                            row_tag = row_elem.tag.split("}")[-1] if "}" in row_elem.tag else row_elem.tag
                            if row_tag == "tr":
                                cell_texts: List[Optional[str]] = []
                                for cell_elem in row_elem:
                                    cell_tag = cell_elem.tag.split("}")[-1] if "}" in cell_elem.tag else cell_elem.tag
                                    if cell_tag == "tc":
                                        c_text = self._extract_text_from_node(cell_elem)
                                        cell_texts.append(c_text if c_text else None)
                                if cell_texts:
                                    table_rows.append(cell_texts)

                        if table_rows:
                            headers = [str(h) if h else "" for h in table_rows[0]]
                            col_count = max(len(r) for r in table_rows) if table_rows else 0
                            tbl_obj = DocxTable(
                                table_index=table_counter,
                                headers=headers,
                                rows=table_rows,
                                row_count=len(table_rows),
                                col_count=col_count,
                            )
                            tables.append(tbl_obj)

                            # Format table in text stream
                            tbl_str = "\n".join(" | ".join(str(c or "") for c in row) for row in table_rows)
                            full_text_fragments.append(f"\n[TABLE {table_counter}]\n{tbl_str}\n")

                # Flush trailing section
                if current_section_paras:
                    sec_text = "\n".join(p.text for p in current_section_paras)
                    sections.append(
                        DocxSection(
                            section_index=section_counter,
                            heading=current_section_heading or "Document Body",
                            text=sec_text,
                            paragraph_count=len(current_section_paras),
                        )
                    )

                combined_text = "\n\n".join(full_text_fragments)

                return DocxExtractionResult(
                    format="DOCX",
                    status="EXTRACTED",
                    paragraph_count=len(paragraphs),
                    table_count=len(tables),
                    text=combined_text,
                    paragraphs=paragraphs,
                    tables=tables,
                    sections=sections,
                    metadata=metadata,
                    is_corrupted=False,
                    error_message=None,
                )

        except Exception as exc:
            logger.error(f"DOCX extraction error for '{filename or 'unknown'}': {exc}", exc_info=True)
            return DocxExtractionResult(
                format="DOCX",
                status="FAILED",
                is_corrupted=True,
                error_message=f"DOCX extraction failure: {str(exc)}",
            )


# Default singleton instance
docx_extractor = DOCXExtractor()
