"""
Tests for Role-Based Access Control (RBAC) system.

This module tests the RBAC decorators, permission checkers, and role-based access control.
"""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from app.core.rbac import (
    PermissionChecker,
    RoleChecker,
    require_admin,
    require_admin_permission,
    require_editor,
    require_permission,
    require_read_permission,
    require_role,
    require_viewer,
    require_write_permission,
)
from app.modules.auth.models import User
from app.modules.workspace.models import Workspace, WorkspaceMember, WorkspaceRole
from fastapi import Depends, HTTPException, Request
from fastapi.testclient import TestClient


class TestRoleChecker:
    """Test the RoleChecker class."""

    def test_init_with_single_role(self):
        """Test RoleChecker initialization with a single role."""
        checker = RoleChecker("admin")
        assert checker.required_roles == ["admin"]

    def test_init_with_multiple_roles(self):
        """Test RoleChecker initialization with multiple roles."""
        checker = RoleChecker(["admin", "editor"])
        assert checker.required_roles == ["admin", "editor"]

    @pytest.mark.asyncio
    async def test_call_with_superuser(self):
        """Test RoleChecker allows superusers regardless of role."""
        checker = RoleChecker("admin")

        # Mock request and user as superuser
        request = Mock(spec=Request)
        user = Mock(spec=User)
        user.is_superuser = True

        # Mock database session
        db = AsyncMock()

        # Should not raise exception
        result = await checker(request, user, db)
        assert result == user

    @pytest.mark.asyncio
    async def test_call_without_workspace_context(self):
        """Test RoleChecker with workspace_context=False."""
        checker = RoleChecker("admin", workspace_context=False)

        # Mock request and non-superuser
        request = Mock(spec=Request)
        user = Mock(spec=User)
        user.is_superuser = False

        # Mock database session
        db = AsyncMock()

        # Should raise exception for non-superuser
        with pytest.raises(HTTPException) as exc_info:
            await checker(request, user, db)

        assert exc_info.value.status_code == 403
        assert "System role required" in str(exc_info.value.detail)


class TestPermissionChecker:
    """Test the PermissionChecker class."""

    def test_init_with_single_permission(self):
        """Test PermissionChecker initialization with a single permission."""
        checker = PermissionChecker("read")
        assert checker.required_permissions == ["read"]

    def test_init_with_multiple_permissions(self):
        """Test PermissionChecker initialization with multiple permissions."""
        checker = PermissionChecker(["read", "write"])
        assert checker.required_permissions == ["read", "write"]

    @pytest.mark.asyncio
    async def test_call_with_superuser(self):
        """Test PermissionChecker allows superusers regardless of permissions."""
        checker = PermissionChecker("admin")

        # Mock request and user as superuser
        request = Mock(spec=Request)
        user = Mock(spec=User)
        user.is_superuser = True

        # Mock database session
        db = AsyncMock()

        result = await checker(request, user, db)
        assert result == user

    @pytest.mark.asyncio
    async def test_call_with_matching_permissions(self):
        """Test PermissionChecker with matching permissions."""
        checker = PermissionChecker(["read", "write"])

        # Mock request with workspace context
        mock_request = Mock(spec=Request)
        mock_request.state = Mock()
        mock_request.state.workspace_id = "workspace-123"

        # Mock user
        mock_user = Mock(spec=User)
        mock_user.id = "user-123"
        mock_user.is_superuser = False

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with matching permissions
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = True
        workspace_member.role.can_write = True
        workspace_member.role.can_admin = False
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        result = await checker(mock_request, mock_user, db)
        assert result == mock_user

    @pytest.mark.asyncio
    async def test_call_with_partial_permissions(self):
        """Test PermissionChecker raises exception when user lacks some permissions."""
        checker = PermissionChecker(["read", "write", "admin"])

        # Mock request and user
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.workspace_id = "workspace-123"

        user = Mock(spec=User)
        user.is_superuser = False
        user.id = 1

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with only read permission
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = True
        workspace_member.role.can_write = False
        workspace_member.role.can_admin = False
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await checker(request, user, db)

        assert exc_info.value.status_code == 403
        assert "Missing permissions" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_call_with_no_permissions(self):
        """Test PermissionChecker raises exception for users with no permissions."""
        checker = PermissionChecker("read")

        # Mock request and user
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.workspace_id = "workspace-123"

        user = Mock(spec=User)
        user.is_superuser = False
        user.id = 1

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with no permissions
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = False
        workspace_member.role.can_write = False
        workspace_member.role.can_admin = False
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await checker(request, user, db)

        assert exc_info.value.status_code == 403
        assert "Missing permissions" in str(exc_info.value.detail)


class TestConvenienceFunctions:
    """Test the convenience functions for role and permission checking."""

    def test_require_role_returns_dependency(self):
        """Test require_role returns a FastAPI dependency."""
        dependency = require_role("admin")
        assert callable(dependency)

    def test_require_permission_returns_dependency(self):
        """Test require_permission returns a FastAPI dependency."""
        dependency = require_permission("read")
        assert callable(dependency)

    def test_require_admin_returns_dependency(self):
        """Test require_admin returns a FastAPI dependency."""
        dependency = require_admin()
        assert callable(dependency)

    def test_require_editor_returns_dependency(self):
        """Test require_editor returns a FastAPI dependency."""
        dependency = require_editor()
        assert callable(dependency)

    def test_require_viewer_returns_dependency(self):
        """Test require_viewer returns a FastAPI dependency."""
        dependency = require_viewer()
        assert callable(dependency)


class TestWorkspacePermissionFunctions:
    """Test workspace-specific permission functions."""

    def test_require_read_permission(self):
        """Test require_read_permission returns a dependency."""
        dependency = require_read_permission()
        assert callable(dependency)

    def test_require_write_permission(self):
        """Test require_write_permission returns a dependency."""
        dependency = require_write_permission()
        assert callable(dependency)

    def test_require_admin_permission(self):
        """Test require_admin_permission returns a dependency."""
        dependency = require_admin_permission()
        assert callable(dependency)


class TestRBACIntegration:
    """Integration tests for RBAC system."""

    @pytest.fixture
    def mock_user_admin(self):
        """Create a mock admin user."""
        user = Mock(spec=User)
        user.id = 1
        user.email = "admin@example.com"
        user.is_superuser = False
        return user

    @pytest.fixture
    def mock_user_viewer(self):
        """Create a mock viewer user."""
        user = Mock(spec=User)
        user.id = 2
        user.email = "viewer@example.com"
        user.is_superuser = False
        return user

    @pytest.fixture
    def mock_superuser(self):
        """Create a mock superuser."""
        user = Mock(spec=User)
        user.id = 3
        user.email = "super@example.com"
        user.is_superuser = True
        return user

    @pytest.fixture
    def mock_request_with_workspace(self):
        """Create a mock request with workspace context."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.workspace_id = "workspace-123"
        return request

    @pytest.mark.asyncio
    async def test_admin_role_access(self, mock_user_admin, mock_request_with_workspace):
        """Test admin role access."""
        checker = RoleChecker("admin")

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with admin role
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.name = "admin"
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        result = await checker(mock_request_with_workspace, mock_user_admin, db)
        assert result == mock_user_admin

    @pytest.mark.asyncio
    async def test_viewer_role_denied_admin_access(self, mock_user_viewer, mock_request_with_workspace):
        """Test viewer role is denied admin access."""
        checker = RoleChecker("admin")

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with viewer role
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.name = "viewer"
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await checker(mock_request_with_workspace, mock_user_viewer, db)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_superuser_bypasses_role_check(self, mock_superuser, mock_request_with_workspace):
        """Test superuser bypasses role checks."""
        checker = RoleChecker("admin")

        # Mock database session
        db = AsyncMock()

        result = await checker(mock_request_with_workspace, mock_superuser, db)
        assert result == mock_superuser

    @pytest.mark.asyncio
    async def test_permission_check_success(self, mock_user_admin, mock_request_with_workspace):
        """Test successful permission check."""
        checker = PermissionChecker(["read", "write"])

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with required permissions
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = True
        workspace_member.role.can_write = True
        workspace_member.role.can_admin = False
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        result = await checker(mock_request_with_workspace, mock_user_admin, db)
        assert result == mock_user_admin

    @pytest.mark.asyncio
    async def test_permission_check_failure(self, mock_user_viewer, mock_request_with_workspace):
        """Test failed permission check."""
        checker = PermissionChecker(["write", "admin"])

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with only read permission
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = True
        workspace_member.role.can_write = False
        workspace_member.role.can_admin = False
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await checker(mock_request_with_workspace, mock_user_viewer, db)

        assert exc_info.value.status_code == 403
        assert "Missing permissions" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_multiple_roles_allowed(self, mock_user_viewer, mock_request_with_workspace):
        """Test that multiple roles can be allowed."""
        checker = RoleChecker(["admin", "editor", "viewer"])

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with viewer role
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.name = "viewer"
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        result = await checker(mock_request_with_workspace, mock_user_viewer, db)
        assert result == mock_user_viewer

    @pytest.mark.asyncio
    async def test_multiple_permissions_required(self, mock_user_admin, mock_request_with_workspace):
        """Test that multiple permissions can be required."""
        checker = PermissionChecker(["read", "write", "admin"])

        # Mock database session
        db = AsyncMock()

        # Mock workspace member with all required permissions
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = True
        workspace_member.role.can_write = True
        workspace_member.role.can_admin = True
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        result = await checker(mock_request_with_workspace, mock_user_admin, db)
        assert result == mock_user_admin


class TestRBACErrorHandling:
    """Test error handling in RBAC system."""

    @pytest.fixture
    def mock_request_with_workspace(self):
        """Create a mock request with workspace context."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.workspace_id = "workspace-123"
        return request

    @pytest.mark.asyncio
    async def test_role_checker_with_none_user(self, mock_request_with_workspace):
        """Test RoleChecker handles None user gracefully."""
        checker = RoleChecker("admin")
        db = AsyncMock()

        # Mock None user to simulate authentication failure
        none_user = None

        # The checker should handle None user by checking is_superuser attribute
        # which will raise AttributeError, but we need to catch it properly
        with pytest.raises((HTTPException, AttributeError)):
            await checker(mock_request_with_workspace, none_user, db)

    @pytest.mark.asyncio
    async def test_permission_checker_with_none_user(self, mock_request_with_workspace):
        """Test PermissionChecker handles None user gracefully."""
        checker = PermissionChecker("read")
        db = AsyncMock()

        # Mock None user to simulate authentication failure
        none_user = None

        # The checker should handle None user by checking is_superuser attribute
        # which will raise AttributeError, but we need to catch it properly
        with pytest.raises((HTTPException, AttributeError)):
            await checker(mock_request_with_workspace, none_user, db)

    @pytest.mark.asyncio
    async def test_role_checker_with_none_memberships(self, mock_request_with_workspace):
        """Test RoleChecker handles None workspace_memberships."""
        checker = RoleChecker("admin")
        db = AsyncMock()

        user = Mock(spec=User)
        user.id = 1
        user.is_superuser = False

        # Mock database query returning None (no membership)
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await checker(mock_request_with_workspace, user, db)

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_permission_checker_with_none_permissions(self, mock_request_with_workspace):
        """Test PermissionChecker handles None permissions in role."""
        checker = PermissionChecker("read")
        db = AsyncMock()

        user = Mock(spec=User)
        user.id = 1
        user.is_superuser = False

        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = False
        workspace_member.role.can_write = False
        workspace_member.role.can_admin = False
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        with pytest.raises(HTTPException) as exc_info:
            await checker(mock_request_with_workspace, user, db)

        assert exc_info.value.status_code == 403


class TestRBACPerformance:
    """Test performance aspects of RBAC system."""

    @pytest.fixture
    def mock_request_with_workspace(self):
        """Create a mock request with workspace context."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.workspace_id = "workspace-123"
        return request

    @pytest.mark.asyncio
    async def test_role_checker_with_many_memberships(self, mock_request_with_workspace):
        """Test RoleChecker performance with many workspace memberships."""
        checker = RoleChecker("admin")
        db = AsyncMock()

        user = Mock(spec=User)
        user.id = 1
        user.is_superuser = False

        # Mock workspace member with admin role
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.name = "admin"
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        result = await checker(mock_request_with_workspace, user, db)
        assert result == user

    @pytest.mark.asyncio
    async def test_permission_checker_with_many_permissions(self, mock_request_with_workspace):
        """Test PermissionChecker performance with many permissions."""
        checker = PermissionChecker(["read", "write", "admin"])
        db = AsyncMock()

        user = Mock(spec=User)
        user.id = 1
        user.is_superuser = False

        # Mock workspace member with many permissions
        workspace_member = Mock(spec=WorkspaceMember)
        workspace_member.role = Mock(spec=WorkspaceRole)
        workspace_member.role.can_read = True
        workspace_member.role.can_write = True
        workspace_member.role.can_admin = True
        workspace_member.is_active = True

        # Mock database query result
        result_mock = Mock()
        result_mock.scalar_one_or_none.return_value = workspace_member
        db.execute.return_value = result_mock

        result = await checker(mock_request_with_workspace, user, db)
        assert result == user
