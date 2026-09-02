from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class TableData(BaseModel):
    """Structured table representation with page or sheet traceability."""

    page_number: Optional[int] = Field(None, description="1-indexed page where table is located (for PDFs)")
    sheet_name: Optional[str] = Field(None, description="Originating worksheet name (for XLSX)")
    table_index: Optional[int] = Field(None, description="1-indexed sequence order in document")
    headers: List[str] = Field(default_factory=list, description="Extracted table column headers")
    rows: List[List[Optional[str]]] = Field(default_factory=list, description="Matrix of table cell values")
    row_count: int = Field(0, description="Number of rows")
    col_count: int = Field(0, description="Number of columns")


class PageExtractionResult(BaseModel):
    """Extracted textual content and layout metadata for a single PDF page."""

    page_number: int = Field(..., description="1-indexed page number")
    section_heading: Optional[str] = Field(None, description="Identified section heading on this page")
    text: str = Field("", description="Raw extracted text on this page")
    word_count: int = Field(0, description="Total word count on this page")
    char_count: int = Field(0, description="Total character count on this page")
    has_text: bool = Field(False, description="True if usable embedded text exists")
    images_count: int = Field(0, description="Number of embedded image objects detected")
    requires_ocr: bool = Field(False, description="True if page contains insufficient embedded text")
    tables: List[List[Optional[str]]] = Field(default_factory=list, description="Raw tables on this page")


# -----------------------------------------------------------------------------
# DOCX STRUCTURED SCHEMAS
# -----------------------------------------------------------------------------

class DocxParagraph(BaseModel):
    """Structured paragraph in a DOCX document with styling and hierarchy metadata."""

    index: int = Field(..., description="0-indexed sequence position in document")
    text: str = Field(..., description="Paragraph text content")
    style: Optional[str] = Field(None, description="Style identifier (e.g., 'Normal', 'Heading 1', 'Title')")
    is_heading: bool = Field(False, description="True if paragraph represents a heading or title")
    heading_level: Optional[int] = Field(None, description="Heading level integer (1, 2, 3...) if applicable")


class DocxTable(BaseModel):
    """Structured table extracted from a DOCX document."""

    table_index: int = Field(..., description="1-indexed table index in document")
    headers: List[str] = Field(default_factory=list, description="Extracted header row cell values")
    rows: List[List[Optional[str]]] = Field(default_factory=list, description="Matrix of table cell strings")
    row_count: int = Field(0, description="Number of table rows")
    col_count: int = Field(0, description="Number of table columns")


class DocxSection(BaseModel):
    """Document section grouped under a heading or title boundary in DOCX."""

    section_index: int = Field(..., description="1-indexed section position in document")
    heading: Optional[str] = Field(None, description="Section heading title")
    text: str = Field("", description="Aggregated text of paragraphs belonging to this section")
    paragraph_count: int = Field(0, description="Number of paragraphs in this section")


class DocxExtractionResult(BaseModel):
    """Full structured extraction output for a DOCX tender document."""

    format: str = Field("DOCX", description="Document format identifier")
    status: str = Field("EXTRACTED", description="Extraction state (EXTRACTED, FAILED)")
    paragraph_count: int = Field(0, description="Total number of paragraphs")
    table_count: int = Field(0, description="Total number of tables")
    text: str = Field("", description="Aggregated full document plain text")
    paragraphs: List[DocxParagraph] = Field(default_factory=list, description="Sequence of paragraphs")
    tables: List[DocxTable] = Field(default_factory=list, description="Extracted tables")
    sections: List[DocxSection] = Field(default_factory=list, description="Extracted sections")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata properties")
    is_corrupted: bool = Field(False, description="True if file was corrupt or unreadable")
    error_message: Optional[str] = Field(None, description="Error message if extraction failed")


# -----------------------------------------------------------------------------
# XLSX STRUCTURED SCHEMAS
# -----------------------------------------------------------------------------

class XlsxCell(BaseModel):
    """Cell value and coordinate inside a worksheet."""

    coordinate: str = Field(..., description="Cell coordinate (e.g. 'A1', 'C4')")
    row: int = Field(..., description="1-indexed row number")
    col: int = Field(..., description="1-indexed column number")
    value: Optional[Any] = Field(None, description="Typed cell value")
    data_type: str = Field("string", description="Value type (string, number, boolean, formula, empty)")


class XlsxTable(BaseModel):
    """Structured range or table inside an Excel worksheet."""

    table_name: Optional[str] = Field(None, description="Named table identifier")
    sheet_name: str = Field(..., description="Name of worksheet containing this table")
    range_ref: Optional[str] = Field(None, description="Cell coordinate range (e.g. 'A1:E20')")
    headers: List[str] = Field(default_factory=list, description="Header column names")
    rows: List[List[Optional[Any]]] = Field(default_factory=list, description="2D cell values matrix")
    row_count: int = Field(0, description="Total row count")
    col_count: int = Field(0, description="Total column count")


class XlsxWorksheet(BaseModel):
    """Extracted content and tabular structures for a single Excel worksheet."""

    sheet_index: int = Field(..., description="1-indexed sheet order in workbook")
    sheet_name: str = Field(..., description="Sheet tab name")
    row_count: int = Field(0, description="Number of populated rows")
    col_count: int = Field(0, description="Number of populated columns")
    rows: List[List[Optional[Any]]] = Field(default_factory=list, description="2D grid of cell string/numeric values")
    tables: List[XlsxTable] = Field(default_factory=list, description="Structured tables or detected ranges")
    text_summary: str = Field("", description="Human-readable text summary of sheet rows for section detection")


class XlsxExtractionResult(BaseModel):
    """Full structured extraction output for an XLSX workbook."""

    format: str = Field("XLSX", description="Document format identifier")
    status: str = Field("EXTRACTED", description="Extraction state (EXTRACTED, FAILED)")
    sheet_count: int = Field(0, description="Number of worksheets in workbook")
    sheet_names: List[str] = Field(default_factory=list, description="List of sheet names in order")
    sheets: List[XlsxWorksheet] = Field(default_factory=list, description="Worksheet extractions")
    total_rows: int = Field(0, description="Total populated rows across all sheets")
    total_cells: int = Field(0, description="Total populated cells across all sheets")
    text: str = Field("", description="Aggregated textual representation across all worksheets")
    tables: List[TableData] = Field(default_factory=list, description="Aggregated tables mapped to TableData")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Workbook metadata properties")
    is_corrupted: bool = Field(False, description="True if file was corrupt or unreadable")
    error_message: Optional[str] = Field(None, description="Error message if extraction failed")


# -----------------------------------------------------------------------------
# UNIFIED EXTRACTION RESULT
# -----------------------------------------------------------------------------

class ExtractionResult(BaseModel):
    """
    Unified multi-format extraction result supporting PDF, DOCX, XLSX, and Image inputs.
    Preserves format-specific richness while exposing a clean unified interface.
    """

    document_id: Optional[str] = Field(None, description="Optional associated document artifact UUID")
    document_type: Optional[str] = Field(None, description="Document type if classified (e.g. TENDER, PAN, GST)")
    format: str = Field("PDF", description="Originating document format (PDF, DOCX, XLSX, IMAGE)")
    status: str = Field("EXTRACTED", description="Extraction lifecycle status (EXTRACTED, OCR_REQUIRED, FAILED)")
    page_count: int = Field(0, description="Total number of pages or worksheets processed")
    text: str = Field("", description="Aggregated full document text")
    pages: List[PageExtractionResult] = Field(default_factory=list, description="Page-by-page results (for PDF)")
    requires_ocr: bool = Field(False, description="True if entire document or key pages require OCR")
    tables: List[TableData] = Field(default_factory=list, description="Aggregated extracted tables")
    docx_data: Optional[DocxExtractionResult] = Field(None, description="Detailed DOCX structure if format is DOCX")
    xlsx_data: Optional[XlsxExtractionResult] = Field(None, description="Detailed XLSX structure if format is XLSX")
    ocr_data: Optional[Dict[str, Any]] = Field(None, description="Detailed OCR execution payload if OCR was triggered")
    is_corrupted: bool = Field(False, description="True if file was corrupt or unreadable")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted metadata properties")

    def to_traceable_pages(self) -> List[Dict[str, Any]]:
        """
        Provides a unified traceable list of page/sheet segments with 1-indexed references
        and section headers for downstream intelligence modules.
        """
        if self.format == "PDF" and self.pages:
            return [
                {
                    "page_number": p.page_number,
                    "section": p.section_heading or "Document Body",
                    "text": p.text,
                    "tables": [t.model_dump() for t in self.tables if t.page_number == p.page_number],
                }
                for p in self.pages
            ]
        elif self.format == "DOCX" and self.docx_data and self.docx_data.sections:
            return [
                {
                    "page_number": s.section_index,
                    "section": s.heading or f"Section {s.section_index}",
                    "text": s.text,
                    "tables": [t.model_dump() for t in self.tables if t.table_index == s.section_index],
                }
                for s in self.docx_data.sections
            ]
        elif self.format == "XLSX" and self.xlsx_data and self.xlsx_data.sheets:
            return [
                {
                    "page_number": s.sheet_index,
                    "section": f"Sheet: {s.sheet_name}",
                    "text": s.text_summary,
                    "tables": [t.model_dump() for t in self.tables if t.sheet_name == s.sheet_name],
                }
                for s in self.xlsx_data.sheets
            ]
        else:
            return [
                {
                    "page_number": 1,
                    "section": "Document Body",
                    "text": self.text,
                    "tables": [t.model_dump() for t in self.tables],
                }
            ]
