"""
Phase 21: GeM Tender Discovery & Import Schemas
app/schemas/gem.py: Strongly typed schemas for GeM tender search, lookup, and import.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.schemas.tender import TenderResponse


class GeMTenderMetadata(BaseModel):
    """Normalized metadata structure for a discovered GeM tender."""
    bid_id: str = Field(..., description="Official GeM Bid / Tender ID (e.g. GEM/2026/B/8912401)")
    title: str = Field(..., description="Procurement tender title or subject")
    organization: str = Field(..., description="Procuring Ministry / Department / Organization")
    department: Optional[str] = Field("General", description="Department / Division / Office")
    category: Optional[str] = Field("General", description="Item / Service procurement category")
    tender_type: Optional[str] = Field("GeM Custom Bid", description="Tender / Bid type")
    published_date: Optional[datetime] = Field(None, description="Tender publication timestamp (UTC)")
    bid_end_date: Optional[datetime] = Field(None, description="Bid submission deadline timestamp (UTC)")
    estimated_value: Optional[float] = Field(None, description="Estimated tender contract value in INR if publicly disclosed")
    location: Optional[str] = Field(None, description="Consignee / Delivery location")
    status: Optional[str] = Field("Active", description="Public tender operational status on GeM")
    source: str = Field("GEM", description="Tender source indicator")
    document_available: bool = Field(False, description="Whether official tender/NIT document is automatically accessible")
    document_url: Optional[str] = Field(None, description="Direct download URL for the tender NIT document if public")
    document_name: Optional[str] = Field(None, description="Original filename of the tender NIT document")
    raw_details: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional raw GeM fields")


class GeMLookupResponse(BaseModel):
    """Response returned upon searching / looking up a GeM Bid ID."""
    status: str = Field(..., description="'found', 'already_imported', 'unavailable', or 'invalid_bid_id'")
    bid_id: str = Field(..., description="Requested GeM Bid ID")
    already_imported: bool = Field(False, description="True if this GeM tender is already persisted in SIH-26100")
    existing_tender_id: Optional[UUID] = Field(None, description="Tender record UUID if already imported")
    existing_tender: Optional[TenderResponse] = Field(None, description="Persisted tender details if already imported")
    gem_data: Optional[GeMTenderMetadata] = Field(None, description="Discovered GeM metadata")
    message: Optional[str] = Field(None, description="Diagnostic explanation or guidance for the user")
    can_manual_upload: bool = Field(True, description="Whether manual tender NIT document upload fallback is enabled")


class GeMImportRequest(BaseModel):
    """Payload for importing a verified GeM tender."""
    bid_id: str = Field(..., description="GeM Bid ID to import")
    title: str = Field(..., description="Tender title")
    organization: str = Field(..., description="Procuring organization")
    department: Optional[str] = Field("General", description="Procuring department")
    category: Optional[str] = Field("General", description="Procurement category")
    bid_start_date: Optional[datetime] = Field(None, description="Bid commencement datetime")
    bid_end_date: Optional[datetime] = Field(None, description="Bid deadline datetime")
    estimated_value: Optional[float] = Field(None, description="Estimated contract value")
