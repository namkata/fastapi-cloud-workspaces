"""
File processing tasks for image optimization, video transcoding, etc.
"""
import asyncio
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, Optional

import ffmpeg
from app.core.celery_app import celery_app
from app.core.database import get_db_session_context
from app.core.logger import logger
from app.modules.storage.models import FileRecord
from app.modules.storage.service import StorageService
from celery import current_task
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@celery_app.task(bind=True)
def process_image(self, file_record_id: str):
    """
    Process and optimize uploaded images.
    """
    return asyncio.run(_process_image_async(file_record_id))


async def _process_image_async(file_record_id: str):
    """Async implementation of image processing."""
    try:
        async with get_db_session_context() as session:
            # Get file record
            stmt = select(FileRecord).where(FileRecord.id == file_record_id)
            result = await session.execute(stmt)
            file_record = result.scalar_one_or_none()

            if not file_record:
                raise ValueError(f"File record {file_record_id} not found")

            # Check if it's an image file
            if not file_record.content_type.startswith('image/'):
                logger.warning(f"File {file_record.filename} is not an image")
                return {"status": "skipped", "reason": "not_an_image"}

            storage_service = StorageService()

            # Download original file
            original_content = await storage_service.get_file_content(file_record.file_path)

            with tempfile.NamedTemporaryFile(suffix=f".{file_record.filename.split('.')[-1]}") as temp_file:
                temp_file.write(original_content)
                temp_file.flush()

                # Open and process image
                with Image.open(temp_file.name) as img:
                    original_size = img.size
                    original_format = img.format

                    # Create thumbnails
                    thumbnails = {}

                    # Small thumbnail (150x150)
                    small_thumb = img.copy()
                    small_thumb.thumbnail((150, 150), Image.Resampling.LANCZOS)

                    # Medium thumbnail (300x300)
                    medium_thumb = img.copy()
                    medium_thumb.thumbnail((300, 300), Image.Resampling.LANCZOS)

                    # Large thumbnail (800x800)
                    large_thumb = img.copy()
                    large_thumb.thumbnail((800, 800), Image.Resampling.LANCZOS)

                    # Save thumbnails
                    for size, thumb_img in [("small", small_thumb), ("medium", medium_thumb), ("large", large_thumb)]:
                        with tempfile.NamedTemporaryFile(suffix=".jpg") as thumb_file:
                            # Convert to RGB if necessary (for JPEG)
                            if thumb_img.mode in ("RGBA", "P"):
                                thumb_img = thumb_img.convert("RGB")

                            thumb_img.save(thumb_file.name, "JPEG", quality=85, optimize=True)
                            thumb_file.seek(0)

                            # Upload thumbnail
                            thumb_path = f"{file_record.file_path}_thumb_{size}.jpg"
                            await storage_service.upload_file_content(
                                content=thumb_file.read(),
                                file_path=thumb_path,
                                content_type="image/jpeg"
                            )

                            thumbnails[size] = {
                                "path": thumb_path,
                                "size": thumb_img.size
                            }

                    # Update file record with processing info
                    file_record.metadata = file_record.metadata or {}
                    file_record.metadata.update({
                        "processed": True,
                        "original_size": original_size,
                        "thumbnails": thumbnails,
                        "processed_at": datetime.utcnow().isoformat()
                    })

                    await session.commit()

                    logger.info(f"Image processing completed for {file_record.filename}")
                    return {
                        "status": "completed",
                        "original_size": original_size,
                        "thumbnails_created": len(thumbnails)
                    }

    except Exception as e:
        logger.error(f"Error processing image {file_record_id}: {str(e)}")
        raise


@celery_app.task(bind=True)
def process_video(self, file_record_id: str):
    """
    Process and transcode uploaded videos.
    """
    return asyncio.run(_process_video_async(file_record_id))


async def _process_video_async(file_record_id: str):
    """Async implementation of video processing."""
    try:
        async with get_db_session_context() as session:
            # Get file record
            stmt = select(FileRecord).where(FileRecord.id == file_record_id)
            result = await session.execute(stmt)
            file_record = result.scalar_one_or_none()

            if not file_record:
                raise ValueError(f"File record {file_record_id} not found")

            # Check if it's a video file
            if not file_record.content_type.startswith('video/'):
                logger.warning(f"File {file_record.filename} is not a video")
                return {"status": "skipped", "reason": "not_a_video"}

            storage_service = StorageService()

            # Download original file
            original_content = await storage_service.get_file_content(file_record.file_path)

            with tempfile.NamedTemporaryFile(suffix=f".{file_record.filename.split('.')[-1]}") as temp_input:
                temp_input.write(original_content)
                temp_input.flush()

                # Get video info
                probe = ffmpeg.probe(temp_input.name)
                video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')

                original_width = int(video_info['width'])
                original_height = int(video_info['height'])
                duration = float(video_info.get('duration', 0))

                # Create preview thumbnail (at 10% of duration)
                thumbnail_time = duration * 0.1 if duration > 0 else 1

                with tempfile.NamedTemporaryFile(suffix=".jpg") as thumb_file:
                    (
                        ffmpeg
                        .input(temp_input.name, ss=thumbnail_time)
                        .output(thumb_file.name, vframes=1, format='image2', vcodec='mjpeg')
                        .overwrite_output()
                        .run(quiet=True)
                    )

                    # Upload thumbnail
                    thumb_file.seek(0)
                    thumb_path = f"{file_record.file_path}_thumb.jpg"
                    await storage_service.upload_file_content(
                        content=thumb_file.read(),
                        file_path=thumb_path,
                        content_type="image/jpeg"
                    )

                # Create compressed version if video is large
                compressed_versions = {}

                if original_width > 1280 or file_record.file_size > 50 * 1024 * 1024:  # 50MB
                    with tempfile.NamedTemporaryFile(suffix=".mp4") as compressed_file:
                        # Compress to 720p
                        (
                            ffmpeg
                            .input(temp_input.name)
                            .output(
                                compressed_file.name,
                                vcodec='libx264',
                                acodec='aac',
                                vf='scale=1280:720:force_original_aspect_ratio=decrease',
                                crf=23,
                                preset='medium'
                            )
                            .overwrite_output()
                            .run(quiet=True)
                        )

                        # Upload compressed version
                        compressed_file.seek(0)
                        compressed_path = f"{file_record.file_path}_720p.mp4"
                        await storage_service.upload_file_content(
                            content=compressed_file.read(),
                            file_path=compressed_path,
                            content_type="video/mp4"
                        )

                        compressed_versions["720p"] = {
                            "path": compressed_path,
                            "resolution": "1280x720"
                        }

                # Update file record with processing info
                file_record.metadata = file_record.metadata or {}
                file_record.metadata.update({
                    "processed": True,
                    "original_resolution": f"{original_width}x{original_height}",
                    "duration": duration,
                    "thumbnail": thumb_path,
                    "compressed_versions": compressed_versions,
                    "processed_at": datetime.utcnow().isoformat()
                })

                await session.commit()

                logger.info(f"Video processing completed for {file_record.filename}")
                return {
                    "status": "completed",
                    "original_resolution": f"{original_width}x{original_height}",
                    "duration": duration,
                    "compressed_versions": len(compressed_versions)
                }

    except Exception as e:
        logger.error(f"Error processing video {file_record_id}: {str(e)}")
        raise


@celery_app.task(bind=True)
def extract_document_text(self, file_record_id: str):
    """
    Extract text content from documents for search indexing.
    """
    return asyncio.run(_extract_document_text_async(file_record_id))


async def _extract_document_text_async(file_record_id: str):
    """Async implementation of document text extraction."""
    try:
        async with get_db_session_context() as session:
            # Get file record
            stmt = select(FileRecord).where(FileRecord.id == file_record_id)
            result = await session.execute(stmt)
            file_record = result.scalar_one_or_none()

            if not file_record:
                raise ValueError(f"File record {file_record_id} not found")

            # Check if it's a document file
            document_types = ['application/pdf', 'text/plain', 'application/msword',
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

            if file_record.content_type not in document_types:
                logger.warning(f"File {file_record.filename} is not a supported document type")
                return {"status": "skipped", "reason": "unsupported_document_type"}

            storage_service = StorageService()

            # Download original file
            original_content = await storage_service.get_file_content(file_record.file_path)

            extracted_text = ""

            if file_record.content_type == 'text/plain':
                # Plain text file
                extracted_text = original_content.decode('utf-8', errors='ignore')

            elif file_record.content_type == 'application/pdf':
                # PDF file - would need PyPDF2 or similar
                # For now, just mark as processed
                extracted_text = "[PDF content - text extraction not implemented]"

            elif file_record.content_type in ['application/msword',
                                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                # Word documents - would need python-docx
                # For now, just mark as processed
                extracted_text = "[Word document - text extraction not implemented]"

            # Update file record with extracted text
            file_record.metadata = file_record.metadata or {}
            file_record.metadata.update({
                "text_extracted": True,
                "extracted_text": extracted_text[:1000],  # Store first 1000 chars
                "text_length": len(extracted_text),
                "processed_at": datetime.utcnow().isoformat()
            })

            await session.commit()

            logger.info(f"Text extraction completed for {file_record.filename}")
            return {
                "status": "completed",
                "text_length": len(extracted_text)
            }

    except Exception as e:
        logger.error(f"Error extracting text from {file_record_id}: {str(e)}")
        raise


@celery_app.task(bind=True)
def process_file_upload(self, file_record_id: str):
    """
    Main task to process newly uploaded files based on their type.
    """
    return asyncio.run(_process_file_upload_async(file_record_id))


async def _process_file_upload_async(file_record_id: str):
    """Async implementation of file upload processing."""
    try:
        async with get_db_session_context() as session:
            # Get file record
            stmt = select(FileRecord).where(FileRecord.id == file_record_id)
            result = await session.execute(stmt)
            file_record = result.scalar_one_or_none()

            if not file_record:
                raise ValueError(f"File record {file_record_id} not found")

            results = {}

            # Process based on file type
            if file_record.content_type.startswith('image/'):
                # Queue image processing
                image_task = process_image.delay(file_record_id)
                results["image_processing"] = image_task.id

            elif file_record.content_type.startswith('video/'):
                # Queue video processing
                video_task = process_video.delay(file_record_id)
                results["video_processing"] = video_task.id

            elif file_record.content_type in ['application/pdf', 'text/plain',
                                            'application/msword',
                                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                # Queue text extraction
                text_task = extract_document_text.delay(file_record_id)
                results["text_extraction"] = text_task.id

            logger.info(f"File processing queued for {file_record.filename}: {results}")
            return results

    except Exception as e:
        logger.error(f"Error queuing file processing for {file_record_id}: {str(e)}")
        raise
