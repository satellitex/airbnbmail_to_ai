"""Google Calendar service for managing Airbnb booking events."""

import datetime
import re
from typing import Dict, Optional, Tuple, Any

from loguru import logger

from airbnmail_to_ai.calendar.calendar_auth import get_calendar_service
from airbnmail_to_ai.db.db_service import DatabaseService
from airbnmail_to_ai.models.notification import AirbnbNotification, NotificationType


# Orange color for events in Google Calendar (value from Google Calendar API)
# Color IDs: 1=blue, 2=green, 3=purple, 4=red, 5=yellow, 6=orange, 7=turquoise, etc.
ORANGE_COLOR_ID = "6"


class CalendarService:
    """Service for managing Google Calendar events for Airbnb bookings."""

    def __init__(
        self,
        credentials_path: str = "credentials.json",
        token_path: str = "calendar_token.json",
        db_path: str = "airbnb_notifications.db",
    ) -> None:
        """Initialize the Calendar Service.

        Args:
            credentials_path: Path to the Google API credentials file.
            token_path: Path to save the authentication token.
            db_path: Path to the SQLite database file.
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.db = DatabaseService(db_path=db_path)

    def connect(self) -> bool:
        """Connect to the Google Calendar API.

        Returns:
            bool: True if connection was successful, False otherwise.
        """
        try:
            self.service = get_calendar_service(
                credentials_path=self.credentials_path,
                token_path=self.token_path,
            )
            return self.service is not None
        except Exception as e:
            logger.exception(f"Failed to connect to Google Calendar API: {e}")
            return False

    def parse_date_from_string(self, date_str: str) -> Optional[datetime.datetime]:
        """Convert a date string from Airbnb notification to a datetime object.

        Args:
            date_str: Date string in format like "14 April 2023"

        Returns:
            datetime.datetime object or None if parsing fails
        """
        try:
            # Common formats in Airbnb emails
            date_formats = [
                "%d %B %Y",  # 14 April 2023
                "%B %d, %Y",  # April 14, 2023
                "%d/%m/%Y",   # 14/04/2023
                "%Y-%m-%d",   # 2023-04-14
            ]

            for date_format in date_formats:
                try:
                    return datetime.datetime.strptime(date_str.strip(), date_format)
                except ValueError:
                    continue

            # If none of the formats match
            logger.warning(f"Could not parse date: {date_str}")
            return None

        except Exception as e:
            logger.exception(f"Error parsing date {date_str}: {e}")
            return None

    def add_booking_to_calendar(
        self, notification: AirbnbNotification, calendar_id: str = "primary"
    ) -> Optional[str]:
        """Add an Airbnb booking to Google Calendar.

        Args:
            notification: Parsed AirbnbNotification object
            calendar_id: Google Calendar ID to add the event to (default: primary)

        Returns:
            Event ID if successful, None otherwise
        """
        if not self.service:
            if not self.connect():
                logger.error("Could not connect to Google Calendar")
                return None

        try:
            # Check if this notification is already in the database
            existing_notification = self.db.get_notification(notification.notification_id)

            # Check if this notification is already in the calendar
            existing_event = self.db.get_calendar_event(notification.notification_id)

            # If notification exists and has a calendar event, check if we need to update
            if existing_notification and existing_event:
                # Check if there are any differences that would affect the calendar event
                needs_update = False

                # Compare fields that would affect the calendar event
                for field in ["property_name", "guest_name", "check_in", "check_out", "num_guests", "amount", "currency", "reservation_id"]:
                    existing_value = getattr(existing_notification, field)
                    new_value = getattr(notification, field)
                    if existing_value != new_value and new_value is not None:
                        logger.info(f"Found change in {field}: {existing_value} -> {new_value}")
                        needs_update = True

                # If LLM analysis changed and it affects dates, we need to update
                if notification.llm_analysis and existing_notification.llm_analysis:
                    if (notification.llm_analysis.get('check_in_date') != existing_notification.llm_analysis.get('check_in_date') or
                        notification.llm_analysis.get('check_out_date') != existing_notification.llm_analysis.get('check_out_date')):
                        logger.info("Found change in LLM-extracted dates")
                        needs_update = True

                if not needs_update:
                    # No significant changes, return existing event ID
                    event_id = existing_event["event_id"]
                    logger.info(f"Notification {notification.notification_id} already has calendar event {event_id} and no significant changes detected")
                    return event_id
                else:
                    # Save the updated notification to database
                    # First delete the existing event
                    event_id = existing_event["event_id"]
                    calendar_id = existing_event["calendar_id"]
                    logger.info(f"Updating calendar event {event_id} for notification {notification.notification_id}")
                    self.delete_event(event_id, calendar_id, notification.notification_id)
                    # Continue to create a new event with updated information

            # Save notification to database (either new or updated)
            if not self.db.save_notification(notification):
                logger.error(f"Failed to save notification {notification.notification_id} to database")
                # Continue anyway, as we still want to try adding to calendar

            # If notification has calendar event but we didn't need to update it
            if existing_event and not locals().get('needs_update'):
                event_id = existing_event["event_id"]
                logger.info(f"Notification {notification.notification_id} already has calendar event {event_id}")
                return event_id

            # Check for duplicate bookings (same property, dates, and guest)
            if notification.property_name and notification.check_in and notification.check_out and notification.guest_name:
                duplicates = self.db.find_duplicate_notifications(
                    property_name=notification.property_name,
                    check_in=notification.check_in,
                    check_out=notification.check_out,
                    guest_name=notification.guest_name
                )

                # If we found duplicates (other than this notification)
                other_duplicates = [d for d in duplicates if d.notification_id != notification.notification_id]
                if other_duplicates:
                    # Check if any of them already have calendar events
                    for duplicate in other_duplicates:
                        dup_event = self.db.get_calendar_event(duplicate.notification_id)
                        if dup_event:
                            logger.info(f"Found duplicate booking already in calendar: {duplicate.notification_id}")
                            # Save the relation to this notification as well
                            self.db.save_calendar_event(
                                notification_id=notification.notification_id,
                                event_id=dup_event["event_id"],
                                calendar_id=dup_event["calendar_id"]
                            )
                            return dup_event["event_id"]

            # Only process booking confirmations
            if notification.notification_type != NotificationType.BOOKING_CONFIRMATION:
                logger.warning(
                    f"Not a booking confirmation: {notification.notification_type}"
                )
                return None

            # Ensure we have the required data
            if not notification.check_in or not notification.check_out:
                logger.warning("Missing check-in or check-out date in notification")
                return None

            # First try to use LLM-extracted dates if available and confidence is good
            llm_check_in_date = notification.llm_analysis.get('check_in_date') if notification.llm_analysis else None
            llm_check_out_date = notification.llm_analysis.get('check_out_date') if notification.llm_analysis else None

            if llm_check_in_date and llm_check_out_date and notification.llm_confidence in ["high", "medium"]:
                logger.info("Using LLM-extracted dates")
                try:
                    check_in_date = datetime.datetime.strptime(llm_check_in_date, "%Y-%m-%d")
                    check_out_date = datetime.datetime.strptime(llm_check_out_date, "%Y-%m-%d")
                except ValueError:
                    logger.warning("Failed to parse LLM dates, falling back to regex-extracted dates")
                    check_in_date = self.parse_date_from_string(notification.check_in)
                    check_out_date = self.parse_date_from_string(notification.check_out)
            else:
                # Parse dates from the regex-extracted fields
                check_in_date = self.parse_date_from_string(notification.check_in)
                check_out_date = self.parse_date_from_string(notification.check_out)

            if not check_in_date or not check_out_date:
                logger.error("Failed to parse check-in or check-out dates")
                return None

            # Add specific times to the dates (check-in at 16:00, check-out at 12:00)
            check_in_datetime = datetime.datetime.combine(
                check_in_date.date(),
                datetime.time(hour=16, minute=0)
            )
            check_out_datetime = datetime.datetime.combine(
                check_out_date.date(),
                datetime.time(hour=12, minute=0)
            )

            # Create event title and description
            guest_name = notification.guest_name or "Guest"
            property_name = notification.property_name or "Airbnb Booking"
            num_guests = notification.num_guests or "?"

            event_title = f"{guest_name} ({num_guests}名) at {property_name}"

            description = (
                f"Airbnb Booking Confirmation\n\n"
                f"Guest: {guest_name}\n"
                f"Property: {property_name}\n"
            )

            if notification.reservation_id:
                description += f"Reservation ID: {notification.reservation_id}\n"

            if notification.num_guests:
                description += f"Number of Guests: {notification.num_guests}\n"

            if notification.amount and notification.currency:
                description += f"Amount: {notification.currency}{notification.amount}\n"

            # Create event with specific check-in and check-out times
            event = {
                "summary": event_title,
                "description": description,
                "start": {
                    "dateTime": check_in_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": "Asia/Tokyo",
                },
                "end": {
                    "dateTime": check_out_datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                    "timeZone": "Asia/Tokyo",
                },
                "colorId": ORANGE_COLOR_ID,
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 24 * 60},  # 1 day before
                        {"method": "email", "minutes": 24 * 60},  # 1 day before
                    ],
                },
            }

            # Add the event to the calendar
            created_event = self.service.events().insert(
                calendarId=calendar_id, body=event
            ).execute()

            # Get the event ID
            event_id = created_event.get("id")

            if event_id:
                # Save the calendar event to the database
                self.db.save_calendar_event(
                    notification_id=notification.notification_id,
                    event_id=event_id,
                    calendar_id=calendar_id
                )

            logger.info(
                f"Added booking to calendar: {event_title} "
                f"({check_in_datetime.strftime('%Y-%m-%d %H:%M')} to "
                f"{check_out_datetime.strftime('%Y-%m-%d %H:%M')})"
            )

            return event_id

        except Exception as e:
            logger.exception(f"Error adding booking to calendar: {e}")
            return None

    def delete_event(self, event_id: str, calendar_id: str = "primary", notification_id: Optional[str] = None) -> bool:
        """Delete an event from Google Calendar.

        Args:
            event_id: ID of the event to delete
            calendar_id: Google Calendar ID (default: primary)
            notification_id: Optional notification ID associated with the event

        Returns:
            True if deletion was successful, False otherwise
        """
        if not self.service:
            if not self.connect():
                logger.error("Could not connect to Google Calendar")
                return False

        try:
            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
            return True
        except Exception as e:
            logger.exception(f"Error deleting event {event_id}: {e}")
            return False
