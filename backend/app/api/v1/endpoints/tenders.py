from typing import List, Optional, Union
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, BadRequestException, NotFoundException
from app.crud.crud_bidder import crud_bidder
from app.crud.crud_tender import crud_tender
from app.crud.crud_tender_requirement import crud_tender_requirement
from app.dependencies.auth import get_current_user, require_role
from app.dependencies.database import get_db
from app.models.enums import DocumentType, TenderStatus, UserRole
from app.models.user import User
from app.schemas.bidder import BidderCreate, TenderBidderResponse
from app.schemas.common import PaginatedResponse, PaginationMeta, StandardResponse
from app.schemas.document import DocumentResponse
from app.schemas.tender import TenderCreate, TenderResponse, TenderUpdate
from app.schemas.tender_intelligence import (
    TenderAnalysisRequest,
    TenderComplianceProfileResponse,
)
from app.schemas.tender_requirement import TenderRequirementResponse
from app.services.bidder_intake_service import bidder_intake_service

from app.services.document_service import (
    list_tender_documents,
    upload_multiple_tender_documents,
    upload_tender_document,
)
from app.services.tender_intelligence_service import tender_intelligence_service


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
    department: Optional[str] = Query(None, description="Filter by procuring department"),
    category: Optional[str] = Query(None, description="Filter by procurement category"),
    search: Optional[str] = Query(None, description="Search term in title, number, org, or category"),
    my_tenders_only: bool = Query(True, description="Filter only tenders created by current user"),
    include_archived: bool = Query(False, description="Include archived / soft-deleted tenders"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TenderResponse]:
    """Lists accessible tenders with pagination and filter criteria."""
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
        department=department,
        category=category,
        search=search,
        include_archived=include_archived,
    )

    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0
    serialized_items = [TenderResponse.model_validate(item) for item in items]

    return PaginatedResponse[TenderResponse](
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


@tenders_router.put(
    "/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Tender",
    description="Updates attributes of an existing tender. Enforces ownership and date validity.",
)
@tenders_router.patch(
    "/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Tender (Partial)",
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


# ---------------------------------------------------------
# PHASE 05A / PHASE 12.3 — TENDER ↔ BIDDER RELATIONSHIP & INTAKE ENDPOINTS
# ---------------------------------------------------------


@tenders_router.post(
    "/{tender_id}/bidders",
    response_model=TenderBidderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create and Associate Bidder with Tender",
    description="Registers a new bidder and associates it with the specified tender in one step.",
)
def create_tender_bidder_endpoint(
    tender_id: UUID,
    bidder_in: BidderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenderBidderResponse:
    """Creates a bidder organization and associates it with the tender."""
    bidder, assignment = bidder_intake_service.create_tender_bidder(
        db,
        tender_id=tender_id,
        bidder_in=bidder_in,
        user_id=current_user.id if current_user.role == UserRole.BIDDER else None,
    )
    return TenderBidderResponse(
        id=bidder.id,
        bidder_id=bidder.id,
        company_name=bidder.company_name,
        registration_number=bidder.registration_number,
        gst_number=bidder.gst_number,
        pan_number=bidder.pan_number,
        contact_person=bidder.contact_person,
        email=bidder.email,
        phone=bidder.phone,
        status=bidder.status,
        assignment_timestamp=assignment.created_at,
    )


@tenders_router.post(
    "/{tender_id}/bidders/{bidder_id}",
    response_model=TenderBidderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign Bidder to Tender",
    description="Assigns an existing bidder to participate in a specific tender.",
)
def assign_bidder_to_tender_endpoint(
    tender_id: UUID,
    bidder_id: UUID,
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN, UserRole.BUYER)
    ),
    db: Session = Depends(get_db),
) -> TenderBidderResponse:
    """Assigns bidder to tender, preventing duplicate assignments."""
    assignment = crud_bidder.assign_bidder_to_tender(
        db, tender_id=tender_id, bidder_id=bidder_id
    )
    bidder = assignment.bidder
    return TenderBidderResponse(
        id=bidder.id,
        bidder_id=bidder.id,
        company_name=bidder.company_name,
        registration_number=bidder.registration_number,
        gst_number=bidder.gst_number,
        pan_number=bidder.pan_number,
        contact_person=bidder.contact_person,
        email=bidder.email,
        phone=bidder.phone,
        status=bidder.status,
        assignment_timestamp=assignment.created_at,
    )


@tenders_router.post(
    "/{tender_id}/bidders/{bidder_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and Intake Bidder Document for Tender",
    description="Uploads, validates, classifies, and deterministically extracts evidence for a bidder participating in a tender.",
)
async def upload_tender_bidder_document_endpoint(
    tender_id: UUID,
    bidder_id: UUID,
    file: UploadFile = File(..., description="Bidder compliance document (PAN, GST, Financial, Experience, etc.)"),
    document_type: DocumentType = Form(
        DocumentType.OTHER,
        description="Document classification (e.g., PAN, GST, UDYAM, FINANCIAL_STATEMENT, EXPERIENCE_CERTIFICATE, OEM_AUTHORIZATION, OTHER)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    """Uploads and processes a compliance document for a participating bidder."""
    doc, _ = await bidder_intake_service.intake_bidder_document(
        db=db,
        bidder_id=bidder_id,
        file=file,
        document_type=document_type,
        tender_id=tender_id,
        process_document=True,
    )
    from app.services.document_service import enrich_document_response
    return enrich_document_response(doc)



@tenders_router.delete(
    "/{tender_id}/bidders/{bidder_id}",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Remove Bidder from Tender",
    description="Removes a bidder's participation from a specific tender.",
)
def remove_bidder_from_tender_endpoint(
    tender_id: UUID,
    bidder_id: UUID,
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN, UserRole.BUYER)
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[dict]:
    """Removes a bidder from a tender."""
    crud_bidder.remove_bidder_from_tender(db, tender_id=tender_id, bidder_id=bidder_id)
    return StandardResponse[dict](
        success=True,
        data={"tender_id": str(tender_id), "bidder_id": str(bidder_id)},
        message="Bidder successfully removed from tender.",
    )


@tenders_router.get(
    "/{tender_id}/bidders",
    response_model=PaginatedResponse[TenderBidderResponse],
    status_code=status.HTTP_200_OK,
    summary="List Bidders for Tender",
    description="Retrieves a paginated list of all bidders participating in a tender with assignment timestamps.",
)
def list_tender_bidders_endpoint(
    tender_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TenderBidderResponse]:
    """Lists participating bidders for a tender."""
    skip = (page - 1) * page_size
    assignments, total_count = crud_bidder.get_tender_bidders(
        db, tender_id=tender_id, skip=skip, limit=page_size
    )

    serialized_items = [
        TenderBidderResponse(
            id=a.bidder.id,
            bidder_id=a.bidder.id,
            company_name=a.bidder.company_name,
            registration_number=a.bidder.registration_number,
            gst_number=a.bidder.gst_number,
            pan_number=a.bidder.pan_number,
            contact_person=a.bidder.contact_person,
            email=a.bidder.email,
            phone=a.bidder.phone,
            status=a.bidder.status,
            assignment_timestamp=a.created_at,
        )
        for a in assignments
    ]
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 0

    return PaginatedResponse[TenderBidderResponse](
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
# PHASE 05B — TENDER DOCUMENT MANAGEMENT ENDPOINTS
# ---------------------------------------------------------


@tenders_router.post(
    "/{tender_id}/documents",
    response_model=Union[DocumentResponse, List[DocumentResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Upload Tender Document(s)",
    description="Uploads one or multiple official Tender documents (RFP, Notice, etc.) to Supabase Storage.",
)
async def upload_tender_document_endpoint(
    tender_id: UUID,
    file: Optional[UploadFile] = File(None, description="Single tender RFP / Notice document"),
    files: Optional[List[UploadFile]] = File(None, description="Multiple tender documents"),
    document_type: DocumentType = Form(
        DocumentType.TENDER_PDF,
        description="Document type (e.g. TENDER, TENDER_PDF, TENDER_NOTICE)",
    ),
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN, UserRole.BUYER)
    ),
    db: Session = Depends(get_db),
):
    """Uploads one or multiple documents for a Tender."""
    upload_list: List[UploadFile] = []
    if files:
        upload_list.extend(files)
    elif file:
        upload_list.append(file)

    if not upload_list:
        raise BadRequestException(message="No files provided for upload.")

    if len(upload_list) == 1:
        return await upload_tender_document(
            db=db,
            tender_id=tender_id,
            file=upload_list[0],
            document_type=document_type,
        )
    else:
        return await upload_multiple_tender_documents(
            db=db,
            tender_id=tender_id,
            files=upload_list,
            document_type=document_type,
        )



@tenders_router.get(
    "/{tender_id}/documents",
    response_model=PaginatedResponse[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tender Documents",
    description="Retrieves a paginated list of uploaded documents for a Tender.",
)
def list_tender_documents_endpoint(
    tender_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PaginatedResponse[DocumentResponse]:
    """Lists all documents attached to a tender."""
    skip = (page - 1) * page_size
    items, total_count = list_tender_documents(
        db=db, tender_id=tender_id, skip=skip, limit=page_size, current_user=current_user
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


# -----------------------------------------------------------------------------
# PHASE 08: TENDER INTELLIGENCE & COMPLIANCE PROFILE ENDPOINTS
# -----------------------------------------------------------------------------
@tenders_router.post(
    "/{tender_id}/intelligence/analyze",
    response_model=TenderComplianceProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Tender Requirements and Generate Compliance Profile",
    description="Executes the hybrid deterministic + controlled AI Gateway pipeline to produce a Tender Compliance Profile.",
)
def analyze_tender_endpoint(
    tender_id: UUID,
    request: Optional[TenderAnalysisRequest] = None,
    current_user: User = Depends(
        require_role(UserRole.PROCUREMENT_OFFICER, UserRole.ADMIN, UserRole.BUYER)
    ),
    db: Session = Depends(get_db),
) -> TenderComplianceProfileResponse:
    """Trigger Tender Intelligence analysis for a tender."""
    return tender_intelligence_service.analyze_tender(
        db=db,
        tender_id=tender_id,
        request=request,
    )


@tenders_router.get(
    "/{tender_id}/intelligence",
    response_model=TenderComplianceProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Tender Compliance Profile",
    description="Retrieves the structured Tender Compliance Profile distinguishing deterministic, AI-assisted, and unresolved criteria.",
)
def get_tender_intelligence_profile_endpoint(
    tender_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenderComplianceProfileResponse:
    """Fetch existing Tender Compliance Profile."""
    return tender_intelligence_service.get_compliance_profile(
        db=db,
        tender_id=tender_id,
    )


@tenders_router.get(
    "/{tender_id}/requirements",
    response_model=List[TenderRequirementResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Tender Requirements",
    description="Retrieves persisted eligibility and compliance requirements for a tender with optional filters.",
)
def get_tender_requirements_endpoint(
    tender_id: UUID,
    requirement_type: Optional[str] = Query(None, description="Optional requirement type filter (e.g. FINANCIAL, OEM)"),
    mandatory_only: bool = Query(False, description="Filter for mandatory requirements only"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TenderRequirementResponse]:
    """Lists persisted requirements for a tender."""
    tender = crud_tender.get_by_id(db, tender_id)
    if not tender:
        raise NotFoundException(f"Tender {tender_id} not found")

    items = crud_tender_requirement.get_by_tender(
        db=db,
        tender_id=tender_id,
        requirement_type=requirement_type,
        mandatory_only=mandatory_only,
    )
    return [TenderRequirementResponse.model_validate(r) for r in items]

