"""Command line interface commands for Airbnb Mail to AI."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger

from airbnmail_to_ai.calendar.calendar_service import CalendarService
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
                # Parse email with LLM analysis
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
                        # Add general parsed data
                        for key, value in msg["parsed_data"].items():
                            if key not in ['llm_analysis'] and value is not None:  # Skip the raw analysis text
                                output += f"    {key}: {value}\n"

                        # Add reservation analysis section
                        if 'llm_check_in_date' in msg['parsed_data'] and msg['parsed_data']['llm_check_in_date']:
                            output += f"  Reservation Analysis:\n"
                            output += f"    Check-In Date: {msg['parsed_data']['llm_check_in_date']}\n"
                            output += f"    Check-Out Date: {msg['parsed_data']['llm_check_out_date']}\n"
                            output += f"    Confidence: {msg['parsed_data']['llm_confidence']}\n"
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


def setup_calendar_parser(subparsers: Any) -> None:
    """Set up the parser for the calendar command.

    Args:
        subparsers: Subparser object to add the calendar command to.
    """
    calendar_parser = subparsers.add_parser(
        "calendar", help="Add Airbnb bookings to Google Calendar"
    )

    # Add arguments specific to calendar command
    calendar_parser.add_argument(
        "--query",
        default="from:automated@airbnb.com subject:予約確定 is:unread",
        help="Gmail search query for booking confirmations (default: 'from:automated@airbnb.com subject:予約確定 is:unread')",
    )
    calendar_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of emails to process (default: 10)",
    )
    calendar_parser.add_argument(
        "--mark-read",
        action="store_true",
        help="Mark processed emails as read",
    )
    calendar_parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to Google API credentials file (default: credentials.json)",
    )
    calendar_parser.add_argument(
        "--gmail-token",
        default="token.json",
        help="Path to Gmail API token file (default: token.json)",
    )
    calendar_parser.add_argument(
        "--calendar-token",
        default="calendar_token.json",
        help="Path to Calendar API token file (default: calendar_token.json)",
    )
    calendar_parser.add_argument(
        "--single",
        help="Process only a single email message ID (for testing)",
    )
    calendar_parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use LLM to analyze reservation emails for more accurate date extraction",
    )
    calendar_parser.add_argument(
        "--api-key",
        help="API key for Anthropic Claude API (default: uses ANTHROPIC_API_KEY environment variable)",
    )
    calendar_parser.set_defaults(func=calendar_command)


def calendar_command(args: argparse.Namespace) -> None:
    """Execute the calendar command to add Airbnb bookings to Google Calendar.

    Args:
        args: Command line arguments.
    """
    try:
        logger.info("Processing Airbnb booking confirmations")
        print("Processing Airbnb booking confirmations...")

        # Initialize Gmail service
        gmail = GmailService(
            credentials_path=args.credentials,
            token_path=args.gmail_token,
        )

        # Initialize Calendar service
        calendar = CalendarService(
            credentials_path=args.credentials,
            token_path=args.calendar_token,
        )
        if not calendar.connect():
            print("Error: Failed to connect to Google Calendar API")
            sys.exit(1)

        # Process a single message if specified
        if args.single:
            message_id = args.single
            logger.info(f"Processing single message with ID: {message_id}")
            message = gmail.get_message(message_id)
            if not message:
                logger.error(f"Message {message_id} not found")
                print(f"Error: Message {message_id} not found")
                sys.exit(1)

            messages = [message]
        else:
            # Fetch messages matching the query
            messages = gmail.get_messages(query=args.query, max_results=args.limit)

        if not messages:
            logger.info("No booking confirmation emails found")
            print("No booking confirmation emails found.")
            return

        logger.info(f"Found {len(messages)} booking confirmation emails")
        print(f"Found {len(messages)} booking confirmation emails")

        # Set API key if provided in command line
        if args.api_key and args.use_llm:
            # Temporarily set environment variable
            os.environ["ANTHROPIC_API_KEY"] = args.api_key
            logger.info("Using provided Anthropic API key")

        # Process each message and add to calendar
        success_count = 0
        for msg in messages:
            logger.info(f"Processing email: {msg['subject']}")

            # Parse email with LLM analysis
            notification = email_parser.parse_email(msg)
            if not notification:
                logger.warning(f"Failed to parse email: {msg['subject']}")
                continue

            # Add booking to calendar
            event_id = calendar.add_booking_to_calendar(notification)
            if event_id:
                success_count += 1

                # Display LLM analysis results if available
                if notification.llm_analysis:
                    print(f"Added booking to calendar: {notification.get_summary()}")
                    print(f"LLM Analysis Results:")
                    print(f"  Check-in date: {notification.llm_check_in_date}")
                    print(f"  Check-out date: {notification.llm_check_out_date}")
                    print(f"  Confidence: {notification.llm_confidence}")
                else:
                    print(f"Added booking to calendar: {notification.get_summary()}")

                # Mark as read if requested
                if args.mark_read:
                    gmail.mark_as_read(msg["id"])
                    logger.debug(f"Marked email {msg['id']} as read")
            else:
                logger.warning(f"Failed to add booking to calendar: {notification.get_summary()}")

        # Report results
        print(f"\nSuccessfully added {success_count} of {len(messages)} bookings to Google Calendar")
        if args.mark_read and success_count > 0:
            print(f"Marked {success_count} processed emails as read")

    except Exception as e:
        logger.exception(f"Error processing bookings: {e}")
        print(f"Error: {e}")
        sys.exit(1)


def list_commands() -> None:
    """Print available commands."""
    print("Available commands:")
    print("  fetch    - Fetch emails from automated@airbnb.com")
    print("  auth     - Authenticate with Gmail API")
    print("  calendar - Add Airbnb bookings to Google Calendar")
    print("\nFor more information on a command, use: <command> --help")
