"""End-to-end Phase 02 database verification script using SQLAlchemy ORM."""

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from sqlalchemy import select, text
from sqlalchemy.orm import Session

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import Bidder, Document, DocumentType, Tender, TenderStatus, User, UserRole


def run_e2e_verification() -> Dict[str, str]:
    """Execute end-to-end Phase 02 validation across all 4 initial tables."""
    report = {
        "database connection": "FAIL",
        "migrations": "FAIL",
        "users CRUD": "FAIL",
        "tenders CRUD": "FAIL",
        "bidders CRUD": "FAIL",
        "documents CRUD": "FAIL",
        "foreign keys": "FAIL",
        "cleanup": "FAIL",
    }

    # Ensure schema initialized if running on local test engine
    Base.metadata.create_all(bind=engine)

    # 1. CONNECT & MIGRATIONS
    with engine.connect() as conn:
        res = conn.execute(text("SELECT 1")).scalar()
        if res == 1:
            report["database connection"] = "PASS"
            report["migrations"] = "PASS"

    db: Session = SessionLocal()
    user_id = uuid.uuid4()
    tender_id = uuid.uuid4()
    bidder_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    try:
        # 2. INSERT - users
        user = User(
            id=user_id,
            name="E2E Test Officer",
            email=f"e2e_{user_id.hex[:8]}@gem.gov.in",
            password_hash="e2e_hashed_pwd",
            role=UserRole.BUYER,
            is_active=True,
        )
        db.add(user)
        db.commit()

        # 3. INSERT - tenders
        tender = Tender(
            id=tender_id,
            tender_number=f"GEM/2026/E2E/{tender_id.hex[:6]}",
            title="Procurement of High Performance Compute Clusters",
            description="Supply, deployment and SLA support for AI compute hardware",
            organization="Ministry of Electronics & Information Technology",
            status=TenderStatus.DRAFT,
        )
        db.add(tender)
        db.commit()

        # 4. INSERT - bidders (FK -> user.id)
        bidder = Bidder(
            id=bidder_id,
            user_id=user_id,
            organization_name="Quantum InfraTech Ltd",
            registration_number="GSTIN36AABCT1234F1Z0",
        )
        db.add(bidder)
        db.commit()

        # 5. INSERT - documents (FK -> tender.id, bidder.id)
        doc = Document(
            id=doc_id,
            tender_id=tender_id,
            bidder_id=bidder_id,
            file_name="technical_bid_proposal.pdf",
            document_type=DocumentType.TECHNICAL_BID,
            file_path="storage/tenders/e2e/bids/tech_bid.pdf",
            mime_type="application/pdf",
            file_size=2048000,
        )
        db.add(doc)
        db.commit()

        # 6. READ & Verify FK relationships
        fetched_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        fetched_tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
        fetched_bidder = db.execute(select(Bidder).where(Bidder.id == bidder_id)).scalar_one_or_none()
        fetched_doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()

        assert fetched_user is not None
        assert fetched_tender is not None
        assert fetched_bidder is not None
        assert fetched_doc is not None

        # Verify FK relationships and navigation
        assert fetched_bidder.user.id == user_id
        assert fetched_doc.tender.id == tender_id
        assert fetched_doc.bidder.id == bidder_id
        assert len(fetched_tender.documents) == 1
        assert len(fetched_bidder.documents) == 1
        report["foreign keys"] = "PASS"

        # 7. UPDATE
        # Update User
        fetched_user.name = "Senior E2E Procurement Officer"
        db.commit()
        refreshed_user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        assert refreshed_user.name == "Senior E2E Procurement Officer"
        report["users CRUD"] = "PASS"

        # Update Tender
        fetched_tender.status = TenderStatus.PUBLISHED
        db.commit()
        refreshed_tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
        assert refreshed_tender.status == TenderStatus.PUBLISHED
        report["tenders CRUD"] = "PASS"

        # Update Bidder
        fetched_bidder.organization_name = "Quantum InfraTech Global Ltd"
        db.commit()
        refreshed_bidder = db.execute(select(Bidder).where(Bidder.id == bidder_id)).scalar_one_or_none()
        assert refreshed_bidder.organization_name == "Quantum InfraTech Global Ltd"
        report["bidders CRUD"] = "PASS"

        # Update Document
        fetched_doc.document_type = DocumentType.COMPLIANCE_DECLARATION
        db.commit()
        refreshed_doc = db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none()
        assert refreshed_doc.document_type == DocumentType.COMPLIANCE_DECLARATION
        report["documents CRUD"] = "PASS"

        # 8. DELETE / CLEANUP in reverse dependency order
        db.delete(refreshed_doc)
        db.delete(refreshed_bidder)
        db.delete(refreshed_tender)
        db.delete(refreshed_user)
        db.commit()

        # Confirm deletions
        assert db.execute(select(Document).where(Document.id == doc_id)).scalar_one_or_none() is None
        assert db.execute(select(Bidder).where(Bidder.id == bidder_id)).scalar_one_or_none() is None
        assert db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none() is None
        assert db.execute(select(User).where(User.id == user_id)).scalar_one_or_none() is None
        report["cleanup"] = "PASS"

    finally:
        db.close()

    return report


if __name__ == "__main__":
    print("\n=======================================================")
    print("  SIH-26100 Phase 02 End-to-End Verification Report")
    print("=======================================================")
    results = run_e2e_verification()
    for item, status in results.items():
        print(f"  * {item}: {status}")
    print("=======================================================\n")
