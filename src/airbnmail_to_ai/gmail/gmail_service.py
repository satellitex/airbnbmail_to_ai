"""Gmail service for interacting with Gmail API."""

import base64
import os.path
import pickle
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger


class GmailService:
    """Service for interacting with Gmail API."""

    # If modifying these scopes, delete the token file.
    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(
        self, credentials_path: str = "credentials.json", token_path: str = "token.json"
    ) -> None:
        """Initialize the Gmail service.

        Args:
            credentials_path: Path to the credentials.json file.
            token_path: Path to store/load the token.json file.
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._get_gmail_service()

    def _get_gmail_service(self) -> Any:
        """Get an authorized Gmail API service instance.

        Returns:
            An authorized Gmail API service instance.

        Raises:
            FileNotFoundError: If the credentials file doesn't exist.
            Exception: If authentication fails.
        """
        creds = None

        # Check if token file exists
        if os.path.exists(self.token_path):
            with open(self.token_path, "rb") as token:
                creds = pickle.load(token)

        # If credentials don't exist or are invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"Credentials file not found at {self.credentials_path}. "
                        "Please obtain one from Google Cloud Console."
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.token_path, "wb") as token:
                pickle.dump(creds, token)

        try:
            # Build the Gmail service
            service = build("gmail", "v1", credentials=creds)
            return service
        except Exception as e:
            logger.exception(f"Failed to build Gmail service: {e}")
            raise

    def get_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Get a single message by ID.

        Args:
            msg_id: The ID of the message.

        Returns:
            Dictionary with message details or None if an error occurs.
        """
        return self._get_message_detail(msg_id)

    def get_messages(
        self, query: str = "from:airbnb.com is:unread", max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """Get messages matching the specified query.

        Args:
            query: Gmail search query. Defaults to "from:airbnb.com is:unread".
            max_results: Maximum number of messages to return. Defaults to 50.

        Returns:
            List of message dictionaries with the following keys:
            - id: The message ID
            - thread_id: The thread ID
            - subject: The email subject
            - from: The sender email
            - date: The date the email was received
            - body_text: Plain text body
            - body_html: HTML body (if available)
            - labels: List of labels attached to the message

        Raises:
            HttpError: If there's an error accessing the Gmail API.
        """
        try:
            # Get messages matching the query
            response = (
                self.service.users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )

            messages = []
            if "messages" in response:
                for message in response["messages"]:
                    msg_detail = self._get_message_detail(message["id"])
                    if msg_detail:
                        messages.append(msg_detail)

            return messages

        except HttpError as e:
            logger.exception(f"An error occurred while getting messages: {e}")
            return []

    def _get_message_detail(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a message.

        Args:
            msg_id: The ID of the message.

        Returns:
            Dictionary with message details or None if an error occurs.
        """
        try:
            # Get the message details
            message = (
                self.service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )

            headers = {}
            for header in message["payload"]["headers"]:
                headers[header["name"].lower()] = header["value"]

            # Process the message parts to get the body
            body_text = ""
            body_html = ""
            if "parts" in message["payload"]:
                parts = message["payload"]["parts"]
                for part in parts:
                    if part["mimeType"] == "text/plain":
                        body_text = self._get_body_text(part)
                    elif part["mimeType"] == "text/html":
                        body_html = self._get_body_text(part)
            else:
                # Handle messages without parts
                if message["payload"]["mimeType"] == "text/plain":
                    body_text = self._get_body_text(message["payload"])
                elif message["payload"]["mimeType"] == "text/html":
                    body_html = self._get_body_text(message["payload"])

            # Construct the result dictionary
            result = {
                "id": msg_id,
                "thread_id": message["threadId"],
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "date": headers.get("date", ""),
                "body_text": body_text,
                "body_html": body_html,
                "labels": message.get("labelIds", []),
            }

            return result

        except HttpError as e:
            logger.exception(f"An error occurred while getting message details: {e}")
            return None

    def _get_body_text(self, part: Dict[str, Any]) -> str:
        """Extract the body text from a message part.

        Args:
            part: The message part dictionary.

        Returns:
            The decoded body text.
        """
        if "body" in part and "data" in part["body"]:
            data = part["body"]["data"]
            text = base64.urlsafe_b64decode(data).decode("utf-8")
            return text
        return ""

    def mark_as_read(self, msg_id: str) -> bool:
        """Mark a message as read by removing the UNREAD label.

        Args:
            msg_id: The ID of the message to mark as read.

        Returns:
            True if successful, False otherwise.
        """
        try:
            self.service.users().messages().modify(
                userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except HttpError as e:
            logger.exception(f"An error occurred while marking message as read: {e}")
            return False

    def send_email(
        self, to: str, subject: str, body: str, html: bool = False
    ) -> Optional[str]:
        """Send an email.

        Args:
            to: The recipient email address.
            subject: The subject of the email.
            body: The body of the email.
            html: Whether the body is HTML. Defaults to False.

        Returns:
            The message ID if successful, None otherwise.
        """
        try:
            # Create message
            message = MIMEText(body, "html" if html else "plain")
            message["to"] = to
            message["subject"] = subject

            # Encode the message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            # Send the message
            sent_message = (
                self.service.users()
                .messages()
                .send(userId="me", body={"raw": raw_message})
                .execute()
            )

            logger.info(f"Message sent to {to}. Message ID: {sent_message['id']}")
            return sent_message["id"]

        except HttpError as e:
            logger.exception(f"An error occurred while sending email: {e}")
            return None
