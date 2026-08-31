import logging
from typing import List, Optional, Tuple, Union
from uuid import UUID
from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import AppException, BadRequestException, NotFoundException
from app.models.bidder import Bidder, TenderBidder
from app.models.enums import BidderStatus
from app.models.tender import Tender
from app.schemas.bidder import BidderCreate, BidderUpdate

logger = logging.getLogger("app.crud.bidder")


def get_bidder_by_id(db: Session, bidder_id: Union[UUID, str]) -> Optional[Bidder]:
    """
    Fetch a single bidder by primary key UUID.
    Returns None if not found or if bidder_id format is invalid.
    """
    if isinstance(bidder_id, str):
        try:
            bidder_id = UUID(bidder_id.strip())
        except (ValueError, AttributeError):
            return None
    stmt = select(Bidder).where(Bidder.id == bidder_id)
    return db.scalars(stmt).first()


def list_bidders(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    status_filter: Optional[BidderStatus] = None,
    search: Optional[str] = None,
) -> Tuple[List[Bidder], int]:
    """
    Retrieves a paginated list of bidders with optional filters.
    Applies safe pagination bounds (max limit 100).
    """
    safe_skip = max(0, skip)
    safe_limit = max(1, min(limit, 100))

    query = select(Bidder)

    if status_filter is not None:
        query = query.where(Bidder.status == status_filter)

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Bidder.company_name.ilike(search_pattern),
                Bidder.registration_number.ilike(search_pattern),
                Bidder.gst_number.ilike(search_pattern),
                Bidder.pan_number.ilike(search_pattern),
                Bidder.contact_person.ilike(search_pattern),
                Bidder.email.ilike(search_pattern),
            )
        )

    # Total matching records count
    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = db.scalar(count_stmt) or 0

    items_stmt = query.order_by(Bidder.created_at.desc()).offset(safe_skip).limit(safe_limit)
    items = list(db.scalars(items_stmt).all())

    return items, total_count


def create_bidder(
    db: Session,
    bidder_in: Union[BidderCreate, dict],
    user_id: Optional[UUID] = None,
) -> Bidder:
    """
    Creates a new Bidder entity in the database.
    """
    if isinstance(bidder_in, dict):
        bidder_in = BidderCreate.model_validate(bidder_in)

    db_bidder = Bidder(
        company_name=bidder_in.company_name.strip(),
        registration_number=bidder_in.registration_number.strip() if bidder_in.registration_number else None,
        gst_number=bidder_in.gst_number.strip() if bidder_in.gst_number else None,
        pan_number=bidder_in.pan_number.strip() if bidder_in.pan_number else None,
        udyam_number=bidder_in.udyam_number.strip() if bidder_in.udyam_number else None,
        contact_person=bidder_in.contact_person.strip() if bidder_in.contact_person else None,
        email=bidder_in.email.strip() if bidder_in.email else None,
        phone=bidder_in.phone.strip() if bidder_in.phone else None,
        address=bidder_in.address.strip() if bidder_in.address else None,
        status=bidder_in.status,
        user_id=user_id,
    )
    db.add(db_bidder)
    db.commit()
    db.refresh(db_bidder)
    logger.info(f"Bidder created [id={db_bidder.id}, company={db_bidder.company_name}]")
    return db_bidder


def update_bidder(
    db: Session,
    db_bidder: Union[Bidder, UUID, str],
    bidder_update: Union[BidderUpdate, dict],
) -> Bidder:
    """
    Updates attributes of an existing Bidder record.
    """
    if isinstance(db_bidder, (UUID, str)):
        target_bidder = get_bidder_by_id(db, db_bidder)
        if not target_bidder:
            raise NotFoundException(message=f"Bidder with ID '{db_bidder}' not found.")
        db_bidder = target_bidder

    if isinstance(bidder_update, BidderUpdate):
        update_data = bidder_update.model_dump(exclude_unset=True)
    elif isinstance(bidder_update, dict):
        update_data = {k: v for k, v in bidder_update.items() if v is not None}
    else:
        update_data = {}

    for field, value in update_data.items():
        if hasattr(db_bidder, field):
            setattr(db_bidder, field, value)

    db.add(db_bidder)
    db.commit()
    db.refresh(db_bidder)
    logger.info(f"Bidder updated [id={db_bidder.id}]")
    return db_bidder


def update_bidder_status(
    db: Session,
    db_bidder: Union[Bidder, UUID, str],
    new_status: BidderStatus,
) -> Bidder:
    """Updates operational status of a bidder."""
    if isinstance(db_bidder, (UUID, str)):
        target_bidder = get_bidder_by_id(db, db_bidder)
        if not target_bidder:
            raise NotFoundException(message=f"Bidder with ID '{db_bidder}' not found.")
        db_bidder = target_bidder

    db_bidder.status = new_status
    db.add(db_bidder)
    db.commit()
    db.refresh(db_bidder)
    logger.info(f"Bidder status updated [id={db_bidder.id}, status={new_status}]")
    return db_bidder


def assign_bidder_to_tender(
    db: Session,
    tender_id: UUID,
    bidder_id: UUID,
) -> TenderBidder:
    """
    Assigns a bidder to participate in a tender.
    Raises 404 if tender or bidder not found.
    Raises 409 if bidder is already assigned to the tender.
    """
    tender = db.get(Tender, tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    bidder = db.get(Bidder, bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    # Check for existing assignment
    stmt = select(TenderBidder).where(
        TenderBidder.tender_id == tender_id,
        TenderBidder.bidder_id == bidder_id,
    )
    existing = db.scalars(stmt).first()
    if existing:
        raise AppException(
            message=f"Bidder '{bidder.company_name}' is already assigned to tender '{tender.tender_number}'.",
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
        )

    assignment = TenderBidder(
        tender_id=tender_id,
        bidder_id=bidder_id,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    logger.info(f"Assigned bidder {bidder_id} to tender {tender_id}")
    return assignment


def remove_bidder_from_tender(
    db: Session,
    tender_id: UUID,
    bidder_id: UUID,
) -> bool:
    """
    Removes a bidder from participating in a tender.
    Raises 404 if tender, bidder, or assignment is not found.
    """
    tender = db.get(Tender, tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    bidder = db.get(Bidder, bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    stmt = select(TenderBidder).where(
        TenderBidder.tender_id == tender_id,
        TenderBidder.bidder_id == bidder_id,
    )
    assignment = db.scalars(stmt).first()
    if not assignment:
        raise NotFoundException(
            message=f"Bidder with id '{bidder_id}' is not assigned to tender with id '{tender_id}'."
        )

    db.delete(assignment)
    db.commit()
    logger.info(f"Removed bidder {bidder_id} from tender {tender_id}")
    return True


def get_tender_bidders(
    db: Session,
    tender_id: UUID,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[TenderBidder], int]:
    """
    Retrieves paginated list of Bidders assigned to a Tender, including assignment timestamp.
    Raises 404 if Tender does not exist.
    """
    tender = db.get(Tender, tender_id)
    if not tender:
        raise NotFoundException(message=f"Tender with id '{tender_id}' not found.")

    safe_skip = max(0, skip)
    safe_limit = max(1, min(limit, 100))

    query = (
        select(TenderBidder)
        .where(TenderBidder.tender_id == tender_id)
        .options(joinedload(TenderBidder.bidder))
    )

    count_stmt = select(func.count()).select_from(
        select(TenderBidder).where(TenderBidder.tender_id == tender_id).subquery()
    )
    total_count = db.scalar(count_stmt) or 0

    items_stmt = query.order_by(TenderBidder.created_at.desc()).offset(safe_skip).limit(safe_limit)
    items = list(db.scalars(items_stmt).all())

    return items, total_count


def get_bidder_tenders(
    db: Session,
    bidder_id: UUID,
    skip: int = 0,
    limit: int = 20,
) -> Tuple[List[TenderBidder], int]:
    """
    Retrieves paginated list of Tenders in which a Bidder is participating.
    Raises 404 if Bidder does not exist.
    """
    bidder = db.get(Bidder, bidder_id)
    if not bidder:
        raise NotFoundException(message=f"Bidder with id '{bidder_id}' not found.")

    safe_skip = max(0, skip)
    safe_limit = max(1, min(limit, 100))

    query = (
        select(TenderBidder)
        .where(TenderBidder.bidder_id == bidder_id)
        .options(joinedload(TenderBidder.tender))
    )

    count_stmt = select(func.count()).select_from(
        select(TenderBidder).where(TenderBidder.bidder_id == bidder_id).subquery()
    )
    total_count = db.scalar(count_stmt) or 0

    items_stmt = query.order_by(TenderBidder.created_at.desc()).offset(safe_skip).limit(safe_limit)
    items = list(db.scalars(items_stmt).all())

    return items, total_count


class CRUDBidder:
    """Data layer and service facade for Bidder entities."""

    get_by_id = staticmethod(get_bidder_by_id)
    get_bidder_by_id = staticmethod(get_bidder_by_id)

    get_multi = staticmethod(list_bidders)
    list_bidders = staticmethod(list_bidders)

    create = staticmethod(create_bidder)
    create_bidder = staticmethod(create_bidder)

    update = staticmethod(update_bidder)
    update_bidder = staticmethod(update_bidder)

    update_status = staticmethod(update_bidder_status)
    update_bidder_status = staticmethod(update_bidder_status)

    assign_to_tender = staticmethod(assign_bidder_to_tender)
    assign_bidder_to_tender = staticmethod(assign_bidder_to_tender)

    remove_from_tender = staticmethod(remove_bidder_from_tender)
    remove_bidder_from_tender = staticmethod(remove_bidder_from_tender)

    get_tender_bidders = staticmethod(get_tender_bidders)
    get_bidder_tenders = staticmethod(get_bidder_tenders)


crud_bidder = CRUDBidder()
