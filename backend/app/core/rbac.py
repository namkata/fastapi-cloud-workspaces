"""
Role-Based Access Control (RBAC) utilities.

This module provides decorators and utilities for role-based access control
across the application.
"""
from functools import wraps
from typing import Callable, List, Optional, Union
from uuid import UUID

from app.core.database import get_db_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.workspace.models import (
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceRoleEnum,
)
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


class RoleChecker:
    """
    Dependency class to check user roles and permissions.

    This class can be used as a FastAPI dependency to enforce role-based
    access control on endpoints.
    """

    def __init__(
        self,
        required_roles: Union[str, List[str]],
        workspace_context: bool = True,
        allow_superuser: bool = True
    ):
        """
        Initialize role checker.

        Args:
            required_roles: Required role name(s) - can be string or list
            workspace_context: Whether to check roles within workspace context
            allow_superuser: Whether superusers bypass role checks
        """
        if isinstance(required_roles, str):
            self.required_roles = [required_roles]
        else:
            self.required_roles = required_roles
        self.workspace_context = workspace_context
        self.allow_superuser = allow_superuser

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
    ) -> User:
        """
        Check if user has required roles.

        Args:
            request: FastAPI request object
            current_user: Current authenticated user
            db: Database session

        Returns:
            The authenticated user

        Raises:
            HTTPException: If user doesn't have required roles
        """
        # Superusers bypass role checks if allowed
        if self.allow_superuser and current_user.is_superuser:
            return current_user

        if self.workspace_context:
            # Check workspace-specific roles
            workspace_id = getattr(request.state, 'workspace_id', None)
            if not workspace_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Workspace context required for role check"
                )

            # Get user's workspace membership
            result = await db.execute(
                select(WorkspaceMember)
                .options(selectinload(WorkspaceMember.role))
                .where(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == current_user.id,
                    WorkspaceMember.is_active == True
                )
            )
            member = result.scalar_one_or_none()

            if not member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You are not a member of this workspace"
                )

            # Check if user has any of the required roles
            user_role = member.role.name.value if hasattr(member.role.name, 'value') else member.role.name
            if user_role not in self.required_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Required role(s): {', '.join(self.required_roles)}, but user has: {user_role}"
                )
        else:
            # For system-wide roles, check if user is superuser or has specific system roles
            # This would require extending the User model with system roles
            # For now, we'll just check superuser status
            if not current_user.is_superuser:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: System role required: {', '.join(self.required_roles)}"
                )

        return current_user


class PermissionChecker:
    """
    Dependency class to check specific permissions.

    This class checks for specific permissions rather than roles,
    providing more granular access control.
    """

    def __init__(
        self,
        required_permissions: Union[str, List[str]],
        allow_superuser: bool = True
    ):
        """
        Initialize permission checker.

        Args:
            required_permissions: Required permission name(s)
            allow_superuser: Whether superusers bypass permission checks
        """
        if isinstance(required_permissions, str):
            self.required_permissions = [required_permissions]
        else:
            self.required_permissions = required_permissions
        self.allow_superuser = allow_superuser

    async def __call__(
        self,
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
    ) -> User:
        """
        Check if user has required permissions.

        Args:
            request: FastAPI request object
            current_user: Current authenticated user
            db: Database session

        Returns:
            The authenticated user

        Raises:
            HTTPException: If user doesn't have required permissions
        """
        # Superusers bypass permission checks if allowed
        if self.allow_superuser and current_user.is_superuser:
            return current_user

        # Get workspace context
        workspace_id = getattr(request.state, 'workspace_id', None)
        if not workspace_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace context required for permission check"
            )

        # Get user's workspace membership
        result = await db.execute(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.role))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
                WorkspaceMember.is_active == True
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not a member of this workspace"
            )

        # Check permissions
        role = member.role
        permission_map = {
            "read": role.can_read,
            "write": role.can_write,
            "admin": role.can_admin,
            "invite": role.can_invite,
            "remove_members": role.can_remove_members,
        }

        # Check if user has all required permissions
        missing_permissions = []
        for permission in self.required_permissions:
            if permission not in permission_map:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Unknown permission: {permission}"
                )

            if not permission_map[permission]:
                missing_permissions.append(permission)

        if missing_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Missing permissions: {', '.join(missing_permissions)}"
            )

        return current_user


# Convenience functions for common role checks
def require_role(
    roles: Union[str, List[str]],
    workspace_context: bool = True,
    allow_superuser: bool = True
) -> RoleChecker:
    """
    Create a role checker dependency.

    Args:
        roles: Required role name(s)
        workspace_context: Whether to check roles within workspace context
        allow_superuser: Whether superusers bypass role checks

    Returns:
        RoleChecker dependency

    Example:
        @router.get("/admin-only", dependencies=[Depends(require_role("admin"))])
        async def admin_endpoint():
            return {"message": "Admin access granted"}
    """
    return RoleChecker(roles, workspace_context, allow_superuser)


def require_permission(
    permissions: Union[str, List[str]],
    allow_superuser: bool = True
) -> PermissionChecker:
    """
    Create a permission checker dependency.

    Args:
        permissions: Required permission name(s)
        allow_superuser: Whether superusers bypass permission checks

    Returns:
        PermissionChecker dependency

    Example:
        @router.post("/create", dependencies=[Depends(require_permission("write"))])
        async def create_endpoint():
            return {"message": "Write access granted"}
    """
    return PermissionChecker(permissions, allow_superuser)


# Convenience functions for common roles
def require_admin(workspace_context: bool = True) -> RoleChecker:
    """Require admin role."""
    return require_role("admin", workspace_context)


def require_editor(workspace_context: bool = True) -> RoleChecker:
    """Require editor role (or higher)."""
    return require_role(["admin", "editor"], workspace_context)


def require_viewer(workspace_context: bool = True) -> RoleChecker:
    """Require viewer role (or higher)."""
    return require_role(["admin", "editor", "viewer"], workspace_context)


# Convenience functions for common permissions
def require_read_permission() -> PermissionChecker:
    """Require read permission."""
    return require_permission("read")


def require_write_permission() -> PermissionChecker:
    """Require write permission."""
    return require_permission("write")


def require_admin_permission() -> PermissionChecker:
    """Require admin permission."""
    return require_permission("admin")


def require_invite_permission() -> PermissionChecker:
    """Require invite permission."""
    return require_permission("invite")


def require_remove_members_permission() -> PermissionChecker:
    """Require remove members permission."""
    return require_permission("remove_members")
