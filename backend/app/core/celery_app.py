"""
Celery application configuration for background tasks.
"""
import os

from app.core.config import settings
from celery import Celery

# Create Celery instance
celery_app = Celery(
    "fastapi-cloud-workspaces",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.cleanup",
        "app.tasks.backup",
        "app.tasks.file_processing"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=3600,  # 1 hour
    beat_schedule={
        "cleanup-inactive-workspaces": {
            "task": "app.tasks.cleanup.cleanup_inactive_workspaces",
            "schedule": 3600.0,  # Run every hour
        },
        "cleanup-orphaned-files": {
            "task": "app.tasks.cleanup.cleanup_orphaned_files",
            "schedule": 7200.0,  # Run every 2 hours
        },
        "backup-metadata": {
            "task": "app.tasks.backup.backup_metadata",
            "schedule": 86400.0,  # Run daily
        },
    },
)

# Optional: Configure task routes for different queues
celery_app.conf.task_routes = {
    "app.tasks.cleanup.*": {"queue": "cleanup"},
    "app.tasks.backup.*": {"queue": "backup"},
    "app.tasks.file_processing.*": {"queue": "processing"},
}
