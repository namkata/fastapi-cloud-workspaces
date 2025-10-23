"""
Storage management API routes.
"""
import io
from typing import List, Optional

from app.core.database import get_db_session
from app.core.logger import logger
from app.core.rbac import require_permission
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.storage.schemas import (
    FileListResponse,
    FileRecordResponse,
    FolderCreateRequest,
    FolderResponse,
    FolderUpdateRequest,
)
from app.modules.storage.service import StorageService
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
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

# from app.tasks.file_processing import process_file_upload

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/{workspace_id}/files", response_model=FileListResponse)
async def list_files(
    workspace_id: int,
    folder_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """List files in workspace or folder."""
    try:
        storage_service = StorageService(session)
        files, total = await storage_service.list_files(
            workspace_id=workspace_id,
            folder_id=folder_id,
            skip=skip,
            limit=limit,
            search=search
        )

        logger.info(f"Listed {len(files)} files in workspace {workspace_id}")
        return FileListResponse(
            files=[FileRecordResponse.from_orm(file) for file in files],
            total=total,
            skip=skip,
            limit=limit
        )

    except Exception as e:
        logger.error(f"Error listing files: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list files"
        )


@router.post("/{workspace_id}/upload", response_model=FileRecordResponse)
async def upload_file(
    workspace_id: int,
    file: UploadFile = File(...),
    folder_id: Optional[int] = Form(None),
    description: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    """Upload file to workspace."""
    try:
        # Read file content
        content = await file.read()

        storage_service = StorageService(session)
        file_record = await storage_service.upload_file(
            workspace_id=workspace_id,
            filename=file.filename,
            content=content,
            content_type=file.content_type,
            folder_id=folder_id,
            uploaded_by=current_user.id
        )

        # Queue file processing
        # process_file_upload.delay(file_record.id)

        logger.info(f"File uploaded: {file.filename} to workspace {workspace_id}")
        return FileRecordResponse.from_orm(file_record)

    except ValueError as e:
        logger.warning(f"File upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )


@router.get("/{workspace_id}/files/{file_id}", response_model=FileRecordResponse)
async def get_file_info(
    workspace_id: int,
    file_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("read"))
):
    """Get file information."""
    try:
        storage_service = StorageService(session)
        file_record = await storage_service.get_file(file_id)

        if not file_record or file_record.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        return FileRecordResponse.from_orm(file_record)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get file information"
        )


@router.get("/{workspace_id}/files/{file_id}/download")
async def download_file(
    workspace_id: int,
    file_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("read"))
):
    """Download file content."""
    try:
        storage_service = StorageService(session)
        file_record = await storage_service.get_file(file_id)

        if not file_record or file_record.workspace_id != workspace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        # Get file content from storage
        content = await storage_service.get_file_content(file_record.file_path)

        # Update download count
        await storage_service.increment_download_count(file_id)

        logger.info(f"File downloaded: {file_record.filename}")

        return StreamingResponse(
            io.BytesIO(content),
            media_type=file_record.content_type,
            headers={
                "Content-Disposition": f"attachment; filename={file_record.filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File download error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File download failed"
        )


@router.delete("/{workspace_id}/files/{file_id}")
async def delete_file(
    workspace_id: int,
    file_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("write"))
):
    """Delete file."""
    try:
        storage_service = StorageService(session)
        success = await storage_service.delete_file(file_id, workspace_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )

        logger.info(f"File deleted: {file_id}")
        return {"message": "File deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File deletion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File deletion failed"
        )


@router.get("/{workspace_id}/folders", response_model=List[FolderResponse])
async def list_folders(
    workspace_id: int,
    parent_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("read"))
):
    """List folders in workspace."""
    try:
        storage_service = StorageService(session)
        folders = await storage_service.list_folders(workspace_id, parent_id)

        logger.info(f"Listed {len(folders)} folders in workspace {workspace_id}")
        return [FolderResponse.from_orm(folder) for folder in folders]

    except Exception as e:
        logger.error(f"Error listing folders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list folders"
        )


@router.post("/{workspace_id}/folders", response_model=FolderResponse)
async def create_folder(
    workspace_id: int,
    folder_data: FolderCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("write"))
):
    """Create new folder."""
    try:
        storage_service = StorageService(session)
        folder = await storage_service.create_folder(
            workspace_id=workspace_id,
            name=request.name,
            parent_id=request.parent_id,
            created_by=current_user.id
        )

        logger.info(f"Folder created: {request.name} in workspace {workspace_id}")
        return FolderResponse.from_orm(folder)

    except ValueError as e:
        logger.warning(f"Folder creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Folder creation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Folder creation failed"
        )


@router.put("/{workspace_id}/folders/{folder_id}", response_model=FolderResponse)
async def update_folder(
    workspace_id: int,
    folder_id: int,
    folder_data: FolderUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("write"))
):
    """Update folder information."""
    try:
        storage_service = StorageService(session)
        folder = await storage_service.update_folder(
            folder_id,
            workspace_id,
            request.dict(exclude_unset=True)
        )

        if not folder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Folder not found"
            )

        logger.info(f"Folder updated: {folder.name}")
        return FolderResponse.from_orm(folder)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Folder update failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Folder update error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Folder update failed"
        )


@router.delete("/{workspace_id}/folders/{folder_id}")
async def delete_folder(
    workspace_id: int,
    folder_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("write"))
):
    """Delete folder and its contents."""
    try:
        storage_service = StorageService(session)
        success = await storage_service.delete_folder(folder_id, workspace_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Folder not found"
            )

        logger.info(f"Folder deleted: {folder_id}")
        return {"message": "Folder deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Folder deletion error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Folder deletion failed"
        )


@router.get("/{workspace_id}/usage")
async def get_storage_usage(
    workspace_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
    _: None = Depends(require_permission("read"))
):
    """Get workspace storage usage statistics."""
    try:
        storage_service = StorageService(session)
        usage = await storage_service.get_workspace_usage(workspace_id)

        logger.info(f"Storage usage retrieved for workspace {workspace_id}")
        return usage

    except Exception as e:
        logger.error(f"Error getting storage usage: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get storage usage"
        )
