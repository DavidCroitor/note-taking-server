import os
import asyncio
import logging
import time

from slowapi import Limiter

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Request
from typing import List

from schemas import NoteRequest
from services.google_drive import get_or_create_folder, save_photo_to_drive, upload_file_to_drive, delete_file_from_drive
from services.gemini_service import transcribe_images_to_markdown

def get_api_key(request: Request):
    return request.headers.get("X-API-Key")

limiter = Limiter(key_func=get_api_key)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notes", tags=["notes"])

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES = 15


async def validate_and_read_files(files: List[UploadFile]) -> List[dict]:
    logger.debug(f"Validating {len(files)} uploaded files.")
    if len(files) > MAX_FILES:
        logger.warning(f"Too many files uploaded: {len(files)}. Maximum allowed is {MAX_FILES}.")
        raise HTTPException(status_code=413, detail=f"Too many files uploaded. Maximum allowed: {MAX_FILES}")

    image_inputs = []
    for file in files:
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            logger.warning(f"Unsupported file type: {file.content_type} for file '{file.filename}'. Allowed types: {ALLOWED_IMAGE_TYPES}")
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has unsupported type '{file.content_type}'. Allowed: {ALLOWED_IMAGE_TYPES}"
            )
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            logger.warning(f"File '{file.filename}' exceeds maximum size: {len(content)} bytes. Limit is {MAX_FILE_SIZE} bytes.")
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' exceeds the maximum size of {MAX_FILE_SIZE} bytes."
            )
        image_inputs.append({"filename": file.filename, "content": content, "content_type": file.content_type})
    logger.debug(f"All files validated successfully. Total valid files: {len(image_inputs)}.")
    return image_inputs


def save_images_to_drive(
        image_inputs: List[dict], 
        folder_name: str = None
    ) -> List[str]:
    logger.debug(f"Saving {len(image_inputs)} images to Google Drive.")
    saved_ids = []
    default_folder_id = os.getenv('DEFAULT_PHOTO_FOLDER_ID')
    if folder_name:
        folder_id = get_or_create_folder(folder_name, parent_folder_id=default_folder_id)
    else:
        folder_id = default_folder_id
    for image in image_inputs:
        result = save_photo_to_drive(
            file_name=image["filename"],
            content=image["content"],
            content_type=image["content_type"],
            folder_id=folder_id
        )
        saved_ids.append(result["id"])
    logger.debug(f"All images saved to Google Drive successfully. Saved file IDs: {saved_ids}.")
    return saved_ids


def cleanup_saved_photos(photo_ids: List[str]) -> None:
    logger.debug(f"Cleaning up {len(photo_ids)} saved photos.")
    for photo_id in photo_ids:
        try:
            delete_file_from_drive(photo_id)
        except Exception as cleanup_error:
            logger.error(f"Failed to delete photo with ID {photo_id} during cleanup: {cleanup_error}")

    logger.debug("Cleanup of saved photos completed.")

@router.post("")
def create_note(request: NoteRequest):
    logger.info("Creating note '%s'.", request.filename)
    resolved_folder_id = request.folder_id or os.getenv('DEFAULT_FOLDER_ID')
    if not resolved_folder_id:
        logger.warning("No folder_id provided and DEFAULT_FOLDER_ID is not set.")
        raise HTTPException(status_code=400, detail="No folder_id provided and DEFAULT_FOLDER_ID is not set.")
    file_id = upload_file_to_drive(request.filename, request.content, resolved_folder_id)
    logger.info("Note '%s' created successfully. file_id=%s.", request.filename, file_id)
    return {"message": "Note created successfully", "file_id": file_id}


@router.post("/from-images")
@limiter.limit("10/minute")
async def create_note_from_images(
    request: Request,
    filename: str = Form(..., description="Name for the resulting markdown file"),
    files: List[UploadFile] = File(..., description="One or more handwritten note photos"),
    folder_id: str = Form(None, description="Google Drive folder ID")
):
    logger.info("Received request to create note from %d image(s). Filename: '%s'.", len(files), filename)
    image_inputs = await validate_and_read_files(files)

    resolved_folder_id = folder_id or os.getenv('DEFAULT_FOLDER_ID')
    if not resolved_folder_id:
        logger.warning("No folder_id provided and DEFAULT_FOLDER_ID is not set.")
        raise HTTPException(status_code=400, detail="No folder_id provided and DEFAULT_FOLDER_ID is not set.")

    try:
        markdown_content = await transcribe_images_to_markdown(image_inputs)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Gemini transcription failed for '%s': %s", filename, e)
        raise HTTPException(status_code=500, detail=f"Gemini transcription failed: {e}")

    saved_photo_ids: List[str] = []
    try:
        saved_photo_ids = save_images_to_drive(
            image_inputs, 
            folder_name = filename)

        safe_filename = Path(filename).name
        if not safe_filename.lower().endswith('.md'):
            safe_filename += '.md'
        file_id = await asyncio.to_thread(upload_file_to_drive, safe_filename, markdown_content, resolved_folder_id)

    except Exception as e:
        logger.error("Drive upload failed for '%s'. Triggering cleanup for %d orphaned photo(s).", filename, len(saved_photo_ids))
        cleanup_saved_photos(saved_photo_ids)
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

    logger.info("Note '%s' created successfully from %d image(s). file_id=%s.", safe_filename, len(files), file_id)
    return {
        "message": "Note created successfully from images",
        "file_id": file_id,
        "images_processed": len(files),
        "markdown_preview": markdown_content[:300] + "..." if len(markdown_content) > 300 else markdown_content
    }
