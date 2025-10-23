"""
MinIO storage driver implementation.

Provides MinIO-specific storage operations with workspace isolation.
"""

import asyncio
import io
from datetime import datetime, timedelta
from typing import BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from minio import Minio
from minio.error import S3Error
from structlog import get_logger

from ..schemas import FileMetadata, SignedUrlResult, UploadResult
from .base import BaseStorageDriver

logger = get_logger(__name__)


class MinIOStorageDriver(BaseStorageDriver):
    """MinIO storage driver with workspace isolation."""

    def __init__(
        self,
        workspace_id: UUID,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = True,
        region: Optional[str] = None
    ):
        """
        Initialize MinIO storage driver.

        Args:
            workspace_id: Workspace UUID for isolation
            endpoint: MinIO server endpoint
            access_key: MinIO access key
            secret_key: MinIO secret key
            secure: Whether to use HTTPS
            region: MinIO region (optional)
        """
        super().__init__(workspace_id)
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region
        )
        self.bucket_name = f"workspace-{str(workspace_id).lower()}"

    async def _ensure_bucket_exists(self) -> None:
        """Ensure the workspace bucket exists."""
        try:
            # Run in thread pool since minio client is synchronous
            loop = asyncio.get_event_loop()
            bucket_exists = await loop.run_in_executor(
                None, self.client.bucket_exists, self.bucket_name
            )

            if not bucket_exists:
                await loop.run_in_executor(
                    None, self.client.make_bucket, self.bucket_name
                )
                logger.info("Created MinIO bucket", bucket=self.bucket_name, workspace_id=self.workspace_id)
        except S3Error as e:
            logger.error("Failed to ensure bucket exists", error=str(e), bucket=self.bucket_name)
            raise

    def get_workspace_prefix(self) -> str:
        """Get the workspace-specific prefix."""
        return f"files/"

    def _generate_file_key(self, filename: str) -> str:
        """Generate a unique file key."""
        prefix = self.get_workspace_prefix()
        unique_id = str(uuid4())
        # Keep original extension if present
        if '.' in filename:
            name, ext = filename.rsplit('.', 1)
            return f"{prefix}{unique_id}_{name}.{ext}"
        return f"{prefix}{unique_id}_{filename}"

    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> UploadResult:
        """Upload a file to MinIO."""
        await self._ensure_bucket_exists()

        file_key = self._generate_file_key(filename)

        # Read file data and get size
        file_content = file_data.read()
        file_size = len(file_content)
        file_stream = io.BytesIO(file_content)

        # Prepare metadata
        object_metadata = {
            "original-filename": filename,
            "content-type": content_type,
            "upload-timestamp": datetime.utcnow().isoformat(),
            "workspace-id": str(self.workspace_id)
        }
        if metadata:
            object_metadata.update(metadata)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.client.put_object,
                self.bucket_name,
                file_key,
                file_stream,
                file_size,
                content_type,
                object_metadata
            )

            logger.info(
                "File uploaded to MinIO",
                file_key=file_key,
                filename=filename,
                size=file_size,
                workspace_id=self.workspace_id
            )

            return UploadResult(
                file_key=file_key,
                filename=filename,
                content_type=content_type,
                size=file_size
            )

        except S3Error as e:
            logger.error("Failed to upload file to MinIO", error=str(e), file_key=file_key)
            raise

    async def download_file(self, file_key: str) -> Tuple[BinaryIO, FileMetadata]:
        """Download a file from MinIO."""
        try:
            loop = asyncio.get_event_loop()

            # Get object and metadata
            response = await loop.run_in_executor(
                None, self.client.get_object, self.bucket_name, file_key
            )

            stat = await loop.run_in_executor(
                None, self.client.stat_object, self.bucket_name, file_key
            )

            # Read file data
            file_data = io.BytesIO(response.read())
            response.close()

            # Extract metadata
            object_metadata = stat.metadata or {}

            metadata = FileMetadata(
                file_key=file_key,
                filename=object_metadata.get("original-filename", file_key.split("/")[-1]),
                content_type=stat.content_type or "application/octet-stream",
                size=stat.size,
                created_at=stat.last_modified,
                workspace_id=self.workspace_id,
                metadata=object_metadata
            )

            return file_data, metadata

        except S3Error as e:
            logger.error("Failed to download file from MinIO", error=str(e), file_key=file_key)
            raise

    async def delete_file(self, file_key: str) -> bool:
        """Delete a file from MinIO."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.client.remove_object, self.bucket_name, file_key
            )

            logger.info("File deleted from MinIO", file_key=file_key, workspace_id=self.workspace_id)
            return True

        except S3Error as e:
            logger.error("Failed to delete file from MinIO", error=str(e), file_key=file_key)
            return False

    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[FileMetadata]:
        """List files in MinIO."""
        try:
            search_prefix = self.get_workspace_prefix()
            if prefix:
                search_prefix += prefix

            loop = asyncio.get_event_loop()
            objects = await loop.run_in_executor(
                None,
                lambda: list(self.client.list_objects(
                    self.bucket_name,
                    prefix=search_prefix,
                    recursive=True
                ))
            )

            # Apply pagination
            paginated_objects = objects[offset:offset + limit]

            files = []
            for obj in paginated_objects:
                try:
                    stat = await loop.run_in_executor(
                        None, self.client.stat_object, self.bucket_name, obj.object_name
                    )

                    object_metadata = stat.metadata or {}

                    files.append(FileMetadata(
                        file_key=obj.object_name,
                        filename=object_metadata.get("original-filename", obj.object_name.split("/")[-1]),
                        content_type=stat.content_type or "application/octet-stream",
                        size=obj.size,
                        created_at=obj.last_modified,
                        workspace_id=self.workspace_id,
                        metadata=object_metadata
                    ))
                except S3Error:
                    # Skip objects that can't be accessed
                    continue

            return files

        except S3Error as e:
            logger.error("Failed to list files from MinIO", error=str(e))
            return []

    async def file_exists(self, file_key: str) -> bool:
        """Check if a file exists in MinIO."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.client.stat_object, self.bucket_name, file_key
            )
            return True
        except S3Error:
            return False

    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """Get metadata for a specific file."""
        try:
            loop = asyncio.get_event_loop()
            stat = await loop.run_in_executor(
                None, self.client.stat_object, self.bucket_name, file_key
            )

            object_metadata = stat.metadata or {}

            return FileMetadata(
                file_key=file_key,
                filename=object_metadata.get("original-filename", file_key.split("/")[-1]),
                content_type=stat.content_type or "application/octet-stream",
                size=stat.size,
                created_at=stat.last_modified,
                workspace_id=self.workspace_id,
                metadata=object_metadata
            )

        except S3Error:
            return None

    async def generate_signed_url(
        self,
        file_key: str,
        expiration: timedelta = timedelta(hours=1),
        operation: str = "GET"
    ) -> SignedUrlResult:
        """Generate a signed URL for secure file access."""
        try:
            loop = asyncio.get_event_loop()

            # Convert operation to MinIO method
            method_map = {
                "GET": "GET",
                "PUT": "PUT",
                "DELETE": "DELETE"
            }

            method = method_map.get(operation.upper(), "GET")

            url = await loop.run_in_executor(
                None,
                self.client.presigned_url,
                method,
                self.bucket_name,
                file_key,
                expiration
            )

            expires_at = datetime.utcnow() + expiration

            return SignedUrlResult(
                url=url,
                expires_at=expires_at,
                operation=operation.upper()
            )

        except S3Error as e:
            logger.error("Failed to generate signed URL", error=str(e), file_key=file_key)
            raise

    async def copy_file(self, source_key: str, destination_key: str) -> bool:
        """Copy a file within MinIO."""
        try:
            from minio.commonconfig import CopySource

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.client.copy_object,
                self.bucket_name,
                destination_key,
                CopySource(self.bucket_name, source_key)
            )

            logger.info(
                "File copied in MinIO",
                source=source_key,
                destination=destination_key,
                workspace_id=self.workspace_id
            )
            return True

        except S3Error as e:
            logger.error("Failed to copy file in MinIO", error=str(e))
            return False

    async def move_file(self, source_key: str, destination_key: str) -> bool:
        """Move/rename a file within MinIO."""
        try:
            # Copy then delete
            if await self.copy_file(source_key, destination_key):
                return await self.delete_file(source_key)
            return False

        except Exception as e:
            logger.error("Failed to move file in MinIO", error=str(e))
            return False
