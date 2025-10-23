"""
Cleanup tasks for inactive workspaces and orphaned files.
"""
import asyncio
from datetime import datetime, timedelta
from typing import List

from app.core.celery_app import celery_app
from app.core.database import get_db_session_context
from app.core.logger import logger
from app.modules.storage.models import FileRecord
from app.modules.storage.service import StorageService
from app.modules.workspace.models import Workspace, WorkspaceMember
from celery import current_task
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


@celery_app.task(bind=True)
def cleanup_inactive_workspaces(self):
    """
    Clean up workspaces that have been inactive for more than 30 days.
    """
    return asyncio.run(_cleanup_inactive_workspaces_async())


async def _cleanup_inactive_workspaces_async():
    """Async implementation of workspace cleanup."""
    try:
        async with get_db_session_context() as session:
            # Find workspaces inactive for more than 30 days
            cutoff_date = datetime.utcnow() - timedelta(days=30)

            stmt = select(Workspace).where(
                and_(
                    Workspace.updated_at < cutoff_date,
                    Workspace.is_active == True
                )
            )

            result = await session.execute(stmt)
            inactive_workspaces = result.scalars().all()

            cleaned_count = 0
            for workspace in inactive_workspaces:
                # Check if workspace has any active members
                member_stmt = select(WorkspaceMember).where(
                    and_(
                        WorkspaceMember.workspace_id == workspace.id,
                        WorkspaceMember.is_active == True
                    )
                )
                member_result = await session.execute(member_stmt)
                active_members = member_result.scalars().all()

                if not active_members:
                    # Mark workspace as inactive
                    workspace.is_active = False
                    workspace.updated_at = datetime.utcnow()
                    cleaned_count += 1

                    logger.info(f"Marked workspace {workspace.id} as inactive due to no active members")

            await session.commit()

            logger.info(f"Cleanup completed: {cleaned_count} workspaces marked as inactive")
            return {"cleaned_workspaces": cleaned_count}

    except Exception as e:
        logger.error(f"Error during workspace cleanup: {str(e)}")
        raise


@celery_app.task(bind=True)
def cleanup_orphaned_files(self):
    """
    Clean up files that are no longer referenced by any workspace.
    """
    return asyncio.run(_cleanup_orphaned_files_async())


async def _cleanup_orphaned_files_async():
    """Async implementation of orphaned files cleanup."""
    try:
        async with get_db_session_context() as session:
            # Find files older than 7 days that belong to inactive workspaces
            cutoff_date = datetime.utcnow() - timedelta(days=7)

            # Get files from inactive workspaces
            stmt = select(FileRecord).join(Workspace).where(
                and_(
                    FileRecord.created_at < cutoff_date,
                    Workspace.is_active == False
                )
            )

            result = await session.execute(stmt)
            orphaned_files = result.scalars().all()

            storage_service = StorageService()
            deleted_count = 0
            deleted_size = 0

            for file_record in orphaned_files:
                try:
                    # Delete from storage
                    await storage_service.delete_file(file_record.file_path)

                    # Delete from database
                    deleted_size += file_record.file_size
                    await session.delete(file_record)
                    deleted_count += 1

                    logger.info(f"Deleted orphaned file: {file_record.file_path}")

                except Exception as e:
                    logger.error(f"Failed to delete file {file_record.file_path}: {str(e)}")
                    continue

            await session.commit()

            logger.info(f"Cleanup completed: {deleted_count} orphaned files deleted, {deleted_size} bytes freed")
            return {
                "deleted_files": deleted_count,
                "freed_bytes": deleted_size
            }

    except Exception as e:
        logger.error(f"Error during orphaned files cleanup: {str(e)}")
        raise


@celery_app.task(bind=True)
def cleanup_expired_temp_files(self):
    """
    Clean up temporary files that have expired.
    """
    return asyncio.run(_cleanup_expired_temp_files_async())


async def _cleanup_expired_temp_files_async():
    """Async implementation of temporary files cleanup."""
    try:
        async with get_db_session_context() as session:
            # Find temporary files older than 24 hours
            cutoff_date = datetime.utcnow() - timedelta(hours=24)

            stmt = select(FileRecord).where(
                and_(
                    FileRecord.is_temporary == True,
                    FileRecord.created_at < cutoff_date
                )
            )

            result = await session.execute(stmt)
            temp_files = result.scalars().all()

            storage_service = StorageService()
            deleted_count = 0
            deleted_size = 0

            for file_record in temp_files:
                try:
                    # Delete from storage
                    await storage_service.delete_file(file_record.file_path)

                    # Delete from database
                    deleted_size += file_record.file_size
                    await session.delete(file_record)
                    deleted_count += 1

                    logger.info(f"Deleted expired temp file: {file_record.file_path}")

                except Exception as e:
                    logger.error(f"Failed to delete temp file {file_record.file_path}: {str(e)}")
                    continue

            await session.commit()

            logger.info(f"Temp cleanup completed: {deleted_count} files deleted, {deleted_size} bytes freed")
            return {
                "deleted_temp_files": deleted_count,
                "freed_bytes": deleted_size
            }

    except Exception as e:
        logger.error(f"Error during temp files cleanup: {str(e)}")
        raise
