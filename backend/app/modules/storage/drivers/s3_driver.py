"""
AWS S3 storage driver implementation.

Provides S3-specific storage operations with workspace isolation using folder prefixes.
"""

import asyncio
import io
from datetime import datetime, timedelta
from typing import BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from structlog import get_logger

from ..schemas import FileMetadata, SignedUrlResult, UploadResult
from .base import BaseStorageDriver

logger = get_logger(__name__)


class S3StorageDriver(BaseStorageDriver):
    """AWS S3 storage driver with workspace isolation using folder prefixes."""

    def __init__(
        self,
        workspace_id: UUID,
        bucket_name: str,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        region_name: str = "us-east-1",
        endpoint_url: Optional[str] = None
    ):
        """
        Initialize S3 storage driver.

        Args:
            workspace_id: Workspace UUID for isolation
            bucket_name: S3 bucket name
            aws_access_key_id: AWS access key (optional, can use IAM roles)
            aws_secret_access_key: AWS secret key (optional, can use IAM roles)
            region_name: AWS region
            endpoint_url: Custom S3 endpoint (for S3-compatible services)
        """
        super().__init__(workspace_id)
        self.bucket_name = bucket_name

        # Initialize S3 client
        session = boto3.Session(
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name
        )

        self.s3_client = session.client('s3', endpoint_url=endpoint_url)
        self.s3_resource = session.resource('s3', endpoint_url=endpoint_url)

    def get_workspace_prefix(self) -> str:
        """Get the workspace-specific prefix for folder isolation."""
        return f"workspaces/{str(self.workspace_id)}/files/"

    def _generate_file_key(self, filename: str) -> str:
        """Generate a unique file key with workspace prefix."""
        prefix = self.get_workspace_prefix()
        unique_id = str(uuid4())
        # Keep original extension if present
        if '.' in filename:
            name, ext = filename.rsplit('.', 1)
            return f"{prefix}{unique_id}_{name}.{ext}"
        return f"{prefix}{unique_id}_{filename}"

    async def _ensure_bucket_exists(self) -> None:
        """Ensure the S3 bucket exists."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, self.s3_client.head_bucket, Bucket=self.bucket_name
            )
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    await loop.run_in_executor(
                        None, self.s3_client.create_bucket, Bucket=self.bucket_name
                    )
                    logger.info("Created S3 bucket", bucket=self.bucket_name, workspace_id=self.workspace_id)
                except ClientError as create_error:
                    logger.error("Failed to create S3 bucket", error=str(create_error), bucket=self.bucket_name)
                    raise
            else:
                logger.error("Failed to access S3 bucket", error=str(e), bucket=self.bucket_name)
                raise

    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> UploadResult:
        """Upload a file to S3."""
        await self._ensure_bucket_exists()

        file_key = self._generate_file_key(filename)

        # Read file data and get size
        file_content = file_data.read()
        file_size = len(file_content)
        file_stream = io.BytesIO(file_content)

        # Prepare metadata
        object_metadata = {
            "original-filename": filename,
            "upload-timestamp": datetime.utcnow().isoformat(),
            "workspace-id": str(self.workspace_id)
        }
        if metadata:
            object_metadata.update(metadata)

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.s3_client.put_object,
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_stream,
                ContentType=content_type,
                Metadata=object_metadata
            )

            logger.info(
                "File uploaded to S3",
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

        except ClientError as e:
            logger.error("Failed to upload file to S3", error=str(e), file_key=file_key)
            raise

    async def download_file(self, file_key: str) -> Tuple[BinaryIO, FileMetadata]:
        """Download a file from S3."""
        try:
            loop = asyncio.get_event_loop()

            # Get object
            response = await loop.run_in_executor(
                None,
                self.s3_client.get_object,
                Bucket=self.bucket_name,
                Key=file_key
            )

            # Read file data
            file_data = io.BytesIO(response['Body'].read())

            # Extract metadata
            object_metadata = response.get('Metadata', {})

            metadata = FileMetadata(
                file_key=file_key,
                filename=object_metadata.get("original-filename", file_key.split("/")[-1]),
                content_type=response.get('ContentType', 'application/octet-stream'),
                size=response['ContentLength'],
                created_at=response['LastModified'],
                workspace_id=self.workspace_id,
                metadata=object_metadata
            )

            return file_data, metadata

        except ClientError as e:
            logger.error("Failed to download file from S3", error=str(e), file_key=file_key)
            raise

    async def delete_file(self, file_key: str) -> bool:
        """Delete a file from S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.s3_client.delete_object,
                Bucket=self.bucket_name,
                Key=file_key
            )

            logger.info("File deleted from S3", file_key=file_key, workspace_id=self.workspace_id)
            return True

        except ClientError as e:
            logger.error("Failed to delete file from S3", error=str(e), file_key=file_key)
            return False

    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[FileMetadata]:
        """List files in S3."""
        try:
            search_prefix = self.get_workspace_prefix()
            if prefix:
                search_prefix += prefix

            loop = asyncio.get_event_loop()

            # List objects with pagination
            paginator = self.s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name,
                Prefix=search_prefix,
                PaginationConfig={
                    'MaxItems': limit,
                    'StartingToken': str(offset) if offset > 0 else None
                }
            )

            files = []
            for page in page_iterator:
                if 'Contents' in page:
                    for obj in page['Contents']:
                        try:
                            # Get object metadata
                            head_response = await loop.run_in_executor(
                                None,
                                self.s3_client.head_object,
                                Bucket=self.bucket_name,
                                Key=obj['Key']
                            )

                            object_metadata = head_response.get('Metadata', {})

                            files.append(FileMetadata(
                                file_key=obj['Key'],
                                filename=object_metadata.get("original-filename", obj['Key'].split("/")[-1]),
                                content_type=head_response.get('ContentType', 'application/octet-stream'),
                                size=obj['Size'],
                                created_at=obj['LastModified'],
                                workspace_id=self.workspace_id,
                                metadata=object_metadata
                            ))
                        except ClientError:
                            # Skip objects that can't be accessed
                            continue

            return files

        except ClientError as e:
            logger.error("Failed to list files from S3", error=str(e))
            return []

    async def file_exists(self, file_key: str) -> bool:
        """Check if a file exists in S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=file_key
            )
            return True
        except ClientError:
            return False

    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """Get metadata for a specific file."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                self.s3_client.head_object,
                Bucket=self.bucket_name,
                Key=file_key
            )

            object_metadata = response.get('Metadata', {})

            return FileMetadata(
                file_key=file_key,
                filename=object_metadata.get("original-filename", file_key.split("/")[-1]),
                content_type=response.get('ContentType', 'application/octet-stream'),
                size=response['ContentLength'],
                created_at=response['LastModified'],
                workspace_id=self.workspace_id,
                metadata=object_metadata
            )

        except ClientError:
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

            # Convert operation to S3 method
            method_map = {
                "GET": "get_object",
                "PUT": "put_object",
                "DELETE": "delete_object"
            }

            method = method_map.get(operation.upper(), "get_object")
            expiration_seconds = int(expiration.total_seconds())

            url = await loop.run_in_executor(
                None,
                self.s3_client.generate_presigned_url,
                method,
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expiration_seconds
            )

            expires_at = datetime.utcnow() + expiration

            return SignedUrlResult(
                url=url,
                expires_at=expires_at,
                operation=operation.upper()
            )

        except ClientError as e:
            logger.error("Failed to generate signed URL", error=str(e), file_key=file_key)
            raise

    async def copy_file(self, source_key: str, destination_key: str) -> bool:
        """Copy a file within S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.s3_client.copy_object,
                Bucket=self.bucket_name,
                Key=destination_key,
                CopySource={'Bucket': self.bucket_name, 'Key': source_key}
            )

            logger.info(
                "File copied in S3",
                source=source_key,
                destination=destination_key,
                workspace_id=self.workspace_id
            )
            return True

        except ClientError as e:
            logger.error("Failed to copy file in S3", error=str(e))
            return False

    async def move_file(self, source_key: str, destination_key: str) -> bool:
        """Move/rename a file within S3."""
        try:
            # Copy then delete
            if await self.copy_file(source_key, destination_key):
                return await self.delete_file(source_key)
            return False

        except Exception as e:
            logger.error("Failed to move file in S3", error=str(e))
            return False
