from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import BidderStatus, TenderStatus


class BidderBase(BaseModel):
    """Base schema attributes for Bidder organizations."""

    company_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Official registered corporate name of the bidder",
    )
    registration_number: Optional[str] = Field(
        None,
        max_length=100,
        description="Corporate registration or CIN number",
    )
    gst_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Goods & Services Tax Identification Number (GSTIN)",
    )
    pan_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Permanent Account Number (PAN)",
    )
    udyam_number: Optional[str] = Field(
        None,
        max_length=50,
        description="MSME Udyam registration certificate number",
    )
    contact_person: Optional[str] = Field(
        None,
        max_length=255,
        description="Primary contact person name",
    )
    email: Optional[EmailStr] = Field(
        None,
        description="Primary official contact email address",
    )
    phone: Optional[str] = Field(
        None,
        max_length=50,
        description="Primary contact telephone or mobile number",
    )
    address: Optional[str] = Field(
        None,
        description="Registered office / postal address",
    )
    status: BidderStatus = Field(
        default=BidderStatus.ACTIVE,
        description="Operational / eligibility status of the bidder",
    )

    @field_validator(
        "company_name",
        "registration_number",
        "gst_number",
        "pan_number",
        "udyam_number",
        "contact_person",
        "phone",
        mode="after",
    )
    @classmethod
    def validate_non_empty_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                return None
            return stripped
        return v


class BidderCreate(BidderBase):
    """Schema for registering a new Bidder entity."""

    pass


class BidderUpdate(BaseModel):
    """Schema for updating an existing Bidder entity."""

    company_name: Optional[str] = Field(None, min_length=1, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=100)
    gst_number: Optional[str] = Field(None, max_length=50)
    pan_number: Optional[str] = Field(None, max_length=50)
    udyam_number: Optional[str] = Field(None, max_length=50)
    contact_person: Optional[str] = Field(None, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = None
    status: Optional[BidderStatus] = None

    @field_validator(
        "company_name",
        "registration_number",
        "gst_number",
        "pan_number",
        "udyam_number",
        "contact_person",
        "phone",
        mode="after",
    )
    @classmethod
    def validate_non_empty_strings(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                return None
            return stripped
        return v


class BidderStatusUpdate(BaseModel):
    """Schema for updating only the operational status of a Bidder."""

    status: BidderStatus = Field(
        ...,
        description="Updated bidder eligibility status (ACTIVE, INACTIVE, SUSPENDED)",
    )


class BidderResponse(BaseModel):
    """Public representation of a registered Bidder entity."""

    id: UUID = Field(..., description="Unique bidder identifier")
    company_name: str = Field(..., description="Company / organization name")
    registration_number: Optional[str] = Field(None, description="Registration number")
    gst_number: Optional[str] = Field(None, description="GST number")
    pan_number: Optional[str] = Field(None, description="PAN number")
    udyam_number: Optional[str] = Field(None, description="Udyam MSME number")
    contact_person: Optional[str] = Field(None, description="Primary contact person")
    email: Optional[str] = Field(None, description="Primary contact email")
    phone: Optional[str] = Field(None, description="Primary contact phone")
    address: Optional[str] = Field(None, description="Office address")
    status: BidderStatus = Field(..., description="Current status")
    created_at: Optional[datetime] = Field(None, description="Record creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class TenderBidderResponse(BaseModel):
    """
    Dedicated response schema representing a bidder assigned to a specific tender,
    including the assignment timestamp.
    """

    id: UUID = Field(..., description="Bidder identifier")
    bidder_id: UUID = Field(..., description="Bidder identifier")
    company_name: str = Field(..., description="Company name")
    registration_number: Optional[str] = Field(None, description="Registration number")
    gst_number: Optional[str] = Field(None, description="GST number")
    pan_number: Optional[str] = Field(None, description="PAN number")
    contact_person: Optional[str] = Field(None, description="Contact person")
    email: Optional[str] = Field(None, description="Email")
    phone: Optional[str] = Field(None, description="Phone")
    status: BidderStatus = Field(..., description="Bidder status")
    assignment_timestamp: datetime = Field(..., description="Timestamp of tender assignment")

    model_config = ConfigDict(from_attributes=True)


class BidderTenderResponse(BaseModel):
    """
    Representation of a Tender associated with a specific Bidder.
    """

    id: UUID = Field(..., description="Tender identifier")
    tender_number: str = Field(..., description="Official tender number")
    title: str = Field(..., description="Tender title")
    organization: str = Field(..., description="Procuring organization")
    department: Optional[str] = Field(None, description="Procuring department")
    category: Optional[str] = Field(None, description="Tender category")
    status: TenderStatus = Field(..., description="Tender lifecycle status")
    bid_start_date: Optional[datetime] = Field(None, description="Bid start date")
    bid_end_date: Optional[datetime] = Field(None, description="Bid end date")
    assignment_timestamp: Optional[datetime] = Field(None, description="Assignment timestamp")

    model_config = ConfigDict(from_attributes=True)
