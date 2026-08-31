import logging
from typing import List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.core.security import hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate

logger = logging.getLogger("app.crud.user")


class CRUDUser:
    """Encapsulates data layer operations for User entities."""

    def get_by_id(self, db: Session, user_id: UUID) -> Optional[User]:
        """Fetch a user by primary key UUID."""
        stmt = select(User).where(User.id == user_id)
        return db.scalars(stmt).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Fetch a user by exact lowercase email match."""
        normalized_email = email.strip().lower()
        stmt = select(User).where(User.email == normalized_email)
        return db.scalars(stmt).first()

    def get_multi(
        self, db: Session, skip: int = 0, limit: int = 100, role: Optional[UserRole] = None
    ) -> List[User]:
        """Retrieve a list of users with optional role filtering."""
        stmt = select(User)
        if role is not None:
            stmt = stmt.where(User.role == role)
        stmt = stmt.offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    def create(self, db: Session, user_in: UserCreate) -> User:
        """
        Creates a new user record.
        Validates duplicate email and secures password using bcrypt hashing.
        """
        normalized_email = user_in.email.strip().lower()
        existing_user = self.get_by_email(db, email=normalized_email)
        if existing_user:
            raise BadRequestException(
                message=f"A user with email '{normalized_email}' is already registered."
            )

        hashed_pw = hash_password(user_in.password)
        db_user = User(
            name=user_in.name.strip(),
            email=normalized_email,
            password_hash=hashed_pw,
            role=user_in.role,
            is_active=user_in.is_active,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        logger.info(f"User registered successfully [id={db_user.id}, role={db_user.role}]")
        return db_user

    def authenticate(
        self, db: Session, email: str, password: str
    ) -> Optional[User]:
        """
        Validates user credentials against password hash.
        Returns the User instance if valid and active, else None.
        """
        user = self.get_by_email(db, email=email)
        if not user:
            logger.info(f"Authentication failed: email not found [{email}]")
            return None
        if not user.is_active:
            logger.warning(f"Authentication rejected: inactive account [{email}]")
            return None
        if not verify_password(password, user.password_hash):
            logger.info(f"Authentication failed: invalid password [{email}]")
            return None

        logger.info(f"User authenticated successfully [{email}]")
        return user

    def update(
        self, db: Session, db_user: User, user_update: UserUpdate
    ) -> User:
        """Updates user account details."""
        update_data = user_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(db_user, field) and value is not None:
                setattr(db_user, field, value)

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user


crud_user = CRUDUser()
