import os
import asyncio

from slowapi import Limiter

from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, logger, Request
from typing import List

from schemas import NoteRequest
from services.google_drive import save_photo_to_drive, upload_file_to_drive, delete_file_from_drive
from services.gemini_service import transcribe_images_to_markdown

def get_api_key(request: Request):
    return request.headers.get("X-API-Key")

limiter = Limiter(key_func=get_api_key)

router = APIRouter(prefix="/notes", tags=["notes"])

ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp']

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILES = 15


async def validate_and_read_files(files: List[UploadFile]) -> List[dict]:
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=413, detail=f"Too many files uploaded. Maximum allowed: {MAX_FILES}")

    image_inputs = []
    for file in files:
        if file.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"File '{file.filename}' has unsupported type '{file.content_type}'. Allowed: {ALLOWED_IMAGE_TYPES}"
            )
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File '{file.filename}' exceeds the maximum size of {MAX_FILE_SIZE} bytes."
            )
        image_inputs.append({"filename": file.filename, "content": content, "content_type": file.content_type})
    return image_inputs


def save_images_to_drive(image_inputs: List[dict]) -> List[str]:
    saved_ids = []
    for image in image_inputs:
        result = save_photo_to_drive(
            file_name=image["filename"],
            content=image["content"],
            content_type=image["content_type"]
        )
        saved_ids.append(result["id"])
    return saved_ids


def cleanup_saved_photos(photo_ids: List[str]) -> None:
    for photo_id in photo_ids:
        try:
            delete_file_from_drive(photo_id)
        except Exception as cleanup_error:
            logger.error(f"Failed to delete photo with ID {photo_id} during cleanup: {cleanup_error}")


@router.post("")
def create_note(request: NoteRequest):
    resolved_folder_id = request.folder_id or os.getenv('DEFAULT_FOLDER_ID')
    if not resolved_folder_id:
        raise HTTPException(status_code=400, detail="No folder_id provided and DEFAULT_FOLDER_ID is not set.")
    file_id = upload_file_to_drive(request.filename, request.content, resolved_folder_id)
    return {"message": "Note created successfully", "file_id": file_id}


@router.post("/from-images")
@limiter.limit("10/minute")
async def create_note_from_images(
    request: Request,
    files: List[UploadFile] = File(..., description="One or more handwritten note photos"),
    filename: str = Form(..., description="Name for the resulting markdown file"),
    folder_id: str = Form(None, description="Google Drive folder ID")
):
    image_inputs = await validate_and_read_files(files)

    resolved_folder_id = folder_id or os.getenv('DEFAULT_FOLDER_ID')
    if not resolved_folder_id:
        raise HTTPException(status_code=400, detail="No folder_id provided and DEFAULT_FOLDER_ID is not set.")

    try:
        markdown_content = await transcribe_images_to_markdown(image_inputs)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini transcription failed: {e}")

    saved_photo_ids: List[str] = []
    try:
        saved_photo_ids = save_images_to_drive(image_inputs)

        safe_filename = Path(filename).name
        if not safe_filename.lower().endswith('.md'):
            safe_filename += '.md'
        file_id = await asyncio.to_thread(upload_file_to_drive, safe_filename, markdown_content, resolved_folder_id)

    except Exception as e:
        cleanup_saved_photos(saved_photo_ids)
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message": "Note created successfully from images",
        "file_id": file_id,
        "images_processed": len(files),
        "markdown_preview": markdown_content[:300] + "..." if len(markdown_content) > 300 else markdown_content
    }
