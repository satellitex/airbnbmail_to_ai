"""Tests for the email parser module."""

from datetime import datetime
from unittest.mock import patch

import pytest

from airbnmail_to_ai.models.notification import NotificationType
from airbnmail_to_ai.parser.email_parser import parse_email


@pytest.fixture
def booking_request_email():
    """Sample booking request email data."""
    return {
        "id": "12345abc",
        "thread_id": "thread123",
        "subject": "Booking request from John for Tokyo Apartment",
        "from": "Airbnb <automated@airbnb.com>",
        "to": "host@example.com",
        "date": "Mon, 15 Apr 2025 12:34:56 +0900",
        "body_text": """
            You have a booking request from John for Tokyo Apartment.
            Dates: 1 May 2025 to 5 May 2025
            Number of guests: 2
            Please review and accept or decline this request.
        """,
        "body_html": "<html><body>Booking request details</body></html>",
        "labels": ["INBOX", "UNREAD"],
    }


@pytest.fixture
def booking_confirmation_email():
    """Sample booking confirmation email data."""
    return {
        "id": "67890xyz",
        "thread_id": "thread456",
        "subject": "Booking for Tokyo Apartment is confirmed",
        "from": "Airbnb <automated@airbnb.com>",
        "to": "host@example.com",
        "date": "Tue, 16 Apr 2025 10:20:30 +0900",
        "body_text": """
            The booking for Tokyo Apartment has been confirmed.
            Reservation code: ABC123
            Dates: 1 May 2025 to 5 May 2025
            Total amount: ¥50000
        """,
        "body_html": "<html><body>Booking confirmation details</body></html>",
        "labels": ["INBOX", "UNREAD"],
    }


def test_parse_booking_request(booking_request_email):
    """Test parsing a booking request email."""
    notification = parse_email(booking_request_email)
    
    assert notification is not None
    assert notification.notification_type == NotificationType.BOOKING_REQUEST
    assert notification.notification_id == "12345abc"
    assert notification.subject == "Booking request from John for Tokyo Apartment"
    assert notification.guest_name == "John"
    assert "Tokyo Apartment" in notification.property_name
    assert notification.num_guests == 2
    assert "1 May 2025" in notification.check_in
    assert "5 May 2025" in notification.check_out


def test_parse_booking_confirmation(booking_confirmation_email):
    """Test parsing a booking confirmation email."""
    notification = parse_email(booking_confirmation_email)
    
    assert notification is not None
    assert notification.notification_type == NotificationType.BOOKING_CONFIRMATION
    assert notification.notification_id == "67890xyz"
    assert notification.subject == "Booking for Tokyo Apartment is confirmed"
    assert notification.reservation_id == "ABC123"
    assert "Tokyo Apartment" in notification.property_name
    assert "1 May 2025" in notification.check_in
    assert "5 May 2025" in notification.check_out
    assert notification.amount == 50000
    assert notification.currency == "¥"


def test_parse_unknown_notification():
    """Test parsing an email with unknown notification type."""
    unknown_email = {
        "id": "unknown123",
        "subject": "Something totally unrelated",
        "body_text": "This is not an Airbnb notification",
    }
    
    notification = parse_email(unknown_email)
    assert notification is None


def test_date_parsing():
    """Test date parsing from email headers."""
    from airbnmail_to_ai.parser.email_parser import _parse_date
    
    # Test standard format
    date_str = "Mon, 15 Apr 2025 12:34:56 +0900"
    parsed_date = _parse_date(date_str)
    assert isinstance(parsed_date, datetime)
    assert parsed_date.year == 2025
    assert parsed_date.month == 4
    assert parsed_date.day == 15
    
    # Test invalid format
    invalid_date = "Not a real date"
    assert _parse_date(invalid_date) is None
    
    # Test empty string
    assert _parse_date("") is None
