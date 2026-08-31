from typing import Any, Dict
from pydantic import BaseModel, ConfigDict, Field


class StructuredExtractionResult(BaseModel):
    """Structured information extracted from a classified document."""

    document_type: str = Field(..., description="Document type category")
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted key-value attributes; unextractable fields are null",
    )
    field_confidence: Dict[str, float] = Field(
        default_factory=dict,
        description="Per-field confidence metric [0.0, 1.0]",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_type": "GST",
                "data": {
                    "gstin": "27ABCDE1234F1Z5",
                    "company_name": "ACME INFOTECH",
                    "legal_name": "ACME GLOBAL INFOTECH PRIVATE LIMITED",
                    "status": "Active",
                },
                "field_confidence": {
                    "gstin": 0.99,
                    "company_name": 0.91,
                    "legal_name": 0.93,
                    "status": 0.85,
                },
            }
        }
    )
