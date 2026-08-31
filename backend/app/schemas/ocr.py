from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OCRTextBox(BaseModel):
    """Recognized text token / line with spatial coordinates and confidence score."""

    text: str = Field(..., description="Recognized textual content")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="OCR model confidence score (0.0 to 1.0)")
    bbox: Optional[List[List[int]]] = Field(None, description="Bounding polygon coordinates [[x1, y1], [x2, y2], ...]")


class OCRPageResult(BaseModel):
    """Page-level OCR extraction result."""

    page_number: int = Field(..., description="1-indexed document page number")
    text: str = Field("", description="Consolidated page text")
    word_count: int = Field(0, description="Total words detected on this page")
    line_count: int = Field(0, description="Total text lines on this page")
    avg_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Average OCR confidence across page tokens")
    boxes: List[OCRTextBox] = Field(default_factory=list, description="Detailed text boxes detected on page")
    is_blank: bool = Field(False, description="True if page is determined to be blank / empty")
    rotation_angle: float = Field(0.0, description="Deskew rotation angle applied in degrees")
    processing_time_ms: float = Field(0.0, description="Execution time for page OCR in milliseconds")


class OCRDocumentResult(BaseModel):
    """Complete document-level OCR pipeline result."""

    document_type: Optional[str] = Field(None, description="Document type classification")
    page_count: int = Field(0, description="Total number of pages processed")
    full_text: str = Field("", description="Aggregated full document text across all pages")
    pages: List[OCRPageResult] = Field(default_factory=list, description="Page-by-page OCR results")
    overall_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Document-wide average confidence")
    engine_used: str = Field("PaddleOCR", description="Name of OCR engine used")
    is_success: bool = Field(True, description="Indicates if OCR execution completed successfully")
    error_message: Optional[str] = Field(None, description="Error details if OCR processing failed")
    execution_time_ms: float = Field(0.0, description="Total pipeline execution duration in milliseconds")
