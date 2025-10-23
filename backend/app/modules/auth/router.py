"""
Authentication router with login, register, and refresh token endpoints.
"""
from datetime import timedelta
from typing import Any

from app.core.config import get_settings
from app.core.database import get_db_session
from app.modules.auth import schemas
from app.modules.auth.dependencies import (
    get_current_active_user,
    get_current_user,
    validate_refresh_token,
)
from app.modules.auth.service import AuthService
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
settings = get_settings()


@router.post("/register", response_model=schemas.RegisterResponse)
async def register(
    user_data: schemas.UserCreate,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Register a new user.
    """
    auth_service = AuthService(db)

    try:
        user = await auth_service.create_user(user_data)

        # Generate tokens for the new user
        tokens = await auth_service.create_tokens(user)

        return schemas.RegisterResponse(
            message="User registered successfully",
            user=schemas.UserResponse.model_validate(user),
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type="bearer"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=schemas.LoginResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Login user and return access and refresh tokens.
    """
    auth_service = AuthService(db)

    # Create login data from form
    login_data = schemas.UserLogin(
        username=form_data.username,  # OAuth2PasswordRequestForm uses 'username' field
        password=form_data.password
    )

    try:
        user = await auth_service.authenticate_user(login_data.username, login_data.password)

        # Parse scopes from form_data.scopes or use default
        scopes = form_data.scopes if form_data.scopes else ["read", "write"]

        # Generate tokens using the create_tokens method
        tokens = await auth_service.create_tokens(user, form_data.scopes is not None)

        # Refresh the user object to ensure all fields are loaded
        await db.refresh(user)

        return schemas.LoginResponse(
            user=schemas.UserResponse.model_validate(user),
            token=schemas.Token(
                access_token=tokens["access_token"],
                refresh_token=tokens["refresh_token"],
                token_type="bearer",
                expires_in=tokens["expires_in"]
            )
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=schemas.Token)
async def refresh_token(
    refresh_data: schemas.RefreshToken,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Refresh access token using refresh token.
    """
    auth_service = AuthService(db)

    try:
        # Validate refresh token and get user
        user = await validate_refresh_token(refresh_data.refresh_token, db)

        # Generate new access token
        access_token = await auth_service.create_access_token(
            user_id=user.id,
            scopes=["read", "write"]  # Default scopes for refresh
        )

        return schemas.Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout", response_model=schemas.MessageResponse)
async def logout(
    current_user: schemas.UserResponse = Depends(get_current_active_user),
) -> Any:
    """
    Logout user (client should discard tokens).
    """
    # In a stateless JWT system, logout is handled client-side
    # For enhanced security, you could maintain a token blacklist
    return schemas.MessageResponse(
        message="Successfully logged out. Please discard your tokens."
    )


@router.get("/me", response_model=schemas.UserResponse)
async def get_current_user_info(
    current_user: schemas.UserResponse = Depends(get_current_active_user),
) -> Any:
    """
    Get current user information.
    """
    return current_user


@router.put("/me", response_model=schemas.UserResponse)
async def update_current_user(
    user_update: schemas.UserUpdate,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Update current user information.
    """
    auth_service = AuthService(db)

    try:
        updated_user = await auth_service.update_user(current_user.id, user_update)
        return schemas.UserResponse.model_validate(updated_user)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/change-password", response_model=schemas.MessageResponse)
async def change_password(
    password_data: schemas.PasswordChange,
    current_user: schemas.UserResponse = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Change user password.
    """
    auth_service = AuthService(db)

    try:
        await auth_service.change_password(
            user_id=current_user.id,
            current_password=password_data.current_password,
            new_password=password_data.new_password
        )
        return schemas.MessageResponse(message="Password changed successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/forgot-password", response_model=schemas.MessageResponse)
async def forgot_password(
    email_data: schemas.PasswordReset,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Initiate password reset process.
    """
    auth_service = AuthService(db)

    try:
        await auth_service.initiate_password_reset(email_data.email)
        return schemas.MessageResponse(
            message="If the email exists, a password reset link has been sent"
        )
    except Exception:
        # Always return success message for security (don't reveal if email exists)
        return schemas.MessageResponse(
            message="If the email exists, a password reset link has been sent"
        )


@router.post("/reset-password", response_model=schemas.MessageResponse)
async def reset_password(
    reset_data: schemas.PasswordResetConfirm,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Confirm password reset with token.
    """
    auth_service = AuthService(db)

    try:
        await auth_service.confirm_password_reset(
            token=reset_data.token,
            new_password=reset_data.new_password
        )
        return schemas.MessageResponse(message="Password reset successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify-email", response_model=schemas.MessageResponse)
async def verify_email(
    verification_data: schemas.EmailVerification,
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Verify user email with token.
    """
    auth_service = AuthService(db)

    try:
        await auth_service.verify_email(verification_data.token)
        return schemas.MessageResponse(message="Email verified successfully")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/resend-verification", response_model=schemas.MessageResponse)
async def resend_verification(
    current_user: schemas.UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> Any:
    """
    Resend email verification token.
    """
    auth_service = AuthService(db)

    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )

    try:
        await auth_service.initiate_email_verification(current_user.email)
        return schemas.MessageResponse(
            message="Verification email sent successfully"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
