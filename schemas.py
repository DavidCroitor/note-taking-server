from pydantic import BaseModel


class NoteRequest(BaseModel):
    filename: str
    content: str
    folder_id: str = None