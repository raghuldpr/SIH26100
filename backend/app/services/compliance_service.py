"""
Phase 09 — Compliance Rule Engine
compliance_service.py: Service-layer orchestration for compliance evaluation.

Follows the required architecture:
API
↓
Compliance Service
↓
Rule Engine
↓
PostgreSQL / SQLAlchemy

Guarantees:
- Never overwrites historical evaluation records (full audit trail).
- Operates inside explicit SQLAlchemy transactions.
- Bridges database models <-> domain compliance models cleanly.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.compliance.engine import ComplianceEngine, engine as global_engine
from app.compliance.enums import Operator, RuleType
from app.compliance.models import (
    BidderEvidence as DomainEvidence,
    ComplianceResult as DomainResult,
    Requirement as DomainRequirement,
    RuleDefinition as DomainRuleDef,
)
from app.models.compliance import (
    BidderEvidenceModel,
    ComplianceRequirement,
    ComplianceResultModel,
)
from app.schemas.compliance import (
    BidderEvidenceCreate,
    RequirementCreate,
)

logger = logging.getLogger("app.services.compliance")


def _make_json_safe(val: Any) -> Any:
    """Recursively convert Decimals, dates, UUIDs to JSON-serializable primitives."""
    if val is None:
        return None
    from decimal import Decimal
    from datetime import date, datetime
    if isinstance(val, Decimal):
        # Prefer float or int representation
        return int(val) if val % 1 == 0 else float(val)
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, dict):
        return {k: _make_json_safe(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_make_json_safe(v) for v in val]
    return val


class ComplianceService:
    """
    Service layer providing database persistence and evaluation dispatch
    for the deterministic compliance rule engine.
    """

    def __init__(self, engine_instance: Optional[ComplianceEngine] = None):
        self.engine = engine_instance or global_engine


    # ------------------------------------------------------------------
    # Requirements Management
    # ------------------------------------------------------------------

    def create_requirement(
        self,
        db: Session,
        requirement_in: Union[RequirementCreate, Dict[str, Any]],
    ) -> ComplianceRequirement:
        """Persist a new compliance requirement for a tender."""
        if isinstance(requirement_in, dict):
            data = requirement_in.copy()
        else:
            data = requirement_in.model_dump()

        tender_id = (
            uuid.UUID(str(data["tender_id"]))
            if not isinstance(data["tender_id"], uuid.UUID)
            else data["tender_id"]
        )

        rule_type_val = data["rule_type"]
        if hasattr(rule_type_val, "value"):
            rule_type_val = rule_type_val.value

        req_obj = ComplianceRequirement(
            id=data.get("id") or uuid.uuid4(),
            requirement_id=data.get("requirement_id") or uuid.uuid4(),
            tender_id=tender_id,
            category=str(data["category"]).upper(),
            field=str(data["field"]).strip().lower().replace(" ", "_"),
            rule_type=str(rule_type_val).upper(),
            rule_definition=data.get("rule_definition", {}),
            mandatory=data.get("mandatory", True),
            description=data.get("description"),
        )
        db.add(req_obj)
        db.commit()
        db.refresh(req_obj)
        logger.info(
            "Created ComplianceRequirement [id=%s, tender_id=%s, field=%s, rule_type=%s]",
            req_obj.id,
            req_obj.tender_id,
            req_obj.field,
            req_obj.rule_type,
        )
        return req_obj

    def get_requirement(
        self,
        db: Session,
        requirement_id: uuid.UUID,
    ) -> Optional[ComplianceRequirement]:
        """Fetch requirement by primary key id or canonical requirement_id."""
        stmt = select(ComplianceRequirement).where(
            (ComplianceRequirement.id == requirement_id)
            | (ComplianceRequirement.requirement_id == requirement_id)
        )
        return db.scalars(stmt).first()

    def list_requirements_by_tender(
        self,
        db: Session,
        tender_id: uuid.UUID,
    ) -> List[ComplianceRequirement]:
        """Retrieve all requirements configured for a tender."""
        stmt = (
            select(ComplianceRequirement)
            .where(ComplianceRequirement.tender_id == tender_id)
            .order_by(ComplianceRequirement.category, ComplianceRequirement.field)
        )
        return list(db.scalars(stmt).all())

    # ------------------------------------------------------------------
    # Bidder Evidence Management
    # ------------------------------------------------------------------

    def save_bidder_evidence(
        self,
        db: Session,
        evidence_in: Union[BidderEvidenceCreate, Dict[str, Any]],
    ) -> BidderEvidenceModel:
        """Persist or record a piece of bidder evidence."""
        if isinstance(evidence_in, dict):
            data = evidence_in.copy()
        else:
            data = evidence_in.model_dump()

        bidder_id = (
            uuid.UUID(str(data["bidder_id"]))
            if not isinstance(data["bidder_id"], uuid.UUID)
            else data["bidder_id"]
        )

        field_norm = str(data["field"]).strip().lower().replace(" ", "_")

        ev_obj = BidderEvidenceModel(
            id=data.get("id") or uuid.uuid4(),
            evidence_id=data.get("evidence_id") or uuid.uuid4(),
            bidder_id=bidder_id,
            field=field_norm,
            value=data.get("value"),
            source_document=data.get("source_document"),
            confidence=float(data.get("confidence", 1.0)),
        )
        db.add(ev_obj)
        db.commit()
        db.refresh(ev_obj)
        logger.info(
            "Saved BidderEvidence [id=%s, bidder_id=%s, field=%s]",
            ev_obj.id,
            ev_obj.bidder_id,
            ev_obj.field,
        )
        return ev_obj

    def get_bidder_evidence(
        self,
        db: Session,
        bidder_id: uuid.UUID,
        field: str,
    ) -> Optional[BidderEvidenceModel]:
        """Retrieve the most recently recorded evidence for a bidder and field."""
        field_norm = str(field).strip().lower().replace(" ", "_")
        stmt = (
            select(BidderEvidenceModel)
            .where(
                BidderEvidenceModel.bidder_id == bidder_id,
                BidderEvidenceModel.field == field_norm,
            )
            .order_by(desc(BidderEvidenceModel.created_at))
        )
        return db.scalars(stmt).first()

    def list_bidder_evidence(
        self,
        db: Session,
        bidder_id: uuid.UUID,
    ) -> List[BidderEvidenceModel]:
        """Retrieve all evidence items submitted by a bidder."""
        stmt = (
            select(BidderEvidenceModel)
            .where(BidderEvidenceModel.bidder_id == bidder_id)
            .order_by(BidderEvidenceModel.field, desc(BidderEvidenceModel.created_at))
        )
        return list(db.scalars(stmt).all())

    # ------------------------------------------------------------------
    # Compliance Evaluation
    # ------------------------------------------------------------------

    def evaluate_requirement(
        self,
        db: Session,
        requirement_id: uuid.UUID,
        bidder_id: uuid.UUID,
        exemptions: Optional[List[Dict[str, Any]]] = None,
    ) -> ComplianceResultModel:
        """
        Evaluate a single requirement for a bidder, persisting the audit outcome.
        Never overwrites previous results.
        """
        db_req = self.get_requirement(db, requirement_id)
        if not db_req:
            raise ValueError(f"Requirement with ID {requirement_id} not found.")

        # Fetch evidence for this field and all evidence for the bidder (for exemptions)
        all_ev_models = self.list_bidder_evidence(db, bidder_id)
        ev_map: Dict[str, DomainEvidence] = {}
        for m in all_ev_models:
            if m.field not in ev_map:  # Keep latest
                ev_map[m.field] = self._to_domain_evidence(m)

        target_ev = ev_map.get(db_req.field)
        domain_req = self._to_domain_requirement(db_req)

        # Evaluate via Rule Engine
        result = self.engine.evaluate(
            domain_req,
            target_ev,
            exemptions=exemptions,
            evidence_map=ev_map,
        )

        # Persist ComplianceResultModel inside transaction
        db_result = self._persist_result(db, db_req.id, bidder_id, result)
        return db_result

    def evaluate_bidder_compliance(
        self,
        db: Session,
        tender_id: uuid.UUID,
        bidder_id: uuid.UUID,
        exemptions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[ComplianceResultModel]:
        """
        Evaluate all requirements of a tender for a bidder in a single transaction.
        Preserves all historical evaluations.
        """
        db_reqs = self.list_requirements_by_tender(db, tender_id)
        all_ev_models = self.list_bidder_evidence(db, bidder_id)

        ev_map: Dict[str, DomainEvidence] = {}
        for m in all_ev_models:
            if m.field not in ev_map:
                ev_map[m.field] = self._to_domain_evidence(m)

        domain_reqs = [self._to_domain_requirement(r) for r in db_reqs]

        # Batch evaluation
        results = self.engine.evaluate_batch(
            domain_reqs,
            ev_map,
            exemptions=exemptions,
        )

        # Persist all results atomically
        persisted_results: List[ComplianceResultModel] = []
        for db_req, res in zip(db_reqs, results):
            db_res = self._persist_result(db, db_req.id, bidder_id, res, commit=False)
            persisted_results.append(db_res)

        db.commit()
        for r in persisted_results:
            db.refresh(r)

        logger.info(
            "Evaluated tender=%s for bidder=%s: %d requirement(s) processed.",
            tender_id,
            bidder_id,
            len(persisted_results),
        )
        return persisted_results

    def get_compliance_results(
        self,
        db: Session,
        bidder_id: uuid.UUID,
        requirement_id: Optional[uuid.UUID] = None,
    ) -> List[ComplianceResultModel]:
        """
        Retrieve audit trail of evaluation results.
        Ordered by evaluated_at descending.
        """
        stmt = select(ComplianceResultModel).where(ComplianceResultModel.bidder_id == bidder_id)
        if requirement_id:
            stmt = stmt.where(ComplianceResultModel.requirement_id == requirement_id)
        stmt = stmt.order_by(desc(ComplianceResultModel.evaluated_at))
        return list(db.scalars(stmt).all())

    # ------------------------------------------------------------------
    # Conversion Helpers
    # ------------------------------------------------------------------

    def _to_domain_requirement(self, db_req: ComplianceRequirement) -> DomainRequirement:
        raw_def = db_req.rule_definition or {}
        op_str = raw_def.get("operator", "EQUAL")
        try:
            op = Operator(op_str)
        except ValueError:
            op = Operator.EQUAL

        rule_def = DomainRuleDef(
            operator=op,
            required_value=raw_def.get("required_value"),
            unit=raw_def.get("unit"),
            logical_operator=raw_def.get("logical_operator"),
            sub_rules=[self._parse_sub_rule(s) for s in raw_def.get("sub_rules", [])] if raw_def.get("sub_rules") else None,
            extra=raw_def.get("extra", {}),
        )

        rule_type_val = db_req.rule_type
        try:
            rt = RuleType(rule_type_val)
        except ValueError:
            rt = RuleType.NUMERIC

        return DomainRequirement(
            requirement_id=db_req.requirement_id or db_req.id,
            tender_id=db_req.tender_id,
            category=db_req.category,
            field=db_req.field,
            rule_type=rt,
            rule_definition=rule_def,
            mandatory=db_req.mandatory,
            description=db_req.description or "",
        )

    def _parse_sub_rule(self, raw: Dict[str, Any]) -> DomainRuleDef:
        op_str = raw.get("operator", "EQUAL")
        try:
            op = Operator(op_str)
        except ValueError:
            op = Operator.EQUAL
        return DomainRuleDef(
            operator=op,
            required_value=raw.get("required_value"),
            unit=raw.get("unit"),
            logical_operator=raw.get("logical_operator"),
            extra=raw.get("extra", {}),
        )

    def _to_domain_evidence(self, db_ev: BidderEvidenceModel) -> DomainEvidence:
        return DomainEvidence(
            evidence_id=db_ev.evidence_id or db_ev.id,
            bidder_id=db_ev.bidder_id,
            field=db_ev.field,
            value=db_ev.value,
            source_document=db_ev.source_document,
            confidence=db_ev.confidence,
        )

    def _persist_result(
        self,
        db: Session,
        db_req_id: uuid.UUID,
        bidder_id: uuid.UUID,
        result: DomainResult,
        commit: bool = True,
    ) -> ComplianceResultModel:
        db_obj = ComplianceResultModel(
            id=uuid.uuid4(),
            requirement_id=db_req_id,
            bidder_id=bidder_id,
            status=result.status.value,
            reason=result.reason,
            evidence_reference=result.evidence_reference,
            rule_type=result.rule_type.value if result.rule_type else None,
            operator_used=result.operator_used.value if result.operator_used else None,
            actual_value=_make_json_safe(result.actual_value),
            required_value=_make_json_safe(result.required_value),
            evaluated_at=result.evaluated_at,
        )

        db.add(db_obj)
        if commit:
            db.commit()
            db.refresh(db_obj)
        return db_obj


# Global singleton service instance
compliance_service = ComplianceService()
