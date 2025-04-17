"""Database commands for Airbnb Mail to AI."""

import argparse
import json
import sys
from typing import Any

import yaml

from airbnmail_to_ai.db.db_service import DatabaseService
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


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
        logger.info("Connected to database at {}", args.db_path)

        if not hasattr(args, "db_command") or args.db_command is None:
            logger.error("No database command specified")
            print("Error: Please specify a database command (list, view, delete, stats)")
            print("For more information, use: db --help")
            return

        # Process the specific db command
        if args.db_command == "list":
            handle_list_command(db, args)
        elif args.db_command == "view":
            handle_view_command(db, args)
        elif args.db_command == "delete":
            handle_delete_command(db, args)
        elif args.db_command == "stats":
            handle_stats_command(db, args)

    except Exception as e:
        logger.exception("Error executing database command: {}", e)
        print(f"Error: {e}")
        sys.exit(1)


def handle_list_command(db: DatabaseService, args: argparse.Namespace) -> None:
    """Handle the list command.

    Args:
        db: DatabaseService instance
        args: Command line arguments
    """
    logger.info("Listing notifications (limit: {}, offset: {})", args.limit, args.offset)
    notifications = db.get_all_notifications(limit=args.limit, offset=args.offset)

    if not notifications:
        logger.info("No notifications found in the database")
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


def handle_view_command(db: DatabaseService, args: argparse.Namespace) -> None:
    """Handle the view command.

    Args:
        db: DatabaseService instance
        args: Command line arguments
    """
    logger.info("Viewing notification: {}", args.notification_id)
    notification = db.get_notification(args.notification_id)

    if not notification:
        logger.warning("Notification ID '{}' not found in database", args.notification_id)
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


def handle_delete_command(db: DatabaseService, args: argparse.Namespace) -> None:
    """Handle the delete command.

    Args:
        db: DatabaseService instance
        args: Command line arguments
    """
    logger.info("Would delete notification ID: {}", args.notification_id)
    # This functionality requires adding a delete_notification method to DatabaseService
    # For now, print a message that this is not implemented
    print("Delete functionality not yet implemented.")
    print(f"Would delete notification ID: {args.notification_id}")


def handle_stats_command(db: DatabaseService, args: argparse.Namespace) -> None:
    """Handle the stats command.

    Args:
        db: DatabaseService instance
        args: Command line arguments
    """
    logger.info("Showing database statistics")
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
