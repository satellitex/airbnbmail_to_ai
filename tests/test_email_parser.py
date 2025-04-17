"""Tests for the email parser module."""

from datetime import datetime
from unittest.mock import patch

import pytest

from airbnmail_to_ai.models.notification import NotificationType
from airbnmail_to_ai.parser.email_parser import parse_email, parse_email_date


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


@pytest.fixture
def mock_llm_request_response():
    """Mock LLM analyzer response for booking request."""
    return {
        "notification_type": "booking_request",
        "check_in_date": "2025-05-01",
        "check_out_date": "2025-05-05",
        "received_date": "2025-04-15",
        "guest_name": "John",
        "num_guests": 2,
        "property_name": "Tokyo Apartment",
        "confidence": "high",
        "analysis": "I found the check-in date (2025-05-01) and check-out date (2025-05-05) with high confidence."
    }


@pytest.fixture
def mock_llm_confirmation_response():
    """Mock LLM analyzer response for booking confirmation."""
    return {
        "notification_type": "booking_confirmation",
        "check_in_date": "2025-05-01",
        "check_out_date": "2025-05-05",
        "received_date": "2025-04-16",
        "guest_name": None,
        "num_guests": None,
        "property_name": "Tokyo Apartment",
        "confidence": "high",
        "analysis": "I found the check-in date (2025-05-01) and check-out date (2025-05-05) with high confidence."
    }


@patch('airbnmail_to_ai.parser.llm.LLMAnalyzer.analyze_reservation')
def test_parse_booking_request(mock_analyze, booking_request_email, mock_llm_request_response):
    """Test parsing a booking request email."""
    # Configure the mock
    mock_analyze.return_value = mock_llm_request_response

    # Call the function
    notification = parse_email(booking_request_email)

    # Check that LLM analyzer was called with correct arguments
    mock_analyze.assert_called_once_with(booking_request_email)

    # Basic assertions
    assert notification is not None
    assert notification.notification_type == NotificationType.BOOKING_REQUEST
    assert notification.notification_id == "12345abc"
    assert notification.subject == "Booking request from John for Tokyo Apartment"

    # Verify LLM analysis and standard fields
    assert notification.llm_confidence == "high"
    assert notification.check_in == "2025-05-01"  # Should match LLM check_in_date
    assert notification.check_out == "2025-05-05"  # Should match LLM check_out_date
    assert notification.guest_name == "John"
    assert notification.num_guests == 2
    assert notification.property_name == "Tokyo Apartment"


@patch('airbnmail_to_ai.parser.llm.LLMAnalyzer.analyze_reservation')
def test_parse_booking_confirmation(mock_analyze, booking_confirmation_email, mock_llm_confirmation_response):
    """Test parsing a booking confirmation email."""
    # Configure the mock
    mock_analyze.return_value = mock_llm_confirmation_response

    # Call the function
    notification = parse_email(booking_confirmation_email)

    # Check that LLM analyzer was called with correct arguments
    mock_analyze.assert_called_once_with(booking_confirmation_email)

    # Basic assertions
    assert notification is not None
    assert notification.notification_type == NotificationType.BOOKING_CONFIRMATION
    assert notification.notification_id == "67890xyz"
    assert notification.subject == "Booking for Tokyo Apartment is confirmed"

    # Verify LLM analysis and standard fields
    assert notification.llm_confidence == "high"
    assert notification.check_in == "2025-05-01"  # Should match LLM check_in_date
    assert notification.check_out == "2025-05-05"  # Should match LLM check_out_date
    assert notification.property_name == "Tokyo Apartment"


@patch('airbnmail_to_ai.parser.llm.LLMAnalyzer.analyze_reservation')
def test_parse_unknown_notification(mock_analyze):
    """Test parsing an email with unknown notification type."""
    # Configure the mock to return empty results
    mock_analyze.return_value = {
        "notification_type": "unknown",
        "check_in_date": None,
        "check_out_date": None,
        "confidence": "low",
        "analysis": "Could not determine dates from this email."
    }

    unknown_email = {
        "id": "unknown123",
        "subject": "Something totally unrelated",
        "body_text": "This is not an Airbnb notification"
    }

    notification = parse_email(unknown_email)
    assert notification is not None
    assert notification.notification_type == NotificationType.UNKNOWN
    assert notification.notification_id == "unknown123"
    assert notification.subject == "Something totally unrelated"
    assert notification.llm_confidence == "low"
    # For unknown notification type, both standard and LLM date fields should be None
    assert notification.check_in is None


def test_date_parsing():
    """Test date parsing from email headers."""
    # Test standard format
    date_str = "Mon, 15 Apr 2025 12:34:56 +0900"
    parsed_date = parse_email_date(date_str)
    assert isinstance(parsed_date, datetime)
    assert parsed_date.year == 2025
    assert parsed_date.month == 4
    assert parsed_date.day == 15

    # Test invalid format
    invalid_date = "Not a real date"
    assert parse_email_date(invalid_date) is None

    # Test empty string
    assert parse_email_date("") is None
