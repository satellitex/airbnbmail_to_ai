"""SQLite database service for Airbnb notifications and calendar events."""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from airbnmail_to_ai.models.notification import AirbnbNotification, NotificationType
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


class DatabaseService:
    """Service for managing SQLite database for Airbnb notifications."""

    def __init__(self, db_path: str = "airbnb_notifications.db") -> None:
        """Initialize the Database Service.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Initialize the SQLite database and create tables if they don't exist."""
        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)

            # Connect to database
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            self.cursor = self.conn.cursor()

            # Create tables if they don't exist
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS airbnb_notifications (
                    notification_id TEXT PRIMARY KEY,
                    notification_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    received_at TEXT,
                    sender TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    raw_html TEXT NOT NULL,
                    reservation_id TEXT,
                    property_name TEXT,
                    guest_name TEXT,
                    check_in TEXT,
                    check_out TEXT,
                    num_guests INTEGER,
                    amount REAL,
                    currency TEXT,
                    cancellation_reason TEXT,
                    sender_name TEXT,
                    message_content TEXT,
                    reviewer_name TEXT,
                    rating INTEGER,
                    review_content TEXT,
                    llm_analysis TEXT,
                    llm_confidence TEXT,
                    created_at TEXT NOT NULL
                )
            ''')

            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS calendar_events (
                    notification_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    calendar_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (notification_id, event_id),
                    FOREIGN KEY (notification_id) REFERENCES airbnb_notifications(notification_id)
                )
            ''')

            self.conn.commit()
            logger.info(f"Initialized database at {self.db_path}")

        except Exception as e:
            logger.exception(f"Error initializing database: {e}")
            if self.conn:
                self.conn.close()
            raise

    def close(self) -> None:
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None

    def save_notification(self, notification: AirbnbNotification) -> bool:
        """Save an Airbnb notification to the database.
        If a notification with the same ID already exists, it will be updated.

        Args:
            notification: The AirbnbNotification object to save.

        Returns:
            bool: True if saved successfully or updated, False otherwise.
        """
        try:
            # Convert notification to dictionary
            notification_dict = notification.to_dict()

            # Convert llm_analysis to JSON string if it exists
            if notification_dict.get("llm_analysis"):
                notification_dict["llm_analysis"] = json.dumps(notification_dict["llm_analysis"])

            # Set created_at timestamp (for new notifications) or update timestamp
            now = datetime.now().isoformat()

            # Check if this notification already exists
            existing = self.get_notification(notification.notification_id)

            if existing:
                logger.info(f"Updating existing notification {notification.notification_id} in database")

                # Extract fields and values for update
                update_items = []
                values = []

                for field, value in notification_dict.items():
                    if field != "notification_id":  # Don't update primary key
                        update_items.append(f"{field} = ?")
                        values.append(value)

                # Add notification_id at the end for WHERE clause
                values.append(notification.notification_id)

                # Construct update query
                query = f'''
                    UPDATE airbnb_notifications
                    SET {", ".join(update_items)}, created_at = ?
                    WHERE notification_id = ?
                '''

                # Add timestamp to values
                values.insert(-1, now)

                # Execute update query
                self.cursor.execute(query, values)
                self.conn.commit()

                logger.info(f"Updated notification {notification.notification_id} in database")
                return True
            else:
                # Set created_at timestamp for new notification
                notification_dict["created_at"] = now

                # Extract fields for insertion
                fields = list(notification_dict.keys())
                placeholders = ["?" for _ in fields]
                values = [notification_dict[field] for field in fields]

                # Construct insert query
                query = f'''
                    INSERT INTO airbnb_notifications
                    ({", ".join(fields)})
                    VALUES ({", ".join(placeholders)})
                '''

                # Execute insert query
                self.cursor.execute(query, values)
                self.conn.commit()

                logger.info(f"Saved new notification {notification.notification_id} to database")
                return True

        except Exception as e:
            logger.exception(f"Error saving notification {notification.notification_id}: {e}")
            self.conn.rollback()
            return False

    def get_notification(self, notification_id: str) -> Optional[AirbnbNotification]:
        """Get an Airbnb notification from the database by ID.

        Args:
            notification_id: The notification ID to retrieve.

        Returns:
            Optional[AirbnbNotification]: The notification if found, None otherwise.
        """
        try:
            query = "SELECT * FROM airbnb_notifications WHERE notification_id = ?"
            self.cursor.execute(query, (notification_id,))
            row = self.cursor.fetchone()

            if not row:
                return None

            # Convert to dictionary
            notification_dict = dict(row)

            # Convert llm_analysis from JSON string back to dictionary if it exists
            if notification_dict.get("llm_analysis"):
                notification_dict["llm_analysis"] = json.loads(notification_dict["llm_analysis"])

            # Remove created_at field (not part of AirbnbNotification model)
            notification_dict.pop("created_at", None)

            # Convert enum string to NotificationType enum
            notification_dict["notification_type"] = NotificationType(notification_dict["notification_type"])

            # Create AirbnbNotification object
            return AirbnbNotification(**notification_dict)

        except Exception as e:
            logger.exception(f"Error retrieving notification {notification_id}: {e}")
            return None

    def save_calendar_event(
        self, notification_id: str, event_id: str, calendar_id: str = "primary"
    ) -> bool:
        """Save a calendar event associated with an Airbnb notification.
        If the notification already has a calendar event, it will update the event ID.

        Args:
            notification_id: The notification ID associated with the event.
            event_id: The Google Calendar event ID.
            calendar_id: The Google Calendar ID (default: primary).

        Returns:
            bool: True if saved successfully, False otherwise.
        """
        try:
            # Check if this notification already has a calendar event
            self.cursor.execute(
                "SELECT event_id FROM calendar_events WHERE notification_id = ?",
                (notification_id,)
            )
            existing_event = self.cursor.fetchone()

            now = datetime.now().isoformat()

            if existing_event:
                # If the event ID is different, update it
                if existing_event['event_id'] != event_id:
                    logger.info(
                        f"Updating calendar event for notification {notification_id} from {existing_event['event_id']} to {event_id}"
                    )
                    self.cursor.execute(
                        """
                        UPDATE calendar_events
                        SET event_id = ?, calendar_id = ?, created_at = ?
                        WHERE notification_id = ?
                        """,
                        (event_id, calendar_id, now, notification_id)
                    )
                else:
                    logger.info(
                        f"Notification {notification_id} already has calendar event {existing_event['event_id']}"
                    )
                self.conn.commit()
                return True
            else:
                # Insert new calendar event
                self.cursor.execute(
                    """
                    INSERT INTO calendar_events
                    (notification_id, event_id, calendar_id, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (notification_id, event_id, calendar_id, now)
                )
                self.conn.commit()

                logger.info(f"Saved new calendar event {event_id} for notification {notification_id}")
                return True

        except Exception as e:
            logger.exception(f"Error saving calendar event for notification {notification_id}: {e}")
            self.conn.rollback()
            return False

    def get_calendar_event(self, notification_id: str) -> Optional[Dict[str, str]]:
        """Get a calendar event associated with an Airbnb notification.

        Args:
            notification_id: The notification ID associated with the event.

        Returns:
            Optional[Dict[str, str]]: The calendar event details if found, None otherwise.
        """
        try:
            self.cursor.execute(
                "SELECT * FROM calendar_events WHERE notification_id = ?",
                (notification_id,)
            )
            row = self.cursor.fetchone()

            if not row:
                return None

            return dict(row)

        except Exception as e:
            logger.exception(f"Error retrieving calendar event for notification {notification_id}: {e}")
            return None

    def notification_exists(self, notification_id: str) -> bool:
        """Check if a notification exists in the database.

        Args:
            notification_id: The notification ID to check.

        Returns:
            bool: True if the notification exists, False otherwise.
        """
        try:
            self.cursor.execute(
                "SELECT 1 FROM airbnb_notifications WHERE notification_id = ?",
                (notification_id,)
            )
            return bool(self.cursor.fetchone())
        except Exception as e:
            logger.exception(f"Error checking if notification {notification_id} exists: {e}")
            return False

    def has_calendar_event(self, notification_id: str) -> bool:
        """Check if a notification has an associated calendar event.

        Args:
            notification_id: The notification ID to check.

        Returns:
            bool: True if the notification has a calendar event, False otherwise.
        """
        try:
            self.cursor.execute(
                "SELECT 1 FROM calendar_events WHERE notification_id = ?",
                (notification_id,)
            )
            return bool(self.cursor.fetchone())
        except Exception as e:
            logger.exception(f"Error checking if notification {notification_id} has calendar event: {e}")
            return False

    def find_duplicate_notifications(
        self, property_name: str, check_in: str, check_out: str, guest_name: str
    ) -> List[AirbnbNotification]:
        """Find duplicate notifications based on booking details.

        Args:
            property_name: The property name.
            check_in: The check-in date.
            check_out: The check-out date.
            guest_name: The guest name.

        Returns:
            List[AirbnbNotification]: List of duplicate notifications.
        """
        try:
            # Query for notifications with matching booking details
            query = """
                SELECT * FROM airbnb_notifications
                WHERE property_name = ?
                AND check_in = ?
                AND check_out = ?
                AND guest_name = ?
            """
            self.cursor.execute(query, (property_name, check_in, check_out, guest_name))
            rows = self.cursor.fetchall()

            # Convert rows to AirbnbNotification objects
            notifications = []
            for row in rows:
                notification_dict = dict(row)

                # Convert llm_analysis from JSON string back to dictionary if it exists
                if notification_dict.get("llm_analysis"):
                    notification_dict["llm_analysis"] = json.loads(notification_dict["llm_analysis"])

                # Remove created_at field (not part of AirbnbNotification model)
                notification_dict.pop("created_at", None)

                # Convert enum string to NotificationType enum
                notification_dict["notification_type"] = NotificationType(notification_dict["notification_type"])

                # Create AirbnbNotification object
                notifications.append(AirbnbNotification(**notification_dict))

            return notifications

        except Exception as e:
            logger.exception(f"Error finding duplicate notifications: {e}")
            return []

    def get_all_notifications(
        self, limit: int = 100, offset: int = 0
    ) -> List[AirbnbNotification]:
        """Get all Airbnb notifications from the database.

        Args:
            limit: Maximum number of notifications to retrieve.
            offset: Number of notifications to skip.

        Returns:
            List[AirbnbNotification]: List of Airbnb notifications.
        """
        try:
            query = "SELECT * FROM airbnb_notifications ORDER BY received_at DESC LIMIT ? OFFSET ?"
            self.cursor.execute(query, (limit, offset))
            rows = self.cursor.fetchall()

            # Convert rows to AirbnbNotification objects
            notifications = []
            for row in rows:
                notification_dict = dict(row)

                # Convert llm_analysis from JSON string back to dictionary if it exists
                if notification_dict.get("llm_analysis"):
                    notification_dict["llm_analysis"] = json.loads(notification_dict["llm_analysis"])

                # Remove created_at field (not part of AirbnbNotification model)
                notification_dict.pop("created_at", None)

                # Convert enum string to NotificationType enum
                notification_dict["notification_type"] = NotificationType(notification_dict["notification_type"])

                # Create AirbnbNotification object
                notifications.append(AirbnbNotification(**notification_dict))

            return notifications

        except Exception as e:
            logger.exception(f"Error retrieving notifications: {e}")
            return []
