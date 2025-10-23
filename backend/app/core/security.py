"""
Security utilities for authentication and authorization.

This module provides JWT token handling, password hashing, and other security utilities.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

import bcrypt
import jwt
from app.core.config import get_settings
from fastapi import HTTPException, status
from passlib.context import CryptContext
from structlog import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Password hashing context with bcrypt configuration
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass


class TokenError(SecurityError):
    """Exception raised for token-related errors."""
    pass


class PasswordError(SecurityError):
    """Exception raised for password-related errors."""
    pass


def generate_password_hash(password: str) -> str:
    """
    Generate a secure hash for the given password.

    Args:
        password: The plain text password to hash

    Returns:
        The hashed password

    Raises:
        PasswordError: If password hashing fails
    """
    try:
        # Truncate password to 72 bytes for bcrypt compatibility
        if len(password.encode('utf-8')) > 72:
            password = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')

        return pwd_context.hash(password)
    except Exception as e:
        logger.error("Password hashing failed", error=str(e))
        raise PasswordError("Failed to hash password") from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against its hash.

    Args:
        plain_password: The plain text password
        hashed_password: The hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error("Password verification failed", error=str(e))
        return False


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Length of the token in bytes

    Returns:
        A secure random token as hex string
    """
    return secrets.token_hex(length)


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: The data to encode in the token
        expires_delta: Token expiration time delta

    Returns:
        The encoded JWT token

    Raises:
        TokenError: If token creation fails
    """
    try:
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.access_token_expire_minutes
            )

        to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})

        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )

        logger.debug("Access token created", expires_at=expire.isoformat())
        return encoded_jwt

    except Exception as e:
        logger.error("Token creation failed", error=str(e))
        raise TokenError("Failed to create access token") from e


def create_refresh_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token with longer expiration.

    Args:
        data: The data to encode in the token
        expires_delta: Token expiration time delta (defaults to 7 days)

    Returns:
        The encoded JWT refresh token

    Raises:
        TokenError: If token creation fails
    """
    try:
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            # Default refresh token expires in 7 days
            expire = datetime.now(timezone.utc) + timedelta(days=7)

        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.secret_key,
            algorithm=settings.algorithm
        )

        logger.debug("Refresh token created", expires_at=expire.isoformat())
        return encoded_jwt

    except Exception as e:
        logger.error("Refresh token creation failed", error=str(e))
        raise TokenError("Failed to create refresh token") from e


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        The decoded token payload

    Raises:
        TokenError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )

        # Check if token has expired
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
            raise TokenError("Token has expired")

        logger.debug("Token decoded successfully", user_id=payload.get("sub"))
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        raise TokenError("Token has expired")
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token", error=str(e))
        raise TokenError("Invalid token")
    except Exception as e:
        logger.error("Token decoding failed", error=str(e))
        raise TokenError("Failed to decode token") from e


def verify_token_type(payload: Dict[str, Any], expected_type: str = "access") -> bool:
    """
    Verify that a token payload has the expected type.

    Args:
        payload: The decoded token payload
        expected_type: The expected token type ("access" or "refresh")

    Returns:
        True if token type matches, False otherwise
    """
    token_type = payload.get("type", "access")  # Default to access if not specified
    return token_type == expected_type


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from a JWT token.

    Args:
        token: The JWT token

    Returns:
        The user ID if found, None otherwise
    """
    try:
        payload = decode_token(token)
        return payload.get("sub")
    except TokenError:
        return None


def create_password_reset_token(user_id: str) -> str:
    """
    Create a password reset token.

    Args:
        user_id: The user ID for whom to create the reset token

    Returns:
        The password reset token
    """
    data = {
        "sub": user_id,
        "type": "password_reset"
    }
    # Password reset tokens expire in 1 hour
    expires_delta = timedelta(hours=1)
    return create_access_token(data, expires_delta)


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token and return the user ID.

    Args:
        token: The password reset token

    Returns:
        The user ID if token is valid, None otherwise
    """
    try:
        payload = decode_token(token)
        if not verify_token_type(payload, "password_reset"):
            return None
        return payload.get("sub")
    except TokenError:
        return None


def create_email_verification_token(user_id: str, email: str) -> str:
    """
    Create an email verification token.

    Args:
        user_id: The user ID
        email: The email address to verify

    Returns:
        The email verification token
    """
    data = {
        "sub": user_id,
        "email": email,
        "type": "email_verification"
    }
    # Email verification tokens expire in 24 hours
    expires_delta = timedelta(hours=24)
    return create_access_token(data, expires_delta)


def verify_email_verification_token(token: str) -> Optional[Dict[str, str]]:
    """
    Verify an email verification token.

    Args:
        token: The email verification token

    Returns:
        Dict with user_id and email if token is valid, None otherwise
    """
    try:
        payload = decode_token(token)
        if not verify_token_type(payload, "email_verification"):
            return None

        user_id = payload.get("sub")
        email = payload.get("email")

        if user_id and email:
            return {"user_id": user_id, "email": email}
        return None

    except TokenError:
        return None


# Authentication exceptions for FastAPI
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

inactive_user_exception = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Inactive user"
)

insufficient_permissions_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Not enough permissions"
)
