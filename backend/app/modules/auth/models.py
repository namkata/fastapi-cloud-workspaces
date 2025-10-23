"""
Authentication models.

This module defines the database models for user authentication.
"""
from datetime import datetime
from typing import Optional

from app.core.models import BaseModel
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class User(BaseModel):
    """User model for authentication and user management."""

    __tablename__ = "users"

    # Basic user information
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="User's email address (unique)"
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="User's username (unique)"
    )

    full_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="User's full name"
    )

    # Authentication fields
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Hashed password"
    )

    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether the user account is active"
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the user's email is verified"
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the user has superuser privileges"
    )

    # Profile information
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to user's avatar image"
    )

    bio: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User's biography"
    )

    # Authentication tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last login timestamp"
    )

    failed_login_attempts: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Number of consecutive failed login attempts"
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Account locked until this timestamp"
    )

    # Email verification
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Token for email verification"
    )

    email_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When email was verified"
    )

    # Password reset
    password_reset_token: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Token for password reset"
    )

    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When password reset token expires"
    )

    # Workspace relationships - using string references for lazy loading
    owned_workspaces = relationship("Workspace", back_populates="owner", lazy="select")
    workspace_memberships = relationship("WorkspaceMember", foreign_keys="WorkspaceMember.user_id", back_populates="user", lazy="select")

    def __repr__(self) -> str:
        """String representation of the User model."""
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

    @property
    def is_locked(self) -> bool:
        """Check if the user account is currently locked."""
        if not self.locked_until:
            return False
        return datetime.utcnow() < self.locked_until

    @property
    def display_name(self) -> str:
        """Get the display name for the user."""
        return self.full_name or self.username

    def can_login(self) -> bool:
        """Check if the user can log in."""
        return self.is_active and not self.is_locked

    def reset_failed_attempts(self) -> None:
        """Reset failed login attempts counter."""
        self.failed_login_attempts = 0
        self.locked_until = None

    def increment_failed_attempts(self, max_attempts: int = 5, lockout_minutes: int = 30) -> None:
        """
        Increment failed login attempts and lock account if necessary.

        Args:
            max_attempts: Maximum allowed failed attempts before lockout
            lockout_minutes: Minutes to lock the account
        """
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= max_attempts:
            from datetime import timedelta
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)

    def set_last_login(self) -> None:
        """Update the last login timestamp."""
        self.last_login = datetime.utcnow()

    def verify_email(self) -> None:
        """Mark email as verified."""
        self.is_verified = True
        self.email_verified_at = datetime.utcnow()
        self.email_verification_token = None
