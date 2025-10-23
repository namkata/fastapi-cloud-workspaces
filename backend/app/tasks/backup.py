"""
Backup tasks for metadata and workspace data.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

from app.core.celery_app import celery_app
from app.core.database import get_db_session_context
from app.core.logger import logger
from app.modules.auth.models import User
from app.modules.storage.models import FileRecord
from app.modules.storage.service import StorageService
from app.modules.workspace.models import Workspace, WorkspaceMember, WorkspaceRole
from celery import current_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@celery_app.task(bind=True)
def backup_metadata(self):
    """
    Create a backup of all workspace metadata.
    """
    return asyncio.run(_backup_metadata_async())


async def _backup_metadata_async():
    """Async implementation of metadata backup."""
    try:
        async with get_db_session_context() as session:
            backup_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "version": "1.0",
                "workspaces": [],
                "users": [],
                "roles": []
            }

            # Backup workspace data
            workspaces_stmt = select(Workspace)
            workspaces_result = await session.execute(workspaces_stmt)
            workspaces = workspaces_result.scalars().all()

            for workspace in workspaces:
                workspace_data = {
                    "id": workspace.id,
                    "name": workspace.name,
                    "description": workspace.description,
                    "is_active": workspace.is_active,
                    "created_at": workspace.created_at.isoformat() if workspace.created_at else None,
                    "updated_at": workspace.updated_at.isoformat() if workspace.updated_at else None,
                    "owner_id": workspace.owner_id,
                    "members": []
                }

                # Get workspace members
                members_stmt = select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == workspace.id
                )
                members_result = await session.execute(members_stmt)
                members = members_result.scalars().all()

                for member in members:
                    member_data = {
                        "user_id": member.user_id,
                        "role_id": member.role_id,
                        "is_active": member.is_active,
                        "joined_at": member.joined_at.isoformat() if member.joined_at else None
                    }
                    workspace_data["members"].append(member_data)

                backup_data["workspaces"].append(workspace_data)

            # Backup user data (excluding sensitive information)
            users_stmt = select(User)
            users_result = await session.execute(users_stmt)
            users = users_result.scalars().all()

            for user in users:
                user_data = {
                    "id": user.id,
                    "email": user.email,
                    "username": user.username,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "is_superuser": user.is_superuser,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "updated_at": user.updated_at.isoformat() if user.updated_at else None
                }
                backup_data["users"].append(user_data)

            # Backup roles
            roles_stmt = select(WorkspaceRole)
            roles_result = await session.execute(roles_stmt)
            roles = roles_result.scalars().all()

            for role in roles:
                role_data = {
                    "id": role.id,
                    "name": role.name,
                    "description": role.description,
                    "can_read": role.can_read,
                    "can_write": role.can_write,
                    "can_admin": role.can_admin,
                    "can_invite": role.can_invite,
                    "can_remove_members": role.can_remove_members,
                    "created_at": role.created_at.isoformat() if role.created_at else None
                }
                backup_data["roles"].append(role_data)

            # Save backup to storage
            backup_filename = f"metadata_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            backup_content = json.dumps(backup_data, indent=2)

            storage_service = StorageService()
            backup_path = f"backups/{backup_filename}"

            # Upload backup to storage
            await storage_service.upload_file_content(
                content=backup_content.encode('utf-8'),
                file_path=backup_path,
                content_type="application/json"
            )

            logger.info(f"Metadata backup completed: {backup_filename}")
            return {
                "backup_file": backup_filename,
                "workspaces_count": len(backup_data["workspaces"]),
                "users_count": len(backup_data["users"]),
                "roles_count": len(backup_data["roles"])
            }

    except Exception as e:
        logger.error(f"Error during metadata backup: {str(e)}")
        raise


@celery_app.task(bind=True)
def backup_workspace_files(self, workspace_id: str):
    """
    Create a backup of all files in a specific workspace.
    """
    return asyncio.run(_backup_workspace_files_async(workspace_id))


async def _backup_workspace_files_async(workspace_id: str):
    """Async implementation of workspace files backup."""
    try:
        async with get_db_session_context() as session:
            # Get workspace
            workspace_stmt = select(Workspace).where(Workspace.id == workspace_id)
            workspace_result = await session.execute(workspace_stmt)
            workspace = workspace_result.scalar_one_or_none()

            if not workspace:
                raise ValueError(f"Workspace {workspace_id} not found")

            # Get all files in workspace
            files_stmt = select(FileRecord).where(FileRecord.workspace_id == workspace_id)
            files_result = await session.execute(files_stmt)
            files = files_result.scalars().all()

            storage_service = StorageService()
            backup_manifest = {
                "workspace_id": workspace_id,
                "workspace_name": workspace.name,
                "backup_timestamp": datetime.utcnow().isoformat(),
                "files": []
            }

            backed_up_count = 0
            total_size = 0

            for file_record in files:
                try:
                    # Create backup path
                    backup_file_path = f"backups/workspace_{workspace_id}/{file_record.filename}"

                    # Copy file to backup location
                    file_content = await storage_service.get_file_content(file_record.file_path)
                    await storage_service.upload_file_content(
                        content=file_content,
                        file_path=backup_file_path,
                        content_type=file_record.content_type
                    )

                    # Add to manifest
                    file_info = {
                        "original_path": file_record.file_path,
                        "backup_path": backup_file_path,
                        "filename": file_record.filename,
                        "file_size": file_record.file_size,
                        "content_type": file_record.content_type,
                        "created_at": file_record.created_at.isoformat() if file_record.created_at else None
                    }
                    backup_manifest["files"].append(file_info)

                    backed_up_count += 1
                    total_size += file_record.file_size

                    logger.info(f"Backed up file: {file_record.filename}")

                except Exception as e:
                    logger.error(f"Failed to backup file {file_record.filename}: {str(e)}")
                    continue

            # Save manifest
            manifest_content = json.dumps(backup_manifest, indent=2)
            manifest_path = f"backups/workspace_{workspace_id}/manifest.json"

            await storage_service.upload_file_content(
                content=manifest_content.encode('utf-8'),
                file_path=manifest_path,
                content_type="application/json"
            )

            logger.info(f"Workspace backup completed: {workspace_id}, {backed_up_count} files, {total_size} bytes")
            return {
                "workspace_id": workspace_id,
                "backed_up_files": backed_up_count,
                "total_size": total_size,
                "manifest_path": manifest_path
            }

    except Exception as e:
        logger.error(f"Error during workspace files backup: {str(e)}")
        raise


@celery_app.task(bind=True)
def cleanup_old_backups(self):
    """
    Clean up backup files older than 30 days.
    """
    return asyncio.run(_cleanup_old_backups_async())


async def _cleanup_old_backups_async():
    """Async implementation of old backups cleanup."""
    try:
        storage_service = StorageService()

        # List all backup files
        backup_files = await storage_service.list_files("backups/")

        cutoff_date = datetime.utcnow() - timedelta(days=30)
        deleted_count = 0
        freed_size = 0

        for file_info in backup_files:
            if file_info.get("last_modified") and file_info["last_modified"] < cutoff_date:
                try:
                    await storage_service.delete_file(file_info["path"])
                    deleted_count += 1
                    freed_size += file_info.get("size", 0)

                    logger.info(f"Deleted old backup: {file_info['path']}")

                except Exception as e:
                    logger.error(f"Failed to delete backup {file_info['path']}: {str(e)}")
                    continue

        logger.info(f"Old backups cleanup completed: {deleted_count} files deleted, {freed_size} bytes freed")
        return {
            "deleted_backups": deleted_count,
            "freed_bytes": freed_size
        }

    except Exception as e:
        logger.error(f"Error during old backups cleanup: {str(e)}")
        raise
