import io
import os
from fastapi import HTTPException
from googleapiclient.http import MediaIoBaseUpload

from services.google_auth import get_drive_service


IGNORED_FOLDERS = ['Google AI Studio', 'My Drive', 'Shared with me', 'Recent', 'Starred', 'Trash', '.obsidian', '.trash']

def list_folders():
    try:
        drive_service = get_drive_service()
        query = (
            "'root' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        folders = [f for f in results.get('files', []) if f['name'] not in IGNORED_FOLDERS]
        return {"folders": folders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def list_subfolders(folder_id: str):
    try:
        drive_service = get_drive_service()
        query = (
            f"'{folder_id}' in parents and "
            "mimeType = 'application/vnd.google-apps.folder' and "
            "trashed = false"
        )
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        subfolders = [f for f in results.get('files', []) if f['name'] not in IGNORED_FOLDERS]
        return {"subfolders": subfolders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def upload_file_to_drive(file_name: str, content: str, folder_id: str) -> str:
    try:
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
        return file.get('id')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
def save_photo_to_drive(file_name: str, content: bytes, content_type: str) -> dict:
    try:
        drive_service = get_drive_service()
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
        return {
            'id': file_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def delete_file_from_drive(file_id: str) -> None:
    try:
        drive_service = get_drive_service()
        drive_service.files().delete(fileId=file_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
