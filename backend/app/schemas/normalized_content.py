from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class NormalizedCurrency(BaseModel):
    """Standardized monetary expression representation."""

    raw: str = Field(..., description="Original raw currency string from document (e.g. '₹5 crore')")
    amount: float = Field(..., description="Normalized numerical amount in INR (e.g. 50000000.0)")
    currency: str = Field("INR", description="ISO currency code")
    formatted: str = Field(..., description="Canonical formatted string representation (e.g. 'INR 50,000,000')")
    unit: Optional[str] = Field(None, description="Original unit suffix if present (e.g. 'crore', 'lakh')")


class NormalizedDate(BaseModel):
    """Standardized ISO date expression representation."""

    raw: str = Field(..., description="Original raw date string from document (e.g. '15th August 2026')")
    iso_date: str = Field(..., description="Standard ISO-8601 formatted date (YYYY-MM-DD)")
    year: int = Field(..., description="Calendar year")
    month: int = Field(..., description="Calendar month (1-12)")
    day: int = Field(..., description="Calendar day (1-31)")


class NormalizedNumber(BaseModel):
    """Standardized numeric value extracted from document content."""

    raw: str = Field(..., description="Original number string (e.g. '5,00,00,000')")
    value: Union[int, float] = Field(..., description="Numerical value (e.g. 50000000)")
    is_integer: bool = Field(True, description="True if value represents an integer")
    formatted_standard: str = Field(..., description="Western comma-grouped format (e.g. '50,000,000')")
    formatted_indian: str = Field(..., description="Indian numbering system format (e.g. '5,00,00,000')")


class NormalizedTable(BaseModel):
    """Cleaned and normalized tabular structure with records dictionary representation."""

    table_index: int = Field(..., description="1-indexed sequence order in document")
    page_number: Optional[int] = Field(None, description="1-indexed page reference for PDF")
    sheet_name: Optional[str] = Field(None, description="Worksheet name for XLSX")
    headers: List[str] = Field(default_factory=list, description="Cleaned column headers")
    rows: List[List[str]] = Field(default_factory=list, description="Cleaned 2D matrix of string values")
    records: List[Dict[str, Any]] = Field(default_factory=list, description="List of row objects keyed by header names")
    row_count: int = Field(0, description="Total row count (excluding header)")
    col_count: int = Field(0, description="Total column count")


class NormalizedPage(BaseModel):
    """Normalized content block for a single document page or section boundary."""

    page_number: int = Field(..., description="1-indexed page or sheet number")
    section: Optional[str] = Field(None, description="Associated section or clause heading")
    raw_text: str = Field(..., description="Original raw extraction text without normalization")
    normalized_text: str = Field(..., description="Cleaned, standardized, whitespace-normalized text")
    tables: List[NormalizedTable] = Field(default_factory=list, description="Normalized tables on this page")
    currencies: List[NormalizedCurrency] = Field(default_factory=list, description="Currencies detected on this page")
    dates: List[NormalizedDate] = Field(default_factory=list, description="Dates detected on this page")
    numbers: List[NormalizedNumber] = Field(default_factory=list, description="Numeric values detected on this page")


class NormalizedDocument(BaseModel):
    """
    Complete normalized document structure.
    Preserves raw source text alongside normalized content, source references,
    and structured values for downstream compliance and verification processing.
    """

    document_id: Optional[str] = Field(None, description="Associated document record UUID if available")
    format: str = Field("PDF", description="Document format (PDF, DOCX, XLSX, IMAGE)")
    raw_text: str = Field(..., description="Original raw source text across whole document")
    normalized_text: str = Field(..., description="Complete normalized text representation")
    page_count: int = Field(0, description="Total pages or worksheets")
    pages: List[NormalizedPage] = Field(default_factory=list, description="Page-by-page normalized content")
    tables: List[NormalizedTable] = Field(default_factory=list, description="Aggregated normalized tables")
    currencies: List[NormalizedCurrency] = Field(default_factory=list, description="All currency values detected")
    dates: List[NormalizedDate] = Field(default_factory=list, description="All dates detected")
    numbers: List[NormalizedNumber] = Field(default_factory=list, description="All significant numbers detected")
    sections: List[Dict[str, Any]] = Field(default_factory=list, description="Preserved section boundaries")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
