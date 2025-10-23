"""
Authentication middleware for JWT token validation.

This middleware provides automatic JWT token validation for protected routes
and adds user context to the request state.
"""
import logging
from typing import Optional

from app.core.database import get_db_session
from app.core.security import TokenError, decode_token
from app.modules.auth.models import User
from app.modules.auth.service import AuthService
from fastapi import HTTPException, Request, Response, status
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware that validates JWT tokens and adds user context.

    This middleware:
    1. Extracts JWT tokens from Authorization headers
    2. Validates tokens and retrieves user information
    3. Adds user context to request state
    4. Handles authentication errors gracefully
    """

    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        """
        Initialize the authentication middleware.

        Args:
            app: FastAPI application instance
            exclude_paths: List of paths to exclude from authentication
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/auth/verify-email",
        ]

    async def dispatch(self, request: Request, call_next):
        """
        Process the request and validate authentication if required.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response from the next handler
        """
        # Skip authentication for excluded paths
        if self._should_skip_auth(request):
            logger.debug(f"Skipping auth for path: {request.url.path}")
            return await call_next(request)

        logger.debug(f"Processing auth for path: {request.url.path}")

        # Initialize request state
        request.state.user = None
        request.state.token_payload = None

        try:
            # Extract and validate token
            token = self._extract_token(request)
            if token:
                user = await self._validate_token(token, request)
                if user:
                    request.state.user = user
                    request.state.token_payload = decode_token(token)

            # Continue to the next handler
            response = await call_next(request)
            return response

        except HTTPException as e:
            # Return authentication error as JSON
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail}
            )
        except Exception as e:
            logger.error(f"Authentication middleware error: {str(e)}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )

    def _should_skip_auth(self, request: Request) -> bool:
        """
        Check if authentication should be skipped for this request.

        Args:
            request: The incoming request

        Returns:
            True if authentication should be skipped
        """
        path = request.url.path

        # Check exact matches
        if path in self.exclude_paths:
            return True

        # Check path prefixes for static files, docs, etc.
        skip_prefixes = ["/static/", "/assets/", "/favicon.ico"]
        for prefix in skip_prefixes:
            if path.startswith(prefix):
                return True

        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from the Authorization header.

        Args:
            request: The incoming request

        Returns:
            The JWT token if found, None otherwise
        """
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None

        scheme, token = get_authorization_scheme_param(authorization)
        if scheme.lower() != "bearer":
            return None

        return token

    async def _validate_token(self, token: str, request: Request) -> Optional[User]:
        """
        Validate JWT token and retrieve user information.

        Args:
            token: The JWT token to validate
            request: The incoming request (for database access)

        Returns:
            The authenticated user if token is valid, None otherwise

        Raises:
            HTTPException: If token is invalid or user not found
        """
        try:
            # Decode the token
            payload = decode_token(token)
            user_id = payload.get("sub")

            if not user_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user ID"
                )

            # Get database session
            db_gen = get_db_session()
            db: AsyncSession = await anext(db_gen)

            try:
                # Get user from database
                auth_service = AuthService(db)
                user = await auth_service.get_user_by_id(user_id)

                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User not found"
                    )

                if not user.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="User account is inactive"
                    )

                return user

            finally:
                await db.close()

        except TokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        except Exception as e:
            logger.error(f"Token validation error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token validation failed"
            )


class RequireAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware that requires authentication for all routes.

    This is a stricter version that returns 401 for any unauthenticated request
    to non-excluded paths.
    """

    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        """
        Initialize the require auth middleware.

        Args:
            app: FastAPI application instance
            exclude_paths: List of paths to exclude from authentication requirement
        """
        super().__init__(app)
        self.auth_middleware = AuthMiddleware(app, exclude_paths)

    async def dispatch(self, request: Request, call_next):
        """
        Process the request and require authentication.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response from the next handler or 401 if not authenticated
        """
        # Use the base auth middleware for token validation
        response = await self.auth_middleware.dispatch(request, call_next)

        # If this is not an excluded path and no user is authenticated, return 401
        if (not self.auth_middleware._should_skip_auth(request) and
            (not hasattr(request.state, 'user') or
             request.state.user is None)):

            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Authentication required"}
            )

        return response


# Utility functions for accessing user context in route handlers

def get_current_user_from_state(request: Request) -> Optional[User]:
    """
    Get the current authenticated user from request state.

    This function can be used in route handlers to access the user
    that was authenticated by the middleware.

    Args:
        request: The FastAPI request object

    Returns:
        The authenticated user or None
    """
    return getattr(request.state, 'user', None)


def get_token_payload_from_state(request: Request) -> Optional[dict]:
    """
    Get the JWT token payload from request state.

    Args:
        request: The FastAPI request object

    Returns:
        The token payload or None
    """
    return getattr(request.state, 'token_payload', None)


def require_authenticated_user(request: Request) -> User:
    """
    Get the current authenticated user or raise an exception.

    Args:
        request: The FastAPI request object

    Returns:
        The authenticated user

    Raises:
        HTTPException: If no user is authenticated
    """
    user = get_current_user_from_state(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user
