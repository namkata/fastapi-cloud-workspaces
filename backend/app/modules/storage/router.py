"""
Storage router.

This module provides API endpoints for file storage management within workspaces.
"""
from typing import List, Optional
from uuid import UUID

from app.core.database import get_db_session
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.workspace.dependencies import (
    require_workspace_context,
    require_workspace_member,
    require_workspace_read,
    require_workspace_write,
)
from app.modules.workspace.models import Workspace, WorkspaceMember
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from .models import StorageFile
from .schemas import (
    FileListResponse,
    FileResponse,
    MessageResponse,
    SignedUrlRequest,
    SignedUrlResult,
    StorageStatsResponse,
    UploadResult,
)
from .service import StorageService

logger = get_logger(__name__)

router = APIRouter()


@router.post("/upload", response_model=UploadResult)
async def upload_file(
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    workspace: Workspace = Depends(require_workspace_context),
    member: WorkspaceMember = Depends(require_workspace_write),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UploadResult:
    """
    Upload a file to the workspace storage.

    Requires workspace write permissions.
    """
    try:
        # Parse tags if provided
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Initialize storage service
        storage_service = StorageService(db, workspace.id)

        # Upload file
        result = await storage_service.upload_file(
            file=file,
            uploaded_by=current_user.id,
            description=description,
            tags=tag_list
        )

        logger.info(
            "File uploaded successfully",
            file_id=result.file_id,
            filename=result.filename,
            workspace_id=workspace.id,
            user_id=current_user.id
        )

        return result

    except ValueError as e:
        logger.error("File upload validation error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("File upload failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )


@router.get("/files", response_model=FileListResponse)
async def list_files(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in filename and description"),
    file_type: Optional[str] = Query(None, description="Filter by file type"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    workspace: Workspace = Depends(require_workspace_context),
    member: WorkspaceMember = Depends(require_workspace_read),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileListResponse:
    """
    List files in the workspace storage.

    Requires workspace read permissions.
    """
    try:
        # Parse tags if provided
        tag_list = []
        if tags:
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]

        # Initialize storage service
        storage_service = StorageService(db, workspace.id)

        # List files with filters
        result = await storage_service.list_files(
            page=page,
            limit=limit,
            search=search,
            file_type=file_type,
            tags=tag_list
        )

        logger.info(
            "Files listed successfully",
            workspace_id=workspace.id,
            user_id=current_user.id,
            page=page,
            limit=limit,
            total_files=result.total
        )

        return result

    except Exception as e:
        logger.error("File listing failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list files"
        )


@router.get("/files/{file_id}", response_model=FileResponse)
async def get_file_details(
    file_id: UUID,
    workspace: Workspace = Depends(require_workspace_context),
    member: WorkspaceMember = Depends(require_workspace_read),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> FileResponse:
    """
    Get detailed information about a specific file.

    Requires workspace read permissions.
    """
    try:
        # Initialize storage service
        storage_service = StorageService(db, workspace.id)

        # Get file details
        file_obj = await storage_service.get_file_by_id(file_id)

        if not file_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        # Log file access
        await storage_service.log_file_access(
            file_id=file_id,
            user_id=current_user.id,
            action="view"
        )

        logger.info(
            "File details retrieved",
            file_id=file_id,
            workspace_id=workspace.id,
            user_id=current_user.id
        )

        return FileResponse(
            id=file_obj.id,
            filename=file_obj.filename,
            original_filename=file_obj.original_filename,
            file_size=file_obj.file_size,
            content_type=file_obj.content_type,
            description=file_obj.description,
            tags=file_obj.tags,
            status=file_obj.status,
            uploaded_by=file_obj.uploaded_by,
            created_at=file_obj.created_at,
            updated_at=file_obj.updated_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get file details", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file details"
        )


@router.delete("/files/{file_id}", response_model=MessageResponse)
async def delete_file(
    file_id: UUID,
    hard_delete: bool = Query(False, description="Permanently delete file"),
    workspace: Workspace = Depends(require_workspace_context),
    member: WorkspaceMember = Depends(require_workspace_write),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> MessageResponse:
    """
    Delete a file from the workspace storage.

    Requires workspace write permissions.
    By default performs soft delete, use hard_delete=true for permanent deletion.
    """
    try:
        # Initialize storage service
        storage_service = StorageService(db, workspace.id)

        # Check if file exists and belongs to workspace
        file_obj = await storage_service.get_file_by_id(file_id)

        if not file_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        # Delete file
        if hard_delete:
            await storage_service.hard_delete_file(file_id, current_user.id)
            message = "File permanently deleted"
        else:
            await storage_service.soft_delete_file(file_id, current_user.id)
            message = "File deleted"

        logger.info(
            "File deleted successfully",
            file_id=file_id,
            filename=file_obj.filename,
            workspace_id=workspace.id,
            user_id=current_user.id,
            hard_delete=hard_delete
        )

        return MessageResponse(message=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File deletion failed", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File deletion failed"
        )


@router.post("/files/{file_id}/signed-url", response_model=SignedUrlResult)
async def generate_signed_url(
    file_id: UUID,
    request: SignedUrlRequest,
    workspace: Workspace = Depends(require_workspace_context),
    member: WorkspaceMember = Depends(require_workspace_read),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SignedUrlResult:
    """
    Generate a signed URL for secure file access.

    Requires workspace read permissions.
    """
    try:
        # Initialize storage service
        storage_service = StorageService(db, workspace.id)

        # Check if file exists and belongs to workspace
        file_obj = await storage_service.get_file_by_id(file_id)

        if not file_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        # Generate signed URL
        signed_url = await storage_service.generate_signed_url(
            file_id=file_id,
            expires_in=request.expires_in,
            operation=request.operation
        )

        # Log file access
        await storage_service.log_file_access(
            file_id=file_id,
            user_id=current_user.id,
            action=f"signed_url_{request.operation}"
        )

        logger.info(
            "Signed URL generated",
            file_id=file_id,
            workspace_id=workspace.id,
            user_id=current_user.id,
            operation=request.operation,
            expires_in=request.expires_in
        )

        return SignedUrlResult(
            url=signed_url,
            expires_in=request.expires_in,
            operation=request.operation
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Signed URL generation failed", error=str(e), file_id=file_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate signed URL"
        )


@router.get("/stats", response_model=StorageStatsResponse)
async def get_storage_stats(
    workspace: Workspace = Depends(require_workspace_context),
    member: WorkspaceMember = Depends(require_workspace_read),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> StorageStatsResponse:
    """
    Get storage statistics for the workspace.

    Requires workspace read permissions.
    """
    try:
        # Initialize storage service
        storage_service = StorageService(db, workspace.id)

        # Get storage stats
        stats = await storage_service.get_storage_stats()

        logger.info(
            "Storage stats retrieved",
            workspace_id=workspace.id,
            user_id=current_user.id,
            total_files=stats.total_files,
            total_size=stats.total_size
        )

        return stats

    except Exception as e:
        logger.error("Failed to get storage stats", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get storage statistics"
        )
