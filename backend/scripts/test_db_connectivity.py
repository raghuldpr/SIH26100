"""Database connectivity and CRUD verification script for SIH-26100 backend."""

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
from app.models import Document, DocumentType, Tender, TenderStatus, User, UserRole


def mask_url(url: str) -> str:
    """Mask password in database URL for safe logging."""
    if not url:
        return "<EMPTY>"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.password:
            netloc = f"{parsed.username}:***@{parsed.hostname}:{parsed.port}" if parsed.port else f"{parsed.username}:***@{parsed.hostname}"
            return parsed._replace(netloc=netloc).geturl()
        return url
    except Exception:
        return "postgresql://***"


def run_database_test() -> Dict[str, Any]:
    """Execute end-to-end database connectivity and CRUD verification."""
    results: Dict[str, Any] = {
        "database_target": mask_url(settings.DATABASE_URL),
        "connection_status": "PENDING",
        "select_1_status": "PENDING",
        "insert_status": "PENDING",
        "read_status": "PENDING",
        "update_status": "PENDING",
        "cleanup_status": "PENDING",
        "overall_status": "FAILED",
        "details": {},
    }

    test_user_id = uuid.uuid4()
    test_email = f"test_conn_{test_user_id.hex[:8]}@gem.gov.in"

    try:
        # Step 1: Verify Connection & SELECT 1
        with engine.connect() as conn:
            query_result = conn.execute(text("SELECT 1")).scalar()
            if query_result == 1:
                results["connection_status"] = "SUCCESS"
                results["select_1_status"] = "SUCCESS"
            else:
                results["connection_status"] = "FAILED"
                results["details"]["error"] = f"Unexpected SELECT 1 result: {query_result}"
                return results

        # Ensure schema tables exist if running against local fallback
        Base.metadata.create_all(bind=engine)

        # Step 2: Open Session and perform INSERT
        db: Session = SessionLocal()
        try:
            test_user = User(
                id=test_user_id,
                name="Connectivity Test Admin",
                email=test_email,
                password_hash="test_secret_hash_secure",
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(test_user)
            db.commit()
            results["insert_status"] = "SUCCESS"
            results["details"]["inserted_id"] = str(test_user_id)

            # Step 3: READ inserted record
            fetched_user = db.execute(
                select(User).where(User.email == test_email)
            ).scalar_one_or_none()

            if (
                fetched_user is not None
                and fetched_user.id == test_user_id
                and fetched_user.email == test_email
                and fetched_user.role == UserRole.ADMIN
            ):
                results["read_status"] = "SUCCESS"
            else:
                results["read_status"] = "FAILED"
                results["details"]["error"] = "Failed to fetch inserted user or data mismatch"
                return results

            # Step 4: UPDATE record
            fetched_user.name = "Updated Connectivity Admin"
            fetched_user.role = UserRole.BUYER
            db.commit()

            # Re-read to confirm update
            updated_user = db.execute(
                select(User).where(User.id == test_user_id)
            ).scalar_one_or_none()

            if (
                updated_user is not None
                and updated_user.name == "Updated Connectivity Admin"
                and updated_user.role == UserRole.BUYER
            ):
                results["update_status"] = "SUCCESS"
            else:
                results["update_status"] = "FAILED"
                results["details"]["error"] = "Failed to update user or verification failed"
                return results

            # Step 5: CLEANUP (DELETE)
            db.delete(updated_user)
            db.commit()

            # Confirm deletion
            deleted_check = db.execute(
                select(User).where(User.id == test_user_id)
            ).scalar_one_or_none()

            if deleted_check is None:
                results["cleanup_status"] = "SUCCESS"
            else:
                results["cleanup_status"] = "FAILED"
                results["details"]["error"] = "Record was not removed after deletion"
                return results

            results["overall_status"] = "SUCCESS"

        finally:
            db.close()

    except Exception as e:
        results["overall_status"] = "ERROR"
        results["details"]["exception"] = str(e)

    return results


if __name__ == "__main__":
    print("\n--- Running SIH-26100 Database Connectivity & CRUD Test ---")
    test_results = run_database_test()
    for key, value in test_results.items():
        if key == "details" and value:
            print(f"  details: {value}")
        elif key != "details":
            print(f"  {key}: {value}")
    print("-----------------------------------------------------------\n")

    if test_results["overall_status"] != "SUCCESS":
        sys.exit(1)
