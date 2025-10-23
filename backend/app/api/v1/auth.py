"""
Authentication API routes.
"""
from typing import Any, Dict

from app.core.database import get_db_session
from app.core.logger import logger
from app.core.rate_limiting import auth_rate_limit, strict_rate_limit
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.schemas import (
    EmailVerification,
    LoginResponse,
    PasswordReset,
    PasswordResetConfirm,
    RefreshToken,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
)
from app.modules.auth.service import AuthService
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@auth_rate_limit
async def register(
    request: UserCreate,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """Register a new user."""
    try:
        auth_service = AuthService(session)
        user = await auth_service.create_user(request)

        logger.info(f"User registered successfully: {user.email}")
        return UserResponse.from_orm(user)

    except ValueError as e:
        logger.warning(f"Registration failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/login", response_model=LoginResponse)
@auth_rate_limit
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    http_request: Request = None,
    session: AsyncSession = Depends(get_db_session)
):
    """Authenticate user and return tokens."""
    try:
        auth_service = AuthService(session)
        user = await auth_service.authenticate_user(
            identifier=form_data.username,  # OAuth2PasswordRequestForm uses username field
            password=form_data.password
        )

        if not user:
            logger.warning(f"Login failed for {form_data.username}: Invalid credentials")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Extract remember_me from scopes if present
        remember_me = "remember_me" in (form_data.scopes or [])

        tokens = await auth_service.create_tokens(user, remember_me)

        logger.info(f"User logged in successfully: {form_data.username}")

        # Refresh the user object to ensure all attributes are loaded
        await session.refresh(user)

        return LoginResponse(
            user=UserResponse.from_orm(user),
            token=Token(**tokens)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for {form_data.username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed"
        )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: RefreshToken,
    session: AsyncSession = Depends(get_db_session)
):
    """Refresh access token using refresh token."""
    try:
        auth_service = AuthService(session)
        tokens = await auth_service.refresh_tokens(request.refresh_token)

        logger.info("Token refreshed successfully")
        return Token(**tokens)

    except ValueError as e:
        logger.warning(f"Token refresh failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )


@router.post("/logout")
async def logout(
    session: AsyncSession = Depends(get_db_session)
):
    """Logout user and invalidate tokens."""
    try:
        auth_service = AuthService(session)
        await auth_service.logout_user(token.credentials)

        logger.info("User logged out successfully")
        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information."""
    return UserResponse.from_orm(current_user)


@router.post("/verify-email")
async def verify_email(
    request: EmailVerification,
    session: AsyncSession = Depends(get_db_session)
):
    """Verify user email address."""
    try:
        auth_service = AuthService(session)
        await auth_service.verify_email(token)

        logger.info("Email verified successfully")
        return {"message": "Email verified successfully"}

    except ValueError as e:
        logger.warning(f"Email verification failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )


@router.post("/forgot-password")
@strict_rate_limit
async def forgot_password(
    request: PasswordReset,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """Send password reset email."""
    try:
        auth_service = AuthService(session)
        await auth_service.send_password_reset(email)

        logger.info(f"Password reset email sent to: {email}")
        return {"message": "Password reset email sent"}

    except Exception as e:
        logger.error(f"Password reset error for {email}: {str(e)}")
        # Don't reveal if email exists or not
        return {"message": "Password reset email sent"}


@router.post("/reset-password")
@strict_rate_limit
async def reset_password(
    request: PasswordResetConfirm,
    http_request: Request,
    session: AsyncSession = Depends(get_db_session)
):
    """Reset password using reset token."""
    try:
        auth_service = AuthService(session)
        await auth_service.reset_password(token, new_password)

        logger.info("Password reset successfully")
        return {"message": "Password reset successfully"}

    except ValueError as e:
        logger.warning(f"Password reset failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Password reset error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password reset failed"
        )
