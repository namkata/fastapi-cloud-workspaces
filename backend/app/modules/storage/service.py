"""
Storage service layer.

This module provides high-level storage operations with workspace context,
database integration, and business logic.
"""

import asyncio
from datetime import datetime, timedelta
from typing import BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID

from app.core.config import get_settings
from app.modules.storage.drivers import (
    BaseStorageDriver,
    MinIOStorageDriver,
    S3StorageDriver,
)
from app.modules.storage.models import (
    FileStatus,
    StorageAccessLog,
    StorageFile,
    StorageProvider,
    StorageQuota,
)
from app.modules.storage.schemas import (
    FileListResponse,
    FileMetadata,
    FileResponse,
    SignedUrlResult,
    StorageStatsResponse,
    UploadResult,
)
from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

logger = get_logger(__name__)
settings = get_settings()


class StorageService:
    """High-level storage service with workspace context."""

    def __init__(self, db_session: AsyncSession, workspace_id: UUID):
        """
        Initialize storage service.

        Args:
            db_session: Database session
            workspace_id: Workspace UUID for context
        """
        self.db = db_session
        self.workspace_id = workspace_id
        self._driver: Optional[BaseStorageDriver] = None

    async def get_driver(self) -> BaseStorageDriver:
        """Get the appropriate storage driver for the workspace."""
        if self._driver is None:
            # Get storage provider from settings
            provider = settings.storage_provider.lower()

            if provider == 'minio':
                self._driver = MinIOStorageDriver(
                    workspace_id=self.workspace_id,
                    endpoint=settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    secure=settings.minio_secure,
                    region=settings.minio_region
                )
            elif provider == 's3':
                self._driver = S3StorageDriver(
                    workspace_id=self.workspace_id,
                    bucket_name=settings.s3_bucket_name,
                    aws_access_key_id=settings.aws_access_key_id,
                    aws_secret_access_key=settings.aws_secret_access_key,
                    region_name=settings.aws_region,
                    endpoint_url=settings.s3_endpoint_url
                )
            else:
                raise ValueError(f"Unsupported storage provider: {provider}")

        return self._driver

    async def get_or_create_quota(self) -> StorageQuota:
        """Get or create storage quota for the workspace."""
        # Check if quota exists
        result = await self.db.execute(
            select(StorageQuota).where(StorageQuota.workspace_id == self.workspace_id)
        )
        quota = result.scalar_one_or_none()

        if quota is None:
            # Create default quota
            quota = StorageQuota(
                workspace_id=self.workspace_id,
                max_storage_bytes=getattr(settings, 'default_storage_quota_bytes', 1024 * 1024 * 1024),  # 1GB
                max_files=getattr(settings, 'default_max_files', 1000),
                max_file_size_bytes=getattr(settings, 'default_max_file_size_bytes', 100 * 1024 * 1024),  # 100MB
                enforce_quota=True
            )
            self.db.add(quota)
            await self.db.commit()
            await self.db.refresh(quota)

        return quota

    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        user_id: UUID,
        folder_path: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[Dict] = None,
        is_public: bool = False,
        expires_at: Optional[datetime] = None
    ) -> FileResponse:
        """
        Upload a file to storage.

        Args:
            file_data: File binary data
            filename: Original filename
            content_type: MIME type
            user_id: ID of the uploading user
            folder_path: Virtual folder path
            metadata: Additional metadata
            tags: File tags
            is_public: Whether file is publicly accessible
            expires_at: File expiration time

        Returns:
            FileResponse with upload details
        """
        # Get file size
        file_data.seek(0, 2)  # Seek to end
        file_size = file_data.tell()
        file_data.seek(0)  # Reset to beginning

        # Check quota
        quota = await self.get_or_create_quota()
        can_upload, reason = quota.can_upload_file(file_size)
        if not can_upload:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=reason
            )

        # Upload to storage backend
        driver = await self.get_driver()
        upload_result = await driver.upload_file(
            file_data=file_data,
            filename=filename,
            content_type=content_type,
            metadata=metadata
        )

        # Create database record
        storage_file = StorageFile(
            file_key=upload_result.file_key,
            original_filename=filename,
            content_type=content_type,
            file_size=file_size,
            status=FileStatus.ACTIVE,
            storage_provider=StorageProvider.MINIO if isinstance(driver, MinIOStorageDriver) else StorageProvider.S3,
            workspace_id=self.workspace_id,
            uploaded_by=user_id,
            metadata=metadata,
            folder_path=folder_path,
            tags=tags,
            is_public=is_public,
            expires_at=expires_at
        )

        self.db.add(storage_file)

        # Update quota usage
        quota.used_storage_bytes += file_size
        quota.used_files += 1

        await self.db.commit()
        await self.db.refresh(storage_file)

        # Log access
        await self._log_access(storage_file.id, user_id, "upload")

        logger.info(
            "File uploaded successfully",
            file_id=storage_file.id,
            filename=filename,
            size=file_size,
            workspace_id=self.workspace_id,
            user_id=user_id
        )

        return FileResponse(
            id=storage_file.id,
            file_key=storage_file.file_key,
            filename=storage_file.original_filename,
            content_type=storage_file.content_type,
            size=storage_file.file_size,
            workspace_id=storage_file.workspace_id,
            uploaded_by=storage_file.uploaded_by,
            created_at=storage_file.created_at,
            updated_at=storage_file.updated_at,
            metadata=storage_file.metadata
        )

    async def download_file(self, file_id: UUID, user_id: UUID) -> Tuple[BinaryIO, FileMetadata]:
        """
        Download a file from storage.

        Args:
            file_id: File ID
            user_id: ID of the downloading user

        Returns:
            Tuple of (file_data, metadata)
        """
        # Get file record
        storage_file = await self._get_file_or_404(file_id)

        # Check if file is deleted or expired
        if storage_file.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or has been deleted"
            )

        if storage_file.is_expired:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="File has expired"
            )

        # Download from storage backend
        driver = await self.get_driver()
        file_data, metadata = await driver.download_file(storage_file.file_key)

        # Log access
        await self._log_access(file_id, user_id, "download")

        logger.info(
            "File downloaded",
            file_id=file_id,
            filename=storage_file.original_filename,
            user_id=user_id
        )

        return file_data, metadata

    async def delete_file(self, file_id: UUID, user_id: UUID, hard_delete: bool = False) -> bool:
        """
        Delete a file from storage.

        Args:
            file_id: File ID
            user_id: ID of the deleting user
            hard_delete: Whether to permanently delete from storage backend

        Returns:
            True if successful
        """
        # Get file record
        storage_file = await self._get_file_or_404(file_id)

        if hard_delete:
            # Delete from storage backend
            driver = await self.get_driver()
            await driver.delete_file(storage_file.file_key)

            # Update quota
            quota = await self.get_or_create_quota()
            quota.used_storage_bytes -= storage_file.file_size
            quota.used_files -= 1

            # Delete database record
            await self.db.delete(storage_file)
        else:
            # Soft delete
            storage_file.soft_delete()

        await self.db.commit()

        # Log access
        await self._log_access(file_id, user_id, "delete")

        logger.info(
            "File deleted",
            file_id=file_id,
            filename=storage_file.original_filename,
            hard_delete=hard_delete,
            user_id=user_id
        )

        return True

    async def list_files(
        self,
        folder_path: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        include_deleted: bool = False
    ) -> FileListResponse:
        """
        List files in the workspace.

        Args:
            folder_path: Filter by folder path
            limit: Maximum number of files to return
            offset: Number of files to skip
            include_deleted: Whether to include soft-deleted files

        Returns:
            FileListResponse with files and pagination info
        """
        # Build query
        query = select(StorageFile).where(StorageFile.workspace_id == self.workspace_id)

        if not include_deleted:
            query = query.where(
                and_(
                    StorageFile.deleted_at.is_(None),
                    StorageFile.status != FileStatus.DELETED
                )
            )

        if folder_path is not None:
            query = query.where(StorageFile.folder_path == folder_path)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # Apply pagination and ordering
        query = query.order_by(desc(StorageFile.created_at)).limit(limit).offset(offset)

        # Execute query
        result = await self.db.execute(query)
        files = result.scalars().all()

        # Convert to response format
        file_responses = [
            FileResponse(
                id=f.id,
                file_key=f.file_key,
                filename=f.original_filename,
                content_type=f.content_type,
                size=f.file_size,
                folder_path=f.folder_path,
                tags=f.tags,
                is_public=f.is_public,
                uploaded_by=f.uploaded_by,
                created_at=f.created_at,
                expires_at=f.expires_at
            )
            for f in files
        ]

        return FileListResponse(
            files=file_responses,
            total=total,
            limit=limit,
            offset=offset,
            has_more=offset + len(files) < total
        )

    async def generate_signed_url(
        self,
        file_id: UUID,
        user_id: UUID,
        expiration: timedelta = timedelta(hours=1),
        operation: str = "GET"
    ) -> SignedUrlResult:
        """
        Generate a signed URL for secure file access.

        Args:
            file_id: File ID
            user_id: ID of the requesting user
            expiration: URL expiration time
            operation: Operation type (GET, PUT, DELETE)

        Returns:
            SignedUrlResult with URL and expiration
        """
        # Get file record
        storage_file = await self._get_file_or_404(file_id)

        # Check if file is accessible
        if storage_file.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or has been deleted"
            )

        # Generate signed URL
        driver = await self.get_driver()
        signed_url = await driver.generate_signed_url(
            file_key=storage_file.file_key,
            expiration=expiration,
            operation=operation
        )

        # Log access
        await self._log_access(file_id, user_id, f"signed_url_{operation.lower()}")

        logger.info(
            "Signed URL generated",
            file_id=file_id,
            operation=operation,
            expires_at=signed_url.expires_at,
            user_id=user_id
        )

        return signed_url

    async def get_storage_stats(self) -> StorageStatsResponse:
        """Get storage statistics for the workspace."""
        quota = await self.get_or_create_quota()

        # Get file count by status
        status_query = select(
            StorageFile.status,
            func.count(StorageFile.id).label('count'),
            func.sum(StorageFile.file_size).label('total_size')
        ).where(StorageFile.workspace_id == self.workspace_id).group_by(StorageFile.status)

        status_result = await self.db.execute(status_query)
        status_stats = {row.status: {'count': row.count, 'size': row.total_size or 0} for row in status_result}

        return StorageStatsResponse(
            total_files=quota.used_files,
            total_size=quota.used_storage_bytes,
            max_files=quota.max_files,
            max_size=quota.max_storage_bytes,
            files_by_status=status_stats,
            storage_usage_percentage=quota.storage_usage_percentage,
            files_usage_percentage=quota.files_usage_percentage
        )

    async def _get_file_or_404(self, file_id: UUID) -> StorageFile:
        """Get file by ID or raise 404."""
        result = await self.db.execute(
            select(StorageFile).where(
                and_(
                    StorageFile.id == file_id,
                    StorageFile.workspace_id == self.workspace_id
                )
            )
        )
        storage_file = result.scalar_one_or_none()

        if storage_file is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        return storage_file

    async def _log_access(self, file_id: UUID, user_id: UUID, action: str, metadata: Optional[Dict] = None) -> None:
        """Log file access for audit purposes."""
        try:
            access_log = StorageAccessLog(
                file_id=file_id,
                user_id=user_id,
                action=action,
                metadata=metadata
            )
            self.db.add(access_log)
            await self.db.commit()
        except Exception as e:
            logger.warning("Failed to log file access", error=str(e), file_id=file_id, action=action)
            # Don't fail the main operation if logging fails
            pass
