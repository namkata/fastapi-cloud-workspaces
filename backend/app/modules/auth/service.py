"""
Authentication service.

This module provides business logic for user authentication and management.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from app.core.security import (
    TokenError,
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    generate_password_hash,
    verify_email_verification_token,
    verify_password,
    verify_password_reset_token,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import UserCreate, UserUpdate
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

logger = get_logger(__name__)


class AuthService:
    """Service class for authentication operations."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the auth service.

        Args:
            db: Database session
        """
        self.db = db

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User if found, None otherwise
        """
        try:
            uuid_id = UUID(user_id)
            result = await self.db.execute(
                select(User).where(User.id == uuid_id)
            )
            return result.scalar_one_or_none()
        except (ValueError, Exception) as e:
            logger.warning("Failed to get user by ID", user_id=user_id, error=str(e))
            return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email.

        Args:
            email: User email

        Returns:
            User if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """
        Get user by username.

        Args:
            username: Username

        Returns:
            User if found, None otherwise
        """
        result = await self.db.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_user_by_username_or_email(self, identifier: str) -> Optional[User]:
        """
        Get user by username or email.

        Args:
            identifier: Username or email

        Returns:
            User if found, None otherwise
        """
        identifier = identifier.lower()
        result = await self.db.execute(
            select(User).where(
                or_(User.username == identifier, User.email == identifier)
            )
        )
        return result.scalar_one_or_none()

    async def create_user(self, user_data: UserCreate) -> User:
        """
        Create a new user.

        Args:
            user_data: User creation data

        Returns:
            Created user

        Raises:
            ValueError: If user already exists
        """
        # Check if user already exists
        existing_user = await self.get_user_by_email(user_data.email)
        if existing_user:
            raise ValueError("User with this email already exists")

        existing_user = await self.get_user_by_username(user_data.username)
        if existing_user:
            raise ValueError("User with this username already exists")

        # Hash password
        hashed_password = generate_password_hash(user_data.password)

        # Create user
        user = User(
            email=user_data.email.lower(),
            username=user_data.username.lower(),
            full_name=user_data.full_name,
            bio=user_data.bio,
            avatar_url=user_data.avatar_url,
            hashed_password=hashed_password,
            is_active=True,
            is_verified=False,  # Email verification required
            is_superuser=False,
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("User created", user_id=str(user.id), email=user.email)
        return user

    async def authenticate_user(self, identifier: str, password: str) -> Optional[User]:
        """
        Authenticate user with username/email and password.

        Args:
            identifier: Username or email
            password: Plain text password

        Returns:
            User if authentication successful, None otherwise
        """
        user = await self.get_user_by_username_or_email(identifier)

        if not user:
            logger.warning("Authentication failed: user not found", identifier=identifier)
            return None

        if not user.can_login():
            logger.warning("Authentication failed: user cannot login", user_id=str(user.id))
            return None

        if not verify_password(password, user.hashed_password):
            # Increment failed attempts
            user.increment_failed_attempts()
            await self.db.commit()

            logger.warning(
                "Authentication failed: invalid password",
                user_id=str(user.id),
                failed_attempts=user.failed_login_attempts
            )
            return None

        # Reset failed attempts and update last login
        user.reset_failed_attempts()
        user.set_last_login()
        await self.db.commit()

        logger.info("User authenticated successfully", user_id=str(user.id))
        return user

    async def update_user(self, user: User, user_data: UserUpdate) -> User:
        """
        Update user information.

        Args:
            user: User to update
            user_data: Update data

        Returns:
            Updated user

        Raises:
            ValueError: If email/username already exists
        """
        # Check for email conflicts
        if user_data.email and user_data.email != user.email:
            existing_user = await self.get_user_by_email(user_data.email)
            if existing_user and existing_user.id != user.id:
                raise ValueError("User with this email already exists")
            user.email = user_data.email.lower()
            user.is_verified = False  # Re-verify email

        # Check for username conflicts
        if user_data.username and user_data.username != user.username:
            existing_user = await self.get_user_by_username(user_data.username)
            if existing_user and existing_user.id != user.id:
                raise ValueError("User with this username already exists")
            user.username = user_data.username.lower()

        # Update other fields
        if user_data.full_name is not None:
            user.full_name = user_data.full_name

        if user_data.bio is not None:
            user.bio = user_data.bio

        if user_data.avatar_url is not None:
            user.avatar_url = user_data.avatar_url

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("User updated", user_id=str(user.id))
        return user

    async def change_password(self, user: User, current_password: str, new_password: str) -> bool:
        """
        Change user password.

        Args:
            user: User to update
            current_password: Current password
            new_password: New password

        Returns:
            True if password changed successfully, False otherwise
        """
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            logger.warning("Password change failed: invalid current password", user_id=str(user.id))
            return False

        # Hash new password
        user.hashed_password = generate_password_hash(new_password)
        await self.db.commit()

        logger.info("Password changed successfully", user_id=str(user.id))
        return True

    async def create_tokens(self, user: User, remember_me: bool = False) -> dict:
        """
        Create access and refresh tokens for user.

        Args:
            user: User to create tokens for
            remember_me: Whether to create long-lived tokens

        Returns:
            Dictionary with access_token, refresh_token, and expires_in
        """
        # Token data
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "scopes": self._get_user_scopes(user)
        }

        # Create tokens
        access_token_expires = timedelta(minutes=30)  # 30 minutes
        if remember_me:
            access_token_expires = timedelta(hours=24)  # 24 hours for remember me

        access_token = create_access_token(token_data, access_token_expires)
        refresh_token = create_refresh_token(token_data)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(access_token_expires.total_seconds())
        }

    def _get_user_scopes(self, user: User) -> list[str]:
        """
        Get scopes for user based on their permissions.

        Args:
            user: User to get scopes for

        Returns:
            List of scopes
        """
        scopes = ["read"]

        if user.is_active:
            scopes.append("write")

        if user.is_superuser:
            scopes.append("admin")

        return scopes

    async def initiate_password_reset(self, email: str) -> Optional[str]:
        """
        Initiate password reset process.

        Args:
            email: User email

        Returns:
            Password reset token if user exists, None otherwise
        """
        user = await self.get_user_by_email(email)
        if not user:
            # Don't reveal if email exists
            logger.warning("Password reset requested for non-existent email", email=email)
            return None

        # Create reset token
        reset_token = create_password_reset_token(str(user.id))

        # Store token and expiration
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)

        await self.db.commit()

        logger.info("Password reset initiated", user_id=str(user.id))
        return reset_token

    async def reset_password(self, token: str, new_password: str) -> bool:
        """
        Reset password using reset token.

        Args:
            token: Password reset token
            new_password: New password

        Returns:
            True if password reset successful, False otherwise
        """
        user_id = verify_password_reset_token(token)
        if not user_id:
            logger.warning("Invalid password reset token")
            return False

        user = await self.get_user_by_id(user_id)
        if not user:
            logger.warning("User not found for password reset", user_id=user_id)
            return False

        # Check if token matches and hasn't expired
        if (user.password_reset_token != token or
            not user.password_reset_expires or
            user.password_reset_expires < datetime.utcnow()):
            logger.warning("Password reset token expired or invalid", user_id=str(user.id))
            return False

        # Reset password
        user.hashed_password = generate_password_hash(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        user.reset_failed_attempts()  # Reset any lockouts

        await self.db.commit()

        logger.info("Password reset successful", user_id=str(user.id))
        return True

    async def initiate_email_verification(self, user: User) -> str:
        """
        Initiate email verification process.

        Args:
            user: User to verify email for

        Returns:
            Email verification token
        """
        verification_token = create_email_verification_token(str(user.id), user.email)

        user.email_verification_token = verification_token
        await self.db.commit()

        logger.info("Email verification initiated", user_id=str(user.id))
        return verification_token

    async def verify_email(self, token: str) -> bool:
        """
        Verify email using verification token.

        Args:
            token: Email verification token

        Returns:
            True if email verified successfully, False otherwise
        """
        token_data = verify_email_verification_token(token)
        if not token_data:
            logger.warning("Invalid email verification token")
            return False

        user = await self.get_user_by_id(token_data["user_id"])
        if not user:
            logger.warning("User not found for email verification", user_id=token_data["user_id"])
            return False

        # Check if token matches and email matches
        if (user.email_verification_token != token or
            user.email != token_data["email"]):
            logger.warning("Email verification token mismatch", user_id=str(user.id))
            return False

        # Verify email
        user.verify_email()
        await self.db.commit()

        logger.info("Email verified successfully", user_id=str(user.id))
        return True

    async def deactivate_user(self, user: User) -> None:
        """
        Deactivate user account.

        Args:
            user: User to deactivate
        """
        user.is_active = False
        await self.db.commit()

        logger.info("User deactivated", user_id=str(user.id))

    async def activate_user(self, user: User) -> None:
        """
        Activate user account.

        Args:
            user: User to activate
        """
        user.is_active = True
        await self.db.commit()
        await self.db.refresh(user)

        logger.info("User activated", user_id=str(user.id))

    async def get_current_user(self, token: str) -> Optional[User]:
        """
        Get current user from JWT token.

        Args:
            token: JWT access token

        Returns:
            User if token is valid and user exists, None otherwise
        """
        try:
            # Decode the JWT token
            payload = decode_token(token)
            user_id: str = payload.get("sub")

            if user_id is None:
                logger.warning("Token missing user ID")
                return None

            # Get user from database
            user = await self.get_user_by_id(user_id)

            if user is None:
                logger.warning(f"User not found for ID: {user_id}")
                return None

            # Check if user is active
            if not user.is_active:
                logger.warning(f"Inactive user attempted access: {user.email}")
                return None

            return user

        except TokenError as e:
            logger.warning(f"Token error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return None
