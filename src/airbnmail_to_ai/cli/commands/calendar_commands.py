"""Calendar commands for Airbnb Mail to AI."""

import argparse
import os
import sys
from typing import Any

from airbnmail_to_ai.calendar.calendar_service import CalendarService
from airbnmail_to_ai.gmail.gmail_service import GmailService
from airbnmail_to_ai.parser import email_parser
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


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
        "--db-path",
        default="airbnb_notifications.db",
        help="Path to SQLite database file (default: airbnb_notifications.db)",
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
        logger.info("Using search query: {}", args.query)

        # Initialize Gmail service
        gmail = GmailService(
            credentials_path=args.credentials,
            token_path=args.gmail_token,
        )

        # Initialize Calendar service with database
        calendar = CalendarService(
            credentials_path=args.credentials,
            token_path=args.calendar_token,
            db_path=args.db_path,
        )
        if not calendar.connect():
            logger.error("Failed to connect to Google Calendar API")
            print("Error: Failed to connect to Google Calendar API")
            sys.exit(1)

        # Fetch messages matching the query
        messages = gmail.get_messages(query=args.query, max_results=args.limit)

        if not messages:
            logger.info("No booking confirmation emails found")
            print("No booking confirmation emails found.")
            return

        logger.info("Found {} booking confirmation emails", len(messages))
        print(f"Found {len(messages)} booking confirmation emails")

        # Set API key if provided in command line
        if args.api_key and args.use_llm:
            # Temporarily set environment variable
            os.environ["ANTHROPIC_API_KEY"] = args.api_key
            logger.info("Using provided Anthropic API key")

        # Process each message and add to calendar
        process_booking_confirmations(messages, gmail, calendar, args)

    except Exception as e:
        logger.exception("Error processing bookings: {}", e)
        print(f"Error: {e}")
        sys.exit(1)


def process_booking_confirmations(
    messages: list, gmail: GmailService, calendar: CalendarService, args: argparse.Namespace
) -> None:
    """Process booking confirmation emails and add to calendar.

    Args:
        messages: List of email message dictionaries
        gmail: GmailService instance
        calendar: CalendarService instance
        args: Command line arguments
    """
    success_count = 0

    for msg in messages:
        logger.info("Processing email: {}", msg['subject'])

        # Parse email with LLM analysis
        notification = email_parser.parse_email(msg)
        if not notification:
            logger.warning("Failed to parse email: {}", msg['subject'])
            continue

        # Add booking to calendar
        event_id = calendar.add_booking_to_calendar(notification)
        if event_id:
            success_count += 1

            # Display LLM analysis results if available
            if notification.llm_analysis:
                print(f"Added booking to calendar: {notification.get_summary()}")
                print(f"LLM Analysis Results:")
                if notification.llm_analysis:
                    check_in_date = notification.llm_analysis.get('check_in_date')
                    check_out_date = notification.llm_analysis.get('check_out_date')
                    if check_in_date:
                        print(f"  Check-in date: {check_in_date}")
                    if check_out_date:
                        print(f"  Check-out date: {check_out_date}")
                    if notification.llm_confidence:
                        print(f"  Confidence: {notification.llm_confidence}")
                    print(f"  Guest name: {notification.guest_name}")
                    print(f"  Reservation ID: {notification.reservation_id}")
                    print(f"  Property name: {notification.property_name}")
                    print(f"  Number of guests: {notification.num_guests}")
            else:
                print(f"Added booking to calendar: {notification.get_summary()}")

            # Mark as read if requested
            if args.mark_read:
                gmail.mark_as_read(msg["id"])
                logger.debug("Marked email {} as read", msg["id"])
        else:
            logger.warning("Failed to add booking to calendar: {}", notification.get_summary())

    # Report results
    print(f"\nSuccessfully added {success_count} of {len(messages)} bookings to Google Calendar")
    if args.mark_read and success_count > 0:
        print(f"Marked {success_count} processed emails as read")
