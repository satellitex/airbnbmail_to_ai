"""Module for parsing Airbnb email notifications using LLM."""

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from airbnmail_to_ai.models.notification import AirbnbNotification, NotificationType
from airbnmail_to_ai.parser.llm import LLMAnalyzer
from airbnmail_to_ai.parser.llm.date_utils import normalize_date
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)

# Initialize LLM Analyzer
llm_analyzer = LLMAnalyzer(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def parse_email(email: Dict[str, Any]) -> Optional[AirbnbNotification]:
    """Parse an Airbnb email and extract relevant information using LLM.

    Args:
        email: Email data from the Gmail API.

    Returns:
        AirbnbNotification object or None if parsing fails.
    """
    try:
        logger.info("Parsing email with subject: {}", email.get("subject", ""))

        # Extract basic email metadata
        email_id = email.get("id", "")
        subject = email.get("subject", "")
        body_text = email.get("body_text", "")

        # Use LLM to analyze complete email (including metadata)
        llm_results = llm_analyzer.analyze_reservation(email)

        logger.debug("LLM analysis results: {}",
                    {k: v for k, v in llm_results.items() if k != 'analysis'})

        # Get notification type from LLM analysis
        llm_notification_type = llm_results.get("notification_type", "unknown")
        notification_type = get_notification_type(llm_notification_type, subject)

        # Create a datetime object from the LLM-parsed received date if available
        received_at = get_received_datetime(llm_results, email)

        # Create notification data with basic fields
        notification_data = {
            "notification_id": email_id,
            "notification_type": notification_type,
            "subject": subject,
            "received_at": received_at,
            "sender": email.get("from", ""),
            "raw_text": body_text,
            "raw_html": email.get("body_html", ""),

            # Store the full LLM analysis
            "llm_analysis": llm_results,
            # Only store confidence from LLM
            "llm_confidence": llm_results.get("confidence"),

            # Set standard fields directly from LLM results
            "check_in": llm_results.get("check_in_date"),
            "check_out": llm_results.get("check_out_date"),
            "guest_name": llm_results.get("guest_name"),
            "property_name": llm_results.get("property_name"),
        }

        # Process number of guests
        notification_data["num_guests"] = extract_num_guests(llm_results, body_text)

        # Create and return the notification object
        logger.info("Successfully parsed email into notification")
        return AirbnbNotification(**notification_data)

    except Exception as e:
        logger.exception("Error parsing email: {}", e)
        return None


def get_notification_type(llm_type: str, subject: str) -> NotificationType:
    """Get notification type from LLM analysis or fallback to subject-based detection.

    Args:
        llm_type: Notification type from LLM analysis
        subject: Email subject line

    Returns:
        NotificationType enum value
    """
    try:
        # Try to get from LLM first
        return NotificationType[llm_type.upper()]
    except (KeyError, AttributeError):
        # Fallback to subject-based identification
        return identify_notification_type_from_subject(subject)


def get_received_datetime(llm_results: Dict[str, Any], email: Dict[str, Any]) -> Optional[datetime]:
    """Get received datetime from LLM analysis or fallback to email date.

    Args:
        llm_results: Results from LLM analysis
        email: Email data dictionary

    Returns:
        datetime object or None
    """
    llm_received_date = llm_results.get("received_date")

    if llm_received_date:
        try:
            return datetime.strptime(llm_received_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            logger.warning("Failed to parse LLM received date: {}", llm_received_date)

    # Fallback to standard parsing
    return parse_email_date(email.get("date", ""))


def extract_num_guests(llm_results: Dict[str, Any], body_text: str) -> Optional[int]:
    """Extract number of guests from LLM results or fallback to text parsing.

    Args:
        llm_results: Results from LLM analysis
        body_text: Email body text

    Returns:
        Integer number of guests or None
    """
    if llm_results.get("num_guests") is not None:
        try:
            return int(llm_results.get("num_guests"))
        except (ValueError, TypeError):
            logger.warning("Failed to parse LLM num_guests: {}", llm_results.get("num_guests"))

    # Fallback to extracting from email text
    if "guest" in body_text.lower():
        for line in body_text.split("\n"):
            if "guest" in line.lower():
                # Try to get number of guests if mentioned
                try:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.isdigit() and i > 0 and "guest" in parts[i+1].lower():
                            return int(part)
                except (IndexError, ValueError):
                    pass

    return None


def identify_notification_type_from_subject(subject: str) -> NotificationType:
    """Identify the notification type based on the email subject.

    Args:
        subject: Email subject line.

    Returns:
        NotificationType enum value.
    """
    subject_lower = subject.lower()

    logger.debug("Identifying notification type from subject: {}", subject)

    notification_keywords = {
        NotificationType.BOOKING_REQUEST: ["booking request", "reservation request"],
        NotificationType.BOOKING_CONFIRMATION: ["confirmed", "confirmation", "booked", "予約確定"],
        NotificationType.CANCELLATION: ["cancelled", "canceled", "cancellation"],
        NotificationType.MESSAGE: ["message", "sent you"],
        NotificationType.REVIEW: ["review", "feedback"],
        NotificationType.REMINDER: ["reminder", "checkout", "checkin"],
        NotificationType.PAYMENT: ["payout", "payment"],
    }

    for notification_type, keywords in notification_keywords.items():
        if any(keyword in subject_lower for keyword in keywords):
            logger.debug("Identified notification type: {}", notification_type)
            return notification_type

    logger.debug("Could not identify notification type, defaulting to UNKNOWN")
    return NotificationType.UNKNOWN


def parse_email_date(date_str: str) -> Optional[datetime]:
    """Parse a date string into a datetime object.

    Args:
        date_str: Date string from the email.

    Returns:
        datetime object or None if parsing fails.
    """
    if not date_str:
        return None

    logger.debug("Parsing email date: {}", date_str)

    # Common email date formats
    date_formats = [
        "%a, %d %b %Y %H:%M:%S %z",         # Mon, 14 Apr 2025 14:56:34 +0000
        "%a, %d %b %Y %H:%M:%S %Z",         # Mon, 14 Apr 2025 14:56:34 UTC
        "%a %d %b %Y %H:%M:%S %z",          # Mon 14 Apr 2025 14:56:34 +0000
        "%a %d %b %Y %H:%M:%S %Z",          # Mon 14 Apr 2025 14:56:34 UTC
        "%d %b %Y %H:%M:%S %z",             # 14 Apr 2025 14:56:34 +0000
        "%d %b %Y %H:%M:%S %Z",             # 14 Apr 2025 14:56:34 UTC
        "%a, %d %b %Y %H:%M:%S",            # Mon, 14 Apr 2025 14:56:34
        "%Y-%m-%dT%H:%M:%S%z",              # 2025-04-14T14:56:34+0000
        "%Y-%m-%d %H:%M:%S",                # 2025-04-14 14:56:34
        "%Y-%m-%d",                         # 2025-04-14
    ]

    # Clean up the date string
    date_str = date_str.replace("(UTC)", "UTC").replace("(GMT)", "GMT")

    # Try each format
    for date_format in date_formats:
        try:
            return datetime.strptime(date_str, date_format)
        except ValueError:
            continue

    # Try extracting just the date part using regex
    date_patterns = [
        r'(\d{4}-\d{2}-\d{2})',                                           # 2025-04-14
        r'(\d{1,2})\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})',  # 14 Apr 2025
        r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+(\d{1,2})\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})'  # Mon, 14 Apr 2025
    ]

    for pattern in date_patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                if len(match.groups()) == 1:
                    # For YYYY-MM-DD format
                    return datetime.strptime(match.group(1), "%Y-%m-%d")
                elif len(match.groups()) == 2:
                    # For patterns with day and year
                    day = match.group(1)
                    year = match.group(2)
                    month_str = re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*', date_str).group(0)
                    month_str = month_str[:3]  # Ensure we just get the first three letters
                    date_part = f"{day} {month_str} {year}"
                    return datetime.strptime(date_part, "%d %b %Y")
            except (ValueError, AttributeError):
                continue

    logger.warning("Could not parse date: {}", date_str)
    return None
