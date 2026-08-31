from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class UnifiedPageExtraction(BaseModel):
    """Extraction details for an individual document page."""

    page_number: int = Field(..., description="1-indexed page number")
    text: str = Field(..., description="Text extracted from page")
    character_count: int = Field(..., description="Number of characters extracted")


class ExtractionSummary(BaseModel):
    """Consolidated extraction method, text, and per-page content."""

    method: str = Field(..., description="Extraction method used ('native_pdf' or 'ocr')")
    ocr_used: bool = Field(..., description="Flag indicating whether OCR was performed")
    text: str = Field(..., description="Consolidated raw document text across all pages")
    pages: List[UnifiedPageExtraction] = Field(
        default_factory=list, description="Per-page extracted text items"
    )


class ProcessingMetadata(BaseModel):
    """Execution telemetry and status descriptor."""

    status: str = Field("completed", description="'completed' or 'failed'")
    processing_time_ms: int = Field(0, description="Total execution duration in milliseconds")
    error_code: Optional[str] = Field(None, description="Error identifier if failed")
    message: Optional[str] = Field(None, description="Status or failure message")


class UnifiedDocumentResponse(BaseModel):
    """Unified document processing response envelope."""

    document_id: str = Field(..., description="Unique processing identifier (UUID)")
    filename: str = Field(..., description="Name of the processed source document")
    document_type: str = Field(..., description="Classified document type category")
    classification_confidence: float = Field(
        ..., description="Confidence level of classification [0.0, 1.0]"
    )
    pages: int = Field(..., description="Total pages or images processed")
    extraction: ExtractionSummary = Field(..., description="Text extraction metadata")
    tables: List[Dict[str, Any]] = Field(
        default_factory=list, description="Extracted tabular structures"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Structured fields extracted from document"
    )
    processing: ProcessingMetadata = Field(..., description="Execution status and duration")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
                "filename": "GST.pdf",
                "document_type": "GST",
                "classification_confidence": 0.97,
                "pages": 2,
                "extraction": {
                    "method": "native_pdf",
                    "ocr_used": False,
                    "text": "Registration Certificate...",
                    "pages": [
                        {
                            "page_number": 1,
                            "text": "Registration Certificate...",
                            "character_count": 120,
                        }
                    ],
                },
                "tables": [],
                "data": {
                    "gstin": "27ABCDE1234F1Z5",
                    "company_name": "ACME INFOTECH",
                    "status": "Active",
                },
                "processing": {
                    "status": "completed",
                    "processing_time_ms": 1234,
                },
            }
        }
    )
