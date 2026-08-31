from typing import List
from pydantic import BaseModel, ConfigDict, Field


class ClassificationResult(BaseModel):
    """Result of deterministic document type classification."""

    document_type: str = Field(
        ...,
        description="Identified document category (PAN, GST, UDYAM, FINANCIAL_STATEMENT, EXPERIENCE_CERTIFICATE, OEM_AUTHORIZATION, MII_DECLARATION, TENDER, UNKNOWN)",
    )
    confidence: float = Field(
        ...,
        description="Confidence level of classification bounded between 0.00 and 0.98",
        ge=0.0,
        le=1.0,
    )
    matched_indicators: List[str] = Field(
        default_factory=list,
        description="List of detected keywords, key phrases, or identifier patterns",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_type": "GST",
                "confidence": 0.97,
                "matched_indicators": [
                    "GSTIN",
                    "Goods and Services Tax",
                    "Registration Certificate",
                ],
            }
        }
    )
