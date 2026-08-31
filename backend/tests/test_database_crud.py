import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import User, UserRole


def test_database_connection_and_crud():
    """Verify database connection, SELECT 1, and full CRUD lifecycle."""
    # Ensure tables exist in fallback/test target
    Base.metadata.create_all(bind=engine)

    # 1. Direct connection and SELECT 1
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1")).scalar()
        assert result == 1

    # 2. Session and INSERT
    db: Session = SessionLocal()
    test_id = uuid.uuid4()
    test_email = f"crud_test_{test_id.hex[:8]}@gem.gov.in"

    try:
        user = User(
            id=test_id,
            name="CRUD Test User",
            email=test_email,
            password_hash="hashed_secret_crud",
            role=UserRole.REVIEWER,
            is_active=True,
        )
        db.add(user)
        db.commit()

        # 3. READ
        fetched = db.execute(
            select(User).where(User.id == test_id)
        ).scalar_one_or_none()
        assert fetched is not None
        assert fetched.email == test_email
        assert fetched.role == UserRole.REVIEWER

        # 4. UPDATE
        fetched.name = "CRUD Test User Updated"
        fetched.role = UserRole.BUYER
        db.commit()

        updated = db.execute(
            select(User).where(User.id == test_id)
        ).scalar_one_or_none()
        assert updated is not None
        assert updated.name == "CRUD Test User Updated"
        assert updated.role == UserRole.BUYER

        # 5. CLEANUP (DELETE)
        db.delete(updated)
        db.commit()

        deleted = db.execute(
            select(User).where(User.id == test_id)
        ).scalar_one_or_none()
        assert deleted is None

    finally:
        db.close()
