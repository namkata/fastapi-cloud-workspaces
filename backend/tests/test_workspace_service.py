"""
Unit tests for WorkspaceService.

This module contains comprehensive tests for workspace management operations.
"""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from app.modules.auth.models import User
from app.modules.workspace.models import (
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceRoleEnum,
    WorkspaceStatus,
)
from app.modules.workspace.schemas import WorkspaceCreate, WorkspaceUpdate
from app.modules.workspace.service import WorkspaceService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class TestWorkspaceService:
    """Test cases for WorkspaceService."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def workspace_service(self, mock_db):
        """WorkspaceService instance with mocked database."""
        return WorkspaceService(db=mock_db)

    @pytest.fixture
    def sample_user(self):
        """Sample user for testing."""
        return User(
            id=uuid4(),
            username="testuser",
            email="test@example.com",
            is_active=True,
            created_at=datetime.utcnow()
        )

    @pytest.fixture
    def sample_workspace(self, sample_user):
        """Sample workspace for testing."""
        return Workspace(
            id=uuid4(),
            name="Test Workspace",
            description="A test workspace",
            owner_id=sample_user.id,
            is_public=False,
            max_members=10,
            status=WorkspaceStatus.ACTIVE,
            created_at=datetime.utcnow()
        )

    @pytest.fixture
    def sample_role(self):
        """Sample workspace role for testing."""
        return WorkspaceRole(
            id=uuid4(),
            name=WorkspaceRoleEnum.ADMIN,
            description="Administrator role",
            is_system_role=True,
            permissions=["read", "write", "admin"]
        )

    @pytest.fixture
    def sample_member(self, sample_workspace, sample_user, sample_role):
        """Sample workspace member for testing."""
        return WorkspaceMember(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            user_id=sample_user.id,
            role_id=sample_role.id,
            is_active=True,
            joined_at=datetime.utcnow()
        )

    async def test_create_workspace_success(self, workspace_service, mock_db, sample_user, sample_role):
        """Test successful workspace creation."""
        # Arrange
        workspace_data = WorkspaceCreate(
            name="New Workspace",
            description="A new workspace",
            is_public=True,
            max_members=20,
            avatar_url="https://example.com/avatar.png"
        )

        # Mock role lookup
        mock_role_result = MagicMock()
        mock_role_result.scalar_one_or_none.return_value = sample_role
        mock_db.execute.return_value = mock_role_result

        # Mock workspace creation
        created_workspace = Workspace(
            id=uuid4(),
            name=workspace_data.name,
            description=workspace_data.description,
            owner_id=sample_user.id,
            is_public=workspace_data.is_public,
            max_members=workspace_data.max_members,
            avatar_url=workspace_data.avatar_url,
            status=WorkspaceStatus.ACTIVE
        )

        # Act
        with patch.object(workspace_service, 'get_role_by_name', return_value=sample_role):
            result = await workspace_service.create_workspace(workspace_data, sample_user)

        # Assert
        mock_db.add.assert_called()
        mock_db.flush.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        # Verify workspace member was added
        assert mock_db.add.call_count == 2  # Workspace + Member

    async def test_create_workspace_no_admin_role(self, workspace_service, mock_db, sample_user):
        """Test workspace creation when admin role is not found."""
        # Arrange
        workspace_data = WorkspaceCreate(name="Test Workspace")

        # Act
        with patch.object(workspace_service, 'get_role_by_name', return_value=None):
            result = await workspace_service.create_workspace(workspace_data, sample_user)

        # Assert
        mock_db.add.assert_called_once()  # Only workspace, no member
        mock_db.commit.assert_called_once()

    async def test_get_workspace_by_id_found(self, workspace_service, mock_db, sample_workspace):
        """Test getting workspace by ID when found."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workspace
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_workspace_by_id(sample_workspace.id)

        # Assert
        assert result == sample_workspace
        mock_db.execute.assert_called_once()

    async def test_get_workspace_by_id_not_found(self, workspace_service, mock_db):
        """Test getting workspace by ID when not found."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_workspace_by_id(uuid4())

        # Assert
        assert result is None
        mock_db.execute.assert_called_once()

    async def test_get_workspace_with_members(self, workspace_service, mock_db, sample_workspace):
        """Test getting workspace with member details."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_workspace
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_workspace_with_members(sample_workspace.id)

        # Assert
        assert result == sample_workspace
        mock_db.execute.assert_called_once()

    async def test_get_user_workspaces_owned_and_member(self, workspace_service, mock_db, sample_user):
        """Test getting user workspaces including owned and member workspaces."""
        # Arrange
        workspaces = [
            Workspace(id=uuid4(), name="Owned Workspace", owner_id=sample_user.id),
            Workspace(id=uuid4(), name="Member Workspace", owner_id=uuid4())
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = workspaces
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_user_workspaces(
            sample_user,
            include_owned=True,
            include_member=True
        )

        # Assert
        assert result == workspaces
        mock_db.execute.assert_called_once()

    async def test_get_user_workspaces_owned_only(self, workspace_service, mock_db, sample_user):
        """Test getting only owned workspaces."""
        # Arrange
        workspaces = [Workspace(id=uuid4(), name="Owned Workspace", owner_id=sample_user.id)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = workspaces
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_user_workspaces(
            sample_user,
            include_owned=True,
            include_member=False
        )

        # Assert
        assert result == workspaces
        mock_db.execute.assert_called_once()

    async def test_get_user_workspaces_with_status_filter(self, workspace_service, mock_db, sample_user):
        """Test getting user workspaces with status filter."""
        # Arrange
        workspaces = [Workspace(id=uuid4(), name="Active Workspace", status=WorkspaceStatus.ACTIVE)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = workspaces
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_user_workspaces(
            sample_user,
            status_filter=WorkspaceStatus.ACTIVE,
            skip=10,
            limit=50
        )

        # Assert
        assert result == workspaces
        mock_db.execute.assert_called_once()

    async def test_update_workspace_success(self, workspace_service, mock_db, sample_workspace):
        """Test successful workspace update."""
        # Arrange
        update_data = WorkspaceUpdate(
            name="Updated Workspace",
            description="Updated description",
            is_public=True
        )

        # Act
        result = await workspace_service.update_workspace(sample_workspace, update_data)

        # Assert
        assert sample_workspace.name == "Updated Workspace"
        assert sample_workspace.description == "Updated description"
        assert sample_workspace.is_public is True
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_workspace)

    async def test_update_workspace_partial_update(self, workspace_service, mock_db, sample_workspace):
        """Test partial workspace update."""
        # Arrange
        original_name = sample_workspace.name
        update_data = WorkspaceUpdate(description="New description only")

        # Act
        result = await workspace_service.update_workspace(sample_workspace, update_data)

        # Assert
        assert sample_workspace.name == original_name  # Unchanged
        assert sample_workspace.description == "New description only"
        mock_db.commit.assert_called_once()

    async def test_delete_workspace(self, workspace_service, mock_db, sample_workspace):
        """Test workspace deletion (archiving)."""
        # Act
        await workspace_service.delete_workspace(sample_workspace)

        # Assert
        assert sample_workspace.status == WorkspaceStatus.ARCHIVED
        mock_db.commit.assert_called_once()

    async def test_add_member_success(self, workspace_service, mock_db, sample_workspace, sample_user, sample_role):
        """Test successful member addition."""
        # Arrange
        inviter = User(id=uuid4(), username="inviter", email="inviter@example.com")

        # Act
        result = await workspace_service.add_member(sample_workspace, sample_user, sample_role, inviter)

        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    async def test_add_member_without_inviter(self, workspace_service, mock_db, sample_workspace, sample_user, sample_role):
        """Test member addition without inviter."""
        # Act
        result = await workspace_service.add_member(sample_workspace, sample_user, sample_role)

        # Assert
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_remove_member(self, workspace_service, mock_db, sample_member):
        """Test member removal."""
        # Act
        await workspace_service.remove_member(sample_member)

        # Assert
        mock_db.delete.assert_called_once_with(sample_member)
        mock_db.commit.assert_called_once()

    async def test_update_member_role(self, workspace_service, mock_db, sample_member, sample_role):
        """Test member role update."""
        # Arrange
        new_role = WorkspaceRole(
            id=uuid4(),
            name=WorkspaceRoleEnum.MEMBER,
            description="Member role"
        )
        sample_member.role = sample_role  # Set current role

        # Act
        result = await workspace_service.update_member_role(sample_member, new_role)

        # Assert
        assert sample_member.role_id == new_role.id
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(sample_member)

    async def test_get_role_by_name_found(self, workspace_service, mock_db, sample_role):
        """Test getting role by name when found."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_role
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_role_by_name(WorkspaceRoleEnum.ADMIN)

        # Assert
        assert result == sample_role
        mock_db.execute.assert_called_once()

    async def test_get_role_by_name_not_found(self, workspace_service, mock_db):
        """Test getting role by name when not found."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_role_by_name(WorkspaceRoleEnum.ADMIN)

        # Assert
        assert result is None
        mock_db.execute.assert_called_once()

    async def test_get_workspace_member_found(self, workspace_service, mock_db, sample_member):
        """Test getting workspace member when found."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_member
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_workspace_member(
            sample_member.workspace_id,
            sample_member.user_id
        )

        # Assert
        assert result == sample_member
        mock_db.execute.assert_called_once()

    async def test_get_workspace_member_not_found(self, workspace_service, mock_db):
        """Test getting workspace member when not found."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.get_workspace_member(uuid4(), uuid4())

        # Assert
        assert result is None
        mock_db.execute.assert_called_once()

    async def test_count_workspace_members(self, workspace_service, mock_db, sample_workspace):
        """Test counting workspace members."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar.return_value = 5
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.count_workspace_members(sample_workspace.id)

        # Assert
        assert result == 5
        mock_db.execute.assert_called_once()

    async def test_count_workspace_members_none_result(self, workspace_service, mock_db, sample_workspace):
        """Test counting workspace members when result is None."""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalar.return_value = None
        mock_db.execute.return_value = mock_result

        # Act
        result = await workspace_service.count_workspace_members(sample_workspace.id)

        # Assert
        assert result == 0
        mock_db.execute.assert_called_once()

    async def test_is_workspace_owner_true(self, workspace_service, sample_workspace, sample_user):
        """Test workspace owner check when user is owner."""
        # Arrange
        sample_workspace.owner_id = sample_user.id

        # Act
        result = await workspace_service.is_workspace_owner(sample_workspace, sample_user)

        # Assert
        assert result is True

    async def test_is_workspace_owner_false(self, workspace_service, sample_workspace, sample_user):
        """Test workspace owner check when user is not owner."""
        # Arrange
        sample_workspace.owner_id = uuid4()  # Different user

        # Act
        result = await workspace_service.is_workspace_owner(sample_workspace, sample_user)

        # Assert
        assert result is False

    async def test_can_add_members_unlimited(self, workspace_service, sample_workspace):
        """Test can add members when no limit is set."""
        # Arrange
        sample_workspace.max_members = None

        # Act
        result = await workspace_service.can_add_members(sample_workspace)

        # Assert
        assert result is True

    async def test_can_add_members_under_limit(self, workspace_service, mock_db, sample_workspace):
        """Test can add members when under limit."""
        # Arrange
        sample_workspace.max_members = 10

        with patch.object(workspace_service, 'count_workspace_members', return_value=5):
            # Act
            result = await workspace_service.can_add_members(sample_workspace)

        # Assert
        assert result is True

    async def test_can_add_members_at_limit(self, workspace_service, mock_db, sample_workspace):
        """Test can add members when at limit."""
        # Arrange
        sample_workspace.max_members = 10

        with patch.object(workspace_service, 'count_workspace_members', return_value=10):
            # Act
            result = await workspace_service.can_add_members(sample_workspace)

        # Assert
        assert result is False

    async def test_can_add_members_over_limit(self, workspace_service, mock_db, sample_workspace):
        """Test can add members when over limit."""
        # Arrange
        sample_workspace.max_members = 10

        with patch.object(workspace_service, 'count_workspace_members', return_value=15):
            # Act
            result = await workspace_service.can_add_members(sample_workspace)

        # Assert
        assert result is False


class TestWorkspaceServiceIntegration:
    """Integration tests for WorkspaceService with more complex scenarios."""

    @pytest.fixture
    def workspace_service(self, mock_db):
        """WorkspaceService instance for integration tests."""
        return WorkspaceService(db=mock_db)

    async def test_create_workspace_with_member_flow(self, workspace_service, mock_db):
        """Test complete workspace creation with member addition flow."""
        # This would be an integration test that tests the full flow
        # of creating a workspace and adding the owner as admin
        pass

    async def test_workspace_member_management_flow(self, workspace_service, mock_db):
        """Test complete member management flow."""
        # This would test adding, updating roles, and removing members
        pass
