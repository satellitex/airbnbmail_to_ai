"""Command line interface commands for Airbnb Mail to AI."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from airbnmail_to_ai.gmail.gmail_service import GmailService
from airbnmail_to_ai.parser import email_parser


def setup_fetch_parser(subparsers: Any) -> None:
    """Set up the parser for the fetch command.

    Args:
        subparsers: Subparser object to add the fetch command to.
    """
    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch emails from automated@airbnb.com"
    )

    # Add arguments specific to fetch command
    fetch_parser.add_argument(
        "--query",
        default="from:automated@airbnb.com is:unread",
        help="Gmail search query (default: 'from:automated@airbnb.com is:unread')",
    )
    fetch_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of emails to fetch (default: 10)",
    )
    fetch_parser.add_argument(
        "--mark-read",
        action="store_true",
        help="Mark fetched emails as read",
    )
    fetch_parser.add_argument(
        "--output",
        choices=["json", "yaml", "text"],
        default="text",
        help="Output format (default: text)",
    )
    fetch_parser.add_argument(
        "--save",
        type=str,
        help="Save output to specified file path",
    )
    fetch_parser.add_argument(
        "--parse",
        action="store_true",
        help="Parse email content for Airbnb notification data",
    )
    fetch_parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to Gmail API credentials file (default: credentials.json)",
    )
    fetch_parser.add_argument(
        "--token",
        default="token.json",
        help="Path to Gmail API token file (default: token.json)",
    )
    fetch_parser.set_defaults(func=fetch_command)


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


def fetch_command(args: argparse.Namespace) -> None:
    """Execute the fetch command.

    Args:
        args: Command line arguments.
    """
    try:
        logger.info("Fetching emails with query: {}", args.query)

        # Initialize Gmail service
        gmail = GmailService(
            credentials_path=args.credentials,
            token_path=args.token,
        )

        # Fetch messages
        messages = gmail.get_messages(query=args.query, max_results=args.limit)

        if not messages:
            logger.info("No emails found matching the query")
            print("No emails found matching the query.")
            return

        logger.info("Found {} emails matching the query", len(messages))

        # Process messages
        results = []
        for msg in messages:
            if args.parse:
                parsed_data = email_parser.parse_email(msg)
                if parsed_data:
                    results.append(
                        {
                            "id": msg["id"],
                            "subject": msg["subject"],
                            "date": msg["date"],
                            "from": msg["from"],
                            "parsed_data": parsed_data.dict(),
                        }
                    )
                else:
                    results.append(
                        {
                            "id": msg["id"],
                            "subject": msg["subject"],
                            "date": msg["date"],
                            "from": msg["from"],
                            "parsed_data": None,
                        }
                    )
            else:
                results.append(
                    {
                        "id": msg["id"],
                        "subject": msg["subject"],
                        "date": msg["date"],
                        "from": msg["from"],
                        "body_text": msg["body_text"][:200] + "..."
                        if len(msg["body_text"]) > 200
                        else msg["body_text"],
                    }
                )

            # Mark as read if requested
            if args.mark_read:
                gmail.mark_as_read(msg["id"])
                logger.debug("Marked email {} as read", msg["id"])

        # Output results
        if args.output == "json":
            output = json.dumps(results, indent=2)
        elif args.output == "yaml":
            output = yaml.dump(results, default_flow_style=False)
        else:  # text
            output = ""
            for i, msg in enumerate(results, 1):
                output += f"Email {i}:\n"
                output += f"  ID: {msg['id']}\n"
                output += f"  Subject: {msg['subject']}\n"
                output += f"  Date: {msg['date']}\n"
                output += f"  From: {msg['from']}\n"
                if not args.parse:
                    output += f"  Preview: {msg['body_text']}\n"
                else:
                    output += f"  Parsed Data: {'Successfully parsed' if msg['parsed_data'] else 'Failed to parse'}\n"
                    if msg["parsed_data"]:
                        for key, value in msg["parsed_data"].items():
                            output += f"    {key}: {value}\n"
                output += "\n"

        # Save or print output
        if args.save:
            save_path = Path(args.save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(output)
            logger.info("Saved output to {}", args.save)
            print(f"Saved output to {args.save}")
        else:
            print(output)

        if args.mark_read:
            print(f"Marked {len(messages)} emails as read.")

    except Exception as e:
        logger.exception("Error fetching emails: {}", e)
        print(f"Error: {e}")
        sys.exit(1)


def auth_command(args: argparse.Namespace) -> None:
    """Execute the auth command.

    Args:
        args: Command line arguments.
    """
    try:
        logger.info("Authenticating with Gmail API")
        print("Initiating Gmail API authentication...")

        # Initialize Gmail service (which will trigger auth flow if needed)
        gmail = GmailService(
            credentials_path=args.credentials,
            token_path=args.token,
        )

        # Test authentication
        user_profile = gmail.service.users().getProfile(userId="me").execute()
        email = user_profile.get("emailAddress", "unknown")

        logger.info("Successfully authenticated as {}", email)
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


def list_commands() -> None:
    """Print available commands."""
    print("Available commands:")
    print("  fetch   - Fetch emails from automated@airbnb.com")
    print("  auth    - Authenticate with Gmail API")
    print("\nFor more information on a command, use: <command> --help")
