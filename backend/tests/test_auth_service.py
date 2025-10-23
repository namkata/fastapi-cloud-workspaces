"""
Unit tests for AuthService class.

This module tests all authentication-related business logic including
user authentication, registration, password operations, and token management.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from app.modules.auth.models import User
from app.modules.auth.schemas import UserCreate, UserUpdate
from app.modules.auth.service import AuthService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import create_mock_user


class TestAuthServiceUserRetrieval:
    """Test user retrieval methods."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, mock_db_session):
        """Test successful user retrieval by ID."""
        # Arrange
        user_id = str(uuid4())
        mock_user = create_mock_user(user_id=user_id)

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.get_user_by_id(user_id)

        # Assert
        assert result == mock_user
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_id_invalid_uuid(self, mock_db_session):
        """Test user retrieval with invalid UUID."""
        # Arrange
        service = AuthService(mock_db_session)

        # Act
        result = await service.get_user_by_id("invalid-uuid")

        # Assert
        assert result is None
        mock_db_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, mock_db_session):
        """Test user retrieval when user not found."""
        # Arrange
        user_id = str(uuid4())

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.get_user_by_id(user_id)

        # Assert
        assert result is None
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_email_success(self, mock_db_session):
        """Test successful user retrieval by email."""
        # Arrange
        email = "test@example.com"
        mock_user = create_mock_user(email=email)

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.get_user_by_email(email)

        # Assert
        assert result == mock_user
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_username_success(self, mock_db_session):
        """Test successful user retrieval by username."""
        # Arrange
        username = "testuser"
        mock_user = create_mock_user(username=username)

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.get_user_by_username(username)

        # Assert
        assert result == mock_user
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_username_or_email_with_email(self, mock_db_session):
        """Test user retrieval by username or email using email."""
        # Arrange
        email = "test@example.com"
        mock_user = create_mock_user(email=email)

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.get_user_by_username_or_email(email)

        # Assert
        assert result == mock_user
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_by_username_or_email_with_username(self, mock_db_session):
        """Test user retrieval by username or email using username."""
        # Arrange
        username = "testuser"
        mock_user = create_mock_user(username=username)

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.get_user_by_username_or_email(username)

        # Assert
        assert result == mock_user
        mock_db_session.execute.assert_called_once()


class TestAuthServiceUserCreation:
    """Test user creation methods."""

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.generate_password_hash')
    async def test_create_user_success(self, mock_hash, mock_db_session, sample_user_data):
        """Test successful user creation."""
        # Arrange
        mock_hash.return_value = "hashed_password"

        # Mock no existing users
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        user_data = UserCreate(**sample_user_data)
        service = AuthService(mock_db_session)

        # Act
        result = await service.create_user(user_data)

        # Assert
        assert isinstance(result, User)
        assert result.email == sample_user_data["email"].lower()
        assert result.username == sample_user_data["username"].lower()
        assert result.full_name == sample_user_data["full_name"]
        assert result.is_active is True
        assert result.is_verified is False
        assert result.is_superuser is False

        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_email_exists(self, mock_db_session, sample_user_data):
        """Test user creation when email already exists."""
        # Arrange
        existing_user = create_mock_user(email=sample_user_data["email"])

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_db_session.execute.return_value = mock_result

        user_data = UserCreate(**sample_user_data)
        service = AuthService(mock_db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="User with this email already exists"):
            await service.create_user(user_data)

    @pytest.mark.asyncio
    async def test_create_user_username_exists(self, mock_db_session, sample_user_data):
        """Test user creation when username already exists."""
        # Arrange
        # First call returns None (email doesn't exist)
        # Second call returns existing user (username exists)
        mock_results = [Mock(), Mock()]
        mock_results[0].scalar_one_or_none.return_value = None
        mock_results[1].scalar_one_or_none.return_value = create_mock_user(username=sample_user_data["username"])

        mock_db_session.execute.side_effect = mock_results

        user_data = UserCreate(**sample_user_data)
        service = AuthService(mock_db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="User with this username already exists"):
            await service.create_user(user_data)


class TestAuthServiceAuthentication:
    """Test user authentication methods."""

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_password')
    async def test_authenticate_user_success(self, mock_verify, mock_db_session):
        """Test successful user authentication."""
        # Arrange
        identifier = "testuser"
        password = "password123"
        mock_user = create_mock_user(username=identifier)
        mock_user.can_login.return_value = True

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        mock_verify.return_value = True

        service = AuthService(mock_db_session)

        # Act
        result = await service.authenticate_user(identifier, password)

        # Assert
        assert result == mock_user
        mock_user.reset_failed_attempts.assert_called_once()
        mock_user.set_last_login.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_not_found(self, mock_db_session):
        """Test authentication when user not found."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.authenticate_user("nonexistent", "password")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_cannot_login(self, mock_db_session):
        """Test authentication when user cannot login."""
        # Arrange
        mock_user = create_mock_user()
        mock_user.can_login.return_value = False

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.authenticate_user("testuser", "password")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_password')
    async def test_authenticate_user_wrong_password(self, mock_verify, mock_db_session):
        """Test authentication with wrong password."""
        # Arrange
        mock_user = create_mock_user()
        mock_user.can_login.return_value = True

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        mock_verify.return_value = False

        service = AuthService(mock_db_session)

        # Act
        result = await service.authenticate_user("testuser", "wrongpassword")

        # Assert
        assert result is None
        mock_user.increment_failed_attempts.assert_called_once()
        mock_db_session.commit.assert_called_once()


class TestAuthServiceUserUpdate:
    """Test user update methods."""

    @pytest.mark.asyncio
    async def test_update_user_success(self, mock_db_session):
        """Test successful user update."""
        # Arrange
        mock_user = create_mock_user()
        update_data = UserUpdate(
            full_name="Updated Name",
            bio="Updated bio",
            avatar_url="https://example.com/new-avatar.jpg"
        )

        # Mock no conflicts
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.update_user(mock_user, update_data)

        # Assert
        assert result == mock_user
        assert mock_user.full_name == "Updated Name"
        assert mock_user.bio == "Updated bio"
        assert mock_user.avatar_url == "https://example.com/new-avatar.jpg"
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_email_conflict(self, mock_db_session):
        """Test user update with email conflict."""
        # Arrange
        mock_user = create_mock_user(email="old@example.com")
        conflicting_user = create_mock_user(email="new@example.com")
        conflicting_user.id = uuid4()  # Different ID

        update_data = UserUpdate(email="new@example.com")

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = conflicting_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="User with this email already exists"):
            await service.update_user(mock_user, update_data)

    @pytest.mark.asyncio
    async def test_update_user_username_conflict(self, mock_db_session):
        """Test user update with username conflict."""
        # Arrange
        mock_user = create_mock_user(username="olduser")
        conflicting_user = create_mock_user(username="newuser")
        conflicting_user.id = uuid4()  # Different ID

        update_data = UserUpdate(username="newuser")

        # Mock email check returns None, username check returns conflicting user
        mock_results = [Mock(), Mock()]
        mock_results[0].scalar_one_or_none.return_value = None
        mock_results[1].scalar_one_or_none.return_value = conflicting_user
        mock_db_session.execute.side_effect = mock_results

        service = AuthService(mock_db_session)

        # Act & Assert
        with pytest.raises(ValueError, match="User with this username already exists"):
            await service.update_user(mock_user, update_data)


class TestAuthServicePasswordOperations:
    """Test password-related operations."""

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_password')
    @patch('app.modules.auth.service.generate_password_hash')
    async def test_change_password_success(self, mock_hash, mock_verify, mock_db_session):
        """Test successful password change."""
        # Arrange
        mock_user = create_mock_user()
        current_password = "oldpassword"
        new_password = "newpassword"

        mock_verify.return_value = True
        mock_hash.return_value = "new_hashed_password"

        service = AuthService(mock_db_session)

        # Act
        result = await service.change_password(mock_user, current_password, new_password)

        # Assert
        assert result is True
        assert mock_user.hashed_password == "new_hashed_password"
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_password')
    async def test_change_password_wrong_current(self, mock_verify, mock_db_session):
        """Test password change with wrong current password."""
        # Arrange
        mock_user = create_mock_user()
        mock_verify.return_value = False

        service = AuthService(mock_db_session)

        # Act
        result = await service.change_password(mock_user, "wrongpassword", "newpassword")

        # Assert
        assert result is False
        mock_db_session.commit.assert_not_called()


class TestAuthServiceTokenOperations:
    """Test token creation and management."""

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.create_access_token')
    @patch('app.modules.auth.service.create_refresh_token')
    async def test_create_tokens_normal(self, mock_refresh, mock_access, mock_db_session):
        """Test normal token creation."""
        # Arrange
        mock_user = create_mock_user()
        mock_access.return_value = "access_token"
        mock_refresh.return_value = "refresh_token"

        service = AuthService(mock_db_session)

        # Act
        result = await service.create_tokens(mock_user)

        # Assert
        assert result["access_token"] == "access_token"
        assert result["refresh_token"] == "refresh_token"
        assert result["token_type"] == "bearer"
        assert result["expires_in"] == 1800  # 30 minutes

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.create_access_token')
    @patch('app.modules.auth.service.create_refresh_token')
    async def test_create_tokens_remember_me(self, mock_refresh, mock_access, mock_db_session):
        """Test token creation with remember me."""
        # Arrange
        mock_user = create_mock_user()
        mock_access.return_value = "access_token"
        mock_refresh.return_value = "refresh_token"

        service = AuthService(mock_db_session)

        # Act
        result = await service.create_tokens(mock_user, remember_me=True)

        # Assert
        assert result["expires_in"] == 86400  # 24 hours

    def test_get_user_scopes_normal_user(self, mock_db_session):
        """Test scope generation for normal user."""
        # Arrange
        mock_user = create_mock_user(is_active=True, is_superuser=False)
        service = AuthService(mock_db_session)

        # Act
        scopes = service._get_user_scopes(mock_user)

        # Assert
        assert "read" in scopes
        assert "write" in scopes
        assert "admin" not in scopes

    def test_get_user_scopes_superuser(self, mock_db_session):
        """Test scope generation for superuser."""
        # Arrange
        mock_user = create_mock_user(is_active=True, is_superuser=True)
        service = AuthService(mock_db_session)

        # Act
        scopes = service._get_user_scopes(mock_user)

        # Assert
        assert "read" in scopes
        assert "write" in scopes
        assert "admin" in scopes

    def test_get_user_scopes_inactive_user(self, mock_db_session):
        """Test scope generation for inactive user."""
        # Arrange
        mock_user = create_mock_user(is_active=False, is_superuser=False)
        service = AuthService(mock_db_session)

        # Act
        scopes = service._get_user_scopes(mock_user)

        # Assert
        assert "read" in scopes
        assert "write" not in scopes
        assert "admin" not in scopes


class TestAuthServicePasswordReset:
    """Test password reset functionality."""

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.create_password_reset_token')
    async def test_initiate_password_reset_success(self, mock_create_token, mock_db_session):
        """Test successful password reset initiation."""
        # Arrange
        email = "test@example.com"
        mock_user = create_mock_user(email=email)
        reset_token = "reset_token_123"

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        mock_create_token.return_value = reset_token

        service = AuthService(mock_db_session)

        # Act
        result = await service.initiate_password_reset(email)

        # Assert
        assert result == reset_token
        assert mock_user.password_reset_token == reset_token
        assert mock_user.password_reset_expires is not None
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_password_reset_user_not_found(self, mock_db_session):
        """Test password reset initiation for non-existent user."""
        # Arrange
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.initiate_password_reset("nonexistent@example.com")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_password_reset_token')
    @patch('app.modules.auth.service.generate_password_hash')
    async def test_reset_password_success(self, mock_hash, mock_verify_token, mock_db_session):
        """Test successful password reset."""
        # Arrange
        user_id = str(uuid4())
        token = "reset_token_123"
        new_password = "newpassword123"

        mock_user = create_mock_user(user_id=user_id)
        mock_user.password_reset_token = token
        mock_user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)

        mock_verify_token.return_value = user_id
        mock_hash.return_value = "new_hashed_password"

        # Mock get_user_by_id
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.reset_password(token, new_password)

        # Assert
        assert result is True
        assert mock_user.hashed_password == "new_hashed_password"
        assert mock_user.password_reset_token is None
        assert mock_user.password_reset_expires is None
        mock_user.reset_failed_attempts.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_password_reset_token')
    async def test_reset_password_invalid_token(self, mock_verify_token, mock_db_session):
        """Test password reset with invalid token."""
        # Arrange
        mock_verify_token.return_value = None

        service = AuthService(mock_db_session)

        # Act
        result = await service.reset_password("invalid_token", "newpassword")

        # Assert
        assert result is False


class TestAuthServiceEmailVerification:
    """Test email verification functionality."""

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.create_email_verification_token')
    async def test_initiate_email_verification(self, mock_create_token, mock_db_session):
        """Test email verification initiation."""
        # Arrange
        mock_user = create_mock_user()
        verification_token = "verification_token_123"

        mock_create_token.return_value = verification_token

        service = AuthService(mock_db_session)

        # Act
        result = await service.initiate_email_verification(mock_user)

        # Assert
        assert result == verification_token
        assert mock_user.email_verification_token == verification_token
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_email_verification_token')
    async def test_verify_email_success(self, mock_verify_token, mock_db_session):
        """Test successful email verification."""
        # Arrange
        user_id = str(uuid4())
        email = "test@example.com"
        token = "verification_token_123"

        mock_user = create_mock_user(user_id=user_id, email=email)
        mock_user.email_verification_token = token

        mock_verify_token.return_value = {"user_id": user_id, "email": email}

        # Mock get_user_by_id
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        service = AuthService(mock_db_session)

        # Act
        result = await service.verify_email(token)

        # Assert
        assert result is True
        mock_user.verify_email.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch('app.modules.auth.service.verify_email_verification_token')
    async def test_verify_email_invalid_token(self, mock_verify_token, mock_db_session):
        """Test email verification with invalid token."""
        # Arrange
        mock_verify_token.return_value = None

        service = AuthService(mock_db_session)

        # Act
        result = await service.verify_email("invalid_token")

        # Assert
        assert result is False


class TestAuthServiceUserActivation:
    """Test user activation/deactivation."""

    @pytest.mark.asyncio
    async def test_deactivate_user(self, mock_db_session):
        """Test user deactivation."""
        # Arrange
        mock_user = create_mock_user(is_active=True)
        service = AuthService(mock_db_session)

        # Act
        await service.deactivate_user(mock_user)

        # Assert
        assert mock_user.is_active is False
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_activate_user(self, mock_db_session):
        """Test user activation."""
        # Arrange
        mock_user = create_mock_user(is_active=False)
        service = AuthService(mock_db_session)

        # Act
        await service.activate_user(mock_user)

        # Assert
        assert mock_user.is_active is True
        mock_user.reset_failed_attempts.assert_called_once()
        mock_db_session.commit.assert_called_once()
