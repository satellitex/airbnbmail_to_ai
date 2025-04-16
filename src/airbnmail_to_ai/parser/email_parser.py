"""Module for parsing Airbnb email notifications."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import nltk
from loguru import logger
from nltk.tokenize import sent_tokenize

from airbnmail_to_ai.models.notification import AirbnbNotification, NotificationType


# Download required NLTK resources
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)


def parse_email(email: Dict[str, Any]) -> Optional[AirbnbNotification]:
    """Parse an Airbnb email and extract relevant information.

    Args:
        email: Email data from the Gmail API.

    Returns:
        AirbnbNotification object or None if parsing fails.
    """
    try:
        # Identify the notification type based on the subject
        subject = email.get("subject", "")
        notification_type = _identify_notification_type(subject)
        
        if notification_type == NotificationType.UNKNOWN:
            logger.warning(f"Unknown notification type for subject: {subject}")
            return None
        
        # Extract information based on the notification type
        notification_data = {
            "notification_id": email.get("id", ""),
            "notification_type": notification_type,
            "subject": subject,
            "received_at": _parse_date(email.get("date", "")),
            "sender": email.get("from", ""),
            "raw_text": email.get("body_text", ""),
            "raw_html": email.get("body_html", ""),
        }
        
        # Extract more specific information based on the notification type
        if notification_type == NotificationType.BOOKING_REQUEST:
            _extract_booking_request_info(notification_data, email)
        elif notification_type == NotificationType.BOOKING_CONFIRMATION:
            _extract_booking_confirmation_info(notification_data, email)
        elif notification_type == NotificationType.CANCELLATION:
            _extract_cancellation_info(notification_data, email)
        elif notification_type == NotificationType.MESSAGE:
            _extract_message_info(notification_data, email)
        elif notification_type == NotificationType.REVIEW:
            _extract_review_info(notification_data, email)
        
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


def _extract_text_between(text: str, start_marker: str, end_marker: str) -> str:
    """Extract text between two markers.

    Args:
        text: The text to search in.
        start_marker: Start marker string.
        end_marker: End marker string.

    Returns:
        Extracted text or empty string if not found.
    """
    try:
        start_idx = text.find(start_marker)
        if start_idx == -1:
            return ""
        
        start_idx += len(start_marker)
        end_idx = text.find(end_marker, start_idx)
        
        if end_idx == -1:
            return text[start_idx:].strip()
        
        return text[start_idx:end_idx].strip()
    except Exception:
        return ""


def _extract_booking_request_info(
    notification_data: Dict[str, Any], email: Dict[str, Any]
) -> None:
    """Extract booking request specific information.

    Args:
        notification_data: Dictionary to update with extracted data.
        email: Raw email data.
    """
    body_text = email.get("body_text", "")
    
    # Extract guest name
    guest_name_match = re.search(r"(?:from|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", body_text)
    if guest_name_match:
        notification_data["guest_name"] = guest_name_match.group(1)
    
    # Extract dates
    date_range_match = re.search(
        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+(?:to|-)\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        body_text,
    )
    if date_range_match:
        notification_data["check_in"] = date_range_match.group(1)
        notification_data["check_out"] = date_range_match.group(2)
    
    # Extract number of guests
    guests_match = re.search(r"(\d+)\s+(?:guest|guests)", body_text)
    if guests_match:
        notification_data["num_guests"] = int(guests_match.group(1))
    
    # Extract property name
    property_match = re.search(r"for\s+(.+?)(?:\.|$)", body_text)
    if property_match:
        notification_data["property_name"] = property_match.group(1).strip()


def _extract_booking_confirmation_info(
    notification_data: Dict[str, Any], email: Dict[str, Any]
) -> None:
    """Extract booking confirmation specific information.

    Args:
        notification_data: Dictionary to update with extracted data.
        email: Raw email data.
    """
    body_text = email.get("body_text", "")
    
    # Extract reservation ID
    res_id_match = re.search(r"Reservation(?:\s+code)?(?:\s*|:\s*)([A-Z0-9]+)", body_text)
    if res_id_match:
        notification_data["reservation_id"] = res_id_match.group(1)
    
    # Extract dates
    date_range_match = re.search(
        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})\s+(?:to|-)\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})",
        body_text,
    )
    if date_range_match:
        notification_data["check_in"] = date_range_match.group(1)
        notification_data["check_out"] = date_range_match.group(2)
    
    # Extract amount
    amount_match = re.search(r"(¥|\$|€|£)(\d+(?:[.,]\d+)?)", body_text)
    if amount_match:
        notification_data["amount"] = float(amount_match.group(2).replace(",", ""))
        notification_data["currency"] = amount_match.group(1)
    
    # Extract property name from subject
    subject = email.get("subject", "")
    if "confirmed" in subject.lower():
        property_match = re.search(r"for\s+(.+?)(?:\s+is\s+confirmed|\.|$)", subject)
        if property_match:
            notification_data["property_name"] = property_match.group(1).strip()


def _extract_cancellation_info(
    notification_data: Dict[str, Any], email: Dict[str, Any]
) -> None:
    """Extract cancellation specific information.

    Args:
        notification_data: Dictionary to update with extracted data.
        email: Raw email data.
    """
    body_text = email.get("body_text", "")
    
    # Extract reservation ID
    res_id_match = re.search(r"Reservation(?:\s+code)?(?:\s*|:\s*)([A-Z0-9]+)", body_text)
    if res_id_match:
        notification_data["reservation_id"] = res_id_match.group(1)
    
    # Extract reason if available
    reason_text = _extract_text_between(body_text, "Reason:", "\n")
    if reason_text:
        notification_data["cancellation_reason"] = reason_text.strip()
    
    # Extract property name
    property_match = re.search(r"for\s+(.+?)(?:\s+has\s+been\s+cancelled|\.|$)", body_text)
    if property_match:
        notification_data["property_name"] = property_match.group(1).strip()


def _extract_message_info(
    notification_data: Dict[str, Any], email: Dict[str, Any]
) -> None:
    """Extract guest message specific information.

    Args:
        notification_data: Dictionary to update with extracted data.
        email: Raw email data.
    """
    body_text = email.get("body_text", "")
    
    # Extract sender name
    sender_match = re.search(r"(?:from|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", body_text)
    if sender_match:
        notification_data["sender_name"] = sender_match.group(1)
    
    # Extract message content
    sentences = sent_tokenize(body_text)
    message_content = ""
    in_message = False
    
    for sentence in sentences:
        if "Message:" in sentence or "wrote:" in sentence:
            in_message = True
            # Remove the prefix and keep the rest
            message_part = sentence.split("Message:", 1)[-1].strip()
            if not message_part:
                continue
            message_content += message_part + " "
        elif in_message and not any(
            marker in sentence
            for marker in ["View this message", "Reply to this message", "Airbnb,", "Copyright"]
        ):
            message_content += sentence + " "
    
    notification_data["message_content"] = message_content.strip()


def _extract_review_info(
    notification_data: Dict[str, Any], email: Dict[str, Any]
) -> None:
    """Extract review specific information.

    Args:
        notification_data: Dictionary to update with extracted data.
        email: Raw email data.
    """
    body_text = email.get("body_text", "")
    
    # Extract reviewer name
    reviewer_match = re.search(r"(?:from|by)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", body_text)
    if reviewer_match:
        notification_data["reviewer_name"] = reviewer_match.group(1)
    
    # Extract rating if available
    rating_match = re.search(r"(\d+)(?:\s+out of \d+)?\s+stars?", body_text, re.IGNORECASE)
    if rating_match:
        notification_data["rating"] = int(rating_match.group(1))
    
    # Extract review content
    review_content = _extract_text_between(body_text, "Review:", "\n\n")
    if review_content:
        notification_data["review_content"] = review_content
