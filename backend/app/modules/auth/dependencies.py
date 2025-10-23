"""
Authentication dependencies.

This module provides FastAPI dependencies for authentication and authorization.
"""
from typing import Optional

from app.core.database import db_manager
from app.core.security import TokenError, credentials_exception, decode_token
from app.modules.auth.models import User
from app.modules.auth.schemas import TokenData
from app.modules.auth.service import AuthService
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth/login",
    scopes={
        "read": "Read access to user data",
        "write": "Write access to user data",
        "admin": "Administrative access",
    }
)


async def get_current_user(
    token: str = Depends(oauth2_scheme)
) -> User:
    """
    Get the current authenticated user from JWT token.

    Args:
        token: JWT access token

    Returns:
        The authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    try:
        # Decode the JWT token
        payload = decode_token(token)
        user_id: str = payload.get("sub")

        if user_id is None:
            raise credentials_exception

        # Create token data
        token_data = TokenData(user_id=user_id)

    except TokenError as e:
        logger.error(f"Token error: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise credentials_exception

    # Get user from database using a proper session context
    async with db_manager.session_factory() as db:
        try:
            auth_service = AuthService(db)
            user = await auth_service.get_user_by_id(token_data.user_id)

            if user is None:
                logger.warning(f"User not found for ID: {token_data.user_id}")
                raise credentials_exception

            # Check if user is active
            if not user.is_active:
                logger.warning(f"Inactive user attempted access: {user.email}")
                raise credentials_exception

            # Ensure user object is properly loaded
            await db.refresh(user)

            return user

        except Exception as e:
            logger.error(f"Database error in get_current_user: {str(e)}")
            raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get the current active user.

    Args:
        current_user: The current authenticated user

    Returns:
        The active user

    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get the current verified user.

    Args:
        current_user: The current active user

    Returns:
        The verified user

    Raises:
        HTTPException: If user email is not verified
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email not verified"
        )

    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get the current superuser.

    Args:
        current_user: The current active user

    Returns:
        The superuser

    Raises:
        HTTPException: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    return current_user


async def get_optional_current_user(
    token: Optional[str] = Depends(oauth2_scheme)
) -> Optional[User]:
    """
    Get the current user if authenticated, otherwise return None.

    This dependency is useful for endpoints that work for both
    authenticated and anonymous users.

    Args:
        token: Optional JWT access token
        db: Database session

    Returns:
        The authenticated user or None
    """
    if not token:
        return None

    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


class RequireScopes:
    """
    Dependency class to require specific scopes.

    Usage:
        @app.get("/admin", dependencies=[Depends(RequireScopes(["admin"]))])
        async def admin_endpoint():
            pass
    """

    def __init__(self, required_scopes: list[str]):
        """
        Initialize with required scopes.

        Args:
            required_scopes: List of required scopes
        """
        self.required_scopes = required_scopes

    async def __call__(
        self,
        token: str = Depends(oauth2_scheme),
        current_user: User = Depends(get_current_active_user)
    ) -> User:
        """
        Check if user has required scopes.

        Args:
            token: JWT access token
            current_user: Current authenticated user

        Returns:
            The authenticated user

        Raises:
            HTTPException: If user doesn't have required scopes
        """
        try:
            payload = decode_token(token)
            token_scopes = payload.get("scopes", [])

            # Check if user has all required scopes
            for scope in self.required_scopes:
                if scope not in token_scopes:
                    # Special case: superusers have all scopes
                    if not current_user.is_superuser:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Not enough permissions. Required scope: {scope}"
                        )

            return current_user

        except TokenError:
            raise credentials_exception


def require_admin():
    """Convenience function to require admin scope."""
    return RequireScopes(["admin"])


def require_write():
    """Convenience function to require write scope."""
    return RequireScopes(["write"])


async def validate_refresh_token(
    token: str
) -> User:
    """
    Validate a refresh token and return the associated user.

    Args:
        token: JWT refresh token
        db: Database session

    Returns:
        The user associated with the token

    Raises:
        HTTPException: If token is invalid
    """
    try:
        payload = decode_token(token)

        # Check if it's a refresh token
        token_type = payload.get("type", "access")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )

        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception

        # Get user from database
        auth_service = AuthService(db)
        user = await auth_service.get_user_by_id(user_id)

        if user is None or not user.is_active:
            raise credentials_exception

        return user

    except TokenError:
        raise credentials_exception
