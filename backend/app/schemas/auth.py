from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.user import UserResponse


class Token(BaseModel):
    """Schema for JWT authentication access token."""
    access_token: str = Field(..., description="Signed JWT bearer access token")
    token_type: str = Field("bearer", description="Token type header prefix")
    expires_in: int = Field(..., description="Access token expiration window in seconds")


class TokenPayload(BaseModel):
    """Decoded JWT claims representation."""
    sub: str = Field(..., description="User identifier subject")
    role: Optional[str] = Field(None, description="User role at issuance")
    exp: int = Field(..., description="Expiration epoch timestamp")
    iat: int = Field(..., description="Issued-at epoch timestamp")


class AuthResponse(BaseModel):
    """Authentication response payload containing user profile and access token."""
    user: UserResponse = Field(..., description="Authenticated user profile")
    token: Token = Field(..., description="Issued access token")
