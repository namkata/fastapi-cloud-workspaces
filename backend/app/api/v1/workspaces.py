"""
Workspace management API routes.
"""
from typing import List, Optional

from app.core.database import get_db_session
from app.core.logger import logger
from app.core.rbac import require_permission
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.workspace.schemas import (
    WorkspaceCreate,
    WorkspaceInviteCreate,
    WorkspaceListResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.modules.workspace.service import WorkspaceService
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.get("/", response_model=WorkspaceListResponse)
async def list_workspaces(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """List user's workspaces."""
    try:
        workspace_service = WorkspaceService(session)
        workspaces, total = await workspace_service.list_user_workspaces(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            search=search
        )

        logger.info(f"Listed {len(workspaces)} workspaces for user {current_user.email}")
        return WorkspaceListResponse(
            workspaces=[WorkspaceResponse.from_orm(ws) for ws in workspaces],
            total=total,
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error(f"Error listing workspaces: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspaces"
        )


@router.post("/", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Create a new workspace."""
    try:
        workspace_service = WorkspaceService(session)
        workspace = await workspace_service.create_workspace(
            name=workspace_data.name,
            description=workspace_data.description,
            owner_id=current_user.id
        )

        logger.info(f"Workspace created: {workspace.name} by {current_user.email}")
        return WorkspaceResponse.from_orm(workspace)

    except ValueError as e:
        logger.warning(f"Workspace creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Workspace creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workspace creation failed"
        )


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Get workspace by ID."""
    try:
        workspace_service = WorkspaceService(session)
        workspace = await workspace_service.get_workspace(workspace_id)

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        return WorkspaceResponse.from_orm(workspace)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workspace {workspace_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workspace"
        )


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: int,
    workspace_data: WorkspaceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Update workspace information."""
    try:
        workspace_service = WorkspaceService(session)
        workspace = await workspace_service.update_workspace(
            workspace_id,
            workspace_data.dict(exclude_unset=True)
        )

        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        logger.info(f"Workspace updated: {workspace.name}")
        return WorkspaceResponse.from_orm(workspace)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Workspace update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Workspace update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workspace update failed"
        )


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Delete workspace."""
    try:
        workspace_service = WorkspaceService(session)
        success = await workspace_service.delete_workspace(workspace_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found"
            )

        logger.info(f"Workspace deleted: {workspace_id}")
        return {"message": "Workspace deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Workspace deletion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Workspace deletion failed"
        )


@router.get("/{workspace_id}/members", response_model=List[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """List workspace members."""
    try:
        workspace_service = WorkspaceService(session)
        members = await workspace_service.list_workspace_members(workspace_id)

        logger.info(f"Listed {len(members)} members for workspace {workspace_id}")
        return [WorkspaceMemberResponse.from_orm(member) for member in members]

    except Exception as e:
        logger.error(f"Error listing workspace members: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list workspace members"
        )


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse)
async def invite_member(
    workspace_id: int,
    invite_data: WorkspaceInviteCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Invite user to workspace."""
    try:
        workspace_service = WorkspaceService(session)
        member = await workspace_service.invite_member(
            workspace_id=workspace_id,
            email=invite_data.email,
            role=invite_data.role,
            invited_by=current_user.id
        )

        logger.info(f"User invited to workspace: {invite_data.email} -> {workspace_id}")
        return WorkspaceMemberResponse.from_orm(member)

    except ValueError as e:
        logger.warning(f"Member invitation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Member invitation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Member invitation failed"
        )


@router.put("/{workspace_id}/members/{member_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    workspace_id: int,
    member_id: int,
    role_data: WorkspaceMemberUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Update workspace member role."""
    try:
        workspace_service = WorkspaceService(session)
        member = await workspace_service.update_member_role(
            workspace_id=workspace_id,
            member_id=member_id,
            role=role_data.role
        )

        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )

        logger.info(f"Member role updated: {member_id} -> {role_data.role}")
        return WorkspaceMemberResponse.from_orm(member)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Member update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Member update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Member update failed"
        )


@router.delete("/{workspace_id}/members/{member_id}")
async def remove_member(
    workspace_id: int,
    member_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Remove member from workspace."""
    try:
        workspace_service = WorkspaceService(session)
        success = await workspace_service.remove_member(workspace_id, member_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )

        logger.info(f"Member removed from workspace: {member_id}")
        return {"message": "Member removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Member removal error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Member removal failed"
        )


@router.post("/{workspace_id}/leave")
async def leave_workspace(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session)
):
    """Leave workspace."""
    try:
        workspace_service = WorkspaceService(session)
        success = await workspace_service.leave_workspace(workspace_id, current_user.id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot leave workspace or not a member"
            )

        logger.info(f"User left workspace: {current_user.email} -> {workspace_id}")
        return {"message": "Left workspace successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Leave workspace error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to leave workspace"
        )
