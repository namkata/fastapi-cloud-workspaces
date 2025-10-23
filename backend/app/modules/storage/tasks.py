"""
Storage cleanup tasks for Celery.

This module provides Celery tasks for automated storage cleanup operations.
"""
from datetime import datetime
from typing import Any, Dict

from app.core.config import get_settings
from app.modules.storage.cleanup import run_cleanup_job
from celery import Celery
from structlog import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    "storage_tasks",
    broker=getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=getattr(settings, 'CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, name="storage.cleanup_orphaned_files")
def cleanup_orphaned_files_task(self, dry_run: bool = False) -> Dict[str, Any]:
    """
    Celery task to clean up orphaned files.

    Args:
        dry_run: If True, only report what would be cleaned up

    Returns:
        Dictionary with cleanup results
    """
    logger.info("Starting orphaned files cleanup task", task_id=self.request.id, dry_run=dry_run)

    try:
        # Import asyncio here to avoid issues with Celery worker
        import asyncio

        # Run the cleanup job
        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=True,
            cleanup_orphaned_records=False,
            cleanup_soft_deleted=False
        ))

        logger.info(
            "Orphaned files cleanup task completed",
            task_id=self.request.id,
            files_cleaned=results["orphaned_files"].get("files_deleted", 0),
            bytes_freed=results["orphaned_files"].get("bytes_freed", 0)
        )

        return results

    except Exception as exc:
        logger.error("Orphaned files cleanup task failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="storage.cleanup_orphaned_records")
def cleanup_orphaned_records_task(self, dry_run: bool = False) -> Dict[str, Any]:
    """
    Celery task to clean up orphaned database records.

    Args:
        dry_run: If True, only report what would be cleaned up

    Returns:
        Dictionary with cleanup results
    """
    logger.info("Starting orphaned records cleanup task", task_id=self.request.id, dry_run=dry_run)

    try:
        import asyncio

        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=False,
            cleanup_orphaned_records=True,
            cleanup_soft_deleted=False
        ))

        logger.info(
            "Orphaned records cleanup task completed",
            task_id=self.request.id,
            records_cleaned=results["orphaned_records"].get("records_deleted", 0)
        )

        return results

    except Exception as exc:
        logger.error("Orphaned records cleanup task failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="storage.cleanup_soft_deleted")
def cleanup_soft_deleted_task(self, dry_run: bool = False, older_than_days: int = 30) -> Dict[str, Any]:
    """
    Celery task to clean up soft-deleted files.

    Args:
        dry_run: If True, only report what would be cleaned up
        older_than_days: Delete files soft-deleted more than this many days ago

    Returns:
        Dictionary with cleanup results
    """
    logger.info(
        "Starting soft-deleted files cleanup task",
        task_id=self.request.id,
        dry_run=dry_run,
        older_than_days=older_than_days
    )

    try:
        import asyncio

        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=False,
            cleanup_orphaned_records=False,
            cleanup_soft_deleted=True,
            soft_deleted_days=older_than_days
        ))

        logger.info(
            "Soft-deleted files cleanup task completed",
            task_id=self.request.id,
            files_cleaned=results["soft_deleted"].get("files_deleted", 0),
            records_cleaned=results["soft_deleted"].get("records_deleted", 0),
            bytes_freed=results["soft_deleted"].get("bytes_freed", 0)
        )

        return results

    except Exception as exc:
        logger.error("Soft-deleted files cleanup task failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="storage.full_cleanup")
def full_cleanup_task(
    self,
    dry_run: bool = False,
    soft_deleted_days: int = 30
) -> Dict[str, Any]:
    """
    Celery task to run complete storage cleanup.

    Args:
        dry_run: If True, only report what would be cleaned up
        soft_deleted_days: Delete files soft-deleted more than this many days ago

    Returns:
        Dictionary with cleanup results
    """
    logger.info(
        "Starting full storage cleanup task",
        task_id=self.request.id,
        dry_run=dry_run,
        soft_deleted_days=soft_deleted_days
    )

    try:
        import asyncio

        results = asyncio.run(run_cleanup_job(
            dry_run=dry_run,
            cleanup_orphaned_files=True,
            cleanup_orphaned_records=True,
            cleanup_soft_deleted=True,
            soft_deleted_days=soft_deleted_days
        ))

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
            "Full storage cleanup task completed",
            task_id=self.request.id,
            files_cleaned=total_files_cleaned,
            records_cleaned=total_records_cleaned,
            bytes_freed=total_bytes_freed
        )

        return results

    except Exception as exc:
        logger.error("Full storage cleanup task failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc, countdown=60, max_retries=3)


@celery_app.task(bind=True, name="storage.get_storage_stats")
def get_storage_stats_task(self) -> Dict[str, Any]:
    """
    Celery task to get storage statistics.

    Returns:
        Dictionary with storage statistics
    """
    logger.info("Getting storage statistics", task_id=self.request.id)

    try:
        import asyncio

        from app.core.database import get_db_session
        from app.modules.storage.cleanup import StorageCleanupService

        async def get_stats():
            async with get_db_session() as db:
                cleanup_service = StorageCleanupService(db)
                return await cleanup_service.get_storage_stats()

        stats = asyncio.run(get_stats())

        logger.info("Storage statistics retrieved", task_id=self.request.id)
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "stats": stats
        }

    except Exception as exc:
        logger.error("Get storage statistics task failed", task_id=self.request.id, error=str(exc))
        raise self.retry(exc=exc, countdown=30, max_retries=3)


# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    # Run orphaned files cleanup daily at 2 AM
    'cleanup-orphaned-files-daily': {
        'task': 'storage.cleanup_orphaned_files',
        'schedule': 60.0 * 60.0 * 24.0,  # 24 hours
        'kwargs': {'dry_run': False},
    },
    # Run orphaned records cleanup daily at 2:30 AM
    'cleanup-orphaned-records-daily': {
        'task': 'storage.cleanup_orphaned_records',
        'schedule': 60.0 * 60.0 * 24.0,  # 24 hours
        'kwargs': {'dry_run': False},
    },
    # Run soft-deleted cleanup weekly on Sunday at 3 AM
    'cleanup-soft-deleted-weekly': {
        'task': 'storage.cleanup_soft_deleted',
        'schedule': 60.0 * 60.0 * 24.0 * 7.0,  # 7 days
        'kwargs': {'dry_run': False, 'older_than_days': 30},
    },
    # Get storage stats every hour
    'storage-stats-hourly': {
        'task': 'storage.get_storage_stats',
        'schedule': 60.0 * 60.0,  # 1 hour
    },
}


# Utility functions for manual task execution
def schedule_cleanup_task(
    task_type: str = "full",
    dry_run: bool = False,
    soft_deleted_days: int = 30,
    countdown: int = 0
) -> str:
    """
    Schedule a cleanup task for execution.

    Args:
        task_type: Type of cleanup ("orphaned_files", "orphaned_records", "soft_deleted", "full")
        dry_run: If True, only report what would be cleaned up
        soft_deleted_days: Days to wait before permanently deleting soft-deleted files
        countdown: Delay in seconds before executing the task

    Returns:
        Task ID
    """
    task_map = {
        "orphaned_files": cleanup_orphaned_files_task,
        "orphaned_records": cleanup_orphaned_records_task,
        "soft_deleted": cleanup_soft_deleted_task,
        "full": full_cleanup_task,
    }

    if task_type not in task_map:
        raise ValueError(f"Invalid task type: {task_type}")

    task = task_map[task_type]

    if task_type == "soft_deleted":
        result = task.apply_async(
            kwargs={"dry_run": dry_run, "older_than_days": soft_deleted_days},
            countdown=countdown
        )
    elif task_type == "full":
        result = task.apply_async(
            kwargs={"dry_run": dry_run, "soft_deleted_days": soft_deleted_days},
            countdown=countdown
        )
    else:
        result = task.apply_async(
            kwargs={"dry_run": dry_run},
            countdown=countdown
        )

    logger.info(
        "Scheduled cleanup task",
        task_type=task_type,
        task_id=result.id,
        dry_run=dry_run,
        countdown=countdown
    )

    return result.id


def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    Get the status of a cleanup task.

    Args:
        task_id: Task ID

    Returns:
        Dictionary with task status information
    """
    result = celery_app.AsyncResult(task_id)

    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None,
        "traceback": result.traceback if result.failed() else None,
        "info": result.info,
    }
