from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, NotFoundException
from app.crud.crud_tender import crud_tender
from app.dependencies.auth import get_current_user, require_role
from app.dependencies.database import get_db
from app.models.enums import TenderStatus, UserRole
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationMeta
from app.schemas.tender import TenderCreate, TenderResponse, TenderUpdate

tenders_router = APIRouter(
    prefix="/tenders",
    tags=["tenders"],
)


@tenders_router.post(
    "",
    response_model=TenderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Procurement Tender",
    description="Creates a new procurement tender associated with the authenticated procurement officer.",
)
def create_tender(
    tender_in: TenderCreate,
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN)
    ),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Creates a new tender with unique number and date validation."""
    tender = crud_tender.create(
        db,
        tender_in=tender_in,
        created_by=current_user.id,
    )
    return TenderResponse.model_validate(tender)


@tenders_router.get(
    "",
    response_model=PaginatedResponse[TenderResponse],
    status_code=status.HTTP_200_OK,
    summary="List Procurement Tenders",
    description="Retrieves a paginated list of procurement tenders with optional filtering and search.",
)
def list_tenders(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[TenderStatus] = Query(None, description="Filter by tender status"),
    search: Optional[str] = Query(None, description="Search term in title, number, org, or category"),
    my_tenders_only: bool = Query(True, description="Filter only tenders created by current user"),
    include_archived: bool = Query(False, description="Include archived / soft-deleted tenders"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TenderResponse]:
    """Lists accessible tenders with pagination."""
    created_by_filter = current_user.id if (my_tenders_only and current_user.role != UserRole.ADMIN) else None
    if my_tenders_only and current_user.role == UserRole.ADMIN:
        created_by_filter = current_user.id

    skip = (page - 1) * page_size
    items, total_count = crud_tender.get_multi(
        db,
        skip=skip,
        limit=page_size,
        created_by=created_by_filter,
        status=status,
        search=search,
        include_archived=include_archived,
    )

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    serialized_items = [TenderResponse.model_validate(item) for item in items]

    return PaginatedResponse[TenderResponse](
        success=True,
        data=serialized_items,
        pagination=PaginationMeta(
            total_count=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@tenders_router.get(
    "/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Tender Details",
    description="Retrieves comprehensive details of a single tender by ID.",
)
def get_tender(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Fetches a tender by UUID; returns 404 if not found."""
    tender = crud_tender.get_by_id(db, tender_id=tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")
    return TenderResponse.model_validate(tender)


@tenders_router.patch(
    "/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Tender",
    description="Updates attributes of an existing tender. Enforces ownership and date validity.",
)
def update_tender(
    tender_id: UUID,
    tender_update: TenderUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Updates tender attributes if the authenticated user is the owner or an admin."""
    tender = crud_tender.get_by_id(db, tender_id=tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    # Enforce ownership: only the creator or ADMIN may modify
    if current_user.role != UserRole.ADMIN and tender.created_by != current_user.id:
        raise AppException(
            message="You do not have permission to modify this tender.",
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
        )

    updated_tender = crud_tender.update(
        db, db_tender=tender, tender_update=tender_update
    )
    return TenderResponse.model_validate(updated_tender)


@tenders_router.delete(
    "/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive / Soft Delete Tender",
    description="Soft-deletes an existing tender by marking its status as ARCHIVED to preserve history.",
)
def archive_tender(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Soft-deletes a tender by setting its status to ARCHIVED."""
    tender = crud_tender.get_by_id(db, tender_id=tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    # Enforce ownership: only the creator or ADMIN may archive
    if current_user.role != UserRole.ADMIN and tender.created_by != current_user.id:
        raise AppException(
            message="You do not have permission to archive this tender.",
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
        )

    archived_tender = crud_tender.archive(db, db_tender=tender)
    return TenderResponse.model_validate(archived_tender)
