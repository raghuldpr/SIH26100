from typing import List
from pydantic import BaseModel, ConfigDict, Field


class PageExtractionResult(BaseModel):
    """Extracted text and metadata for an individual document page."""

    page_number: int = Field(..., description="1-indexed page number within the document")
    text: str = Field(..., description="Raw text extracted from this page")
    character_count: int = Field(..., description="Total character length of the page text")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page_number": 1,
                "text": "BID DOCUMENT FOR PROCUREMENT OF NETWORKING EQUIPMENT\n...",
                "character_count": 1234,
            }
        }
    )


class PDFExtractionResult(BaseModel):
    """Aggregate result of native PDF document text extraction."""

    extraction_method: str = Field(
        "native_pdf", description="Method employed for extraction (e.g. native_pdf, ocr)"
    )
    pages: List[PageExtractionResult] = Field(
        default_factory=list, description="List of per-page extraction results"
    )
    total_pages: int = Field(..., description="Total number of pages processed")
    total_characters: int = Field(
        ..., description="Cumulative character count across all extracted pages"
    )
    has_meaningful_text: bool = Field(
        ...,
        description="Indicates whether the document contains meaningful extractable native text",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "extraction_method": "native_pdf",
                "pages": [
                    {
                        "page_number": 1,
                        "text": "BID DETAILS\nTender Number: GEM/2026/B/100200",
                        "character_count": 42,
                    }
                ],
                "total_pages": 1,
                "total_characters": 42,
                "has_meaningful_text": True,
            }
        }
    )
