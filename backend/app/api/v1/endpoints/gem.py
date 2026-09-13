"""
Phase 21: GeM Tender Discovery & Import Endpoints
app/api/v1/endpoints/gem.py: HTTP API routes for looking up public GeM bids and importing them into SIH-26100.
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.dependencies.auth import require_role
from app.dependencies.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.gem import GeMLookupResponse
from app.schemas.tender import TenderResponse
from app.services.gem_service import gem_service

logger = logging.getLogger("app.api.v1.gem")

gem_router = APIRouter(
    prefix="/gem",
    tags=["gem"],
)


@gem_router.get(
    "/lookup/{bid_id:path}",
    response_model=GeMLookupResponse,
    status_code=status.HTTP_200_OK,
    summary="Lookup GeM Tender by Bid ID",
    description="Validates GeM Bid ID format, checks for prior imports in PostgreSQL, and queries available GeM metadata.",
)
async def lookup_gem_tender_endpoint(
    bid_id: str,
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN, UserRole.BUYER)
    ),
    db: Session = Depends(get_db),
) -> GeMLookupResponse:
    """Performs discovery lookup for a GeM Bid ID."""
    return await gem_service.lookup_tender(db=db, bid_id=bid_id)


@gem_router.post(
    "/import",
    response_model=TenderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import GeM Tender",
    description="Imports a GeM bid as a persistent SIH-26100 tender record, preventing duplicates and attaching NIT documents.",
)
async def import_gem_tender_endpoint(
    bid_id: str = Form(..., description="Official GeM Bid ID (e.g. GEM/2026/B/8912401)"),
    title: str = Form(..., description="Tender title"),
    organization: str = Form(..., description="Procuring organization"),
    department: Optional[str] = Form("General", description="Procuring department"),
    category: Optional[str] = Form("General", description="Procurement category"),
    bid_start_date: Optional[str] = Form(None, description="Bid commencement ISO timestamp"),
    bid_end_date: Optional[str] = Form(None, description="Bid deadline ISO timestamp"),
    file: Optional[UploadFile] = File(None, description="Official Tender NIT PDF document"),
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN, UserRole.BUYER)
    ),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Imports GeM tender into persistent PostgreSQL database."""
    start_dt = None
    if bid_start_date:
        try:
            start_dt = datetime.fromisoformat(bid_start_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    end_dt = None
    if bid_end_date:
        try:
            end_dt = datetime.fromisoformat(bid_end_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    tender = await gem_service.import_tender(
        db=db,
        bid_id=bid_id,
        title=title,
        organization=organization,
        department=department,
        category=category,
        bid_start_date=start_dt,
        bid_end_date=end_dt,
        file=file,
        current_user=current_user,
    )

    return TenderResponse.model_validate(tender)
