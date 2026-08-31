from typing import List
from pydantic import BaseModel, ConfigDict, Field


class ExtractedTable(BaseModel):
    """Structured representation of a single extracted table."""

    page: int = Field(..., description="1-indexed page number where the table appears")
    table_index: int = Field(
        ..., description="0-indexed table sequence index on the respective page"
    )
    rows: List[List[str]] = Field(
        ..., description="Normalized 2D matrix of table cells (rows and columns)"
    )
    num_rows: int = Field(..., description="Total row count")
    num_cols: int = Field(..., description="Total column count (normalized)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 2,
                "table_index": 0,
                "rows": [
                    ["Description", "Amount"],
                    ["Annual Turnover", "2500000"],
                ],
                "num_rows": 2,
                "num_cols": 2,
            }
        }
    )


class TableExtractionResult(BaseModel):
    """Aggregate result of table extraction across a PDF document."""

    extraction_method: str = Field(
        "pdfplumber", description="Method employed for table extraction"
    )
    total_tables: int = Field(..., description="Total number of tables detected and extracted")
    tables: List[ExtractedTable] = Field(
        default_factory=list, description="List of extracted table objects"
    )
    pages_with_tables: List[int] = Field(
        default_factory=list, description="Sorted list of page numbers containing tables"
    )
    is_scanned_pdf: bool = Field(
        False, description="Flag indicating if PDF lacks digital text and is scanned"
    )
    requires_ocr: bool = Field(
        False,
        description="Flag indicating that OCR/layout processing is required for table extraction",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "extraction_method": "pdfplumber",
                "total_tables": 1,
                "tables": [
                    {
                        "page": 2,
                        "table_index": 0,
                        "rows": [
                            ["Description", "Amount"],
                            ["Annual Turnover", "2500000"],
                        ],
                        "num_rows": 2,
                        "num_cols": 2,
                    }
                ],
                "pages_with_tables": [2],
                "is_scanned_pdf": False,
                "requires_ocr": False,
            }
        }
    )
