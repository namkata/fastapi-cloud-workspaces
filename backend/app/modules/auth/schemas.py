"""
Authentication schemas.

This module defines Pydantic models for authentication requests and responses.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.core.validators import CommonValidators, PasswordValidators
from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr = Field(..., description="User's email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")
    bio: Optional[str] = Field(None, max_length=1000, description="User biography")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        return CommonValidators.validate_username(v)

    @validator('email')
    def validate_email(cls, v):
        """Validate and normalize email."""
        return CommonValidators.validate_email(v)


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)"
    )
    confirm_password: str = Field(..., description="Password confirmation")

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Validate that passwords match."""
        return PasswordValidators.validate_password_match(v, values)

    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password strength."""
        return CommonValidators.validate_strong_password(v)


class UserLogin(BaseModel):
    """Schema for user login."""

    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")
    remember_me: bool = Field(default=False, description="Remember login")


class UserUpdate(BaseModel):
    """Schema for updating user information."""

    email: Optional[EmailStr] = Field(None, description="New email address")
    username: Optional[str] = Field(None, min_length=3, max_length=50, description="New username")
    full_name: Optional[str] = Field(None, max_length=255, description="New full name")
    bio: Optional[str] = Field(None, max_length=1000, description="New biography")
    avatar_url: Optional[str] = Field(None, description="New avatar URL")

    @validator('username')
    def validate_username(cls, v):
        """Validate username format."""
        if v is not None:
            return CommonValidators.validate_username(v)
        return v

    @validator('email')
    def validate_email(cls, v):
        """Validate and normalize email."""
        if v is not None:
            return CommonValidators.validate_email(v)
        return v


class UserResponse(UserBase):
    """Schema for user response (excludes sensitive data)."""

    id: UUID = Field(..., description="User ID")
    is_active: bool = Field(..., description="Whether user is active")
    is_verified: bool = Field(..., description="Whether email is verified")
    is_superuser: bool = Field(..., description="Whether user is superuser")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class UserProfile(UserResponse):
    """Extended user profile schema."""

    email_verified_at: Optional[datetime] = Field(None, description="Email verification timestamp")


class PasswordChange(BaseModel):
    """Schema for password change."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )
    confirm_password: str = Field(..., description="New password confirmation")

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Validate that passwords match."""
        return PasswordValidators.validate_password_match(v, values, 'new_password')

    @validator('new_password')
    def validate_password_strength(cls, v):
        """Validate password strength."""
        return CommonValidators.validate_strong_password(v)


class PasswordReset(BaseModel):
    """Schema for password reset request."""

    email: EmailStr = Field(..., description="Email address for password reset")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="New password"
    )
    confirm_password: str = Field(..., description="New password confirmation")

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Validate that passwords match."""
        return PasswordValidators.validate_password_match(v, values, 'new_password')


class EmailVerification(BaseModel):
    """Schema for email verification."""

    token: str = Field(..., description="Email verification token")


class Token(BaseModel):
    """Schema for authentication tokens."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")


class TokenData(BaseModel):
    """Schema for token data."""

    user_id: Optional[str] = Field(None, description="User ID from token")
    username: Optional[str] = Field(None, description="Username from token")
    scopes: list[str] = Field(default_factory=list, description="Token scopes")


class RefreshToken(BaseModel):
    """Schema for token refresh."""

    refresh_token: str = Field(..., description="Refresh token")


class LoginResponse(BaseModel):
    """Schema for login response."""

    user: UserResponse = Field(..., description="User information")
    token: Token = Field(..., description="Authentication tokens")
    message: str = Field(default="Login successful", description="Success message")


class RegisterResponse(BaseModel):
    """Schema for registration response."""

    user: UserResponse = Field(..., description="Created user information")
    message: str = Field(default="Registration successful", description="Success message")


class MessageResponse(BaseModel):
    """Schema for simple message responses."""

    message: str = Field(..., description="Response message")
    success: bool = Field(default=True, description="Whether operation was successful")


class UserListResponse(BaseModel):
    """Schema for user list response."""

    users: List[UserResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of users per page")
    pages: int = Field(..., description="Total number of pages")
