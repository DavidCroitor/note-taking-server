from fastapi import APIRouter

from services.google_drive import list_folders, list_subfolders

router = APIRouter(prefix="/folders", tags=["folders"])


@router.get("")
def get_folders():
    return list_folders()


@router.get("/{folder_id}/subfolders")
def get_subfolders(folder_id: str):
    return list_subfolders(folder_id)
