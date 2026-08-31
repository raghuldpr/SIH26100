from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ClassificationResult(BaseModel):
    """Structured document classification output."""

    document_type: str = Field(..., description="Classified document type (e.g., PAN, GST, UDYAM, TENDER, OTHER)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Classification confidence score (0.0 to 1.0)")
    matched_signals: List[str] = Field(default_factory=list, description="Exact regex, keyword, or layout signals matched")
    explanation: Optional[str] = Field(None, description="Human-readable explanation of the classification decision")
    scores: Optional[Dict[str, float]] = Field(default_factory=dict, description="Raw score breakdown across categories")
