from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


class UserBase(BaseModel):
    """Base user properties shared across request schemas."""
    email: EmailStr = Field(..., description="Official user email address")
    name: str = Field(..., min_length=2, max_length=255, description="Full name of user")
    role: UserRole = Field(
        default=UserRole.PROCUREMENT_OFFICER,
        description="Assigned role for authorization access control",
    )
    is_active: bool = Field(default=True, description="Account active status")


class UserCreate(UserBase):
    """Schema for registering a new user account."""
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Account password (minimum 8 characters)",
    )


class UserLogin(BaseModel):
    """Schema for user credentials authentication request."""
    email: EmailStr = Field(..., description="Registered account email")
    password: str = Field(..., min_length=1, description="Account plaintext password")


class UserUpdate(BaseModel):
    """Schema for updating user account attributes."""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None


class UserResponse(BaseModel):
    """
    Public user profile response schema.
    Guarantees password_hash and sensitive credentials are never serialized or returned.
    """
    id: UUID = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="Registered account email")
    name: str = Field(..., description="Full name of user")
    role: UserRole = Field(..., description="User access control role")
    is_active: bool = Field(..., description="Account active status")
    created_at: Optional[datetime] = Field(None, description="Account creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last profile update timestamp")

    model_config = ConfigDict(from_attributes=True)

