"""
Unit tests for StorageCleanupService.

This module contains comprehensive tests for the storage cleanup functionality,
including orphaned file detection, database record cleanup, and storage statistics.
"""
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import UUID

import pytest
from app.modules.storage.cleanup import StorageCleanupService, run_cleanup_job
from app.modules.storage.models import StorageFile


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = Mock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def mock_storage_file():
    """Mock storage file record."""
    file_record = Mock(spec=StorageFile)
    file_record.id = UUID("11111111-1111-1111-1111-111111111111")
    file_record.file_path = "test/file.txt"
    file_record.file_size = 1024
    file_record.created_at = datetime.now() - timedelta(hours=25)
    file_record.deleted_at = None
    file_record.soft_delete = Mock()
    return file_record


@pytest.fixture
def cleanup_service(mock_db_session):
    """Create StorageCleanupService instance with mocked dependencies."""
    with patch('app.modules.storage.cleanup.get_settings') as mock_settings:
        mock_settings.return_value.UPLOAD_DIR = "/tmp/test_storage"
        service = StorageCleanupService(mock_db_session)
        return service


@pytest.mark.asyncio
class TestStorageCleanupService:
    """Test cases for StorageCleanupService."""

    async def test_init(self, mock_db_session):
        """Test service initialization."""
        with patch('app.modules.storage.cleanup.get_settings') as mock_settings:
            mock_settings.return_value.UPLOAD_DIR = "/tmp/test_storage"

            service = StorageCleanupService(mock_db_session)

            assert service.db == mock_db_session
            assert service.storage_path == Path("/tmp/test_storage")

    async def test_find_orphaned_files_no_storage_path(self, cleanup_service):
        """Test finding orphaned files when storage path doesn't exist."""
        with patch.object(cleanup_service.storage_path, 'exists', return_value=False):
            result = await cleanup_service.find_orphaned_files()

            assert result == []

    async def test_find_orphaned_files_success(self, cleanup_service, mock_db_session):
        """Test successful orphaned file detection."""
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchall.return_value = [("existing/file.txt",), ("another/file.txt",)]
        mock_db_session.execute.return_value = mock_result

        # Mock file system
        mock_files = [
            Mock(spec=Path),  # orphaned file
            Mock(spec=Path),  # existing file
        ]

        # Configure first file (orphaned)
        mock_files[0].is_file.return_value = True
        mock_files[0].stat.return_value.st_mtime = (datetime.now() - timedelta(hours=25)).timestamp()
        mock_files[0].relative_to.return_value = Path("orphaned/file.txt")
        mock_files[0].__str__ = lambda: "/tmp/test_storage/orphaned/file.txt"

        # Configure second file (exists in DB)
        mock_files[1].is_file.return_value = True
        mock_files[1].stat.return_value.st_mtime = (datetime.now() - timedelta(hours=25)).timestamp()
        mock_files[1].relative_to.return_value = Path("existing/file.txt")
        mock_files[1].__str__ = lambda: "/tmp/test_storage/existing/file.txt"

        with patch.object(cleanup_service.storage_path, 'exists', return_value=True), \
             patch.object(cleanup_service.storage_path, 'rglob', return_value=mock_files):

            result = await cleanup_service.find_orphaned_files()

            assert len(result) == 1
            assert result[0] == mock_files[0]

    async def test_find_orphaned_files_recent_files_ignored(self, cleanup_service, mock_db_session):
        """Test that recent files are ignored in orphaned file detection."""
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        mock_db_session.execute.return_value = mock_result

        # Mock recent file
        mock_file = Mock(spec=Path)
        mock_file.is_file.return_value = True
        mock_file.stat.return_value.st_mtime = datetime.now().timestamp()  # Recent file

        with patch.object(cleanup_service.storage_path, 'exists', return_value=True), \
             patch.object(cleanup_service.storage_path, 'rglob', return_value=[mock_file]):

            result = await cleanup_service.find_orphaned_files()

            assert result == []

    async def test_find_orphaned_database_records_success(self, cleanup_service, mock_db_session, mock_storage_file):
        """Test successful orphaned database record detection."""
        # Mock database query result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_storage_file]
        mock_db_session.execute.return_value = mock_result

        # Mock file doesn't exist on disk
        with patch.object(cleanup_service.storage_path, '__truediv__') as mock_div:
            mock_file_path = Mock()
            mock_file_path.exists.return_value = False
            mock_div.return_value = mock_file_path

            result = await cleanup_service.find_orphaned_database_records()

            assert len(result) == 1
            assert result[0] == mock_storage_file

    async def test_find_orphaned_database_records_file_exists(self, cleanup_service, mock_db_session, mock_storage_file):
        """Test orphaned database record detection when file exists on disk."""
        # Mock database query result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_storage_file]
        mock_db_session.execute.return_value = mock_result

        # Mock file exists on disk
        with patch.object(cleanup_service.storage_path, '__truediv__') as mock_div:
            mock_file_path = Mock()
            mock_file_path.exists.return_value = True
            mock_div.return_value = mock_file_path

            result = await cleanup_service.find_orphaned_database_records()

            assert result == []

    async def test_cleanup_orphaned_files_dry_run(self, cleanup_service):
        """Test orphaned file cleanup in dry run mode."""
        # Mock orphaned files
        mock_files = [Mock(spec=Path), Mock(spec=Path)]
        mock_files[0].stat.return_value.st_size = 1024
        mock_files[0].__str__ = lambda: "/tmp/test_storage/file1.txt"
        mock_files[1].stat.return_value.st_size = 2048
        mock_files[1].__str__ = lambda: "/tmp/test_storage/file2.txt"

        with patch.object(cleanup_service, 'find_orphaned_files', return_value=mock_files):
            result = await cleanup_service.cleanup_orphaned_files(dry_run=True)

            assert result["files_found"] == 2
            assert result["files_deleted"] == 0
            assert result["files_failed"] == 0
            assert result["bytes_freed"] == 3072
            assert result["errors"] == []

            # Verify files were not actually deleted
            mock_files[0].unlink.assert_not_called()
            mock_files[1].unlink.assert_not_called()

    async def test_cleanup_orphaned_files_actual_cleanup(self, cleanup_service):
        """Test actual orphaned file cleanup."""
        # Mock orphaned files
        mock_files = [Mock(spec=Path), Mock(spec=Path)]
        mock_files[0].stat.return_value.st_size = 1024
        mock_files[0].__str__ = lambda: "/tmp/test_storage/file1.txt"
        mock_files[1].stat.return_value.st_size = 2048
        mock_files[1].__str__ = lambda: "/tmp/test_storage/file2.txt"

        with patch.object(cleanup_service, 'find_orphaned_files', return_value=mock_files):
            result = await cleanup_service.cleanup_orphaned_files(dry_run=False)

            assert result["files_found"] == 2
            assert result["files_deleted"] == 2
            assert result["files_failed"] == 0
            assert result["bytes_freed"] == 3072
            assert result["errors"] == []

            # Verify files were actually deleted
            mock_files[0].unlink.assert_called_once()
            mock_files[1].unlink.assert_called_once()

    async def test_cleanup_orphaned_files_with_errors(self, cleanup_service):
        """Test orphaned file cleanup with errors."""
        # Mock orphaned files
        mock_files = [Mock(spec=Path), Mock(spec=Path)]
        mock_files[0].stat.return_value.st_size = 1024
        mock_files[0].unlink.side_effect = OSError("Permission denied")
        mock_files[0].__str__ = lambda: "/tmp/test_storage/file1.txt"
        mock_files[1].stat.return_value.st_size = 2048
        mock_files[1].__str__ = lambda: "/tmp/test_storage/file2.txt"

        with patch.object(cleanup_service, 'find_orphaned_files', return_value=mock_files):
            result = await cleanup_service.cleanup_orphaned_files(dry_run=False)

            assert result["files_found"] == 2
            assert result["files_deleted"] == 1
            assert result["files_failed"] == 1
            assert result["bytes_freed"] == 2048
            assert len(result["errors"]) == 1
            assert "Permission denied" in result["errors"][0]

    async def test_cleanup_orphaned_database_records_dry_run(self, cleanup_service, mock_storage_file):
        """Test orphaned database record cleanup in dry run mode."""
        with patch.object(cleanup_service, 'find_orphaned_database_records', return_value=[mock_storage_file]):
            result = await cleanup_service.cleanup_orphaned_database_records(dry_run=True)

            assert result["records_found"] == 1
            assert result["records_deleted"] == 0
            assert result["records_failed"] == 0
            assert result["errors"] == []

            # Verify record was not actually deleted
            mock_storage_file.soft_delete.assert_not_called()

    async def test_cleanup_orphaned_database_records_actual_cleanup(self, cleanup_service, mock_storage_file, mock_db_session):
        """Test actual orphaned database record cleanup."""
        with patch.object(cleanup_service, 'find_orphaned_database_records', return_value=[mock_storage_file]):
            result = await cleanup_service.cleanup_orphaned_database_records(dry_run=False)

            assert result["records_found"] == 1
            assert result["records_deleted"] == 1
            assert result["records_failed"] == 0
            assert result["errors"] == []

            # Verify record was soft deleted and committed
            mock_storage_file.soft_delete.assert_called_once()
            mock_db_session.commit.assert_called_once()

    async def test_cleanup_orphaned_database_records_with_errors(self, cleanup_service, mock_storage_file):
        """Test orphaned database record cleanup with errors."""
        mock_storage_file.soft_delete.side_effect = Exception("Database error")

        with patch.object(cleanup_service, 'find_orphaned_database_records', return_value=[mock_storage_file]):
            result = await cleanup_service.cleanup_orphaned_database_records(dry_run=False)

            assert result["records_found"] == 1
            assert result["records_deleted"] == 0
            assert result["records_failed"] == 1
            assert len(result["errors"]) == 1
            assert "Database error" in result["errors"][0]

    async def test_cleanup_soft_deleted_files_dry_run(self, cleanup_service, mock_db_session):
        """Test soft-deleted file cleanup in dry run mode."""
        # Mock soft-deleted file
        mock_file = Mock(spec=StorageFile)
        mock_file.id = UUID("11111111-1111-1111-1111-111111111111")
        mock_file.file_path = "test/file.txt"
        mock_file.deleted_at = datetime.now() - timedelta(days=31)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_file]
        mock_db_session.execute.return_value = mock_result

        # Mock file exists on disk
        with patch.object(cleanup_service.storage_path, '__truediv__') as mock_div:
            mock_file_path = Mock()
            mock_file_path.exists.return_value = True
            mock_file_path.stat.return_value.st_size = 1024
            mock_file_path.__str__ = lambda: "/tmp/test_storage/test/file.txt"
            mock_div.return_value = mock_file_path

            result = await cleanup_service.cleanup_soft_deleted_files(dry_run=True)

            assert result["files_found"] == 1
            assert result["files_deleted"] == 0
            assert result["records_deleted"] == 0
            assert result["files_failed"] == 0
            assert result["bytes_freed"] == 1024
            assert result["errors"] == []

            # Verify nothing was actually deleted
            mock_file_path.unlink.assert_not_called()
            mock_db_session.delete.assert_not_called()

    async def test_cleanup_soft_deleted_files_actual_cleanup(self, cleanup_service, mock_db_session):
        """Test actual soft-deleted file cleanup."""
        # Mock soft-deleted file
        mock_file = Mock(spec=StorageFile)
        mock_file.id = UUID("11111111-1111-1111-1111-111111111111")
        mock_file.file_path = "test/file.txt"
        mock_file.deleted_at = datetime.now() - timedelta(days=31)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_file]
        mock_db_session.execute.return_value = mock_result

        # Mock file exists on disk
        with patch.object(cleanup_service.storage_path, '__truediv__') as mock_div:
            mock_file_path = Mock()
            mock_file_path.exists.return_value = True
            mock_file_path.stat.return_value.st_size = 1024
            mock_file_path.__str__ = lambda: "/tmp/test_storage/test/file.txt"
            mock_div.return_value = mock_file_path

            result = await cleanup_service.cleanup_soft_deleted_files(dry_run=False)

            assert result["files_found"] == 1
            assert result["files_deleted"] == 1
            assert result["records_deleted"] == 1
            assert result["files_failed"] == 0
            assert result["bytes_freed"] == 1024
            assert result["errors"] == []

            # Verify file and record were deleted
            mock_file_path.unlink.assert_called_once()
            mock_db_session.delete.assert_called_once_with(mock_file)
            mock_db_session.commit.assert_called_once()

    async def test_cleanup_soft_deleted_files_no_physical_file(self, cleanup_service, mock_db_session):
        """Test soft-deleted file cleanup when physical file doesn't exist."""
        # Mock soft-deleted file
        mock_file = Mock(spec=StorageFile)
        mock_file.id = UUID("11111111-1111-1111-1111-111111111111")
        mock_file.file_path = "test/file.txt"
        mock_file.deleted_at = datetime.now() - timedelta(days=31)

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_file]
        mock_db_session.execute.return_value = mock_result

        # Mock file doesn't exist on disk
        with patch.object(cleanup_service.storage_path, '__truediv__') as mock_div:
            mock_file_path = Mock()
            mock_file_path.exists.return_value = False
            mock_div.return_value = mock_file_path

            result = await cleanup_service.cleanup_soft_deleted_files(dry_run=False)

            assert result["files_found"] == 1
            assert result["files_deleted"] == 0
            assert result["records_deleted"] == 1
            assert result["files_failed"] == 0
            assert result["bytes_freed"] == 0
            assert result["errors"] == []

            # Verify only record was deleted
            mock_file_path.unlink.assert_not_called()
            mock_db_session.delete.assert_called_once_with(mock_file)

    async def test_get_storage_stats_success(self, cleanup_service, mock_db_session):
        """Test successful storage statistics retrieval."""
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchone.return_value = (100, 80, 20, 1024000, 1280000)  # total, active, deleted, active_size, total_size
        mock_db_session.execute.return_value = mock_result

        # Mock disk usage
        with patch('shutil.disk_usage', return_value=(10000000, 5000000, 5000000)), \
             patch.object(cleanup_service.storage_path, 'exists', return_value=True):

            result = await cleanup_service.get_storage_stats()

            assert result["database"]["total_files"] == 100
            assert result["database"]["active_files"] == 80
            assert result["database"]["deleted_files"] == 20
            assert result["database"]["active_size_bytes"] == 1024000
            assert result["database"]["total_size_bytes"] == 1280000
            assert result["disk"]["total"] == 10000000
            assert result["disk"]["used"] == 5000000
            assert result["disk"]["free"] == 5000000
            assert result["storage_path"] == str(cleanup_service.storage_path)

    async def test_get_storage_stats_no_storage_path(self, cleanup_service, mock_db_session):
        """Test storage statistics when storage path doesn't exist."""
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchone.return_value = (0, 0, 0, 0, 0)
        mock_db_session.execute.return_value = mock_result

        with patch.object(cleanup_service.storage_path, 'exists', return_value=False):
            result = await cleanup_service.get_storage_stats()

            assert result["database"]["total_files"] == 0
            assert result["disk"]["total"] == 0
            assert result["disk"]["used"] == 0
            assert result["disk"]["free"] == 0

    async def test_get_storage_stats_disk_usage_error(self, cleanup_service, mock_db_session):
        """Test storage statistics when disk usage fails."""
        # Mock database query result
        mock_result = Mock()
        mock_result.fetchone.return_value = (10, 8, 2, 1024, 1280)
        mock_db_session.execute.return_value = mock_result

        with patch('shutil.disk_usage', side_effect=OSError("Permission denied")), \
             patch.object(cleanup_service.storage_path, 'exists', return_value=True):

            result = await cleanup_service.get_storage_stats()

            assert result["database"]["total_files"] == 10
            assert result["disk"]["total"] == 0
            assert result["disk"]["used"] == 0
            assert result["disk"]["free"] == 0


@pytest.mark.asyncio
class TestRunCleanupJob:
    """Test cases for the run_cleanup_job function."""

    async def test_run_cleanup_job_dry_run(self):
        """Test running cleanup job in dry run mode."""
        mock_cleanup_service = Mock()
        mock_cleanup_service.get_storage_stats = AsyncMock(return_value={"test": "stats"})
        mock_cleanup_service.cleanup_orphaned_files = AsyncMock(return_value={"files_deleted": 0, "bytes_freed": 1024})
        mock_cleanup_service.cleanup_orphaned_database_records = AsyncMock(return_value={"records_deleted": 0})
        mock_cleanup_service.cleanup_soft_deleted_files = AsyncMock(return_value={"files_deleted": 0, "records_deleted": 0, "bytes_freed": 2048})

        with patch('app.modules.storage.cleanup.get_db_session') as mock_get_db, \
             patch('app.modules.storage.cleanup.StorageCleanupService', return_value=mock_cleanup_service):

            mock_db = Mock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await run_cleanup_job(dry_run=True)

            assert result["dry_run"] is True
            assert "started_at" in result
            assert "completed_at" in result
            assert result["orphaned_files"]["files_deleted"] == 0
            assert result["orphaned_records"]["records_deleted"] == 0
            assert result["soft_deleted"]["files_deleted"] == 0

            # Verify all cleanup methods were called
            mock_cleanup_service.cleanup_orphaned_files.assert_called_once_with(True)
            mock_cleanup_service.cleanup_orphaned_database_records.assert_called_once_with(True)
            mock_cleanup_service.cleanup_soft_deleted_files.assert_called_once_with(older_than_days=30, dry_run=True)

    async def test_run_cleanup_job_actual_cleanup(self):
        """Test running actual cleanup job."""
        mock_cleanup_service = Mock()
        mock_cleanup_service.get_storage_stats = AsyncMock(return_value={"test": "stats"})
        mock_cleanup_service.cleanup_orphaned_files = AsyncMock(return_value={"files_deleted": 5, "bytes_freed": 1024})
        mock_cleanup_service.cleanup_orphaned_database_records = AsyncMock(return_value={"records_deleted": 3})
        mock_cleanup_service.cleanup_soft_deleted_files = AsyncMock(return_value={"files_deleted": 2, "records_deleted": 2, "bytes_freed": 2048})

        with patch('app.modules.storage.cleanup.get_db_session') as mock_get_db, \
             patch('app.modules.storage.cleanup.StorageCleanupService', return_value=mock_cleanup_service):

            mock_db = Mock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await run_cleanup_job(dry_run=False)

            assert result["dry_run"] is False
            assert result["orphaned_files"]["files_deleted"] == 5
            assert result["orphaned_records"]["records_deleted"] == 3
            assert result["soft_deleted"]["files_deleted"] == 2

            # Verify all cleanup methods were called
            mock_cleanup_service.cleanup_orphaned_files.assert_called_once_with(False)
            mock_cleanup_service.cleanup_orphaned_database_records.assert_called_once_with(False)
            mock_cleanup_service.cleanup_soft_deleted_files.assert_called_once_with(older_than_days=30, dry_run=False)

    async def test_run_cleanup_job_selective_cleanup(self):
        """Test running cleanup job with selective operations."""
        mock_cleanup_service = Mock()
        mock_cleanup_service.get_storage_stats = AsyncMock(return_value={"test": "stats"})
        mock_cleanup_service.cleanup_orphaned_files = AsyncMock(return_value={"files_deleted": 0, "bytes_freed": 0})

        with patch('app.modules.storage.cleanup.get_db_session') as mock_get_db, \
             patch('app.modules.storage.cleanup.StorageCleanupService', return_value=mock_cleanup_service):

            mock_db = Mock()
            mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_get_db.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await run_cleanup_job(
                dry_run=True,
                cleanup_orphaned_files=True,
                cleanup_orphaned_records=False,
                cleanup_soft_deleted=False
            )

            assert result["orphaned_files"]["files_deleted"] == 0
            assert result["orphaned_records"] == {}
            assert result["soft_deleted"] == {}

            # Verify only orphaned files cleanup was called
            mock_cleanup_service.cleanup_orphaned_files.assert_called_once()
            mock_cleanup_service.cleanup_orphaned_database_records.assert_not_called()
            mock_cleanup_service.cleanup_soft_deleted_files.assert_not_called()
