import io
import os
import logging
from fastapi import HTTPException
from googleapiclient.http import HttpError, MediaIoBaseUpload

from services.google_auth import get_drive_service

logger = logging.getLogger(__name__)

IGNORED_FOLDERS = ['Google AI Studio', 'My Drive', 'Shared with me', 'Recent', 'Starred', 'Trash', '.obsidian', '.trash']

def list_folders():
    try:
        logger.debug("Fetching root folders from Google Drive.")
        drive_service = get_drive_service()
        query = (
            "'root' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        folders = [f for f in results.get('files', []) if f['name'] not in IGNORED_FOLDERS]
        logger.info("Listed %d root folders.", len(folders))
        return {"folders": folders}
    except Exception as e:
        logger.error("Failed to list folders: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

def list_subfolders(folder_id: str):
    try:
        logger.debug("Fetching subfolders for folder_id=%s.", folder_id)
        drive_service = get_drive_service()
        query = (
            f"'{folder_id}' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        subfolders = [f for f in results.get('files', []) if f['name'] not in IGNORED_FOLDERS]
        logger.info("Listed %d subfolders for folder_id=%s.", len(subfolders), folder_id)
        return {"subfolders": subfolders}
    except HttpError as e:
        if e.resp.status == 404:
            logger.warning("Folder not found: folder_id=%s.", folder_id)
            raise HTTPException(status_code=404, detail="Folder not found")
        logger.error("Google Drive API error listing subfolders for folder_id=%s: %s", folder_id, e)
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error listing subfolders for folder_id=%s: %s", folder_id, e)
        raise HTTPException(status_code=500, detail=str(e))

def upload_file_to_drive(file_name: str, content: str, folder_id: str) -> str:
    try:
        logger.debug("Uploading '%s' to folder_id=%s.", file_name, folder_id)
        drive_service = get_drive_service()
        file_metadata = {
            'name': file_name,
            'mimeType': 'text/markdown',
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(
            io.BytesIO(content.encode('utf-8')),
            mimetype='text/markdown',
            resumable=True
        )
        file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        file_id = file.get('id')
        logger.info("File '%s' uploaded successfully. file_id=%s.", file_name, file_id)
        return file_id
    except HttpError as e:
        if e.resp.status == 404:
            logger.warning("Folder not found during upload: folder_id=%s.", folder_id)
            raise HTTPException(status_code=404, detail="Folder not found")
        logger.error("Google Drive API error uploading '%s': %s", file_name, e)
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error uploading '%s': %s", file_name, e)
        raise HTTPException(status_code=500, detail=str(e))
    
def save_photo_to_drive(
        file_name: str, 
        content: bytes, 
        content_type: str,
        folder_id: str = None
    ) -> dict:
    try:
        logger.debug("Saving photo '%s' (%s, %d bytes) to Google Drive.", file_name, content_type, len(content))
        drive_service = get_drive_service()

        escaped_file_name = file_name.replace("'", "\\'")

        if folder_id is None:
            folder_id = os.getenv('DEFAULT_PHOTO_FOLDER_ID')

        file_metadata = {
            'name': file_name,
            'parents': [folder_id] if folder_id else []
        }
        
        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype=content_type,
            resumable=True
        )
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        file_id = file.get('id')
        logger.info("Photo '%s' saved successfully. file_id=%s.", file_name, file_id)
        return {
            'id': file_id
        }
    except HttpError as e:
        if e.resp.status == 404:
            logger.warning("Folder not found saving photo '%s'.", file_name)
            raise HTTPException(status_code=404, detail="Folder not found")
        logger.error("Google Drive API error saving photo '%s': %s", file_name, e)
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error saving photo '%s': %s", file_name, e)
        raise HTTPException(status_code=500, detail=str(e))


def delete_file_from_drive(file_id: str) -> None:
    try:
        logger.debug("Deleting file_id=%s from Google Drive.", file_id)
        drive_service = get_drive_service()
        drive_service.files().delete(fileId=file_id).execute()
        logger.info("File file_id=%s deleted successfully.", file_id)
    except Exception as e:
        logger.error("Failed to delete file_id=%s: %s", file_id, e)
        raise HTTPException(status_code=500, detail=str(e))


def get_or_create_folder(
        folder_name: str, 
        parent_folder_id: str = None) -> str:
    try:
        logger.debug("Getting or creating folder '%s' in Google Drive.", folder_name)
        drive_service = get_drive_service()
        
        escaped_folder_name = folder_name.replace("'", "\\'")
        
        query = (
            f"name = '{escaped_folder_name}' and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        folders = results.get('files', [])  
        
        if folders:
            folder_id = folders[0]['id']
            logger.info("Folder '%s' already exists. folder_id=%s.", folder_name, folder_id)
            return folder_id
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            if parent_folder_id:
                file_metadata['parents'] = [parent_folder_id]
                
            folder = drive_service.files().create(body=file_metadata, fields='id').execute()
            folder_id = folder.get('id')
            logger.info("Folder '%s' created successfully. folder_id=%s.", folder_name, folder_id)
            return folder_id
            
    except HttpError as e:
        logger.error("Google Drive API error getting or creating folder '%s': %s", folder_name, e)
        raise HTTPException(status_code=e.resp.status, detail=str(e))
    except Exception as e:
        logger.error("Unexpected error getting or creating folder '%s': %s", folder_name, e)
        raise HTTPException(status_code=500, detail=str(e))