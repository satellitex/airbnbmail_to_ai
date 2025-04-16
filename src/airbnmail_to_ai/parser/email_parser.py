"""Module for parsing Airbnb email notifications using LLM."""

import os
from datetime import datetime
from typing import Any, Dict, Optional

from loguru import logger

from airbnmail_to_ai.models.notification import AirbnbNotification, NotificationType
from airbnmail_to_ai.parser.llm_analyzer import LLMAnalyzer


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
        # Extract basic email metadata
        email_id = email.get("id", "")
        subject = email.get("subject", "")
        body_text = email.get("body_text", "")

        # Extract notification type from the subject
        notification_type = _identify_notification_type(subject)

        # Use LLM to analyze email content for all emails
        llm_results = llm_analyzer.analyze_reservation(body_text)

        # Create notification data with basic fields
        notification_data = {
            "notification_id": email_id,
            "notification_type": notification_type,
            "subject": subject,
            "received_at": _parse_date(email.get("date", "")),
            "sender": email.get("from", ""),
            "raw_text": body_text,
            "raw_html": email.get("body_html", ""),

            # Add LLM analysis results
            "llm_analysis": llm_results,
            "llm_check_in_date": llm_results.get("check_in_date"),
            "llm_check_out_date": llm_results.get("check_out_date"),
            "llm_confidence": llm_results.get("confidence"),

            # Add check-in and check-out dates from LLM analysis to standard fields
            "check_in": llm_results.get("check_in_date"),
            "check_out": llm_results.get("check_out_date"),
        }

        # Extract additional information if available in the email
        # This is kept minimal but ensures basic compatibility with existing code
        if "guest" in body_text.lower():
            for line in body_text.split("\n"):
                if "guest" in line.lower():
                    # Try to get number of guests if mentioned
                    try:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part.isdigit() and i > 0 and "guest" in parts[i+1].lower():
                                notification_data["num_guests"] = int(part)
                                break
                    except (IndexError, ValueError):
                        pass

        # Create and return the notification object
        return AirbnbNotification(**notification_data)

    except Exception as e:
        logger.exception(f"Error parsing email: {e}")
        return None


def _identify_notification_type(subject: str) -> NotificationType:
    """Identify the notification type based on the email subject.

    Args:
        subject: Email subject line.

    Returns:
        NotificationType enum value.
    """
    subject_lower = subject.lower()

    if any(keyword in subject_lower for keyword in ["booking request", "reservation request"]):
        return NotificationType.BOOKING_REQUEST

    if any(keyword in subject_lower for keyword in ["confirmed", "confirmation", "booked"]):
        return NotificationType.BOOKING_CONFIRMATION

    if any(keyword in subject_lower for keyword in ["cancelled", "canceled", "cancellation"]):
        return NotificationType.CANCELLATION

    if any(keyword in subject_lower for keyword in ["message", "sent you"]):
        return NotificationType.MESSAGE

    if any(keyword in subject_lower for keyword in ["review", "feedback"]):
        return NotificationType.REVIEW

    if any(keyword in subject_lower for keyword in ["reminder", "checkout", "checkin"]):
        return NotificationType.REMINDER

    if any(keyword in subject_lower for keyword in ["payout", "payment"]):
        return NotificationType.PAYMENT

    return NotificationType.UNKNOWN


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse a date string into a datetime object.

    Args:
        date_str: Date string from the email.

    Returns:
        datetime object or None if parsing fails.
    """
    if not date_str:
        return None

    try:
        # Try standard email date format
        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
    except ValueError:
        try:
            # Try alternative format
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return None
