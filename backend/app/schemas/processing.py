from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TableData(BaseModel):
    """Extracted table representation."""

    page_number: int = Field(..., description="1-indexed page where table is located")
    rows: List[List[Optional[str]]] = Field(default_factory=list, description="Matrix of table cell values")
    row_count: int = Field(0, description="Number of rows")
    col_count: int = Field(0, description="Number of columns")


class PageExtractionResult(BaseModel):
    """Extracted textual content and layout metadata for a single PDF page."""

    page_number: int = Field(..., description="1-indexed page number")
    text: str = Field("", description="Raw extracted text on this page")
    word_count: int = Field(0, description="Total word count on this page")
    char_count: int = Field(0, description="Total character count on this page")
    has_text: bool = Field(False, description="True if usable embedded text exists")
    images_count: int = Field(0, description="Number of embedded image objects detected")
    requires_ocr: bool = Field(False, description="True if page contains insufficient embedded text")
    tables: List[List[Optional[str]]] = Field(default_factory=list, description="Raw tables on this page")


class ExtractionResult(BaseModel):
    """Overall document text extraction result."""

    document_type: Optional[str] = Field(None, description="Document type if classified")
    page_count: int = Field(0, description="Total number of pages processed")
    text: str = Field("", description="Aggregated full document text")
    pages: List[PageExtractionResult] = Field(default_factory=list, description="Page-by-page results")
    requires_ocr: bool = Field(False, description="True if entire document or key pages require OCR")
    tables: List[TableData] = Field(default_factory=list, description="Aggregated extracted tables")
    is_corrupted: bool = Field(False, description="True if file was corrupt or unreadable")
    error_message: Optional[str] = Field(None, description="Error message if processing failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extracted PDF metadata (Author, Producer, etc.)")
