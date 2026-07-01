from datetime import datetime
from typing import Optional

from pydantic import EmailStr, Field

from src.modules.users.enums import UserRole
from src.shared.schemas import CamelModel


class UserBase(CamelModel):
    email: EmailStr = Field(..., description="Login email (unique)")
    full_name: Optional[str] = Field(None, max_length=128, description="Full name")
    role: UserRole = Field(
        default=UserRole.OPERATOR,
        description="Role: administrador, vendedor or operador",
    )
    branch_id: Optional[int] = Field(
        default=None,
        description=(
            "Assigned branch (required for vendedor/operador). The "
            "administrador is global: ignored and left null."
        ),
    )


class UserCreate(UserBase):
    """User creation. The password travels in plain text only here; it's hashed on persist."""

    password: str = Field(..., min_length=8, max_length=128, description="Password")


class UserUpdate(CamelModel):
    """Partial update. Sending ``password`` rehashes it; ``isActive`` deactivates."""

    email: Optional[EmailStr] = Field(None, description="Login email (unique)")
    full_name: Optional[str] = Field(None, max_length=128, description="Full name")
    role: Optional[UserRole] = Field(None, description="User role")
    is_active: Optional[bool] = Field(
        None, description="Active/inactive (logical deactivation)"
    )
    branch_id: Optional[int] = Field(
        None, description="Assigned branch (staff); null/ignored for administrador"
    )
    password: Optional[str] = Field(
        None, min_length=8, max_length=128, description="New password"
    )


class UserResponse(UserBase):
    """Public representation of a user. Never includes the password or its hash."""

    id: int = Field(..., description="User ID")
    is_active: bool = Field(..., description="Active/inactive")
    created_at: datetime = Field(..., description="Creation date")


class ProfileUpdate(CamelModel):
    """Self-service: the user edits their own profile (``fullName`` only)."""

    full_name: Optional[str] = Field(None, max_length=128, description="Full name")


class ChangePasswordRequest(CamelModel):
    """Self-service: own password change after verifying the current one."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="New password"
    )


class LoginRequest(CamelModel):
    email: EmailStr = Field(..., description="Login email")
    password: str = Field(..., description="Password")


class RefreshRequest(CamelModel):
    """Exchanges the refresh token for a new pair on ``/auth/refresh``."""

    refresh_token: str = Field(..., description="Opaque refresh token issued at login")


class TokenResponse(CamelModel):
    """Login/refresh response: token pair + authenticated user data."""

    access_token: str = Field(..., description="Access JWT (short-lived)")
    refresh_token: str = Field(
        ..., description="Opaque refresh token (long, revocable)"
    )
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token validity in seconds")
    user: UserResponse = Field(..., description="Authenticated user")
