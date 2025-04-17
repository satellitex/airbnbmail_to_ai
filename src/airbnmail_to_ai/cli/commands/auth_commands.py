"""Authentication commands for Airbnb Mail to AI."""

import argparse
import sys
from typing import Any

from airbnmail_to_ai.gmail.gmail_service import GmailService
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


def setup_auth_parser(subparsers: Any) -> None:
    """Set up the parser for the auth command.

    Args:
        subparsers: Subparser object to add the auth command to.
    """
    auth_parser = subparsers.add_parser("auth", help="Authenticate with Gmail API")

    auth_parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to Gmail API credentials file (default: credentials.json)",
    )
    auth_parser.add_argument(
        "--token",
        default="token.json",
        help="Path to Gmail API token file (default: token.json)",
    )
    auth_parser.set_defaults(func=auth_command)


def auth_command(args: argparse.Namespace) -> None:
    """Execute the auth command.

    Args:
        args: Command line arguments.
    """
    try:
        logger.info("Authenticating with Gmail API")
        logger.info("Using credentials from {}", args.credentials)
        logger.info("Token will be saved to {}", args.token)

        # Initialize Gmail service (which will trigger auth flow if needed)
        gmail = GmailService(
            credentials_path=args.credentials,
            token_path=args.token,
        )

        # Test authentication
        user_profile = gmail.service.users().getProfile(userId="me").execute()
        email = user_profile.get("emailAddress", "unknown")

        logger.info("Successfully authenticated as {}", email)
        logger.info("Token saved to {}", args.token)

        # User-friendly output
        print(f"Successfully authenticated as {email}")
        print(f"Token saved to {args.token}")

    except Exception as e:
        logger.exception("Authentication error: {}", e)
        print(f"Authentication error: {e}")
        print("\nPlease make sure you have:")
        print("1. Created a project in Google Cloud Console")
        print("2. Enabled the Gmail API")
        print("3. Created OAuth client ID credentials")
        print("4. Downloaded the credentials as JSON and saved as credentials.json")
        sys.exit(1)
