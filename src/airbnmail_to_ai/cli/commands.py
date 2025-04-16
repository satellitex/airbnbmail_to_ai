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
from airbnmail_to_ai.db.db_service import DatabaseService
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
                        if 'llm_analysis' in msg['parsed_data'] and msg['parsed_data']['llm_analysis']:
                            llm_analysis = msg['parsed_data']['llm_analysis']
                            check_in_date = llm_analysis.get('check_in_date')
                            check_out_date = llm_analysis.get('check_out_date')
                            if check_in_date or check_out_date:
                                output += f"  Reservation Analysis:\n"
                                if check_in_date:
                                    output += f"    Check-In Date: {check_in_date}\n"
                                if check_out_date:
                                    output += f"    Check-Out Date: {check_out_date}\n"
                                if 'llm_confidence' in msg['parsed_data']:
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
        "--db-path",
        default="airbnb_notifications.db",
        help="Path to SQLite database file (default: airbnb_notifications.db)",
    )
    # Removed the single parameter as we'll use --limit=1 instead
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

        # Initialize Calendar service with database
        calendar = CalendarService(
            credentials_path=args.credentials,
            token_path=args.calendar_token,
            db_path=args.db_path,
        )
        if not calendar.connect():
            print("Error: Failed to connect to Google Calendar API")
            sys.exit(1)

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
                    if notification.llm_analysis:
                        check_in_date = notification.llm_analysis.get('check_in_date')
                        check_out_date = notification.llm_analysis.get('check_out_date')
                        if check_in_date:
                            print(f"  Check-in date: {check_in_date}")
                        if check_out_date:
                            print(f"  Check-out date: {check_out_date}")
                        if notification.llm_confidence:
                            print(f"  Confidence: {notification.llm_confidence}")
                        print(f"    Guest name: {notification.guest_name}")
                        print(f"    Reservation ID: {notification.reservation_id}")
                        print(f"    Property name: {notification.property_name}")
                        print(f"    Number of guests: {notification.num_guests}")
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


def setup_db_parser(subparsers: Any) -> None:
    """Set up the parser for the db command.

    Args:
        subparsers: Subparser object to add the db command to.
    """
    db_parser = subparsers.add_parser(
        "db", help="Manage Airbnb notification database"
    )

    # Create subcommands for db (list, view, delete)
    db_subparsers = db_parser.add_subparsers(dest="db_command", help="Database command")

    # List subcommand
    list_parser = db_subparsers.add_parser("list", help="List all notifications in the database")
    list_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of notifications to list (default: 10)",
    )
    list_parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Number of notifications to skip (default: 0)",
    )
    list_parser.add_argument(
        "--output",
        choices=["json", "yaml", "text"],
        default="text",
        help="Output format (default: text)",
    )
    list_parser.add_argument(
        "--db-path",
        default="airbnb_notifications.db",
        help="Path to SQLite database file (default: airbnb_notifications.db)",
    )

    # View subcommand
    view_parser = db_subparsers.add_parser("view", help="View a specific notification")
    view_parser.add_argument(
        "notification_id",
        help="ID of the notification to view",
    )
    view_parser.add_argument(
        "--output",
        choices=["json", "yaml", "text"],
        default="text",
        help="Output format (default: text)",
    )
    view_parser.add_argument(
        "--db-path",
        default="airbnb_notifications.db",
        help="Path to SQLite database file (default: airbnb_notifications.db)",
    )

    # Delete subcommand
    delete_parser = db_subparsers.add_parser("delete", help="Delete a notification from database")
    delete_parser.add_argument(
        "notification_id",
        help="ID of the notification to delete",
    )
    delete_parser.add_argument(
        "--db-path",
        default="airbnb_notifications.db",
        help="Path to SQLite database file (default: airbnb_notifications.db)",
    )

    # Stats subcommand
    stats_parser = db_subparsers.add_parser("stats", help="Show database statistics")
    stats_parser.add_argument(
        "--db-path",
        default="airbnb_notifications.db",
        help="Path to SQLite database file (default: airbnb_notifications.db)",
    )

    db_parser.set_defaults(func=db_command)


def db_command(args: argparse.Namespace) -> None:
    """Execute the db command to manage the Airbnb notifications database.

    Args:
        args: Command line arguments.
    """
    try:
        # Initialize Database service
        db = DatabaseService(db_path=args.db_path)

        if not hasattr(args, "db_command") or args.db_command is None:
            print("Error: Please specify a database command (list, view, delete, stats)")
            print("For more information, use: db --help")
            return

        # List notifications
        if args.db_command == "list":
            notifications = db.get_all_notifications(limit=args.limit, offset=args.offset)

            if not notifications:
                print("No notifications found in the database.")
                return

            if args.output == "json":
                output = json.dumps([n.to_dict() for n in notifications], indent=2)
                print(output)
            elif args.output == "yaml":
                output = yaml.dump([n.to_dict() for n in notifications], default_flow_style=False)
                print(output)
            else:  # text
                print(f"Found {len(notifications)} notifications:")
                print("-" * 80)
                for i, notification in enumerate(notifications, 1):
                    print(f"#{i} - {notification.notification_id}")
                    print(f"  Type: {notification.notification_type.value}")
                    print(f"  Subject: {notification.subject}")
                    print(f"  Received: {notification.received_at}")
                    if notification.property_name:
                        print(f"  Property: {notification.property_name}")
                    if notification.guest_name:
                        print(f"  Guest: {notification.guest_name}")
                    if notification.check_in and notification.check_out:
                        print(f"  Stay: {notification.check_in} to {notification.check_out}")
                    if db.has_calendar_event(notification.notification_id):
                        cal_event = db.get_calendar_event(notification.notification_id)
                        print(f"  Calendar Event: {cal_event['event_id']}")
                    print("-" * 80)

        # View a notification
        elif args.db_command == "view":
            notification = db.get_notification(args.notification_id)

            if not notification:
                print(f"Notification ID '{args.notification_id}' not found in database.")
                return

            if args.output == "json":
                output = json.dumps(notification.to_dict(), indent=2)
                print(output)
            elif args.output == "yaml":
                output = yaml.dump(notification.to_dict(), default_flow_style=False)
                print(output)
            else:  # text
                print(f"Notification ID: {notification.notification_id}")
                print(f"Type: {notification.notification_type.value}")
                print(f"Subject: {notification.subject}")
                print(f"Received at: {notification.received_at}")
                print(f"Sender: {notification.sender}")

                if notification.property_name:
                    print(f"Property name: {notification.property_name}")
                if notification.guest_name:
                    print(f"Guest name: {notification.guest_name}")
                if notification.reservation_id:
                    print(f"Reservation ID: {notification.reservation_id}")
                if notification.check_in:
                    print(f"Check-in: {notification.check_in}")
                if notification.check_out:
                    print(f"Check-out: {notification.check_out}")
                if notification.num_guests:
                    print(f"Number of guests: {notification.num_guests}")
                if notification.amount:
                    print(f"Amount: {notification.currency or ''}{notification.amount}")

                # Check if this notification has a calendar event
                if db.has_calendar_event(notification.notification_id):
                    cal_event = db.get_calendar_event(notification.notification_id)
                    print(f"\nCalendar Event: {cal_event['event_id']}")
                    print(f"Calendar ID: {cal_event['calendar_id']}")
                    print(f"Created at: {cal_event['created_at']}")
                else:
                    print("\nNo calendar event associated with this notification.")

        # Delete a notification
        elif args.db_command == "delete":
            # This functionality requires adding a delete_notification method to DatabaseService
            # For now, print a message that this is not implemented
            print("Delete functionality not yet implemented.")
            print(f"Would delete notification ID: {args.notification_id}")

        # Show database statistics
        elif args.db_command == "stats":
            # This requires adding methods to DatabaseService to get counts
            # For now, implement a basic version using SQL directly
            db.cursor.execute("SELECT COUNT(*) FROM airbnb_notifications")
            notification_count = db.cursor.fetchone()[0]

            db.cursor.execute("SELECT COUNT(*) FROM calendar_events")
            event_count = db.cursor.fetchone()[0]

            db.cursor.execute(
                "SELECT notification_type, COUNT(*) FROM airbnb_notifications GROUP BY notification_type"
            )
            type_counts = db.cursor.fetchall()

            print("Database Statistics:")
            print(f"  Database path: {args.db_path}")
            print(f"  Total notifications: {notification_count}")
            print(f"  Total calendar events: {event_count}")

            if type_counts:
                print("\nNotification types:")
                for type_row in type_counts:
                    print(f"  {type_row[0]}: {type_row[1]}")

    except Exception as e:
        logger.exception(f"Error executing database command: {e}")
        print(f"Error: {e}")
        sys.exit(1)


def list_commands() -> None:
    """Print available commands."""
    print("Available commands:")
    print("  fetch    - Fetch emails from automated@airbnb.com")
    print("  auth     - Authenticate with Gmail API")
    print("  calendar - Add Airbnb bookings to Google Calendar")
    print("  db       - Manage Airbnb notification database")
    print("\nFor more information on a command, use: <command> --help")
