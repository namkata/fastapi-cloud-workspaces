"""
Storage module schemas.

Pydantic models for storage-related data transfer objects.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from app.core.validators import CommonValidators
from pydantic import BaseModel, Field, validator


class FileMetadata(BaseModel):
    """File metadata information."""

    file_key: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(..., description="Upload timestamp")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")
    metadata: Optional[Dict[str, str]] = Field(None, description="Custom metadata")
    workspace_id: UUID = Field(..., description="Associated workspace ID")

    class Config:
        from_attributes = True


class UploadResult(BaseModel):
    """Result of file upload operation."""

    file_key: str = Field(..., description="Unique file identifier")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")
    url: Optional[str] = Field(None, description="Direct access URL if available")

    class Config:
        from_attributes = True


class SignedUrlResult(BaseModel):
    """Result of signed URL generation."""

    url: str = Field(..., description="Signed URL")
    expires_at: datetime = Field(..., description="URL expiration timestamp")
    operation: str = Field(..., description="Allowed HTTP operation")

    class Config:
        from_attributes = True


class FileUploadRequest(BaseModel):
    """File upload request schema."""

    filename: str = Field(..., description="Original filename")
    content_type: Optional[str] = Field(None, description="MIME type")
    metadata: Optional[Dict[str, str]] = Field(None, description="Custom metadata")

    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename format."""
        return CommonValidators.validate_filename(v)


class FileListRequest(BaseModel):
    """File listing request schema."""

    prefix: Optional[str] = Field(None, description="Filter by prefix")
    limit: int = Field(100, ge=1, le=1000, description="Maximum files to return")
    offset: int = Field(0, ge=0, description="Number of files to skip")


class FileListResponse(BaseModel):
    """File listing response schema."""

    files: List[FileMetadata] = Field(..., description="List of files")
    total: int = Field(..., description="Total number of files")
    limit: int = Field(..., description="Applied limit")
    offset: int = Field(..., description="Applied offset")
    has_more: bool = Field(..., description="Whether more files are available")


class FileResponse(BaseModel):
    """Single file response schema."""

    id: UUID = Field(..., description="Database record ID")
    file_key: str = Field(..., description="Storage file key")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")
    workspace_id: UUID = Field(..., description="Associated workspace ID")
    uploaded_by: UUID = Field(..., description="User who uploaded the file")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Optional[Dict[str, str]] = Field(None, description="Custom metadata")

    class Config:
        from_attributes = True


class SignedUrlRequest(BaseModel):
    """Signed URL generation request."""

    file_key: str = Field(..., description="File identifier")
    operation: str = Field("GET", description="HTTP operation")
    expiration_hours: int = Field(1, ge=1, le=24, description="URL expiration in hours")

    @validator('operation')
    def validate_operation(cls, v):
        allowed_operations = ['GET', 'PUT', 'DELETE']
        if v.upper() not in allowed_operations:
            raise ValueError(f"Operation must be one of: {allowed_operations}")
        return v.upper()


class StorageStatsResponse(BaseModel):
    """Storage statistics response."""

    total_files: int = Field(..., description="Total number of files")
    total_size: int = Field(..., description="Total size in bytes")
    workspace_id: UUID = Field(..., description="Workspace ID")

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Response with a message."""

    message: str = Field(..., description="Response message")

    class Config:
        from_attributes = True


class FileRecordResponse(BaseModel):
    """File record response schema."""

    id: UUID = Field(..., description="Database record ID")
    file_key: str = Field(..., description="Storage file key")
    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size: int = Field(..., description="File size in bytes")
    workspace_id: UUID = Field(..., description="Associated workspace ID")
    uploaded_by: UUID = Field(..., description="User who uploaded the file")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Optional[Dict[str, str]] = Field(None, description="Custom metadata")

    class Config:
        from_attributes = True


class FolderResponse(BaseModel):
    """Folder response schema."""

    id: UUID = Field(..., description="Folder ID")
    name: str = Field(..., description="Folder name")
    parent_id: Optional[UUID] = Field(None, description="Parent folder ID")
    workspace_id: UUID = Field(..., description="Associated workspace ID")
    created_by: UUID = Field(..., description="User who created the folder")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class FolderCreateRequest(BaseModel):
    """Folder creation request schema."""

    name: str = Field(..., min_length=1, max_length=255, description="Folder name")
    parent_id: Optional[UUID] = Field(None, description="Parent folder ID")

    @validator('name')
    def validate_name(cls, v):
        """Validate folder name."""
        return CommonValidators.validate_workspace_name(v)


class FolderUpdateRequest(BaseModel):
    """Folder update request schema."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="New folder name")
    parent_id: Optional[UUID] = Field(None, description="New parent folder ID")

    @validator('name')
    def validate_name(cls, v):
        """Validate folder name."""
        if v is not None:
            return CommonValidators.validate_workspace_name(v)
        return v
