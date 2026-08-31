from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AppException
from app.core.security import create_access_token
from app.crud.crud_user import crud_user
from app.dependencies.auth import get_current_user
from app.dependencies.database import get_db
from app.models.user import User
from app.schemas.auth import AuthResponse, Token
from app.schemas.user import UserCreate, UserLogin, UserResponse

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Procurement Officer Account",
    description="Registers a new platform user with initial PROCUREMENT_OFFICER role.",
)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Creates a new user record and returns the safe user profile."""
    user = crud_user.create(db, user_in=user_in)
    return UserResponse.model_validate(user)


@auth_router.post(
    "/login",
    response_model=AuthResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login & Access Token Generation",
    description="Authenticates credentials and issues a signed JWT access token.",
)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db),
) -> AuthResponse:
    """Authenticates email/password credentials and returns an access token."""
    user = crud_user.authenticate(
        db, email=login_data.email, password=login_data.password
    )
    if not user:
        raise AppException(
            message="Invalid email or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
        )

    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    access_token = create_access_token(
        subject=str(user.id),
        claims={"role": user.role.value, "email": user.email},
    )

    return AuthResponse(
        user=UserResponse.model_validate(user),
        token=Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in_seconds,
        ),
    )


@auth_router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Authenticated User Profile",
    description="Returns the profile of the authenticated user identified by the Bearer JWT token.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Returns safe user profile for the active session."""
    return UserResponse.model_validate(current_user)
