from datetime import datetime, timezone
import logging
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session


from app.core.exceptions import BadRequestException
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


class CRUDTender:
    """Data layer operations for Tender procurement entities."""

    def get_by_id(self, db: Session, tender_id: UUID) -> Optional[Tender]:
        """Fetch a single tender by primary key UUID."""
        stmt = select(Tender).where(Tender.id == tender_id)
        return db.scalars(stmt).first()

    def get_by_tender_number(self, db: Session, tender_number: str) -> Optional[Tender]:
        """Fetch a tender by unique official tender number."""
        stmt = select(Tender).where(Tender.tender_number == tender_number.strip())
        return db.scalars(stmt).first()

    def get_multi(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 20,
        created_by: Optional[UUID] = None,
        status: Optional[TenderStatus] = None,
        search: Optional[str] = None,
        include_archived: bool = False,
    ) -> Tuple[List[Tender], int]:
        """
        Retrieves a paginated list of tenders with optional filters.
        Returns a tuple of (items, total_count).
        """
        query = select(Tender)

        if created_by is not None:
            query = query.where(Tender.created_by == created_by)

        if status is not None:
            query = query.where(Tender.status == status)
        elif not include_archived:
            query = query.where(Tender.status != TenderStatus.ARCHIVED)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Tender.title.ilike(search_pattern),
                    Tender.tender_number.ilike(search_pattern),
                    Tender.organization.ilike(search_pattern),
                    Tender.category.ilike(search_pattern),
                )
            )

        # Count total matching records
        count_stmt = select(func.count()).select_from(query.subquery())
        total_count = db.scalar(count_stmt) or 0

        # Apply ordering and pagination
        items_stmt = query.order_by(Tender.created_at.desc()).offset(skip).limit(limit)
        items = list(db.scalars(items_stmt).all())

        return items, total_count

    def create(
        self, db: Session, tender_in: TenderCreate, created_by: UUID
    ) -> Tender:
        """
        Creates a new tender record associated with the creating user.
        Rejects duplicate tender numbers.
        """
        existing = self.get_by_tender_number(db, tender_number=tender_in.tender_number)
        if existing:
            raise BadRequestException(
                message=f"Tender with number '{tender_in.tender_number}' already exists."
            )

        db_tender = Tender(
            tender_number=tender_in.tender_number.strip(),
            title=tender_in.title.strip(),
            organization=tender_in.organization.strip(),
            department=tender_in.department.strip() if tender_in.department else None,
            category=tender_in.category.strip() if tender_in.category else None,
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

    def update(
        self, db: Session, db_tender: Tender, tender_update: TenderUpdate
    ) -> Tender:
        """
        Updates tender attributes while enforcing date validity and protecting immutable fields.
        """
        update_data = tender_update.model_dump(exclude_unset=True)

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


    def archive(self, db: Session, db_tender: Tender) -> Tender:
        """
        Soft-deletes / archives a tender record, preserving historical data.
        """
        db_tender.status = TenderStatus.ARCHIVED
        db.add(db_tender)
        db.commit()
        db.refresh(db_tender)
        logger.info(f"Tender archived [id={db_tender.id}, num={db_tender.tender_number}]")
        return db_tender


crud_tender = CRUDTender()
