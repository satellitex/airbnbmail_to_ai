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

        # Use LLM to analyze complete email (including metadata)
        llm_results = llm_analyzer.analyze_reservation(email)

        # Get notification type from LLM analysis
        llm_notification_type = llm_results.get("notification_type", "unknown")
        notification_type = getattr(NotificationType, llm_notification_type.upper(), NotificationType.UNKNOWN)

        # Create a datetime object from the LLM-parsed received date if available
        llm_received_date = llm_results.get("received_date")
        received_at = None
        if llm_received_date:
            try:
                received_at = datetime.strptime(llm_received_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                # Fallback to standard parsing if LLM parsing fails
                received_at = _parse_date(email.get("date", ""))
        else:
            # Fallback to standard parsing if LLM didn't extract a date
            received_at = _parse_date(email.get("date", ""))

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
            "num_guests": llm_results.get("num_guests"),
            "property_name": llm_results.get("property_name"),
        }

        # Set number of guests, converting to int if present
        if llm_results.get("num_guests") is not None:
            try:
                notification_data["num_guests"] = int(llm_results.get("num_guests"))
            except (ValueError, TypeError):
                # Fallback to extracting from the email text if LLM parsing fails
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
    import re
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

    logger.warning(f"Could not parse date: {date_str}")
    return None
