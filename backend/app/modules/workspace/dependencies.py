"""
Workspace dependencies.

This module provides dependency functions for workspace context validation
and member access control.
"""
from typing import Optional
from uuid import UUID

from app.core.database import get_db_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Workspace, WorkspaceMember, WorkspaceRole, WorkspaceRoleEnum


async def get_workspace_id_from_header(request: Request) -> Optional[UUID]:
    """
    Extract workspace ID from X-Workspace-ID header.

    Args:
        request: FastAPI request object

    Returns:
        Workspace ID if present in header, None otherwise
    """
    workspace_id_str = request.headers.get("X-Workspace-ID")
    if not workspace_id_str:
        return None

    try:
        return UUID(workspace_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workspace ID format in X-Workspace-ID header"
        )


async def get_workspace_context(
    workspace_id: Optional[UUID] = Depends(get_workspace_id_from_header),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[Workspace]:
    """
    Get workspace context from header and validate it exists.

    Args:
        workspace_id: Workspace ID from header
        db: Database session

    Returns:
        Workspace object if found, None if no workspace ID provided

    Raises:
        HTTPException: If workspace ID provided but workspace not found
    """
    if not workspace_id:
        return None

    result = await db.execute(
        select(Workspace).where(
            Workspace.id == workspace_id,
            Workspace.status != "archived"
        )
    )
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or archived"
        )

    return workspace


async def require_workspace_context(
    workspace: Optional[Workspace] = Depends(get_workspace_context)
) -> Workspace:
    """
    Require workspace context to be present.

    Args:
        workspace: Workspace from context

    Returns:
        Workspace object

    Raises:
        HTTPException: If no workspace context provided
    """
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID header is required for this operation"
        )

    return workspace


async def get_workspace_member(
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[WorkspaceMember]:
    """
    Get workspace member for current user in the workspace context.

    Args:
        workspace: Current workspace context
        current_user: Current authenticated user
        db: Database session

    Returns:
        WorkspaceMember object if user is a member, None otherwise
    """
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.role))
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == current_user.id,
            WorkspaceMember.is_active == True
        )
    )
    return result.scalar_one_or_none()


async def require_workspace_member(
    member: Optional[WorkspaceMember] = Depends(get_workspace_member)
) -> WorkspaceMember:
    """
    Require user to be a member of the workspace.

    Args:
        member: Workspace member from context

    Returns:
        WorkspaceMember object

    Raises:
        HTTPException: If user is not a member of the workspace
    """
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: You are not a member of this workspace"
        )

    return member


async def require_workspace_permission(
    permission: str,
    member: WorkspaceMember = Depends(require_workspace_member)
) -> WorkspaceMember:
    """
    Require specific workspace permission.

    Args:
        permission: Permission name (read, write, admin, invite, remove_members)
        member: Workspace member

    Returns:
        WorkspaceMember object

    Raises:
        HTTPException: If user doesn't have the required permission
    """
    role = member.role

    permission_map = {
        "read": role.can_read,
        "write": role.can_write,
        "admin": role.can_admin,
        "invite": role.can_invite,
        "remove_members": role.can_remove_members,
    }

    if permission not in permission_map:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unknown permission: {permission}"
        )

    if not permission_map[permission]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: You don't have {permission} permission in this workspace"
        )

    return member


# Convenience dependency functions for common permissions
async def require_workspace_read(
    member: WorkspaceMember = Depends(require_workspace_member)
) -> WorkspaceMember:
    """Require workspace read permission."""
    return await require_workspace_permission("read", member)


async def require_workspace_write(
    member: WorkspaceMember = Depends(require_workspace_member)
) -> WorkspaceMember:
    """Require workspace write permission."""
    return await require_workspace_permission("write", member)


async def require_workspace_admin(
    member: WorkspaceMember = Depends(require_workspace_member)
) -> WorkspaceMember:
    """Require workspace admin permission."""
    return await require_workspace_permission("admin", member)


async def require_workspace_invite(
    member: WorkspaceMember = Depends(require_workspace_member)
) -> WorkspaceMember:
    """Require workspace invite permission."""
    return await require_workspace_permission("invite", member)


async def require_workspace_remove_members_permission(
    member: WorkspaceMember = Depends(require_workspace_member)
) -> WorkspaceMember:
    """Require workspace remove members permission."""
    return await require_workspace_permission("remove_members", member)


async def get_workspace_by_id(
    workspace_id: UUID,
    db: AsyncSession = Depends(get_db_session)
) -> Workspace:
    """
    Get workspace by ID.

    Args:
        workspace_id: Workspace ID
        db: Database session

    Returns:
        Workspace object

    Raises:
        HTTPException: If workspace not found
    """
    result = await db.execute(
        select(Workspace).where(Workspace.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )

    return workspace


async def check_workspace_access(
    workspace: Workspace,
    current_user: User,
    db: AsyncSession,
    required_permission: str = "read"
) -> bool:
    """
    Check if user has access to workspace.

    Args:
        workspace: Workspace to check
        current_user: User to check access for
        db: Database session
        required_permission: Required permission level

    Returns:
        True if user has access, False otherwise
    """
    # Owner always has access
    if workspace.owner_id == current_user.id:
        return True

    # Check if user is a member with required permission
    result = await db.execute(
        select(WorkspaceMember)
        .options(selectinload(WorkspaceMember.role))
        .where(
            WorkspaceMember.workspace_id == workspace.id,
            WorkspaceMember.user_id == current_user.id,
            WorkspaceMember.is_active == True
        )
    )
    member = result.scalar_one_or_none()

    if not member:
        return False

    # Check permission
    role = member.role
    permission_map = {
        "read": role.can_read,
        "write": role.can_write,
        "admin": role.can_admin,
        "invite": role.can_invite,
        "remove_members": role.can_remove_members,
    }

    return permission_map.get(required_permission, False)
