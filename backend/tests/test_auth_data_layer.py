import uuid
import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.core.security import hash_password, verify_password
from app.crud.crud_user import crud_user
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, UserUpdate


@pytest.fixture
def db_session():
    """Yield a database session and clean up created test records."""
    db = SessionLocal()
    created_user_ids = []
    yield db, created_user_ids
    for uid in created_user_ids:
        try:
            user = db.get(User, uid)
            if user:
                db.delete(user)
                db.commit()
        except Exception:
            db.rollback()
    db.close()


def test_password_hashing_and_verification():
    """Verify bcrypt password hashing and verification behavior."""
    raw_password = "SecureProcurementPassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(raw_password, "") is False


def test_user_creation_procurement_officer(db_session):
    """Verify user registration with initial role PROCUREMENT_OFFICER."""
    db, created_ids = db_session
    email = f"officer_{uuid.uuid4().hex[:8]}@gem.gov.in"
    raw_pw = "OfficerSecurePassword2026!"

    user_in = UserCreate(
        name="Procurement Officer Sharma",
        email=email,
        password=raw_pw,
        role=UserRole.PROCUREMENT_OFFICER,
    )

    db_user = crud_user.create(db, user_in=user_in)
    created_ids.append(db_user.id)

    assert db_user.id is not None
    assert db_user.name == "Procurement Officer Sharma"
    assert db_user.email == email.lower()
    assert db_user.role == UserRole.PROCUREMENT_OFFICER
    assert db_user.is_active is True
    assert db_user.password_hash != raw_pw
    assert verify_password(raw_pw, db_user.password_hash) is True


def test_prevent_duplicate_user_registration(db_session):
    """Verify duplicate email registration is rejected with BadRequestException."""
    db, created_ids = db_session
    email = f"duplicate_{uuid.uuid4().hex[:8]}@gem.gov.in"
    user_in = UserCreate(
        name="Officer One",
        email=email,
        password="Password12345!",
        role=UserRole.PROCUREMENT_OFFICER,
    )

    db_user = crud_user.create(db, user_in=user_in)
    created_ids.append(db_user.id)

    # Attempt to register with the same email
    duplicate_in = UserCreate(
        name="Officer Two",
        email=email.upper(),  # Test case-insensitivity
        password="AnotherPassword123!",
        role=UserRole.PROCUREMENT_OFFICER,
    )

    with pytest.raises(BadRequestException, match="already registered"):
        crud_user.create(db, user_in=duplicate_in)


def test_user_authentication_lifecycle(db_session):
    """Verify user authentication logic for valid, invalid, and inactive accounts."""
    db, created_ids = db_session
    email = f"auth_test_{uuid.uuid4().hex[:8]}@gem.gov.in"
    password = "CorrectPassword123!"

    user_in = UserCreate(
        name="Authentication Test User",
        email=email,
        password=password,
        role=UserRole.PROCUREMENT_OFFICER,
    )
    user = crud_user.create(db, user_in=user_in)
    created_ids.append(user.id)

    # 1. Successful authentication
    auth_success = crud_user.authenticate(db, email=email, password=password)
    assert auth_success is not None
    assert auth_success.id == user.id

    # 2. Authentication with wrong password
    auth_wrong_pw = crud_user.authenticate(db, email=email, password="WrongPassword!")
    assert auth_wrong_pw is None

    # 3. Authentication with non-existent email
    auth_non_existent = crud_user.authenticate(
        db, email="nonexistent@gem.gov.in", password=password
    )
    assert auth_non_existent is None

    # 4. Authentication with deactivated account
    crud_user.update(db, db_user=user, user_update=UserUpdate(is_active=False))
    auth_deactivated = crud_user.authenticate(db, email=email, password=password)
    assert auth_deactivated is None


def test_user_response_schema_never_exposes_password():
    """Verify UserResponse schema does not contain password or password_hash fields."""
    assert "password" not in UserResponse.model_fields
    assert "password_hash" not in UserResponse.model_fields

    fake_id = uuid.uuid4()
    user_model = User(
        id=fake_id,
        name="Officer Name",
        email="officer@gem.gov.in",
        password_hash="$2b$12$SomeHashedSecretValue",
        role=UserRole.PROCUREMENT_OFFICER,
        is_active=True,
    )

    response_dto = UserResponse.model_validate(user_model)
    dumped = response_dto.model_dump()

    assert "password_hash" not in dumped
    assert "password" not in dumped
    assert dumped["id"] == fake_id
    assert dumped["role"] == UserRole.PROCUREMENT_OFFICER


def test_user_create_pydantic_validation():
    """Verify Pydantic validates email format and password minimum length."""
    # Invalid email format
    with pytest.raises(ValidationError):
        UserCreate(
            name="Valid Name",
            email="not-an-email",
            password="ValidPassword123!",
        )

    # Short password (< 8 chars)
    with pytest.raises(ValidationError):
        UserCreate(
            name="Valid Name",
            email="valid@gem.gov.in",
            password="short",
        )


def test_role_support_architecture():
    """Verify PROCUREMENT_OFFICER as initial role and future roles in enum."""
    assert UserRole.PROCUREMENT_OFFICER == "PROCUREMENT_OFFICER"
    assert UserRole.ADMIN == "ADMIN"
    assert UserRole.REVIEWER == "REVIEWER"
    assert UserRole.BUYER == "BUYER"
    assert UserRole.BIDDER == "BIDDER"
