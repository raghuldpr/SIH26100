import logging
from typing import Optional
from uuid import UUID
from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import AppException
from app.core.security import decode_access_token
from app.crud.crud_user import crud_user
from app.dependencies.database import get_db
from app.models.enums import UserRole
from app.models.user import User

logger = logging.getLogger("app.dependencies.auth")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency that extracts, verifies, and decodes the Bearer JWT token,
    and returns the authenticated active User instance.
    """
    if not token:
        raise AppException(
            message="Missing authentication token. Please provide 'Authorization: Bearer <token>'",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
        )

    try:
        payload = decode_access_token(token)
        user_id_str: Optional[str] = payload.get("sub")
        if not user_id_str:
            raise AppException(
                message="Invalid token payload: missing subject identifier.",
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_TOKEN",
            )
        user_id = UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        raise AppException(
            message="Authentication token has expired. Please log in again.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_EXPIRED",
        )
    except (jwt.PyJWTError, ValueError) as exc:
        logger.info(f"JWT validation failure: {type(exc).__name__}")
        raise AppException(
            message="Invalid or malformed authentication token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_TOKEN",
        )

    user = crud_user.get_by_id(db, user_id=user_id)
    if not user:
        raise AppException(
            message="User associated with token not found.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_NOT_FOUND",
        )

    if not user.is_active:
        raise AppException(
            message="User account is deactivated.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="ACCOUNT_INACTIVE",
        )

    return user


def require_role(*allowed_roles: UserRole):
    """
    Dependency factory to enforce role-based access control.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise AppException(
                message=f"Access forbidden: User role '{current_user.role}' is not authorized.",
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN",
            )
        return current_user

    return role_checker


def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional authentication dependency.
    Returns User if valid Bearer token is provided, None if no token provided,
    or raises 401 if an invalid/expired token was provided.
    """
    if not token:
        return None
    return get_current_user(token=token, db=db)

