"""Authentication module for Google Calendar API."""

import os
import pickle
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger

# Calendar API scope for read/write access
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_service(
    credentials_path: str = "credentials.json", token_path: str = "calendar_token.json"
) -> Optional[any]:
    """Authenticate with the Google Calendar API and return the service.

    Args:
        credentials_path: Path to the credentials file.
        token_path: Path to save/load the token file.

    Returns:
        Authenticated calendar service or None if authentication fails.
    """
    try:
        creds = None

        # The file token.json stores the user's access and refresh tokens
        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        # If there are no valid credentials, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)

        # Build and return the service
        service = build("calendar", "v3", credentials=creds)
        return service

    except Exception as e:
        logger.exception(f"Error authenticating with Google Calendar API: {e}")
        return None
