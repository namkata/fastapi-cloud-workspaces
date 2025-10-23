"""
Workspace models.

This module defines the database models for workspace management.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from app.core.models import BaseModel
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


class WorkspaceStatus(str, Enum):
    """Workspace status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"


class WorkspaceRoleEnum(str, Enum):
    """Workspace role enumeration."""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class Workspace(BaseModel):
    """Workspace model for multi-tenant workspace management."""

    __tablename__ = "workspaces"

    # Basic workspace information
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Workspace name"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Workspace description"
    )

    # Owner relationship
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID of the workspace owner"
    )

    # Workspace status
    status: Mapped[WorkspaceStatus] = mapped_column(
        String(20),
        default=WorkspaceStatus.ACTIVE,
        nullable=False,
        comment="Workspace status"
    )

    # Settings
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether workspace is publicly accessible"
    )

    max_members: Mapped[Optional[int]] = mapped_column(
        nullable=True,
        comment="Maximum number of members allowed"
    )

    # Metadata
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to workspace avatar image"
    )

    # Relationships
    owner = relationship("User", back_populates="owned_workspaces")
    members = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    files = relationship("StorageFile", back_populates="workspace", cascade="all, delete-orphan")
    storage_quota = relationship("StorageQuota", back_populates="workspace", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """String representation of the Workspace model."""
        return f"<Workspace(id={self.id}, name='{self.name}', owner_id={self.owner_id})>"


class WorkspaceRole(BaseModel):
    """Workspace role model for defining permissions."""

    __tablename__ = "workspace_roles"

    # Role information
    name: Mapped[WorkspaceRoleEnum] = mapped_column(
        String(20),
        nullable=False,
        comment="Role name"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Role description"
    )

    # Permissions stored as JSON to match database schema
    permissions: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Role permissions as JSON"
    )

    # System role flag
    is_system_role: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether this is a system-wide role"
    )

    # Workspace relationship (for workspace-specific roles)
    workspace_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        comment="ID of the workspace (null for system roles)"
    )

    # Relationships
    members = relationship("WorkspaceMember", back_populates="role")
    workspace = relationship("Workspace", foreign_keys=[workspace_id])

    # Constraints
    __table_args__ = (
        UniqueConstraint('name', 'workspace_id', name='uq_workspace_role_name_workspace'),
    )

    # Properties for backward compatibility with individual permission fields
    @property
    def can_read(self) -> bool:
        """Can read workspace content."""
        return self.permissions.get("can_read", False) if self.permissions else False

    @property
    def can_write(self) -> bool:
        """Can write/edit workspace content."""
        return self.permissions.get("can_write", False) if self.permissions else False

    @property
    def can_admin(self) -> bool:
        """Can perform admin actions."""
        return self.permissions.get("can_admin", False) if self.permissions else False

    @property
    def can_invite(self) -> bool:
        """Can invite new members."""
        return self.permissions.get("can_invite", False) if self.permissions else False

    @property
    def can_remove_members(self) -> bool:
        """Can remove members."""
        return self.permissions.get("can_remove_members", False) if self.permissions else False

    @property
    def display_name(self) -> str:
        """Human-readable role name."""
        return self.name.title()

    def __repr__(self) -> str:
        """String representation of the WorkspaceRole model."""
        return f"<WorkspaceRole(id={self.id}, name='{self.name}', system={self.is_system_role})>"


class WorkspaceMember(BaseModel):
    """Workspace member model for many-to-many relationship between users and workspaces."""

    __tablename__ = "workspace_members"

    # Foreign keys
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID of the workspace"
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID of the user"
    )

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspace_roles.id", ondelete="RESTRICT"),
        nullable=False,
        comment="ID of the workspace role"
    )

    # Member status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether membership is active"
    )

    # Invitation tracking
    invited_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of the user who sent the invitation"
    )

    invited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the invitation was sent"
    )

    joined_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the user joined the workspace"
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("User", foreign_keys=[user_id], back_populates="workspace_memberships")
    role = relationship("WorkspaceRole", back_populates="members")
    inviter = relationship("User", foreign_keys=[invited_by])

    # Constraints
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_member'),
    )

    def __repr__(self) -> str:
        """String representation of the WorkspaceMember model."""
        return f"<WorkspaceMember(workspace_id={self.workspace_id}, user_id={self.user_id}, role_id={self.role_id})>"


# Add relationships to User model (this would typically be done via a relationship update)
# Note: This requires updating the User model to include these relationships:
# owned_workspaces = relationship("Workspace", back_populates="owner")
# workspace_memberships = relationship("WorkspaceMember", foreign_keys="WorkspaceMember.user_id", back_populates="user")
