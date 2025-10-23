"""
Workspace service.

This module provides business logic for workspace management.
"""
from typing import List, Optional
from uuid import UUID

from app.modules.auth.models import User
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from structlog import get_logger

from .models import (
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    WorkspaceRoleEnum,
    WorkspaceStatus,
)
from .schemas import WorkspaceCreate, WorkspaceUpdate

logger = get_logger(__name__)


class WorkspaceService:
    """Service class for workspace operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_workspace(self, workspace_data: WorkspaceCreate, owner: User) -> Workspace:
        """
        Create a new workspace.

        Args:
            workspace_data: Workspace creation data
            owner: Owner user

        Returns:
            Created workspace
        """
        workspace = Workspace(
            name=workspace_data.name,
            description=workspace_data.description,
            owner_id=owner.id,
            is_public=workspace_data.is_public,
            max_members=workspace_data.max_members,
            avatar_url=workspace_data.avatar_url,
            status=WorkspaceStatus.ACTIVE
        )

        self.db.add(workspace)
        await self.db.flush()  # Get the workspace ID

        # Add owner as admin member
        admin_role = await self.get_role_by_name(WorkspaceRoleEnum.ADMIN)
        if admin_role:
            owner_member = WorkspaceMember(
                workspace_id=workspace.id,
                user_id=owner.id,
                role_id=admin_role.id,
                is_active=True,
                joined_at=workspace.created_at
            )
            self.db.add(owner_member)

        await self.db.commit()
        await self.db.refresh(workspace)

        logger.info("Workspace created", workspace_id=workspace.id, owner_id=owner.id)
        return workspace

    async def get_workspace_by_id(self, workspace_id: UUID) -> Optional[Workspace]:
        """
        Get workspace by ID.

        Args:
            workspace_id: Workspace ID

        Returns:
            Workspace if found, None otherwise
        """
        result = await self.db.execute(
            select(Workspace).where(Workspace.id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_workspace_with_members(self, workspace_id: UUID) -> Optional[Workspace]:
        """
        Get workspace with member details.

        Args:
            workspace_id: Workspace ID

        Returns:
            Workspace with members if found, None otherwise
        """
        result = await self.db.execute(
            select(Workspace)
            .options(
                selectinload(Workspace.members).selectinload(WorkspaceMember.role),
                selectinload(Workspace.members).selectinload(WorkspaceMember.user)
            )
            .where(Workspace.id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def get_user_workspaces(
        self,
        user: User,
        include_owned: bool = True,
        include_member: bool = True,
        status_filter: Optional[WorkspaceStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Workspace]:
        """
        Get workspaces for a user.

        Args:
            user: User to get workspaces for
            include_owned: Include owned workspaces
            include_member: Include workspaces where user is a member
            status_filter: Filter by workspace status
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of workspaces
        """
        conditions = []

        if include_owned and include_member:
            # User is owner OR member
            conditions.append(
                or_(
                    Workspace.owner_id == user.id,
                    and_(
                        WorkspaceMember.user_id == user.id,
                        WorkspaceMember.is_active == True
                    )
                )
            )
        elif include_owned:
            conditions.append(Workspace.owner_id == user.id)
        elif include_member:
            conditions.append(
                and_(
                    WorkspaceMember.user_id == user.id,
                    WorkspaceMember.is_active == True
                )
            )

        if status_filter:
            conditions.append(Workspace.status == status_filter)

        query = select(Workspace).distinct()

        if include_member:
            query = query.outerjoin(WorkspaceMember)

        if conditions:
            query = query.where(and_(*conditions))

        query = query.offset(skip).limit(limit).order_by(Workspace.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_workspace(
        self,
        workspace: Workspace,
        workspace_data: WorkspaceUpdate
    ) -> Workspace:
        """
        Update workspace.

        Args:
            workspace: Workspace to update
            workspace_data: Update data

        Returns:
            Updated workspace
        """
        update_data = workspace_data.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(workspace, field, value)

        await self.db.commit()
        await self.db.refresh(workspace)

        logger.info("Workspace updated", workspace_id=workspace.id)
        return workspace

    async def delete_workspace(self, workspace: Workspace) -> None:
        """
        Delete (archive) workspace.

        Args:
            workspace: Workspace to delete
        """
        workspace.status = WorkspaceStatus.ARCHIVED
        await self.db.commit()

        logger.info("Workspace archived", workspace_id=workspace.id)

    async def add_member(
        self,
        workspace: Workspace,
        user: User,
        role: WorkspaceRole,
        invited_by: Optional[User] = None
    ) -> WorkspaceMember:
        """
        Add member to workspace.

        Args:
            workspace: Workspace to add member to
            user: User to add
            role: Role to assign
            invited_by: User who invited (optional)

        Returns:
            Created workspace member
        """
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=user.id,
            role_id=role.id,
            is_active=True,
            invited_by=invited_by.id if invited_by else None,
            joined_at=func.now()
        )

        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)

        logger.info(
            "Member added to workspace",
            workspace_id=workspace.id,
            user_id=user.id,
            role=role.name
        )
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        """
        Remove member from workspace.

        Args:
            member: Member to remove
        """
        await self.db.delete(member)
        await self.db.commit()

        logger.info(
            "Member removed from workspace",
            workspace_id=member.workspace_id,
            user_id=member.user_id
        )

    async def update_member_role(
        self,
        member: WorkspaceMember,
        new_role: WorkspaceRole
    ) -> WorkspaceMember:
        """
        Update member role.

        Args:
            member: Member to update
            new_role: New role to assign

        Returns:
            Updated member
        """
        old_role_name = member.role.name if member.role else "unknown"
        member.role_id = new_role.id

        await self.db.commit()
        await self.db.refresh(member)

        logger.info(
            "Member role updated",
            workspace_id=member.workspace_id,
            user_id=member.user_id,
            old_role=old_role_name,
            new_role=new_role.name
        )
        return member

    async def get_role_by_name(self, role_name: WorkspaceRoleEnum, workspace_id: Optional[UUID] = None) -> Optional[WorkspaceRole]:
        """
        Get workspace role by name.

        Args:
            role_name: Role name
            workspace_id: Optional workspace ID for workspace-specific roles

        Returns:
            WorkspaceRole if found, None otherwise
        """
        query = select(WorkspaceRole).where(WorkspaceRole.name == role_name)

        # For now, prioritize system roles (is_system_role = True)
        # In the future, this could be extended to support workspace-specific roles
        query = query.where(WorkspaceRole.is_system_role == True)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_workspace_member(
        self,
        workspace_id: UUID,
        user_id: UUID
    ) -> Optional[WorkspaceMember]:
        """
        Get workspace member.

        Args:
            workspace_id: Workspace ID
            user_id: User ID

        Returns:
            WorkspaceMember if found, None otherwise
        """
        result = await self.db.execute(
            select(WorkspaceMember)
            .options(selectinload(WorkspaceMember.role))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.is_active == True
            )
        )
        return result.scalar_one_or_none()

    async def count_workspace_members(self, workspace_id: UUID) -> int:
        """
        Count active members in workspace.

        Args:
            workspace_id: Workspace ID

        Returns:
            Number of active members
        """
        result = await self.db.execute(
            select(func.count(WorkspaceMember.id))
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.is_active == True
            )
        )
        return result.scalar() or 0

    async def is_workspace_owner(self, workspace: Workspace, user: User) -> bool:
        """
        Check if user is workspace owner.

        Args:
            workspace: Workspace to check
            user: User to check

        Returns:
            True if user is owner, False otherwise
        """
        return workspace.owner_id == user.id

    async def can_add_members(self, workspace: Workspace) -> bool:
        """
        Check if workspace can accept new members.

        Args:
            workspace: Workspace to check

        Returns:
            True if can add members, False otherwise
        """
        if not workspace.max_members:
            return True

        current_count = await self.count_workspace_members(workspace.id)
        return current_count < workspace.max_members
