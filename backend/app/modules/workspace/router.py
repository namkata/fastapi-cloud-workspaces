"""
Workspace router.

This module provides API endpoints for workspace management.
"""
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from .dependencies import (
    get_workspace_context,
    require_workspace_admin,
    require_workspace_context,
    require_workspace_invite,
    require_workspace_member,
    require_workspace_read,
    require_workspace_remove_members_permission,
    require_workspace_write,
)
from .models import Workspace, WorkspaceRoleEnum, WorkspaceStatus
from .schemas import (
    MessageResponse,
    WorkspaceCreate,
    WorkspaceDetailResponse,
    WorkspaceListResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceStatsResponse,
    WorkspaceUpdate,
)
from .service import WorkspaceService

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new workspace",
    description="Create a new workspace. The creator becomes the owner and admin.",
)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new workspace."""
    service = WorkspaceService(db)

    try:
        workspace = await service.create_workspace(workspace_data, current_user)
        logger.info("Workspace created via API", workspace_id=workspace.id, user_id=current_user.id)
        return WorkspaceResponse.from_orm(workspace)
    except Exception as e:
        logger.error("Failed to create workspace", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workspace"
        )


@router.get(
    "/workspaces",
    response_model=WorkspaceListResponse,
    summary="List workspaces",
    description="List workspaces. Returns all workspaces for admin users, or user's own workspaces for regular users.",
)
async def list_workspaces(
    include_owned: bool = Query(True, description="Include owned workspaces"),
    include_member: bool = Query(True, description="Include workspaces where user is a member"),
    status_filter: Optional[WorkspaceStatus] = Query(None, description="Filter by workspace status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List workspaces for the current user."""
    service = WorkspaceService(db)

    try:
        workspaces = await service.get_user_workspaces(
            user=current_user,
            include_owned=include_owned,
            include_member=include_member,
            status_filter=status_filter,
            skip=skip,
            limit=limit
        )

        workspace_responses = [WorkspaceResponse.from_orm(ws) for ws in workspaces]

        logger.info(
            "Workspaces listed via API",
            user_id=current_user.id,
            count=len(workspace_responses)
        )

        return WorkspaceListResponse(
            workspaces=workspace_responses,
            total=len(workspace_responses),
            page=skip // limit + 1,  # Calculate page number from skip and limit
            size=limit
        )
    except Exception as e:
        logger.error("Failed to list workspaces", error=str(e), user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workspaces"
        )


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceDetailResponse,
    summary="Get workspace details",
    description="Get detailed information about a specific workspace including members.",
)
async def get_workspace_details(
    workspace_id: UUID,
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Get workspace details."""
    service = WorkspaceService(db)

    try:
        # Get workspace with members
        workspace_with_members = await service.get_workspace_with_members(workspace_id)
        if not workspace_with_members:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        # Get member count and stats
        member_count = await service.count_workspace_members(workspace_id)

        # Convert to response model
        workspace_response = WorkspaceResponse.from_orm(workspace_with_members)

        # Get member responses
        member_responses = []
        if workspace_with_members.members:
            for member in workspace_with_members.members:
                if member.is_active:
                    member_responses.append(WorkspaceMemberResponse.from_orm(member))

        stats = WorkspaceStatsResponse(
            total_members=member_count,
            active_members=len(member_responses),
            max_members=workspace_with_members.max_members
        )

        logger.info("Workspace details retrieved via API", workspace_id=workspace_id, user_id=current_user.id)

        return WorkspaceDetailResponse(
            workspace=workspace_response,
            members=member_responses,
            stats=stats
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get workspace details", error=str(e), workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workspace details"
        )


@router.put(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace",
    description="Update workspace information. Requires admin access.",
)
async def update_workspace(
    workspace_id: UUID,
    workspace_data: WorkspaceUpdate,
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Update workspace."""
    service = WorkspaceService(db)

    try:
        updated_workspace = await service.update_workspace(workspace, workspace_data)
        logger.info("Workspace updated via API", workspace_id=workspace_id, user_id=current_user.id)
        return WorkspaceResponse.from_orm(updated_workspace)
    except Exception as e:
        logger.error("Failed to update workspace", error=str(e), workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace"
        )


@router.delete(
    "/workspaces/{workspace_id}",
    response_model=MessageResponse,
    summary="Delete workspace",
    description="Archive/delete a workspace. Requires admin access.",
)
async def delete_workspace(
    workspace_id: UUID,
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete (archive) workspace."""
    service = WorkspaceService(db)

    try:
        await service.delete_workspace(workspace)
        logger.info("Workspace deleted via API", workspace_id=workspace_id, user_id=current_user.id)
        return MessageResponse(message="Workspace archived successfully")
    except Exception as e:
        logger.error("Failed to delete workspace", error=str(e), workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workspace"
        )


# Member management endpoints
@router.post(
    "/workspaces/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add workspace member",
    description="Add a new member to the workspace. Requires admin access.",
)
async def add_workspace_member(
    workspace_id: UUID,
    member_data: WorkspaceMemberCreate,
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(require_workspace_invite),
    db: AsyncSession = Depends(get_db_session),
):
    """Add member to workspace."""
    service = WorkspaceService(db)

    try:
        # Check if workspace can accept new members
        if not await service.can_add_members(workspace):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace has reached maximum member limit"
            )

        # Get the user to add
        from app.modules.auth.service import AuthService
        auth_service = AuthService(db)
        user_to_add = await auth_service.get_user_by_email(member_data.email)

        if not user_to_add:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        # Check if user is already a member
        existing_member = await service.get_workspace_member(workspace_id, user_to_add.id)
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this workspace"
            )

        # Get the role
        role = await service.get_role_by_name(member_data.role)
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role specified"
            )

        # Add member
        member = await service.add_member(workspace, user_to_add, role, current_user)

        logger.info(
            "Member added to workspace via API",
            workspace_id=workspace_id,
            new_member_id=user_to_add.id,
            added_by=current_user.id
        )

        return WorkspaceMemberResponse.from_orm(member)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to add workspace member", error=str(e), workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add workspace member"
        )


@router.get(
    "/workspaces/{workspace_id}/members",
    response_model=List[WorkspaceMemberResponse],
    summary="List workspace members",
    description="List all members of the workspace. Requires member access.",
)
async def list_workspace_members(
    workspace_id: UUID,
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(require_workspace_read),
    db: AsyncSession = Depends(get_db_session),
):
    """List workspace members."""
    service = WorkspaceService(db)

    try:
        workspace_with_members = await service.get_workspace_with_members(workspace_id)
        if not workspace_with_members:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        members = []
        if workspace_with_members.members:
            for member in workspace_with_members.members:
                if member.is_active:
                    members.append(WorkspaceMemberResponse.from_orm(member))

        logger.info("Workspace members listed via API", workspace_id=workspace_id, user_id=current_user.id)
        return members
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list workspace members", error=str(e), workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve workspace members"
        )


@router.put(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
    summary="Update workspace member",
    description="Update workspace member role. Requires admin access.",
)
async def update_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    member_data: WorkspaceMemberUpdate,
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Update workspace member."""
    service = WorkspaceService(db)

    try:
        # Get the member
        member = await service.get_workspace_member(workspace_id, user_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in workspace"
            )

        # Prevent changing owner role
        if workspace.owner_id == user_id and member_data.role != WorkspaceRoleEnum.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change workspace owner role"
            )

        # Get the new role
        new_role = await service.get_role_by_name(member_data.role)
        if not new_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role specified"
            )

        # Update member role
        updated_member = await service.update_member_role(member, new_role)

        logger.info(
            "Workspace member updated via API",
            workspace_id=workspace_id,
            member_id=user_id,
            updated_by=current_user.id
        )

        return WorkspaceMemberResponse.from_orm(updated_member)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update workspace member", error=str(e), workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workspace member"
        )


@router.delete(
    "/workspaces/{workspace_id}/members/{user_id}",
    response_model=MessageResponse,
    summary="Remove workspace member",
    description="Remove a member from the workspace. Requires admin access.",
)
async def remove_workspace_member(
    workspace_id: UUID,
    user_id: UUID,
    workspace: Workspace = Depends(require_workspace_context),
    current_user: User = Depends(require_workspace_remove_members_permission),
    db: AsyncSession = Depends(get_db_session),
):
    """Remove workspace member."""
    service = WorkspaceService(db)

    try:
        # Get the member
        member = await service.get_workspace_member(workspace_id, user_id)
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in workspace"
            )

        # Prevent removing workspace owner
        if workspace.owner_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove workspace owner"
            )

        # Remove member
        await service.remove_member(member)

        logger.info(
            "Workspace member removed via API",
            workspace_id=workspace_id,
            removed_member_id=user_id,
            removed_by=current_user.id
        )

        return MessageResponse(message="Member removed successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to remove workspace member", error=str(e), workspace_id=workspace_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to remove workspace member"
        )
