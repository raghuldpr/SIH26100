from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.classification import ClassificationResult
from app.schemas.processing import TableData


class ExtractedEntity(BaseModel):
    """Structured representation of an extracted entity field."""

    value: Optional[Any] = Field(None, description="Extracted entity value")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)")
    page: Optional[int] = Field(1, description="1-indexed source document page number")
    raw_match: Optional[str] = Field(None, description="Original raw snippet before normalization")


class StructuredDocumentOutput(BaseModel):
    """Complete structured JSON output of the document processing pipeline."""

    document_type: str = Field(..., description="Classified document type (PAN, GST, UDYAM, TENDER, etc.)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall classification confidence score")
    classification: Optional[ClassificationResult] = Field(None, description="Detailed classification signals")
    entities: Dict[str, ExtractedEntity] = Field(default_factory=dict, description="Extracted key-value entities")
    tables: List[TableData] = Field(default_factory=list, description="Extracted tabular data structures")
    page_count: int = Field(0, description="Total number of pages processed")
    raw_text: Optional[str] = Field(None, description="Cleaned full extracted text")
    is_scanned: bool = Field(False, description="True if document required OCR rendering")
    processing_time_ms: float = Field(0.0, description="Total end-to-end processing duration in milliseconds")
