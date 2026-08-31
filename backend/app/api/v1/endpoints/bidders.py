from typing import List, Optional, Union
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, NotFoundException
from app.crud.crud_bidder import crud_bidder
from app.dependencies.auth import get_current_user, require_role
from app.dependencies.database import get_db
from app.models.enums import BidderStatus, DocumentType, UserRole
from app.models.user import User
from app.schemas.bidder import (
    BidderCreate,
    BidderResponse,
    BidderStatusUpdate,
    BidderTenderResponse,
    BidderUpdate,
)
from app.schemas.common import PaginatedResponse, PaginationMeta, StandardResponse
from app.schemas.document import DocumentResponse
from app.services.document_service import (
    list_bidder_documents,
    upload_bidder_document,
    upload_multiple_bidder_documents,
)

bidders_router = APIRouter(
    prefix="/bidders",
    tags=["bidders"],
)


@bidders_router.post(
    "",
    response_model=BidderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Bidder Entity",
    description="Registers a new reusable bidder organization entity in the procurement system.",
)
def create_bidder(
    bidder_in: BidderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BidderResponse:
    """Creates a new bidder entity."""
    bidder = crud_bidder.create(
        db,
        bidder_in=bidder_in,
        user_id=current_user.id if current_user.role == UserRole.BIDDER else None,
    )
    return BidderResponse.model_validate(bidder)


@bidders_router.get(
    "",
    response_model=PaginatedResponse[BidderResponse],
    status_code=status.HTTP_200_OK,
    summary="List Registered Bidders",
    description="Retrieves a paginated list of registered bidder organizations with optional filtering.",
)
def list_bidders(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[BidderStatus] = Query(None, description="Filter by operational status"),
    search: Optional[str] = Query(None, description="Search term in name, PAN, GST, or email"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[BidderResponse]:
    """Lists registered bidder entities with pagination."""
    skip = (page - 1) * page_size
    items, total_count = crud_bidder.get_multi(
        db,
        skip=skip,
        limit=page_size,
        status_filter=status,
        search=search,
    )

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    serialized_items = [BidderResponse.model_validate(item) for item in items]

    return PaginatedResponse[BidderResponse](
        success=True,
        data=serialized_items,
        items=serialized_items,
        page=page,
        page_size=page_size,
        total=total_count,
        pagination=PaginationMeta(
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@bidders_router.get(
    "/{bidder_id}",
    response_model=BidderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Bidder Details",
    description="Retrieves full profile details of a registered bidder by ID.",
)
def get_bidder(
    bidder_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BidderResponse:
    """Fetches a bidder by UUID; returns 404 if not found."""
    bidder = crud_bidder.get_by_id(db, bidder_id=bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")
    return BidderResponse.model_validate(bidder)


@bidders_router.put(
    "/{bidder_id}",
    response_model=BidderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Bidder",
    description="Updates attributes of an existing bidder organization.",
)
@bidders_router.patch(
    "/{bidder_id}",
    response_model=BidderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Bidder (Partial)",
    description="Updates attributes of an existing bidder organization.",
)
def update_bidder(
    bidder_id: UUID,
    bidder_update: BidderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BidderResponse:
    """Updates bidder attributes."""
    bidder = crud_bidder.get_by_id(db, bidder_id=bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    updated_bidder = crud_bidder.update(
        db, db_bidder=bidder, bidder_update=bidder_update
    )
    return BidderResponse.model_validate(updated_bidder)


@bidders_router.patch(
    "/{bidder_id}/status",
    response_model=BidderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Bidder Operational Status",
    description="Updates the eligibility / active status of a bidder organization.",
)
def update_bidder_status(
    bidder_id: UUID,
    status_in: BidderStatusUpdate,
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> BidderResponse:
    """Updates bidder status."""
    bidder = crud_bidder.get_by_id(db, bidder_id=bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    updated_bidder = crud_bidder.update_status(
        db, db_bidder=bidder, new_status=status_in.status
    )
    return BidderResponse.model_validate(updated_bidder)


@bidders_router.get(
    "/{bidder_id}/tenders",
    response_model=PaginatedResponse[BidderTenderResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tenders for Bidder",
    description="Retrieves a paginated list of all procurement tenders in which this bidder participates.",
)
def list_bidder_tenders(
    bidder_id: UUID,
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[BidderTenderResponse]:
    """Lists tenders associated with a bidder."""
    skip = (page - 1) * page_size
    assignments, total_count = crud_bidder.get_bidder_tenders(
        db, bidder_id=bidder_id, skip=skip, limit=page_size
    )

    serialized_items = [
        BidderTenderResponse(
            id=a.tender.id,
            tender_number=a.tender.tender_number,
            title=a.tender.title,
            organization=a.tender.organization,
            department=a.tender.department,
            category=a.tender.category,
            status=a.tender.status,
            bid_start_date=a.tender.bid_start_date,
            bid_end_date=a.tender.bid_end_date,
            assignment_timestamp=a.created_at,
        )
        for a in assignments
    ]
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    return PaginatedResponse[BidderTenderResponse](
        success=True,
        data=serialized_items,
        items=serialized_items,
        page=page,
        page_size=page_size,
        total=total_count,
        pagination=PaginationMeta(
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


# ---------------------------------------------------------
# PHASE 05B — BIDDER DOCUMENT MANAGEMENT ENDPOINTS
# ---------------------------------------------------------


@bidders_router.post(
    "/{bidder_id}/documents",
    response_model=Union[DocumentResponse, List[DocumentResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Bidder Document(s)",
    description="Uploads one or multiple compliance documents (PAN, GST, UDYAM, etc.) for a Bidder to Supabase Storage.",
)
async def upload_bidder_documents_endpoint(
    bidder_id: UUID,
    file: Optional[UploadFile] = File(None, description="Single compliance document to upload"),
    files: Optional[List[UploadFile]] = File(None, description="Multiple compliance documents to upload"),
    document_type: DocumentType = Form(
        DocumentType.OTHER,
        description="Document classification (e.g., PAN, GST, UDYAM, FINANCIAL_STATEMENT, EXPERIENCE_CERTIFICATE, OEM_AUTHORIZATION, MII_DECLARATION, OTHER)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads one or multiple documents for a Bidder."""
    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend(files)
    elif file:
        upload_list.append(file)

    if not upload_list:
        raise BadRequestException(message="No files provided for upload.")

    if len(upload_list) == 1:
        return await upload_bidder_document(
            db=db,
            bidder_id=bidder_id,
            file=upload_list[0],
            document_type=document_type,
        )
    else:
        return await upload_multiple_bidder_documents(
            db=db,
            bidder_id=bidder_id,
            files=upload_list,
            document_type=document_type,
        )



@bidders_router.get(
    "/{bidder_id}/documents",
    response_model=PaginatedResponse[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Bidder Documents",
    description="Retrieves a paginated list of uploaded compliance documents for a Bidder.",
)
def list_bidder_documents_endpoint(
    bidder_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DocumentResponse]:
    """Lists compliance documents uploaded for a Bidder."""
    skip = (page - 1) * page_size
    items, total_count = list_bidder_documents(
        db=db, bidder_id=bidder_id, skip=skip, limit=page_size, current_user=current_user
    )
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0


    return PaginatedResponse[DocumentResponse](
        success=True,
        data=items,
        items=items,
        page=page,
        page_size=page_size,
        total=total_count,
        pagination=PaginationMeta(
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )
