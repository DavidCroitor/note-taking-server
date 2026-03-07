import io
import os
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from dotenv import load_dotenv

from main import app

load_dotenv()

client = TestClient(app)

FAKE_MARKDOWN = "# My Note\n- item 1\n- item 2"

@pytest.fixture(autouse=True)
def mock_openai():
    with patch(
        "routers.notes.transcribe_images_to_markdown",
        new=AsyncMock(return_value=FAKE_MARKDOWN)
    ):
        yield

@pytest.fixture(autouse=True)
def mock_drive():
    with patch("routers.notes.upload_file_to_drive", return_value="fake-file-id"):
        yield

def test_from_images_missing_api_key():
    response = client.post(
        "/notes/from-images",
        data={"filename": "my-note", "folder_id": "folder-123"},
        files=[("files", ("note.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg"))],
        headers={} 
    )
    assert response.status_code == 401

def test_from_images_openai_failure():
    with patch("routers.notes.transcribe_images_to_markdown", new=AsyncMock(side_effect=Exception("OpenAI is down!"))):
        response = client.post(
            "/notes/from-images",
            data={"filename": "my-note", "folder_id": "folder-123"},
            files=[("files", ("note.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg"))],
            headers={"x-API-Key": os.getenv("MY_SECRET_KEY_API_KEY")}
        )
        assert response.status_code == 500
        assert "OpenAI is down!" in response.json()["detail"]

def test_create_note_success():
    response = client.post(
        "/notes",
        json={"filename": "test-note", "content": "Hello World", "folder_id": "folder-123"},
        headers={"x-API-Key": os.getenv("MY_SECRET_KEY_API_KEY")}
    )
    assert response.status_code == 200
    assert response.json()["file_id"] == "fake-file-id"


def test_from_images_success():
    response = client.post(
        "/notes/from-images",
        data={"filename": "my-note", "folder_id": "folder-123"},
        files=[("files", ("note.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg"))],
        headers={"x-API-Key": os.getenv("MY_SECRET_KEY_API_KEY")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == "fake-file-id"
    assert data["images_processed"] == 1
    assert "markdown_preview" in data


def test_from_images_invalid_file_type():
    response = client.post(
        "/notes/from-images",
        data={"filename": "my-note", "folder_id": "folder-123"},
        files=[("files", ("note.pdf", io.BytesIO(b"fake-pdf-bytes"), "application/pdf"))],
        headers={"x-API-Key": os.getenv("MY_SECRET_KEY_API_KEY")}
    )
    assert response.status_code == 400
    assert "unsupported type" in response.json()["detail"]


def test_from_images_no_folder_id(monkeypatch):
    monkeypatch.delenv("DEFAULT_FOLDER_ID", raising=False)
    response = client.post(
        "/notes/from-images",
        data={"filename": "my-note"},
        files=[("files", ("note.jpg", io.BytesIO(b"fake-image-bytes"), "image/jpeg"))],
        headers={"x-API-Key": os.getenv("MY_SECRET_KEY_API_KEY")}
    )
    assert response.status_code == 400
    assert "DEFAULT_FOLDER_ID" in response.json()["detail"]