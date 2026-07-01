"""api/schemas/auth.py - Authentication Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """POST /auth/register - Create new business account."""
    model_config = ConfigDict(frozen=True)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    business_name: str = Field(..., min_length=1, max_length=200)
    phone_number: str = Field(..., min_length=10, max_length=15)
    timezone: str = Field(default="America/New_York")
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    plan: Optional[str] = Field(None, description="basic | pro | pro_plus | free")

    @field_validator("phone_number")
    @classmethod
    def validate_e164(cls, v: str) -> str:
        cleaned = v.replace("+", "").replace(" ", "").replace("-", "")
        if not cleaned.isdigit() or len(cleaned) < 10:
            raise ValueError("Phone number must be valid E.164 format")
        return f"+{cleaned}"


class RegisterResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    user_id: UUID
    tenant_id: UUID
    email: EmailStr
    business_name: str
    message: str = (
        "Registration successful. Please check your email to verify."
    )


class TokenPair(BaseModel):
    model_config = ConfigDict(frozen=True)
    access_token: str = Field(..., description="JWT access token (15 min TTL)")
    refresh_token: str = Field(..., description="JWT refresh token (7 day TTL)")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(default=900, description="Access token TTL in seconds")


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    role: str
    is_active: bool
    email_verified: bool
    last_login_at: Optional[datetime] = Field(default=None)
    created_at: datetime


class TenantSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID
    name: str
    slug: str
    timezone: str
    plan: str = Field(default="free")


class SignupResponse(BaseModel):
    """Response returned by /auth/signup with auto-login tokens."""
    model_config = ConfigDict(frozen=True)
    user: UserProfile
    tokens: TokenPair
    tenant: TenantSummary


class LoginRequest(BaseModel):
    """POST /auth/login - Authenticate and receive tokens."""
    model_config = ConfigDict(frozen=True)
    email: EmailStr
    password: str
    device_id: Optional[str] = Field(default=None)


class LoginResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    user: UserProfile
    tokens: TokenPair
    tenant: TenantSummary


class RefreshRequest(BaseModel):
    """POST /auth/refresh - Obtain new access token."""
    model_config = ConfigDict(frozen=True)
    refresh_token: str


class RefreshResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer")
    expires_in: int = Field(default=900)


class LogoutRequest(BaseModel):
    """POST /auth/logout - Revoke tokens."""
    model_config = ConfigDict(frozen=True)
    refresh_token: Optional[str] = Field(default=None)
    all_devices: bool = Field(default=False)


class PasswordResetRequest(BaseModel):
    """POST /auth/password-reset - Request password reset email."""
    model_config = ConfigDict(frozen=True)
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """POST /auth/password-reset/confirm - Set new password."""
    model_config = ConfigDict(frozen=True)
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    """POST /auth/password - Change password (authenticated)."""
    model_config = ConfigDict(frozen=True)
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    """POST /auth/verify-email - Verify email address."""
    model_config = ConfigDict(frozen=True)
    token: str


class MagicLinkRequest(BaseModel):
    """POST /auth/magic-link - Request magic link login."""
    model_config = ConfigDict(frozen=True)
    email: EmailStr
    redirect_url: Optional[str] = Field(default=None)


class MagicLinkResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    message: str = "Magic link sent to your email if the account exists."


# -- API Key Management ---------------------------------------------------

class APIKeyCreateRequest(BaseModel):
    """POST /auth/api-keys - Create API key for integrations."""
    model_config = ConfigDict(frozen=True)
    name: str = Field(..., min_length=1, max_length=100)
    scopes: list[str] = Field(
        default_factory=lambda: ["read:calls", "read:messages"]
    )
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class APIKeyCreatedResponse(BaseModel):
    """Response after API key creation (key shown once)."""
    model_config = ConfigDict(frozen=True)
    id: UUID
    name: str
    key: str = Field(..., description="The API key (shown ONLY at creation)")
    scopes: list[str]
    expires_at: Optional[datetime]
    created_at: datetime


class APIKeyResponse(BaseModel):
    """API key listing (never includes the key itself)."""
    model_config = ConfigDict(frozen=True)
    id: UUID
    name: str
    scopes: list[str]
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
    is_active: bool


# -- Forgot Password (alias for consistency) ------------------------------

class ForgotPasswordRequest(BaseModel):
    """POST /auth/forgot-password - Request password reset."""
    model_config = ConfigDict(frozen=True)
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """POST /auth/reset-password - Reset password with token."""
    model_config = ConfigDict(frozen=True)
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)
