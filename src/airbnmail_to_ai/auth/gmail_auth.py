"""Gmail API authentication helper."""

import os
import pickle
from pathlib import Path
from typing import Optional

import google.auth.exceptions
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger


# If modifying these scopes, delete the token file.
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def authenticate(
    credentials_path: str = "credentials.json", token_path: str = "token.json"
) -> Optional[Credentials]:
    """Authenticate with the Gmail API.

    Args:
        credentials_path: Path to the credentials.json file.
        token_path: Path to store/load the token.json file.

    Returns:
        Valid credentials object or None if authentication fails.
    """
    credentials = None

    # Check if the token file exists and load credentials
    if os.path.exists(token_path):
        logger.info(f"Loading existing token from {token_path}")
        with open(token_path, "rb") as token:
            credentials = pickle.load(token)

    # Check if credentials are valid, refresh if expired
    if credentials and credentials.valid:
        logger.info("Credentials are valid")
        return credentials
    
    if credentials and credentials.expired and credentials.refresh_token:
        logger.info("Refreshing expired credentials")
        try:
            credentials.refresh(Request())
            logger.info("Credentials refreshed successfully")
        except google.auth.exceptions.RefreshError as e:
            logger.error(f"Failed to refresh credentials: {e}")
            credentials = None
    
    # If no valid credentials, start OAuth flow
    if not credentials:
        if not os.path.exists(credentials_path):
            logger.error(
                f"Credentials file not found at {credentials_path}. "
                "Please obtain one from Google Cloud Console."
            )
            return None
        
        try:
            logger.info(f"Starting OAuth flow with credentials from {credentials_path}")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            credentials = flow.run_local_server(port=0)
            logger.info("Authentication successful")
        except Exception as e:
            logger.exception(f"Error during authentication: {e}")
            return None
    
    # Save the credentials for the next run
    with open(token_path, "wb") as token:
        pickle.dump(credentials, token)
        logger.info(f"Credentials saved to {token_path}")
    
    return credentials


def validate_credentials(credentials: Credentials) -> bool:
    """Validate credentials by making a simple API call.

    Args:
        credentials: The credentials to validate.

    Returns:
        True if credentials are valid, False otherwise.
    """
    try:
        # Build the Gmail service
        service = build("gmail", "v1", credentials=credentials)
        
        # Make a simple API call
        profile = service.users().getProfile(userId="me").execute()
        
        logger.info(f"Successfully authenticated as: {profile.get('emailAddress')}")
        return True
    
    except HttpError as e:
        logger.error(f"API error: {e}")
        return False
    
    except Exception as e:
        logger.exception(f"Error validating credentials: {e}")
        return False


def main() -> None:
    """Main function to run the authentication flow."""
    logger.info("Starting Gmail API authentication")
    
    # Default paths
    credentials_path = "credentials.json"
    token_path = "token.json"
    
    # Check for credentials file
    if not os.path.exists(credentials_path):
        logger.error(
            f"Credentials file not found at {credentials_path}. "
            "Please obtain one from Google Cloud Console: "
            "https://console.cloud.google.com/apis/credentials"
        )
        logger.info(
            "1. Create a project in Google Cloud Console\n"
            "2. Enable the Gmail API\n"
            "3. Create OAuth client ID credentials\n"
            "4. Download the credentials as JSON\n"
            "5. Save the file as 'credentials.json' in the project root"
        )
        return
    
    # Authenticate
    credentials = authenticate(credentials_path, token_path)
    if not credentials:
        logger.error("Authentication failed")
        return
    
    # Validate the credentials
    if validate_credentials(credentials):
        logger.info("Gmail API authentication successful")
    else:
        logger.error("Gmail API authentication failed")


if __name__ == "__main__":
    main()
