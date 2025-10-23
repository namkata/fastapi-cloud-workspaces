"""
Storage models.

This module defines the database models for file storage management.
"""
from datetime import UTC, datetime
from enum import Enum
from typing import Dict, Optional
from uuid import UUID

from app.core.models import BaseModel
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


class FileStatus(str, Enum):
    """File status enumeration."""
    UPLOADING = "uploading"
    ACTIVE = "active"
    DELETED = "deleted"
    ARCHIVED = "archived"


class StorageProvider(str, Enum):
    """Storage provider enumeration."""
    MINIO = "minio"
    S3 = "s3"
    LOCAL = "local"


class StorageFile(BaseModel):
    """Storage file model for tracking uploaded files."""

    __tablename__ = "storage_files"

    # File identification
    file_key: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
        comment="Unique file key in storage backend"
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original filename as uploaded by user"
    )

    # File metadata
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME type of the file"
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes"
    )

    # File status and provider
    status: Mapped[FileStatus] = mapped_column(
        String(20),
        nullable=False,
        default=FileStatus.ACTIVE,
        comment="Current status of the file"
    )

    storage_provider: Mapped[StorageProvider] = mapped_column(
        String(20),
        nullable=False,
        comment="Storage provider used for this file"
    )

    # Workspace relationship
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID of the workspace this file belongs to"
    )

    # User relationship
    uploaded_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of the user who uploaded the file"
    )

    # Additional metadata
    file_metadata: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional file metadata as JSON"
    )

    # File organization
    folder_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Virtual folder path for file organization"
    )

    tags: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="File tags for categorization"
    )

    # Access control
    is_public: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether the file is publicly accessible"
    )

    # Expiration
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the file expires and should be deleted"
    )

    # Soft delete
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the file was soft deleted"
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="files")
    uploader = relationship("User", foreign_keys=[uploaded_by])

    def __repr__(self) -> str:
        """String representation of the StorageFile model."""
        return f"<StorageFile(id={self.id}, file_key={self.file_key}, workspace_id={self.workspace_id})>"

    @property
    def is_deleted(self) -> bool:
        """Check if the file is soft deleted."""
        return self.deleted_at is not None or self.status == FileStatus.DELETED

    @property
    def is_expired(self) -> bool:
        """Check if the file has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def soft_delete(self) -> None:
        """Soft delete the file."""
        self.deleted_at = datetime.now(UTC)
        self.status = FileStatus.DELETED


class StorageQuota(BaseModel):
    """Storage quota model for workspace storage limits."""

    __tablename__ = "storage_quotas"

    # Workspace relationship
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="ID of the workspace"
    )

    # Quota limits
    max_storage_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum storage in bytes (null for unlimited)"
    )

    max_files: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum number of files (null for unlimited)"
    )

    max_file_size_bytes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum individual file size in bytes (null for unlimited)"
    )

    # Current usage (updated by triggers or background jobs)
    used_storage_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Currently used storage in bytes"
    )

    used_files: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Currently used number of files"
    )

    # Quota settings
    enforce_quota: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Whether to enforce quota limits"
    )

    # Relationships
    workspace = relationship("Workspace", back_populates="storage_quota")

    def __repr__(self) -> str:
        """String representation of the StorageQuota model."""
        return f"<StorageQuota(workspace_id={self.workspace_id}, used={self.used_storage_bytes}/{self.max_storage_bytes})>"

    @property
    def storage_usage_percentage(self) -> Optional[float]:
        """Calculate storage usage percentage."""
        if self.max_storage_bytes is None or self.max_storage_bytes == 0:
            return None
        return (self.used_storage_bytes / self.max_storage_bytes) * 100

    @property
    def files_usage_percentage(self) -> Optional[float]:
        """Calculate files usage percentage."""
        if self.max_files is None or self.max_files == 0:
            return None
        return (self.used_files / self.max_files) * 100

    def can_upload_file(self, file_size: int) -> tuple[bool, str]:
        """
        Check if a file can be uploaded within quota limits.

        Args:
            file_size: Size of the file to upload in bytes

        Returns:
            Tuple of (can_upload, reason)
        """
        if not self.enforce_quota:
            return True, "Quota enforcement disabled"

        # Check file size limit
        if self.max_file_size_bytes and file_size > self.max_file_size_bytes:
            return False, f"File size exceeds limit of {self.max_file_size_bytes} bytes"

        # Check storage limit
        if self.max_storage_bytes and (self.used_storage_bytes + file_size) > self.max_storage_bytes:
            return False, f"Storage quota exceeded. Available: {self.max_storage_bytes - self.used_storage_bytes} bytes"

        # Check file count limit
        if self.max_files and self.used_files >= self.max_files:
            return False, f"File count limit of {self.max_files} reached"

        return True, "Upload allowed"


class StorageAccessLog(BaseModel):
    """Storage access log model for tracking file access."""

    __tablename__ = "storage_access_logs"

    # File relationship
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("storage_files.id", ondelete="CASCADE"),
        nullable=False,
        comment="ID of the accessed file"
    )

    # User relationship
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of the user who accessed the file"
    )

    # Access details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Action performed (download, view, delete, etc.)"
    )

    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
        comment="IP address of the accessor"
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="User agent string"
    )

    # Additional context
    access_metadata: Mapped[Optional[Dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional access metadata"
    )

    # Relationships
    file = relationship("StorageFile")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        """String representation of the StorageAccessLog model."""
        return f"<StorageAccessLog(file_id={self.file_id}, action={self.action}, user_id={self.user_id})>"
