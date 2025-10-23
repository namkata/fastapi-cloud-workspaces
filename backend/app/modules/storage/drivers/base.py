"""
Base storage driver interface.

Defines the contract that all storage drivers must implement.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import BinaryIO, Dict, List, Optional, Tuple
from uuid import UUID

from ..schemas import FileMetadata, SignedUrlResult, UploadResult


class BaseStorageDriver(ABC):
    """Abstract base class for storage drivers."""

    def __init__(self, workspace_id: UUID):
        """
        Initialize the storage driver for a specific workspace.

        Args:
            workspace_id: The workspace UUID for isolation
        """
        self.workspace_id = workspace_id

    @abstractmethod
    async def upload_file(
        self,
        file_data: BinaryIO,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> UploadResult:
        """
        Upload a file to storage.

        Args:
            file_data: Binary file data stream
            filename: Original filename
            content_type: MIME type of the file
            metadata: Optional metadata dictionary

        Returns:
            UploadResult with file information
        """
        pass

    @abstractmethod
    async def download_file(self, file_key: str) -> Tuple[BinaryIO, FileMetadata]:
        """
        Download a file from storage.

        Args:
            file_key: Unique file identifier

        Returns:
            Tuple of (file_data, metadata)
        """
        pass

    @abstractmethod
    async def delete_file(self, file_key: str) -> bool:
        """
        Delete a file from storage.

        Args:
            file_key: Unique file identifier

        Returns:
            True if deletion was successful
        """
        pass

    @abstractmethod
    async def list_files(
        self,
        prefix: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[FileMetadata]:
        """
        List files in storage.

        Args:
            prefix: Optional prefix filter
            limit: Maximum number of files to return
            offset: Number of files to skip

        Returns:
            List of file metadata
        """
        pass

    @abstractmethod
    async def file_exists(self, file_key: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            file_key: Unique file identifier

        Returns:
            True if file exists
        """
        pass

    @abstractmethod
    async def get_file_metadata(self, file_key: str) -> Optional[FileMetadata]:
        """
        Get metadata for a specific file.

        Args:
            file_key: Unique file identifier

        Returns:
            File metadata or None if not found
        """
        pass

    @abstractmethod
    async def generate_signed_url(
        self,
        file_key: str,
        expiration: timedelta = timedelta(hours=1),
        operation: str = "GET"
    ) -> SignedUrlResult:
        """
        Generate a signed URL for secure file access.

        Args:
            file_key: Unique file identifier
            expiration: URL expiration time
            operation: HTTP operation (GET, PUT, DELETE)

        Returns:
            SignedUrlResult with URL and expiration info
        """
        pass

    @abstractmethod
    def get_workspace_prefix(self) -> str:
        """
        Get the workspace-specific prefix for file isolation.

        Returns:
            Workspace prefix string
        """
        pass

    @abstractmethod
    async def copy_file(self, source_key: str, destination_key: str) -> bool:
        """
        Copy a file within storage.

        Args:
            source_key: Source file identifier
            destination_key: Destination file identifier

        Returns:
            True if copy was successful
        """
        pass

    @abstractmethod
    async def move_file(self, source_key: str, destination_key: str) -> bool:
        """
        Move/rename a file within storage.

        Args:
            source_key: Source file identifier
            destination_key: Destination file identifier

        Returns:
            True if move was successful
        """
        pass
