from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple, Union
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.enums import TenderStatus
from app.models.tender import Tender
from app.schemas.tender import TenderCreate, TenderUpdate

logger = logging.getLogger("app.crud.tender")


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalizes datetime to UTC timezone-aware for reliable comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_tender_by_id(db: Session, tender_id: Union[UUID, str]) -> Optional[Tender]:
    """
    Fetch a single tender by primary key UUID.
    Returns None if not found or if tender_id format is invalid.
    """
    if isinstance(tender_id, str):
        try:
            tender_id = UUID(tender_id.strip())
        except (ValueError, AttributeError):
            return None
    stmt = select(Tender).where(Tender.id == tender_id)
    return db.scalars(stmt).first()


def get_tender_by_number(db: Session, tender_number: str) -> Optional[Tender]:
    """Fetch a tender by unique official tender number."""
    if not tender_number or not tender_number.strip():
        return None
    stmt = select(Tender).where(Tender.tender_number == tender_number.strip())
    return db.scalars(stmt).first()


def list_tenders(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    status: Optional[TenderStatus] = None,
    department: Optional[str] = None,
    category: Optional[str] = None,
    created_by: Optional[UUID] = None,
    search: Optional[str] = None,
    include_archived: bool = False,
) -> Tuple[List[Tender], int]:
    """
    Retrieves a paginated list of tenders with optional filters.
    Applies sensible pagination limits (capped at 100).
    Returns a tuple of (items, total_count).
    """
    # Enforce safe pagination bounds
    safe_skip = max(0, skip)
    safe_limit = max(1, min(limit, 100))

    query = select(Tender)

    if created_by is not None:
        query = query.where(Tender.created_by == created_by)

    if status is not None:
        query = query.where(Tender.status == status)
    elif not include_archived:
        query = query.where(Tender.status != TenderStatus.ARCHIVED)

    if department:
        query = query.where(Tender.department.ilike(department.strip()))

    if category:
        query = query.where(Tender.category.ilike(category.strip()))

    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                Tender.title.ilike(search_pattern),
                Tender.tender_number.ilike(search_pattern),
                Tender.organization.ilike(search_pattern),
                Tender.department.ilike(search_pattern),
                Tender.category.ilike(search_pattern),
            )
        )

    # Count total matching records
    count_stmt = select(func.count()).select_from(query.subquery())
    total_count = db.scalar(count_stmt) or 0

    # Apply ordering and pagination
    items_stmt = query.order_by(Tender.created_at.desc()).offset(safe_skip).limit(safe_limit)
    items = list(db.scalars(items_stmt).all())

    return items, total_count


def create_tender(
    db: Session,
    tender_in: Union[TenderCreate, dict],
    created_by: Optional[UUID] = None,
) -> Tender:
    """
    Creates a new tender record.
    Detects duplicate tender_number and returns a clean error.
    """
    if isinstance(tender_in, dict):
        tender_in = TenderCreate.model_validate(tender_in)

    existing = get_tender_by_number(db, tender_number=tender_in.tender_number)
    if existing:
        raise BadRequestException(
            message=f"Tender with number '{tender_in.tender_number}' already exists."
        )

    # Validate date relationship
    start_utc = _ensure_utc(tender_in.bid_start_date)
    end_utc = _ensure_utc(tender_in.bid_end_date)
    if start_utc and end_utc and end_utc < start_utc:
        raise BadRequestException(
            message="Invalid date range: bid_end_date cannot be earlier than bid_start_date."
        )

    db_tender = Tender(
        tender_number=tender_in.tender_number.strip(),
        title=tender_in.title.strip(),
        organization=tender_in.organization.strip(),
        department=tender_in.department.strip() if tender_in.department else "General",
        category=tender_in.category.strip() if tender_in.category else "General",
        description=tender_in.description,
        bid_start_date=tender_in.bid_start_date,
        bid_end_date=tender_in.bid_end_date,
        status=tender_in.status,
        created_by=created_by,
    )
    db.add(db_tender)
    db.commit()
    db.refresh(db_tender)
    logger.info(f"Tender created [id={db_tender.id}, num={db_tender.tender_number}, by={created_by}]")
    return db_tender


def update_tender(
    db: Session,
    db_tender: Union[Tender, UUID, str],
    tender_update: Union[TenderUpdate, dict],
) -> Tender:
    """
    Updates tender attributes while enforcing date validity and unique tender_number.
    Preserves existing values for omitted fields.
    """
    if isinstance(db_tender, (UUID, str)):
        target_tender = get_tender_by_id(db, db_tender)
        if not target_tender:
            raise NotFoundException(message=f"Tender with ID '{db_tender}' not found.")
        db_tender = target_tender

    if isinstance(tender_update, TenderUpdate):
        update_data = tender_update.model_dump(exclude_unset=True)
    elif isinstance(tender_update, dict):
        update_data = {k: v for k, v in tender_update.items() if v is not None}
    else:
        update_data = {}

    # Check for duplicate tender_number if being modified
    if "tender_number" in update_data and update_data["tender_number"]:
        new_num = update_data["tender_number"].strip()
        if new_num != db_tender.tender_number:
            existing = get_tender_by_number(db, tender_number=new_num)
            if existing and existing.id != db_tender.id:
                raise BadRequestException(
                    message=f"Tender with number '{new_num}' already exists."
                )
            update_data["tender_number"] = new_num

    # Check cross-field date validity against updated or existing values
    new_start = update_data.get("bid_start_date", db_tender.bid_start_date)
    new_end = update_data.get("bid_end_date", db_tender.bid_end_date)
    new_start_utc = _ensure_utc(new_start)
    new_end_utc = _ensure_utc(new_end)
    if new_start_utc and new_end_utc and new_end_utc < new_start_utc:
        raise BadRequestException(
            message="Invalid date range: bid_end_date cannot be earlier than bid_start_date."
        )

    for field, value in update_data.items():
        if hasattr(db_tender, field):
            setattr(db_tender, field, value)

    db.add(db_tender)
    db.commit()
    db.refresh(db_tender)
    logger.info(f"Tender updated [id={db_tender.id}]")
    return db_tender


def archive_tender(db: Session, db_tender: Union[Tender, UUID, str]) -> Tender:
    """
    Soft-archives a tender record, preserving full history without destructive deletion.
    """
    if isinstance(db_tender, (UUID, str)):
        target_tender = get_tender_by_id(db, db_tender)
        if not target_tender:
            raise NotFoundException(message=f"Tender with ID '{db_tender}' not found.")
        db_tender = target_tender

    db_tender.status = TenderStatus.ARCHIVED
    db.add(db_tender)
    db.commit()
    db.refresh(db_tender)
    logger.info(f"Tender archived [id={db_tender.id}, num={db_tender.tender_number}]")
    return db_tender


class CRUDTender:
    """Data layer operations and service methods for Tender procurement entities."""

    get_by_id = staticmethod(get_tender_by_id)
    get_tender_by_id = staticmethod(get_tender_by_id)

    get_by_tender_number = staticmethod(get_tender_by_number)
    get_tender_by_number = staticmethod(get_tender_by_number)

    get_multi = staticmethod(list_tenders)
    list_tenders = staticmethod(list_tenders)

    create = staticmethod(create_tender)
    create_tender = staticmethod(create_tender)

    update = staticmethod(update_tender)
    update_tender = staticmethod(update_tender)

    archive = staticmethod(archive_tender)
    archive_tender = staticmethod(archive_tender)


crud_tender = CRUDTender()
