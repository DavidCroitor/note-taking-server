import os
import json
import logging
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/drive']
TOKEN_PATH = os.getenv('GOOGLE_TOKEN_PATH', 'token.json')

logger = logging.getLogger(__name__)


def load_credentials() -> Credentials:
    if not os.path.exists(TOKEN_PATH):
        logger.critical("No credentials found at %s. Cannot initialize Google Auth.", TOKEN_PATH)
        raise RuntimeError(
            f"No credentials found at {TOKEN_PATH}. "
            "Run the auth flow locally or set GOOGLE_TOKEN_PATH."
        )
    logger.debug("Loading credentials from %s", TOKEN_PATH)
    return Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

def get_drive_service():
    logger.debug("Initializing Google Drive service.")
    creds = load_credentials()
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            logger.info("Google credentials expired. Attempting token refresh...")
            try:
                creds.refresh(Request())
                logger.info("Access token refreshed successfully.")
            except Exception as e:
                logger.error("Failed to refresh Google credentials: %s", e)
                raise RuntimeError(
                    f"Token refresh failed: {e}. "
                    "The refresh token in your Secret File may be revoked. "
                    "Re-run the auth flow locally and update the Secret File."
                ) from e
        else:
            logger.error("Credentials invalid and no refresh token available.")
            raise RuntimeError(
                "Credentials invalid and no refresh token available. "
                "Update the Secret File"
            )

    logger.debug("Google Drive service successfully initialized.")
    return build('drive', 'v3', credentials=creds)