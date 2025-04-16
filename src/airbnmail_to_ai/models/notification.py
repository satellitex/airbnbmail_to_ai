"""Notification data models."""

from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class NotificationType(str, Enum):
    """Types of Airbnb notifications."""

    BOOKING_REQUEST = "booking_request"
    BOOKING_CONFIRMATION = "booking_confirmation"
    CANCELLATION = "cancellation"
    MESSAGE = "message"
    REVIEW = "review"
    REMINDER = "reminder"
    PAYMENT = "payment"
    UNKNOWN = "unknown"


class AirbnbNotification(BaseModel):
    """Model representing an Airbnb notification email."""

    # Base notification fields
    notification_id: str
    notification_type: NotificationType
    subject: str
    received_at: Optional[datetime] = None
    sender: str
    raw_text: str
    raw_html: str

    # Booking-related fields
    reservation_id: Optional[str] = None
    property_name: Optional[str] = None
    guest_name: Optional[str] = None
    check_in: Optional[str] = None
    check_out: Optional[str] = None
    num_guests: Optional[int] = None
    amount: Optional[float] = None
    currency: Optional[str] = None

    # Cancellation-related fields
    cancellation_reason: Optional[str] = None

    # Message-related fields
    sender_name: Optional[str] = None
    message_content: Optional[str] = None

    # Review-related fields
    reviewer_name: Optional[str] = None
    rating: Optional[int] = None
    review_content: Optional[str] = None

    # LLM analysis results
    llm_analysis: Optional[Dict[str, Any]] = None
    llm_check_in_date: Optional[str] = None
    llm_check_out_date: Optional[str] = None
    llm_confidence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the notification to a dictionary.

        Returns:
            Dictionary representation of the notification.
        """
        return self.model_dump(exclude_none=True)

    def get_summary(self) -> str:
        """Get a human-readable summary of the notification.

        Returns:
            Summary string.
        """
        summary_parts = [f"Type: {self.notification_type.value}"]

        if self.reservation_id:
            summary_parts.append(f"Reservation: {self.reservation_id}")

        if self.property_name:
            summary_parts.append(f"Property: {self.property_name}")

        if self.guest_name:
            summary_parts.append(f"Guest: {self.guest_name}")

        if self.check_in and self.check_out:
            summary_parts.append(f"Stay: {self.check_in} to {self.check_out}")

        if self.num_guests:
            summary_parts.append(f"Guests: {self.num_guests}")

        if self.amount and self.currency:
            summary_parts.append(f"Amount: {self.currency}{self.amount}")

        if self.message_content:
            # Truncate long messages
            message = (
                f"{self.message_content[:100]}..."
                if len(self.message_content) > 100
                else self.message_content
            )
            summary_parts.append(f"Message: {message}")

        return " | ".join(summary_parts)
