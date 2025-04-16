#!/usr/bin/env python
"""
Demo script for the database and calendar integration.

This script demonstrates:
1. Creating a test notification
2. Saving it to the database
3. Adding it to the calendar
4. Checking for duplicate bookings

Usage:
    python examples/db_calendar_demo.py
"""

import os
import sys
from datetime import datetime

from loguru import logger

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from airbnmail_to_ai.calendar.calendar_service import CalendarService
from airbnmail_to_ai.db.db_service import DatabaseService
from airbnmail_to_ai.models.notification import AirbnbNotification, NotificationType


def create_test_notification(notification_id: str, reservation_id: str) -> AirbnbNotification:
    """Create a test notification for demonstration purposes.

    Args:
        notification_id: Unique ID for the notification
        reservation_id: Reservation ID for the booking

    Returns:
        AirbnbNotification: A test notification object
    """
    return AirbnbNotification(
        notification_id=notification_id,
        notification_type=NotificationType.BOOKING_CONFIRMATION,
        subject="予約確定: 山田さんが5月1日〜5月3日に予約しました",
        received_at=datetime.now().isoformat(),
        sender="automated@airbnb.com",
        raw_text="This is a test notification",
        raw_html="<p>This is a test notification</p>",
        reservation_id=reservation_id,
        property_name="東京タワービュー",
        guest_name="山田太郎",
        check_in="2025-05-01",
        check_out="2025-05-03",
        num_guests=2,
        amount=15000,
        currency="¥",
        llm_analysis={
            "check_in_date": "2025-05-01",
            "check_out_date": "2025-05-03",
            "guest_name": "山田太郎",
            "property_name": "東京タワービュー",
            "num_guests": 2
        },
        llm_confidence="high"
    )


def run_demo():
    """Run the database and calendar integration demo."""
    # Initialize the database service
    logger.info("Initializing database service...")
    db = DatabaseService(db_path="demo_notifications.db")

    # Initialize the calendar service with the same database
    logger.info("Initializing calendar service...")
    calendar = CalendarService(
        credentials_path="credentials.json",
        token_path="calendar_token.json",
        db_path="demo_notifications.db"
    )

    # Connect to Google Calendar
    if not calendar.connect():
        logger.error("Failed to connect to Google Calendar")
        return

    # Create two notifications with the same booking details but different IDs
    logger.info("Creating test notifications...")
    notification1 = create_test_notification(
        notification_id="test-notification-1",
        reservation_id="RES123456"
    )
    notification2 = create_test_notification(
        notification_id="test-notification-2",
        reservation_id="RES123456"
    )

    # Save the first notification directly to the database
    logger.info("Saving first notification to database...")
    if db.save_notification(notification1):
        logger.success("Saved notification1 to database")
    else:
        logger.error("Failed to save notification1 to database")

    # Try to find the notification in the database
    logger.info("Checking if notification exists in database...")
    if db.notification_exists(notification1.notification_id):
        logger.success("Found notification1 in database")
    else:
        logger.error("Could not find notification1 in database")

    # Add the first notification to the calendar
    logger.info("Adding first notification to calendar...")
    event_id1 = calendar.add_booking_to_calendar(notification1)
    if event_id1:
        logger.success(f"Added notification1 to calendar with event ID: {event_id1}")
    else:
        logger.error("Failed to add notification1 to calendar")

    # Check if the notification has a calendar event
    logger.info("Checking if notification has calendar event...")
    if db.has_calendar_event(notification1.notification_id):
        cal_event = db.get_calendar_event(notification1.notification_id)
        logger.success(f"Found calendar event for notification1: {cal_event['event_id']}")
    else:
        logger.error("No calendar event found for notification1")

    # Now try adding the second notification
    # The system should detect it's a duplicate and link it to the existing calendar event
    logger.info("Adding second notification to calendar...")
    event_id2 = calendar.add_booking_to_calendar(notification2)
    if event_id2:
        logger.success(f"Added notification2 to calendar with event ID: {event_id2}")
        logger.info(f"Event ID1: {event_id1}, Event ID2: {event_id2}")
        if event_id1 == event_id2:
            logger.success("DUPLICATE DETECTED: Both notifications linked to the same calendar event")
        else:
            logger.warning("Notifications were not detected as duplicates")
    else:
        logger.error("Failed to add notification2 to calendar")

    # Show database statistics
    logger.info("Database statistics:")
    db.cursor.execute("SELECT COUNT(*) FROM airbnb_notifications")
    notification_count = db.cursor.fetchone()[0]

    db.cursor.execute("SELECT COUNT(*) FROM calendar_events")
    event_count = db.cursor.fetchone()[0]

    logger.info(f"Total notifications in database: {notification_count}")
    logger.info(f"Total calendar events in database: {event_count}")

    # Clean up - delete the calendar event
    if event_id1:
        logger.info(f"Cleaning up: Deleting calendar event {event_id1}...")
        if calendar.delete_event(event_id1):
            logger.success("Successfully deleted calendar event")
        else:
            logger.error("Failed to delete calendar event")


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )

    logger.info("Starting database and calendar integration demo...")
    run_demo()
    logger.info("Demo completed.")
