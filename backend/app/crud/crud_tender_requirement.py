import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tender_requirement import TenderRequirement
from app.schemas.tender_requirement import TenderRequirementCreate, TenderRequirementUpdate

logger = logging.getLogger("app.crud.tender_requirement")


class CRUDTenderRequirement:
    """Data access operations for Tender Requirements."""

    def create(
        self,
        db: Session,
        tender_id: Union[UUID, str],
        requirement_in: Union[TenderRequirementCreate, Dict[str, Any]],
    ) -> TenderRequirement:
        """Creates and persists a single requirement for a tender."""
        if isinstance(requirement_in, dict):
            req_data = requirement_in.copy()
        else:
            req_data = requirement_in.model_dump()

        target_tender_id = UUID(str(tender_id)) if not isinstance(tender_id, UUID) else tender_id
        db_obj = TenderRequirement(
            tender_id=target_tender_id,
            requirement_type=str(req_data["requirement_type"]).upper(),
            rule=str(req_data["rule"]).strip(),
            description=req_data["description"],
            parameters=req_data.get("parameters", {}),
            mandatory=req_data.get("mandatory", True),
            confidence=float(req_data.get("confidence", 1.0)),
            source_page=req_data.get("source_page"),
            source_section=req_data.get("source_section"),
            source_text=req_data.get("source_text"),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        logger.info(
            f"Created TenderRequirement [id={db_obj.id}, tender_id={target_tender_id}, "
            f"type={db_obj.requirement_type}, rule={db_obj.rule}]"
        )
        return db_obj

    def bulk_create(
        self,
        db: Session,
        tender_id: Union[UUID, str],
        requirements_in: List[Union[TenderRequirementCreate, Dict[str, Any]]],
    ) -> List[TenderRequirement]:
        """Bulk creates multiple requirements for a tender in a single transaction."""
        target_tender_id = UUID(str(tender_id)) if not isinstance(tender_id, UUID) else tender_id
        created_objects: List[TenderRequirement] = []

        for req in requirements_in:
            if isinstance(req, dict):
                req_data = req.copy()
            else:
                req_data = req.model_dump()

            db_obj = TenderRequirement(
                tender_id=target_tender_id,
                requirement_type=str(req_data["requirement_type"]).upper(),
                rule=str(req_data["rule"]).strip(),
                description=req_data["description"],
                parameters=req_data.get("parameters", {}),
                mandatory=req_data.get("mandatory", True),
                confidence=float(req_data.get("confidence", 1.0)),
                source_page=req_data.get("source_page"),
                source_section=req_data.get("source_section"),
                source_text=req_data.get("source_text"),
            )
            db.add(db_obj)
            created_objects.append(db_obj)

        db.commit()
        for obj in created_objects:
            db.refresh(obj)

        logger.info(f"Bulk created {len(created_objects)} requirements for tender_id={target_tender_id}")
        return created_objects

    def get_by_id(
        self,
        db: Session,
        requirement_id: Union[UUID, str],
    ) -> Optional[TenderRequirement]:
        """Fetches a requirement by primary key UUID."""
        try:
            target_id = UUID(str(requirement_id)) if not isinstance(requirement_id, UUID) else requirement_id
        except (ValueError, AttributeError):
            return None
        stmt = select(TenderRequirement).where(TenderRequirement.id == target_id)
        return db.scalars(stmt).first()

    def get_by_tender(
        self,
        db: Session,
        tender_id: Union[UUID, str],
        requirement_type: Optional[str] = None,
        mandatory_only: bool = False,
    ) -> List[TenderRequirement]:
        """Fetches all requirements for a specific tender, with optional type and mandatory filters."""
        try:
            target_id = UUID(str(tender_id)) if not isinstance(tender_id, UUID) else tender_id
        except (ValueError, AttributeError):
            return []

        stmt = select(TenderRequirement).where(TenderRequirement.tender_id == target_id)

        if requirement_type:
            stmt = stmt.where(TenderRequirement.requirement_type == requirement_type.strip().upper())
        if mandatory_only:
            stmt = stmt.where(TenderRequirement.mandatory.is_(True))

        stmt = stmt.order_by(TenderRequirement.created_at.asc())
        return list(db.scalars(stmt).all())

    def update(
        self,
        db: Session,
        db_obj: TenderRequirement,
        requirement_in: Union[TenderRequirementUpdate, Dict[str, Any]],
    ) -> TenderRequirement:
        """Updates attributes of an existing requirement."""
        if isinstance(requirement_in, dict):
            update_data = requirement_in
        else:
            update_data = requirement_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            if field == "requirement_type" and value is not None:
                setattr(db_obj, field, str(value).upper())
            elif field == "rule" and value is not None:
                setattr(db_obj, field, str(value).strip())
            elif hasattr(db_obj, field):
                setattr(db_obj, field, value)

        db.commit()
        db.refresh(db_obj)
        logger.info(f"Updated TenderRequirement [id={db_obj.id}]")
        return db_obj

    def delete(
        self,
        db: Session,
        requirement_id: Union[UUID, str],
    ) -> bool:
        """Deletes a requirement by ID. Returns True if deleted, False if not found."""
        db_obj = self.get_by_id(db, requirement_id=requirement_id)
        if not db_obj:
            return False
        db.delete(db_obj)
        db.commit()
        logger.info(f"Deleted TenderRequirement [id={requirement_id}]")
        return True

    def delete_by_tender(
        self,
        db: Session,
        tender_id: Union[UUID, str],
    ) -> int:
        """Deletes all requirements for a tender. Returns count of deleted records."""
        items = self.get_by_tender(db, tender_id=tender_id)
        count = len(items)
        for item in items:
            db.delete(item)
        db.commit()
        logger.info(f"Deleted {count} requirements for tender_id={tender_id}")
        return count


crud_tender_requirement = CRUDTenderRequirement()

# Convenience functional exports
create_requirement = crud_tender_requirement.create
bulk_create_requirements = crud_tender_requirement.bulk_create
get_requirement_by_id = crud_tender_requirement.get_by_id
get_requirements_by_tender = crud_tender_requirement.get_by_tender
update_requirement = crud_tender_requirement.update
delete_requirement = crud_tender_requirement.delete
delete_requirements_by_tender = crud_tender_requirement.delete_by_tender
