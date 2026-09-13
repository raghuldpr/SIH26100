"""
Phase 18 — End-to-End Tender Intelligence Integration Test
Covers:
Tender -> Document -> Extraction -> Requirement Intelligence
-> Deterministic/Groq normalization -> Requirement persistence
-> Bidder evidence -> Compliance -> Verification -> Audit
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import fitz
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.compliance.enums import ComplianceStatus, Operator, RuleType
from app.config import settings
from app.core.storage import storage_service
from app.core.validation import calculate_sha256
from app.crud.crud_verification import crud_verification
from app.db.session import SessionLocal
from app.models.bidder import Bidder, TenderBidder
from app.models.compliance import BidderEvidenceModel, ComplianceRequirement, ComplianceResultModel
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType, ProcessingStatus, TenderStatus
from app.models.tender import Tender
from app.models.tender_requirement import TenderRequirement
from app.models.verification import VerificationAuditEvent, VerificationExecution
from app.schemas.tender_requirement_normalizer import NormalizationStatus
from app.schemas.verification import (
    OverallComplianceEnum,
    RequirementComplianceEnum,
    RequirementEvaluation,
    RiskLevelEnum,
    VerificationDecisionEnum,
    VerificationResponse,
    VerificationStatusEnum,
)
from app.services.ai_gateway import AIGateway
from app.services.compliance_service import compliance_service
from app.services.document_classifier import document_classifier
from app.services.document_processor import document_processor
from app.services.tender_intelligence_service import TenderIntelligenceService


@pytest.mark.integration
def test_phase18_end_to_end_pipeline():
    """Execute complete Phase 18 pipeline with deterministic bypass, live Groq, and full cleanup."""
    db: Session = SessionLocal()

    created_tender_ids = []
    created_bidder_ids = []
    created_doc_paths = []
    created_verification_ids = []

    all_tables = [
        "users", "tenders", "bidders", "documents", "requirements",
        "tender_requirements", "tender_bidders", "bidder_evidence",
        "compliance_results", "verification_executions", "verification_audit_events"
    ]

    try:
        # Step 1: Verify Groq Model
        assert settings.GROQ_MODEL == "qwen/qwen3.8-27b"

        # Step 2: Create Tender
        test_uuid = uuid.uuid4()
        tender_number = f"GEM/2026/B/P18_{str(test_uuid)[:8].upper()}"
        tender = Tender(
            id=test_uuid,
            tender_number=tender_number,
            title="SYNTHETIC TENDER - PHASE 18 AUTOMATED TEST",
            description="Procurement of enterprise cloud services and infrastructure support.",
            organization="Ministry of Electronics and Information Technology",
            department="Information Technology",
            category="IT_SERVICES",
            status=TenderStatus.PUBLISHED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(tender)
        db.commit()
        db.refresh(tender)
        created_tender_ids.append(tender.id)

        # Step 3: Generate & Upload Tender PDF
        tender_doc_text = f"""NOTICE INVITING TENDER
Tender Ref: {tender_number}
SECTION III: QUALIFICATION & ELIGIBILITY CRITERIA

1. The bidder must have valid GST registration certificate and provide active GSTIN.
2. The bidder must have an average annual turnover of at least Rs. 10 Lakhs during the last three financial years.
3. The bidder must have at least 5 years of experience in similar contracts.
4. The bidder must have past experience and track record with sufficient experience in cloud systems.
"""
        fitz_doc = fitz.open()
        f_page = fitz_doc.new_page()
        f_page.insert_text((50, 72), tender_doc_text)
        tender_pdf_bytes = fitz_doc.tobytes()
        fitz_doc.close()

        tender_sha256 = calculate_sha256(tender_pdf_bytes)
        tender_storage_path = f"tenders/{tender.id}/tender_document.pdf"
        uploaded_path = storage_service.upload(
            storage_path=tender_storage_path,
            file_content=tender_pdf_bytes,
            mime_type="application/pdf",
        )
        created_doc_paths.append(uploaded_path)

        doc_record = Document(
            id=uuid.uuid4(),
            tender_id=tender.id,
            original_filename="tender_document.pdf",
            storage_path=uploaded_path,
            document_type=DocumentType.TENDER_PDF,
            mime_type="application/pdf",
            file_size=len(tender_pdf_bytes),
            sha256=tender_sha256,
            status=DocumentStatus.UPLOADED,
            processing_status=ProcessingStatus.NOT_PROCESSED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(doc_record)
        db.commit()

        # Step 4: Extraction & Classification
        extraction_res = document_processor.process_pdf(tender_pdf_bytes, filename="tender_document.pdf")
        assert extraction_res.status == "EXTRACTED"

        classification_res = document_classifier.classify(text=extraction_res.text, filename="tender_document.pdf")
        assert classification_res.document_type == DocumentType.TENDER.value

        # Step 5: Tender Intelligence Processing (Deterministic + Live Groq)
        live_gateway = AIGateway()
        intel_service = TenderIntelligenceService(gateway=live_gateway)

        groq_call_count = 0
        real_chat_create = live_gateway._client.chat.completions.create

        def counted_chat_create(*args, **kwargs):
            nonlocal groq_call_count
            groq_call_count += 1
            return real_chat_create(*args, **kwargs)

        with patch.object(live_gateway._client.chat.completions, "create", side_effect=counted_chat_create):
            batch_result = intel_service.process_tender_pages(
                pages=[{"page_number": 1, "text": extraction_res.text}],
                tender_id=tender.id,
                db=db,
                persist=True,
            )

        # Scenario A: Deterministic clauses bypass Groq
        assert batch_result.normalized_count >= 3
        # Scenario B: Exactly 1 ambiguous clause escalated to Groq
        assert groq_call_count == 1

        ambiguous_reqs = [r for r in batch_result.requirements if r.resolution_method == "AI_GATEWAY"]
        assert len(ambiguous_reqs) == 1
        assert ambiguous_reqs[0].status == NormalizationStatus.UNRESOLVED
        assert "min_years" not in ambiguous_reqs[0].parameters

        persisted_reqs = db.scalars(
            select(TenderRequirement).where(TenderRequirement.tender_id == tender.id)
        ).all()
        assert len(persisted_reqs) >= 3

        # Step 6: Bidder Registration & Evidence Intake
        bidder = Bidder(
            id=uuid.uuid4(),
            company_name="SYNTHETIC BIDDER SOLUTIONS PVT LTD",
            pan_number="AAACB1234K",
            gst_number="27AAACB1234K1Z5",
            email="compliance@syntheticbidder18.com",
            phone="+919876543210",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(bidder)
        db.commit()
        db.refresh(bidder)
        created_bidder_ids.append(bidder.id)

        tb_assoc = TenderBidder(
            id=uuid.uuid4(),
            tender_id=tender.id,
            bidder_id=bidder.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(tb_assoc)
        db.commit()

        bidder_storage_path = f"documents/bidders/{bidder.id}/gst_cert.pdf"
        storage_service.upload(
            storage_path=bidder_storage_path,
            file_content=tender_pdf_bytes,
            mime_type="application/pdf",
        )
        created_doc_paths.append(bidder_storage_path)

        bidder_doc_record = Document(
            id=uuid.uuid4(),
            bidder_id=bidder.id,
            original_filename="gst_cert.pdf",
            storage_path=bidder_storage_path,
            document_type=DocumentType.GST,
            mime_type="application/pdf",
            file_size=len(tender_pdf_bytes),
            sha256=tender_sha256,
            status=DocumentStatus.UPLOADED,
            processing_status=ProcessingStatus.PROCESSED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(bidder_doc_record)
        db.commit()

        compliance_service.save_bidder_evidence(
            db=db,
            evidence_in={
                "bidder_id": bidder.id,
                "field": "gst_registered",
                "value": True,
                "source_document": bidder_storage_path,
                "confidence": 1.0,
            },
        )
        compliance_service.save_bidder_evidence(
            db=db,
            evidence_in={
                "bidder_id": bidder.id,
                "field": "annual_turnover",
                "value": 1500000,
                "source_document": bidder_storage_path,
                "confidence": 0.98,
            },
        )
        compliance_service.save_bidder_evidence(
            db=db,
            evidence_in={
                "bidder_id": bidder.id,
                "field": "years_of_experience",
                "value": 6,
                "source_document": bidder_storage_path,
                "confidence": 0.95,
            },
        )

        # Step 7: Compliance Rule Evaluation
        compliance_service.create_requirement(
            db=db,
            requirement_in={
                "tender_id": tender.id,
                "category": "STATUTORY",
                "rule_type": RuleType.BOOLEAN.value,
                "field": "gst_registered",
                "rule_definition": {"operator": Operator.EQUAL.value, "required_value": True},
                "description": "Active GST Registration",
            },
        )
        compliance_service.create_requirement(
            db=db,
            requirement_in={
                "tender_id": tender.id,
                "category": "FINANCIAL",
                "rule_type": RuleType.NUMERIC.value,
                "field": "annual_turnover",
                "rule_definition": {"operator": Operator.GREATER_THAN_OR_EQUAL.value, "required_value": 1000000},
                "description": "Minimum Turnover 10L",
            },
        )
        compliance_service.create_requirement(
            db=db,
            requirement_in={
                "tender_id": tender.id,
                "category": "TECHNICAL",
                "rule_type": RuleType.NUMERIC.value,
                "field": "years_of_experience",
                "rule_definition": {"operator": Operator.GREATER_THAN_OR_EQUAL.value, "required_value": 5},
                "description": "Minimum 5 Years Experience",
            },
        )
        compliance_service.create_requirement(
            db=db,
            requirement_in={
                "tender_id": tender.id,
                "category": "TECHNICAL",
                "rule_type": RuleType.BOOLEAN.value,
                "field": "cloud_systems_experience_verified",
                "rule_definition": {"operator": Operator.EQUAL.value, "required_value": True},
                "description": "Subjective Cloud Experience",
            },
        )

        outcomes = compliance_service.evaluate_bidder_compliance(
            db=db,
            tender_id=tender.id,
            bidder_id=bidder.id,
        )
        status_map = {}
        for o in outcomes:
            req_obj = compliance_service.get_requirement(db, o.requirement_id)
            status_map[req_obj.field] = o.status

        assert status_map["gst_registered"] == ComplianceStatus.PASS.value
        assert status_map["annual_turnover"] == ComplianceStatus.PASS.value
        assert status_map["years_of_experience"] == ComplianceStatus.PASS.value
        assert status_map["cloud_systems_experience_verified"] == ComplianceStatus.REVIEW.value

        # Step 8: Verification Execution & Audit Logging
        ver_id = f"VER-P18-{str(uuid.uuid4())[:8].upper()}"
        req_id = f"REQ-P18-{str(uuid.uuid4())[:8].upper()}"
        req_hash = hashlib.sha256(f"{tender.id}:{bidder.id}".encode()).hexdigest()
        res_hash = hashlib.sha256("result_summary".encode()).hexdigest()

        exec_record = crud_verification.create_execution(
            db=db,
            verification_id=ver_id,
            request_id=req_id,
            tender_id=tender.id,
            bidder_id=bidder.id,
            request_hash=req_hash,
            status="RUNNING",
        )
        created_verification_ids.append(exec_record.id)

        crud_verification.record_audit_event(
            db=db,
            verification_id=ver_id,
            tender_id=tender.id,
            bidder_id=bidder.id,
            event_type="EXECUTION_INITIALIZED",
            result_hash=None,
            details={"request_hash": req_hash},
        )

        dummy_resp = VerificationResponse(
            id=exec_record.id,
            verification_id=ver_id,
            request_id=req_id,
            tender_id=tender.id,
            bidder_id=bidder.id,
            bidder_name=bidder.company_name,
            status=VerificationStatusEnum.COMPLETED,
            decision=VerificationDecisionEnum.MANUAL_REVIEW,
            overall_compliance=OverallComplianceEnum.PARTIALLY_COMPLIANT,
            risk_score=20.0,
            risk_level=RiskLevelEnum.LOW,
            overall_confidence=0.95,
            result_hash=res_hash,
            reasons=["3 requirements passed; 1 subjective clause pending manual review"],
            failed_requirements=[],
            warnings=[],
            inconclusive_checks=["cloud_systems_experience_verified"],
            missing_documents=[],
            agent_results=[],
            requirements=[
                RequirementEvaluation(
                    requirement_id="RULE-GST",
                    rule="GST_REGISTRATION",
                    mandatory=True,
                    decision=RequirementComplianceEnum.COMPLIANT,
                    confidence=1.0,
                    reason="Valid GSTIN provided",
                ),
            ],
            evidence_snapshot=[{"field": "gst_registered", "value": True}],
            document_hashes={"tender_pdf": tender_sha256},
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        completed_exec = crud_verification.update_execution_completed(
            db=db,
            execution=exec_record,
            resp=dummy_resp,
            result_hash=res_hash,
            evidence_snapshot=dummy_resp.evidence_snapshot,
            document_hashes=dummy_resp.document_hashes,
        )
        assert completed_exec.status == "COMPLETED"
        assert completed_exec.decision == "MANUAL_REVIEW"

        crud_verification.record_audit_event(
            db=db,
            verification_id=ver_id,
            tender_id=tender.id,
            bidder_id=bidder.id,
            event_type="VERIFICATION_COMPLETED",
            result_hash=res_hash,
            details={"decision": completed_exec.decision},
        )

        audit_history = crud_verification.get_audit_events_for_verification(db, verification_id=ver_id)
        assert len(audit_history) == 2

    finally:
        # Step 9: Cleanup
        for p in created_doc_paths:
            try:
                storage_service.delete(p)
            except Exception:
                pass

        db.close()

        # Execute cleanup via raw engine connection to avoid open session transaction state
        from app.db.session import engine
        with engine.begin() as conn:
            for vid in created_verification_ids:
                conn.execute(text("DELETE FROM verification_audit_events WHERE verification_id IN (SELECT verification_id FROM verification_executions WHERE id = :id)"), {"id": vid})
                conn.execute(text("DELETE FROM verification_executions WHERE id = :id"), {"id": vid})
            for tid in created_tender_ids:
                conn.execute(text("DELETE FROM compliance_results WHERE requirement_id IN (SELECT id FROM requirements WHERE tender_id = :id)"), {"id": tid})
                conn.execute(text("DELETE FROM requirements WHERE tender_id = :id"), {"id": tid})
                conn.execute(text("DELETE FROM tender_requirements WHERE tender_id = :id"), {"id": tid})
                conn.execute(text("DELETE FROM documents WHERE tender_id = :id"), {"id": tid})
                conn.execute(text("DELETE FROM tender_bidders WHERE tender_id = :id"), {"id": tid})
                conn.execute(text("DELETE FROM tenders WHERE id = :id"), {"id": tid})
            for bid in created_bidder_ids:
                conn.execute(text("DELETE FROM bidder_evidence WHERE bidder_id = :id"), {"id": bid})
                conn.execute(text("DELETE FROM compliance_results WHERE bidder_id = :id"), {"id": bid})
                conn.execute(text("DELETE FROM documents WHERE bidder_id = :id"), {"id": bid})
                conn.execute(text("DELETE FROM tender_bidders WHERE bidder_id = :id"), {"id": bid})
                conn.execute(text("DELETE FROM bidders WHERE id = :id"), {"id": bid})

        # Verify zero rows remaining in all tables (allowing active procurement officer user)
        with engine.connect() as conn:
            for t in all_tables:
                cnt = conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                if t == "users":
                    assert cnt <= 1, f"Table {t} has unexpected excess rows ({cnt}) after cleanup!"
                else:
                    assert cnt == 0, f"Table {t} has {cnt} rows remaining after cleanup!"
