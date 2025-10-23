"""
Storage cleanup utilities.

This module provides functionality to clean up orphaned files and manage
storage maintenance tasks.
"""
import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from app.core.config import get_settings
from app.core.database import get_db_session
from app.modules.storage.models import StorageFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

logger = get_logger(__name__)
settings = get_settings()


class StorageCleanupService:
    """Service for cleaning up orphaned files and managing storage."""

    def __init__(self, db: AsyncSession):
        """
        Initialize cleanup service.

        Args:
            db: Database session
        """
        self.db = db
        self.storage_path = Path(settings.UPLOAD_DIR)

    async def find_orphaned_files(self, older_than_hours: int = 24) -> List[Path]:
        """
        Find files on disk that don't have corresponding database records.

        Args:
            older_than_hours: Only consider files older than this many hours

        Returns:
            List of orphaned file paths
        """
        orphaned_files = []
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

        if not self.storage_path.exists():
            logger.warning("Storage path does not exist", path=str(self.storage_path))
            return orphaned_files

        # Get all file paths from database
        result = await self.db.execute(
            select(StorageFile.file_path).where(StorageFile.deleted_at.is_(None))
        )
        db_file_paths = {row[0] for row in result.fetchall()}

        # Walk through storage directory
        for file_path in self.storage_path.rglob("*"):
            if file_path.is_file():
                # Check if file is older than cutoff
                try:
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime > cutoff_time:
                        continue
                except OSError:
                    logger.warning("Could not get file stats", path=str(file_path))
                    continue

                # Convert to relative path for comparison
                try:
                    relative_path = file_path.relative_to(self.storage_path)
                    if str(relative_path) not in db_file_paths:
                        orphaned_files.append(file_path)
                except ValueError:
                    # File is not within storage path
                    continue

        logger.info("Found orphaned files", count=len(orphaned_files))
        return orphaned_files

    async def find_orphaned_database_records(self, older_than_hours: int = 24) -> List[StorageFile]:
        """
        Find database records that don't have corresponding files on disk.

        Args:
            older_than_hours: Only consider records older than this many hours

        Returns:
            List of orphaned database records
        """
        cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

        # Get all non-deleted files from database
        result = await self.db.execute(
            select(StorageFile)
            .where(
                StorageFile.deleted_at.is_(None),
                StorageFile.created_at < cutoff_time
            )
        )
        db_files = result.scalars().all()

        orphaned_records = []
        for db_file in db_files:
            file_path = self.storage_path / db_file.file_path
            if not file_path.exists():
                orphaned_records.append(db_file)

        logger.info("Found orphaned database records", count=len(orphaned_records))
        return orphaned_records

    async def cleanup_orphaned_files(self, dry_run: bool = True) -> dict:
        """
        Clean up orphaned files from disk.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup statistics
        """
        orphaned_files = await self.find_orphaned_files()

        stats = {
            "files_found": len(orphaned_files),
            "files_deleted": 0,
            "files_failed": 0,
            "bytes_freed": 0,
            "errors": []
        }

        for file_path in orphaned_files:
            try:
                # Get file size before deletion
                file_size = file_path.stat().st_size

                if not dry_run:
                    file_path.unlink()
                    stats["files_deleted"] += 1
                    stats["bytes_freed"] += file_size
                    logger.info("Deleted orphaned file", path=str(file_path), size=file_size)
                else:
                    stats["bytes_freed"] += file_size
                    logger.info("Would delete orphaned file", path=str(file_path), size=file_size)

            except OSError as e:
                stats["files_failed"] += 1
                error_msg = f"Failed to delete {file_path}: {e}"
                stats["errors"].append(error_msg)
                logger.error("Failed to delete orphaned file", path=str(file_path), error=str(e))

        if dry_run:
            stats["files_deleted"] = 0  # Reset since nothing was actually deleted

        return stats

    async def cleanup_orphaned_database_records(self, dry_run: bool = True) -> dict:
        """
        Clean up orphaned database records.

        Args:
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup statistics
        """
        orphaned_records = await self.find_orphaned_database_records()

        stats = {
            "records_found": len(orphaned_records),
            "records_deleted": 0,
            "records_failed": 0,
            "errors": []
        }

        for record in orphaned_records:
            try:
                if not dry_run:
                    # Soft delete the record
                    record.soft_delete()
                    stats["records_deleted"] += 1
                    logger.info("Soft deleted orphaned record", file_id=record.id, path=record.file_path)
                else:
                    logger.info("Would soft delete orphaned record", file_id=record.id, path=record.file_path)

            except Exception as e:
                stats["records_failed"] += 1
                error_msg = f"Failed to delete record {record.id}: {e}"
                stats["errors"].append(error_msg)
                logger.error("Failed to delete orphaned record", file_id=record.id, error=str(e))

        if not dry_run and stats["records_deleted"] > 0:
            await self.db.commit()

        if dry_run:
            stats["records_deleted"] = 0  # Reset since nothing was actually deleted

        return stats

    async def cleanup_soft_deleted_files(self, older_than_days: int = 30, dry_run: bool = True) -> dict:
        """
        Permanently delete files that have been soft-deleted for a specified period.

        Args:
            older_than_days: Delete files soft-deleted more than this many days ago
            dry_run: If True, only report what would be deleted

        Returns:
            Dictionary with cleanup statistics
        """
        cutoff_time = datetime.now() - timedelta(days=older_than_days)

        # Get soft-deleted files older than cutoff
        result = await self.db.execute(
            select(StorageFile)
            .where(
                StorageFile.deleted_at.is_not(None),
                StorageFile.deleted_at < cutoff_time
            )
        )
        soft_deleted_files = result.scalars().all()

        stats = {
            "files_found": len(soft_deleted_files),
            "files_deleted": 0,
            "records_deleted": 0,
            "files_failed": 0,
            "bytes_freed": 0,
            "errors": []
        }

        for db_file in soft_deleted_files:
            try:
                file_path = self.storage_path / db_file.file_path
                file_size = 0

                # Delete physical file if it exists
                if file_path.exists():
                    file_size = file_path.stat().st_size
                    if not dry_run:
                        file_path.unlink()
                        stats["files_deleted"] += 1
                        stats["bytes_freed"] += file_size
                        logger.info("Deleted soft-deleted file", path=str(file_path), size=file_size)
                    else:
                        stats["bytes_freed"] += file_size
                        logger.info("Would delete soft-deleted file", path=str(file_path), size=file_size)

                # Delete database record
                if not dry_run:
                    await self.db.delete(db_file)
                    stats["records_deleted"] += 1
                    logger.info("Deleted database record", file_id=db_file.id)
                else:
                    logger.info("Would delete database record", file_id=db_file.id)

            except Exception as e:
                stats["files_failed"] += 1
                error_msg = f"Failed to delete {db_file.id}: {e}"
                stats["errors"].append(error_msg)
                logger.error("Failed to delete soft-deleted file", file_id=db_file.id, error=str(e))

        if not dry_run and stats["records_deleted"] > 0:
            await self.db.commit()

        if dry_run:
            stats["files_deleted"] = 0
            stats["records_deleted"] = 0

        return stats

    async def get_storage_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage statistics
        """
        # Database statistics
        result = await self.db.execute(
            text("""
                SELECT
                    COUNT(*) as total_files,
                    COUNT(CASE WHEN deleted_at IS NULL THEN 1 END) as active_files,
                    COUNT(CASE WHEN deleted_at IS NOT NULL THEN 1 END) as deleted_files,
                    COALESCE(SUM(CASE WHEN deleted_at IS NULL THEN file_size END), 0) as active_size,
                    COALESCE(SUM(file_size), 0) as total_size
                FROM storage_files
            """)
        )
        db_stats = result.fetchone()

        # Disk usage statistics
        disk_usage = {"total": 0, "used": 0, "free": 0}
        if self.storage_path.exists():
            try:
                import shutil
                total, used, free = shutil.disk_usage(self.storage_path)
                disk_usage = {
                    "total": total,
                    "used": used,
                    "free": free
                }
            except Exception as e:
                logger.warning("Could not get disk usage", error=str(e))

        return {
            "database": {
                "total_files": db_stats[0] if db_stats else 0,
                "active_files": db_stats[1] if db_stats else 0,
                "deleted_files": db_stats[2] if db_stats else 0,
                "active_size_bytes": db_stats[3] if db_stats else 0,
                "total_size_bytes": db_stats[4] if db_stats else 0,
            },
            "disk": disk_usage,
            "storage_path": str(self.storage_path)
        }


async def run_cleanup_job(
    dry_run: bool = True,
    cleanup_orphaned_files: bool = True,
    cleanup_orphaned_records: bool = True,
    cleanup_soft_deleted: bool = True,
    soft_deleted_days: int = 30
) -> dict:
    """
    Run the complete cleanup job.

    Args:
        dry_run: If True, only report what would be cleaned up
        cleanup_orphaned_files: Whether to clean up orphaned files
        cleanup_orphaned_records: Whether to clean up orphaned database records
        cleanup_soft_deleted: Whether to clean up soft-deleted files
        soft_deleted_days: Days to wait before permanently deleting soft-deleted files

    Returns:
        Dictionary with cleanup results
    """
    logger.info("Starting storage cleanup job", dry_run=dry_run)

    results = {
        "started_at": datetime.now().isoformat(),
        "dry_run": dry_run,
        "orphaned_files": {},
        "orphaned_records": {},
        "soft_deleted": {},
        "storage_stats": {}
    }

    async with get_db_session() as db:
        cleanup_service = StorageCleanupService(db)

        # Get initial storage stats
        results["storage_stats"]["before"] = await cleanup_service.get_storage_stats()

        # Clean up orphaned files
        if cleanup_orphaned_files:
            logger.info("Cleaning up orphaned files")
            results["orphaned_files"] = await cleanup_service.cleanup_orphaned_files(dry_run)

        # Clean up orphaned database records
        if cleanup_orphaned_records:
            logger.info("Cleaning up orphaned database records")
            results["orphaned_records"] = await cleanup_service.cleanup_orphaned_database_records(dry_run)

        # Clean up soft-deleted files
        if cleanup_soft_deleted:
            logger.info("Cleaning up soft-deleted files")
            results["soft_deleted"] = await cleanup_service.cleanup_soft_deleted_files(
                older_than_days=soft_deleted_days,
                dry_run=dry_run
            )

        # Get final storage stats
        results["storage_stats"]["after"] = await cleanup_service.get_storage_stats()

    results["completed_at"] = datetime.now().isoformat()

    # Log summary
    total_files_cleaned = (
        results["orphaned_files"].get("files_deleted", 0) +
        results["soft_deleted"].get("files_deleted", 0)
    )
    total_records_cleaned = (
        results["orphaned_records"].get("records_deleted", 0) +
        results["soft_deleted"].get("records_deleted", 0)
    )
    total_bytes_freed = (
        results["orphaned_files"].get("bytes_freed", 0) +
        results["soft_deleted"].get("bytes_freed", 0)
    )

    logger.info(
        "Storage cleanup job completed",
        dry_run=dry_run,
        files_cleaned=total_files_cleaned,
        records_cleaned=total_records_cleaned,
        bytes_freed=total_bytes_freed
    )

    return results


if __name__ == "__main__":
    # Allow running cleanup as a standalone script
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run storage cleanup job")
    parser.add_argument("--dry-run", action="store_true", help="Only report what would be cleaned")
    parser.add_argument("--no-orphaned-files", action="store_true", help="Skip orphaned files cleanup")
    parser.add_argument("--no-orphaned-records", action="store_true", help="Skip orphaned records cleanup")
    parser.add_argument("--no-soft-deleted", action="store_true", help="Skip soft-deleted files cleanup")
    parser.add_argument("--soft-deleted-days", type=int, default=30, help="Days before permanently deleting soft-deleted files")

    args = parser.parse_args()

    async def main():
        results = await run_cleanup_job(
            dry_run=args.dry_run,
            cleanup_orphaned_files=not args.no_orphaned_files,
            cleanup_orphaned_records=not args.no_orphaned_records,
            cleanup_soft_deleted=not args.no_soft_deleted,
            soft_deleted_days=args.soft_deleted_days
        )
        print(json.dumps(results, indent=2))

    asyncio.run(main())
