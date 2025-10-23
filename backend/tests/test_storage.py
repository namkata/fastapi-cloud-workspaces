"""
Tests for the storage module functionality.
"""
from datetime import UTC, datetime, timedelta
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID

import pytest
from app.modules.storage.drivers.base import BaseStorageDriver
from app.modules.storage.drivers.minio_driver import MinIOStorageDriver
from app.modules.storage.drivers.s3_driver import S3StorageDriver
from app.modules.storage.models import FileStatus, StorageFile, StorageProvider
from app.modules.storage.schemas import (
    FileListResponse,
    FileResponse,
    StorageStatsResponse,
)
from app.modules.storage.service import StorageService


class MockStorageDriver(BaseStorageDriver):
    """Mock storage driver for testing."""

    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
        self.files = {}

    def get_workspace_prefix(self) -> str:
        return f"workspace-{self.workspace_id}/"

    async def upload_file(self, file_data, filename: str, content_type: str = None, metadata: dict = None) -> dict:
        file_key = f"{self.get_workspace_prefix()}{filename}"
        self.files[file_key] = {
            "content": file_data.read() if hasattr(file_data, 'read') else file_data,
            "content_type": content_type,
            "metadata": metadata or {}
        }
        return {"file_key": file_key, "size": len(self.files[file_key]["content"])}

    async def download_file(self, file_key: str) -> tuple:
        if file_key in self.files:
            content = self.files[file_key]["content"]
            return BytesIO(content), {
                "content_type": self.files[file_key]["content_type"],
                "size": len(content)
            }
        raise FileNotFoundError(f"File {file_key} not found")

    async def delete_file(self, file_key: str) -> bool:
        if file_key in self.files:
            del self.files[file_key]
            return True
        return False

    async def list_files(self, prefix: str = None, limit: int = 100, offset: int = 0) -> list:
        files = list(self.files.keys())
        if prefix:
            files = [f for f in files if f.startswith(prefix)]
        return files[offset:offset + limit]

    async def file_exists(self, file_key: str) -> bool:
        return file_key in self.files

    async def get_file_metadata(self, file_key: str) -> dict:
        if file_key in self.files:
            return self.files[file_key]["metadata"]
        return {}

    async def generate_signed_url(self, file_key: str, expiration: timedelta = timedelta(hours=1), operation: str = "GET") -> dict:
        return {
            "url": f"https://example.com/signed-url/{file_key}",
            "expires_at": datetime.now() + expiration
        }

    async def copy_file(self, source_key: str, dest_key: str) -> bool:
        if source_key in self.files:
            self.files[dest_key] = self.files[source_key].copy()
            return True
        return False

    async def move_file(self, source_key: str, dest_key: str) -> bool:
        if await self.copy_file(source_key, dest_key):
            await self.delete_file(source_key)
            return True
        return False


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def workspace_id():
    """Test workspace ID."""
    return UUID("12345678-1234-5678-9012-123456789012")


@pytest.fixture
def user_id():
    """Test user ID."""
    return UUID("87654321-4321-8765-2109-876543210987")


@pytest.mark.asyncio
class TestStorageService:
    """Test cases for StorageService."""

    async def test_upload_file_success(self):
        """Test successful file upload."""
        # Create a mock session and service
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock the driver
        mock_driver = Mock()
        mock_upload_result = Mock()
        mock_upload_result.file_key = "test-key"
        mock_upload_result.file_size = 17
        mock_upload_result.content_type = "text/plain"
        mock_upload_result.etag = "test-etag"
        mock_driver.upload_file = AsyncMock(return_value=mock_upload_result)

        # Mock quota
        mock_quota = Mock()
        mock_quota.used_storage_bytes = 0
        mock_quota.max_storage_bytes = 1000000
        mock_quota.used_files = 0
        mock_quota.can_upload_file.return_value = (True, "Upload allowed")

        with patch.object(service, 'get_driver', return_value=mock_driver), \
             patch.object(service, 'get_or_create_quota', new_callable=AsyncMock, return_value=mock_quota), \
             patch('app.modules.storage.models.StorageFile') as mock_storage_file_class, \
             patch.object(service, '_log_access', new_callable=AsyncMock):

            # Mock StorageFile instance with all required fields
            mock_file = Mock()
            mock_file.id = UUID("11111111-1111-1111-1111-111111111111")
            mock_file.file_key = "test-key"
            mock_file.original_filename = "test.txt"
            mock_file.content_type = "text/plain"
            mock_file.file_size = 17
            mock_file.workspace_id = workspace_id
            mock_file.uploaded_by = user_id
            mock_file.created_at = datetime.now(UTC)
            mock_file.updated_at = datetime.now(UTC)
            mock_file.metadata = None

            # Additional fields that the service tries to access
            mock_file.folder_path = None
            mock_file.tags = None
            mock_file.is_public = False
            mock_file.expires_at = None

            mock_storage_file_class.return_value = mock_file

            # Mock session operations
            mock_session.add = Mock()
            mock_session.commit = AsyncMock()

            # Mock the refresh operation to populate database-generated fields
            async def mock_refresh(obj):
                obj.id = UUID("11111111-1111-1111-1111-111111111111")
                obj.created_at = datetime.now(UTC)
                obj.updated_at = datetime.now(UTC)

            mock_session.refresh = AsyncMock(side_effect=mock_refresh)

            file_data = BytesIO(b"test file content")

            result = await service.upload_file(
                file_data=file_data,
                filename="test.txt",
                content_type="text/plain",
                user_id=user_id
            )

            assert result is not None
            assert result.id == UUID("11111111-1111-1111-1111-111111111111")

    async def test_upload_file_quota_exceeded(self):
        """Test file upload when quota is exceeded."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock quota that rejects upload
        mock_quota = Mock()
        mock_quota.can_upload_file.return_value = (False, "Storage quota exceeded")

        with patch.object(service, 'get_or_create_quota', new_callable=AsyncMock, return_value=mock_quota):
            file_data = BytesIO(b"test file content")

            with pytest.raises(HTTPException) as exc_info:
                await service.upload_file(
                    file_data=file_data,
                    filename="test.txt",
                    content_type="text/plain",
                    user_id=user_id
                )

            assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    async def test_download_file_success(self):
        """Test successful file download."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock file record
        mock_file = Mock()
        mock_file.id = file_id
        mock_file.file_key = "test-key"
        mock_file.original_filename = "test.txt"
        mock_file.is_deleted = False
        mock_file.is_expired = False

        # Mock driver
        mock_driver = Mock()
        file_content = BytesIO(b"test content")
        metadata = {"content_type": "text/plain", "size": 12}
        mock_driver.download_file = AsyncMock(return_value=(file_content, metadata))

        with patch.object(service, '_get_file_or_404', new_callable=AsyncMock, return_value=mock_file), \
             patch.object(service, 'get_driver', return_value=mock_driver), \
             patch.object(service, '_log_access', new_callable=AsyncMock):

            result_data, result_metadata = await service.download_file(file_id, user_id)

            assert result_data == file_content
            assert result_metadata == metadata

    async def test_download_file_deleted(self):
        """Test downloading a deleted file."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock deleted file
        mock_file = Mock()
        mock_file.is_deleted = True

        with patch.object(service, '_get_file_or_404', new_callable=AsyncMock, return_value=mock_file):
            with pytest.raises(HTTPException) as exc_info:
                await service.download_file(file_id, user_id)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_download_file_expired(self):
        """Test downloading an expired file."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock expired file
        mock_file = Mock()
        mock_file.is_deleted = False
        mock_file.is_expired = True

        with patch.object(service, '_get_file_or_404', new_callable=AsyncMock, return_value=mock_file):
            with pytest.raises(HTTPException) as exc_info:
                await service.download_file(file_id, user_id)

            assert exc_info.value.status_code == status.HTTP_410_GONE

    async def test_delete_file_soft_delete(self):
        """Test soft delete of a file."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock file record
        mock_file = Mock()
        mock_file.id = file_id
        mock_file.soft_delete = Mock()

        mock_session.commit = AsyncMock()

        with patch.object(service, '_get_file_or_404', new_callable=AsyncMock, return_value=mock_file), \
             patch.object(service, '_log_access', new_callable=AsyncMock):

            result = await service.delete_file(file_id, user_id, hard_delete=False)

            assert result is True
            mock_file.soft_delete.assert_called_once()
            mock_session.commit.assert_called_once()

    async def test_delete_file_hard_delete(self):
        """Test hard delete of a file."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock file record
        mock_file = Mock()
        mock_file.id = file_id
        mock_file.file_key = "test-key"
        mock_file.file_size = 1024

        # Mock driver
        mock_driver = Mock()
        mock_driver.delete_file = AsyncMock(return_value=True)

        # Mock quota
        mock_quota = Mock()
        mock_quota.used_storage_bytes = 2048
        mock_quota.used_files = 5

        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch.object(service, '_get_file_or_404', new_callable=AsyncMock, return_value=mock_file), \
             patch.object(service, 'get_driver', return_value=mock_driver), \
             patch.object(service, 'get_or_create_quota', new_callable=AsyncMock, return_value=mock_quota), \
             patch.object(service, '_log_access', new_callable=AsyncMock):

            result = await service.delete_file(file_id, user_id, hard_delete=True)

            assert result is True
            mock_driver.delete_file.assert_called_once_with("test-key")
            assert mock_quota.used_storage_bytes == 1024  # 2048 - 1024
            assert mock_quota.used_files == 4  # 5 - 1
            mock_session.delete.assert_called_once_with(mock_file)

    async def test_list_files_success(self):
        """Test successful file listing."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock files
        mock_files = [
            Mock(
                id=UUID("11111111-1111-1111-1111-111111111111"),
                file_key="file1.txt",
                original_filename="file1.txt",
                content_type="text/plain",
                file_size=100,
                folder_path=None,
                tags=None,
                is_public=False,
                uploaded_by=UUID("87654321-4321-8765-2109-876543210987"),
                created_at=datetime.now(UTC),
                expires_at=None
            ),
            Mock(
                id=UUID("22222222-2222-2222-2222-222222222222"),
                file_key="file2.txt",
                original_filename="file2.txt",
                content_type="text/plain",
                file_size=200,
                folder_path="documents",
                tags={"category": "test"},
                is_public=True,
                uploaded_by=UUID("87654321-4321-8765-2109-876543210987"),
                created_at=datetime.now(UTC),
                expires_at=None
            )
        ]

        # Mock database results
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_files

        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 2

        mock_session.execute = AsyncMock(side_effect=[mock_count_result, mock_result])

        result = await service.list_files(limit=10, offset=0)

        assert len(result.files) == 2
        assert result.total == 2
        assert result.limit == 10
        assert result.offset == 0
        assert result.has_more is False

    async def test_generate_signed_url_success(self):
        """Test successful signed URL generation."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock file record
        mock_file = Mock()
        mock_file.id = file_id
        mock_file.file_key = "test-key"
        mock_file.is_deleted = False

        # Mock driver
        mock_driver = Mock()
        mock_signed_url = Mock()
        mock_signed_url.url = "https://example.com/signed-url"
        mock_signed_url.expires_at = datetime.now(UTC) + timedelta(hours=1)
        mock_driver.generate_signed_url = AsyncMock(return_value=mock_signed_url)

        with patch.object(service, '_get_file_or_404', new_callable=AsyncMock, return_value=mock_file), \
             patch.object(service, 'get_driver', return_value=mock_driver), \
             patch.object(service, '_log_access', new_callable=AsyncMock):

            result = await service.generate_signed_url(file_id, user_id, operation="GET")

            assert result == mock_signed_url
            mock_driver.generate_signed_url.assert_called_once()

    async def test_generate_signed_url_deleted_file(self):
        """Test signed URL generation for deleted file."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        user_id = UUID("87654321-4321-8765-2109-876543210987")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock deleted file
        mock_file = Mock()
        mock_file.is_deleted = True

        with patch.object(service, '_get_file_or_404', new_callable=AsyncMock, return_value=mock_file):
            with pytest.raises(HTTPException) as exc_info:
                await service.generate_signed_url(file_id, user_id)

            assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_storage_stats(self):
        """Test getting storage statistics."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock quota
        mock_quota = Mock()
        mock_quota.used_files = 10
        mock_quota.used_storage_bytes = 1024000
        mock_quota.max_files = 1000
        mock_quota.max_storage_bytes = 10240000
        mock_quota.storage_usage_percentage = 10.0
        mock_quota.files_usage_percentage = 1.0

        # Mock status stats
        mock_status_result = Mock()
        mock_status_row = Mock()
        mock_status_row.status = FileStatus.ACTIVE
        mock_status_row.count = 8
        mock_status_row.total_size = 800000
        mock_status_result.__iter__ = Mock(return_value=iter([mock_status_row]))

        mock_session.execute = AsyncMock(return_value=mock_status_result)

        with patch.object(service, 'get_or_create_quota', new_callable=AsyncMock, return_value=mock_quota):
            result = await service.get_storage_stats()

            assert result.total_files == 10
            assert result.total_size == 1024000
            assert result.max_files == 1000
            assert result.max_size == 10240000
            assert result.storage_usage_percentage == 10.0
            assert result.files_usage_percentage == 1.0
            assert FileStatus.ACTIVE in result.files_by_status

    async def test_get_or_create_quota_existing(self):
        """Test getting existing quota."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock existing quota
        mock_quota = Mock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_quota
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.get_or_create_quota()

        assert result == mock_quota
        mock_session.execute.assert_called_once()

    async def test_get_or_create_quota_new(self):
        """Test creating new quota."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock no existing quota
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = Mock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        with patch('app.modules.storage.models.StorageQuota') as mock_quota_class:
            mock_quota = Mock()
            mock_quota_class.return_value = mock_quota

            result = await service.get_or_create_quota()

            assert result == mock_quota
            mock_session.add.assert_called_once_with(mock_quota)
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once_with(mock_quota)

    async def test_get_file_or_404_found(self):
        """Test getting file when it exists."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock file found
        mock_file = Mock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_file
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._get_file_or_404(file_id)

        assert result == mock_file

    async def test_get_file_or_404_not_found(self):
        """Test getting file when it doesn't exist."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")
        file_id = UUID("11111111-1111-1111-1111-111111111111")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        # Mock file not found
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(HTTPException) as exc_info:
            await service._get_file_or_404(file_id)

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_log_access_success(self):
        """Test successful access logging."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        file_id = UUID("11111111-1111-1111-1111-111111111111")
        user_id = UUID("87654321-4321-8765-2109-876543210987")

        mock_session.add = Mock()
        mock_session.commit = AsyncMock()

        with patch('app.modules.storage.models.StorageAccessLog') as mock_log_class:
            mock_log = Mock()
            mock_log_class.return_value = mock_log

            await service._log_access(file_id, user_id, "download", {"test": "metadata"})

            mock_session.add.assert_called_once_with(mock_log)
            mock_session.commit.assert_called_once()

    async def test_log_access_failure(self):
        """Test access logging failure doesn't break main operation."""
        mock_session = Mock()
        workspace_id = UUID("12345678-1234-5678-9012-123456789012")

        service = StorageService(db_session=mock_session, workspace_id=workspace_id)

        file_id = UUID("11111111-1111-1111-1111-111111111111")
        user_id = UUID("87654321-4321-8765-2109-876543210987")

        mock_session.add = Mock(side_effect=Exception("Database error"))

        with patch('app.modules.storage.models.StorageAccessLog'):
            # Should not raise exception
            await service._log_access(file_id, user_id, "download")

    async def test_minio_driver_initialization(self):
        """Test MinIO driver initialization."""
        driver = MinIOStorageDriver(
            workspace_id=UUID("12345678-1234-5678-9012-123456789012"),
            endpoint="localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False
        )

        assert driver.workspace_id == UUID("12345678-1234-5678-9012-123456789012")
        assert driver.bucket_name == f"workspace-{str(UUID('12345678-1234-5678-9012-123456789012')).lower()}"

    async def test_s3_driver_initialization(self):
        """Test S3 driver initialization."""
        driver = S3StorageDriver(
            workspace_id=UUID("12345678-1234-5678-9012-123456789012"),
            bucket_name="test-bucket",
            aws_access_key_id="test-key",
            aws_secret_access_key="test-secret",
            region_name="us-east-1"
        )

        assert driver.workspace_id == UUID("12345678-1234-5678-9012-123456789012")
        assert driver.bucket_name == "test-bucket"


class TestStorageModels:
    """Test cases for storage models."""

    def test_storage_file_model(self):
        """Test StorageFile model creation."""
        file_data = {
            "file_key": "test-key",
            "original_filename": "test.txt",
            "content_type": "text/plain",
            "file_size": 1024,
            "storage_provider": StorageProvider.MINIO,
            "workspace_id": UUID("12345678-1234-5678-9012-123456789012"),
            "uploaded_by": UUID("12345678-1234-5678-9012-123456789012")
        }

        storage_file = StorageFile(**file_data)

        assert storage_file.file_key == "test-key"
        assert storage_file.original_filename == "test.txt"
        assert storage_file.file_size == 1024
        # Note: status default is set by SQLAlchemy, not in constructor

    def test_storage_file_soft_delete(self):
        """Test StorageFile soft delete functionality."""
        file_data = {
            "file_key": "test-key",
            "original_filename": "test.txt",
            "content_type": "text/plain",
            "file_size": 1024,
            "storage_provider": StorageProvider.MINIO,
            "workspace_id": UUID("12345678-1234-5678-9012-123456789012"),
            "uploaded_by": UUID("12345678-1234-5678-9012-123456789012")
        }

        storage_file = StorageFile(**file_data)

        # Soft delete
        storage_file.soft_delete()

        # Should be marked as deleted
        assert storage_file.status == FileStatus.DELETED
        assert storage_file.deleted_at is not None


class TestMockStorageDriver:
    """Test cases for MockStorageDriver."""

    @pytest.mark.asyncio
    async def test_mock_driver_upload_download(self):
        """Test mock driver upload and download."""
        driver = MockStorageDriver("test-workspace")

        # Upload file
        file_data = BytesIO(b"test content")
        result = await driver.upload_file(file_data, "test.txt", "text/plain")

        assert "file_key" in result
        assert result["size"] == 12

        # Download file
        content, metadata = await driver.download_file(result["file_key"])
        assert content.read() == b"test content"
        assert metadata["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_mock_driver_delete(self):
        """Test mock driver file deletion."""
        driver = MockStorageDriver("test-workspace")

        # Upload and then delete
        file_data = BytesIO(b"test content")
        result = await driver.upload_file(file_data, "test.txt", "text/plain")

        # File should exist
        assert await driver.file_exists(result["file_key"])

        # Delete file
        deleted = await driver.delete_file(result["file_key"])
        assert deleted is True

        # File should no longer exist
        assert not await driver.file_exists(result["file_key"])


if __name__ == "__main__":
    pytest.main([__file__])
