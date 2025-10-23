"""
Workspace schemas.

This module defines Pydantic models for workspace requests and responses.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from app.core.validators import CommonValidators
from pydantic import BaseModel, Field, validator

from .models import WorkspaceRoleEnum, WorkspaceStatus


class WorkspaceBase(BaseModel):
    """Base workspace schema with common fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    description: Optional[str] = Field(None, max_length=1000, description="Workspace description")
    is_public: bool = Field(default=False, description="Whether workspace is publicly accessible")
    max_members: Optional[int] = Field(None, ge=1, le=1000, description="Maximum number of members")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")

    @validator('name')
    def validate_name(cls, v):
        """Validate workspace name."""
        return CommonValidators.validate_workspace_name(v)


class WorkspaceCreate(WorkspaceBase):
    """Schema for workspace creation."""

    # Inherits all fields from WorkspaceBase
    pass


class WorkspaceUpdate(BaseModel):
    """Schema for workspace updates."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="New workspace name")
    description: Optional[str] = Field(None, max_length=1000, description="New workspace description")
    is_public: Optional[bool] = Field(None, description="Whether workspace is publicly accessible")
    max_members: Optional[int] = Field(None, ge=1, le=1000, description="Maximum number of members")
    avatar_url: Optional[str] = Field(None, description="New avatar image URL")
    status: Optional[WorkspaceStatus] = Field(None, description="Workspace status")

    @validator('name')
    def validate_name(cls, v):
        """Validate workspace name."""
        if v is not None:
            return CommonValidators.validate_workspace_name(v)
        return v


class WorkspaceResponse(WorkspaceBase):
    """Schema for workspace response."""

    id: UUID = Field(..., description="Workspace ID")
    owner_id: UUID = Field(..., description="Owner user ID")
    status: WorkspaceStatus = Field(..., description="Workspace status")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class WorkspaceListResponse(BaseModel):
    """Schema for workspace list response."""

    workspaces: List[WorkspaceResponse] = Field(..., description="List of workspaces")
    total: int = Field(..., description="Total number of workspaces")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")


class WorkspaceRoleResponse(BaseModel):
    """Schema for workspace role response."""

    id: UUID = Field(..., description="Role ID")
    name: WorkspaceRoleEnum = Field(..., description="Role name")
    display_name: str = Field(..., description="Human-readable role name")
    description: Optional[str] = Field(None, description="Role description")
    can_read: bool = Field(..., description="Can read workspace content")
    can_write: bool = Field(..., description="Can write/edit workspace content")
    can_admin: bool = Field(..., description="Can perform admin actions")
    can_invite: bool = Field(..., description="Can invite new members")
    can_remove_members: bool = Field(..., description="Can remove members")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class WorkspaceMemberResponse(BaseModel):
    """Schema for workspace member response."""

    id: UUID = Field(..., description="Membership ID")
    workspace_id: UUID = Field(..., description="Workspace ID")
    user_id: UUID = Field(..., description="User ID")
    role_id: UUID = Field(..., description="Role ID")
    is_active: bool = Field(..., description="Whether membership is active")
    invited_by: Optional[UUID] = Field(None, description="ID of user who sent invitation")
    invited_at: Optional[datetime] = Field(None, description="Invitation timestamp")
    joined_at: Optional[datetime] = Field(None, description="Join timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Nested objects
    role: Optional[WorkspaceRoleResponse] = Field(None, description="Role details")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class WorkspaceMemberCreate(BaseModel):
    """Schema for adding a member to workspace."""

    user_id: UUID = Field(..., description="User ID to add")
    role_name: WorkspaceRoleEnum = Field(..., description="Role to assign")


class WorkspaceMemberUpdate(BaseModel):
    """Schema for updating workspace member."""

    role_name: Optional[WorkspaceRoleEnum] = Field(None, description="New role to assign")
    is_active: Optional[bool] = Field(None, description="Whether membership is active")


class WorkspaceInviteCreate(BaseModel):
    """Schema for workspace invitation."""

    email: str = Field(..., description="Email address to invite")
    role_name: WorkspaceRoleEnum = Field(..., description="Role to assign")
    message: Optional[str] = Field(None, max_length=500, description="Optional invitation message")


class WorkspaceInviteResponse(BaseModel):
    """Schema for workspace invitation response."""

    id: UUID = Field(..., description="Invitation ID")
    workspace_id: UUID = Field(..., description="Workspace ID")
    email: str = Field(..., description="Invited email address")
    role_name: WorkspaceRoleEnum = Field(..., description="Assigned role")
    invited_by: UUID = Field(..., description="ID of user who sent invitation")
    message: Optional[str] = Field(None, description="Invitation message")
    expires_at: datetime = Field(..., description="Invitation expiration")
    created_at: datetime = Field(..., description="Creation timestamp")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class WorkspaceDetailResponse(WorkspaceResponse):
    """Extended workspace response with member details."""

    members: List[WorkspaceMemberResponse] = Field(..., description="Workspace members")
    member_count: int = Field(..., description="Total number of members")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class WorkspaceStatsResponse(BaseModel):
    """Schema for workspace statistics."""

    total_workspaces: int = Field(..., description="Total number of workspaces")
    active_workspaces: int = Field(..., description="Number of active workspaces")
    archived_workspaces: int = Field(..., description="Number of archived workspaces")
    total_members: int = Field(..., description="Total number of workspace members")

    class Config:
        """Pydantic configuration."""
        from_attributes = True


class MessageResponse(BaseModel):
    """Schema for simple message responses."""

    message: str = Field(..., description="Response message")
    success: bool = Field(default=True, description="Whether operation was successful")
