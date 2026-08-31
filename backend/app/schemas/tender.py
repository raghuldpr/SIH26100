from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TenderStatus


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class TenderBase(BaseModel):
    """Base tender properties shared across request and response schemas."""
    tender_number: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Official unique tender reference number",
    )
    title: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Descriptive title of the procurement tender",
    )
    organization: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Procuring organization name",
    )
    department: Optional[str] = Field(
        None,
        max_length=255,
        description="Procuring department or division",
    )
    category: Optional[str] = Field(
        None,
        max_length=100,
        description="Procurement classification category",
    )
    description: Optional[str] = Field(
        None,
        description="Detailed tender scope, instructions, and technical notes",
    )
    bid_start_date: Optional[datetime] = Field(
        None,
        description="Bid submission start timestamp (UTC)",
    )
    bid_end_date: Optional[datetime] = Field(
        None,
        description="Bid submission deadline timestamp (UTC)",
    )
    status: TenderStatus = Field(
        default=TenderStatus.DRAFT,
        description="Procurement lifecycle state",
    )

    @model_validator(mode="after")
    def validate_bid_dates(self) -> "TenderBase":
        """Validates that bid_end_date is not earlier than bid_start_date."""
        start_utc = _ensure_utc(self.bid_start_date)
        end_utc = _ensure_utc(self.bid_end_date)
        if start_utc and end_utc and end_utc < start_utc:
            raise ValueError("bid_end_date must not be earlier than bid_start_date")
        return self


class TenderCreate(TenderBase):
    """Schema for creating a new procurement tender."""
    pass


class TenderUpdate(BaseModel):
    """Schema for updating an existing tender."""
    title: Optional[str] = Field(None, min_length=3, max_length=500)
    organization: Optional[str] = Field(None, min_length=2, max_length=255)
    department: Optional[str] = Field(None, max_length=255)
    category: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    bid_start_date: Optional[datetime] = None
    bid_end_date: Optional[datetime] = None
    status: Optional[TenderStatus] = None

    @model_validator(mode="after")
    def validate_update_bid_dates(self) -> "TenderUpdate":
        """Validates that bid_end_date is not earlier than bid_start_date if both are present."""
        start_utc = _ensure_utc(self.bid_start_date)
        end_utc = _ensure_utc(self.bid_end_date)
        if start_utc and end_utc and end_utc < start_utc:
            raise ValueError("bid_end_date must not be earlier than bid_start_date")
        return self



class TenderResponse(BaseModel):
    """
    Public tender representation response schema.
    Conceals internal implementation details while providing full procurement attributes.
    """
    id: UUID = Field(..., description="Unique tender record identifier")
    tender_number: str = Field(..., description="Official unique tender reference number")
    title: str = Field(..., description="Tender title")
    organization: str = Field(..., description="Procuring organization")
    department: Optional[str] = Field(None, description="Procuring department")
    category: Optional[str] = Field(None, description="Tender category")
    description: Optional[str] = Field(None, description="Tender description")
    bid_start_date: Optional[datetime] = Field(None, description="Bid start date (UTC)")
    bid_end_date: Optional[datetime] = Field(None, description="Bid deadline date (UTC)")
    status: TenderStatus = Field(..., description="Current tender lifecycle status")
    created_by: Optional[UUID] = Field(None, description="ID of creating procurement officer")
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Record last update timestamp")

    model_config = ConfigDict(from_attributes=True)
