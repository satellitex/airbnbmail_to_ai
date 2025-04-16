"""LLM-based analyzer for Airbnb reservation emails using Anthropic's Claude."""

import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

import requests
from loguru import logger

# Default system prompt for reservation analysis
DEFAULT_SYSTEM_PROMPT = """
You are an AI assistant specialized in analyzing Airbnb reservation emails in both English and Japanese.
Extract the following information from the email:
1. Notification type: Classify the email as one of the following types:
   - BOOKING_REQUEST: When a guest requests to book
   - BOOKING_CONFIRMATION: When a booking is confirmed
   - CANCELLATION: When a booking is cancelled
   - MESSAGE: When a guest sends a message
   - REVIEW: When a review is submitted
   - REMINDER: Check-in or check-out reminders
   - PAYMENT: Payment related notifications
   - UNKNOWN: If none of the above apply
2. Check-in date: Extract the check-in date and format it as YYYY-MM-DD
3. Check-out date: Extract the check-out date and format it as YYYY-MM-DD
4. Received date: Parse the email received date into a standardized format (YYYY-MM-DD)
5. Guest name: Extract the full name of the guest making the booking
6. Number of guests: Extract the total number of guests for the booking
   - For Japanese emails, look for patterns like "ゲスト人数 大人X人" and extract X as the number
   - Look for numbers following words like "大人", "成人", "人", etc.
   - Always return only the numeric value (e.g., "4" not "4人")
7. Property name: Extract the name of the property being booked

Use all available information including subject line, received date, and email body.
If you cannot determine any piece of information with certainty, indicate this clearly.
For the number of guests, be precise - extract only the total number of adult guests.
Provide your confidence level for each extracted piece of information.

When outputting the number of guests, always include it in this format: "Number of guests: X"
"""


class LLMAnalyzer:
    """Analyzer that uses Claude to extract information from Airbnb emails."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_url: str = "https://api.anthropic.com/v1/messages",
        model: str = "claude-3-7-sonnet-20250219",
    ):
        """Initialize the LLM Analyzer.

        Args:
            api_key: API key for Anthropic's Claude API
            api_url: URL for the Anthropic API endpoint
            model: Claude model name to use
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    def analyze_reservation(
        self, email_data: Dict[str, Any], system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze reservation email content using LLM.

        Args:
            email_data: Email data dictionary containing subject, date, from, body_text, etc.
            system_prompt: Custom system prompt to use (defaults to reservation analysis)

        Returns:
            Dictionary with analysis results, including:
            - notification_type: Classified email type (BOOKING_CONFIRMATION, etc.)
            - check_in_date: Extracted check-in date (YYYY-MM-DD format)
            - check_out_date: Extracted check-out date (YYYY-MM-DD format)
            - received_date: Parsed received date (YYYY-MM-DD format)
            - confidence: Confidence level of the extraction (high, medium, low)
            - analysis: Full analysis text from the LLM
        """
        if not system_prompt:
            system_prompt = DEFAULT_SYSTEM_PROMPT

        try:
            # Prepare a comprehensive email summary with all available metadata
            email_summary = f"Subject: {email_data.get('subject', '')}\n"
            email_summary += f"Date: {email_data.get('date', '')}\n"
            email_summary += f"From: {email_data.get('from', '')}\n"
            email_summary += f"To: {email_data.get('to', '')}\n\n"
            email_summary += f"Email Body:\n{email_data.get('body_text', '')}"

            # Prepare messages for the LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract information from this Airbnb email:\n\n{email_summary}"},
            ]

            # Call LLM API or local model
            result = self._call_llm_api(messages)

            # Parse the LLM response to extract structured data
            analysis_result = self._parse_llm_response(result)

            return analysis_result

        except Exception as e:
            logger.exception(f"Error in LLM analysis: {e}")
            return {
                "check_in_date": None,
                "check_out_date": None,
                "confidence": "low",
                "analysis": f"Error occurred during analysis: {str(e)}",
                "error": str(e),
            }

    def _call_llm_api(self, messages: list) -> str:
        """Call the Anthropic Claude API with the given messages.

        Args:
            messages: List of message dictionaries for the LLM

        Returns:
            Text response from Claude
        """
        # If no API key is provided, return a placeholder response for development/testing
        if not self.api_key:
            logger.warning("No API key provided, using mock Claude response")
            return "Could not determine exact dates from the email content."

        # Convert OpenAI-style messages format to Anthropic format
        system_content = ""
        user_content = ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                user_content = msg["content"]

        # Make API request to Anthropic
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        data = {
            "model": self.model,
            "system": system_content,
            "messages": [
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.1,  # Low temperature for more deterministic results
            "max_tokens": 500,
        }

        response = requests.post(self.api_url, headers=headers, json=data)
        response.raise_for_status()

        return response.json()["content"][0]["text"]

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """Parse the LLM response to extract structured data.

        Args:
            llm_response: Raw text response from the LLM

        Returns:
            Dictionary with structured data extracted from the response
        """
        # Initialize result with default values
        result = {
            "notification_type": "unknown",
            "check_in_date": None,
            "check_out_date": None,
            "received_date": None,
            "guest_name": None,
            "num_guests": None,
            "property_name": None,
            "confidence": "low",
            "analysis": llm_response,
        }

        try:
            import re

            # Extract notification type
            notification_types = {
                "booking_request": ["booking request", "reservation request"],
                "booking_confirmation": ["booking confirmation", "reservation confirmation", "confirmed", "booked"],
                "cancellation": ["cancelled", "canceled", "cancellation"],
                "message": ["message", "sent you"],
                "review": ["review", "feedback"],
                "reminder": ["reminder", "checkout", "checkin"],
                "payment": ["payout", "payment"],
            }

            for notification_type, keywords in notification_types.items():
                if any(keyword.lower() in llm_response.lower() for keyword in keywords):
                    result["notification_type"] = notification_type
                    break

            # Find all dates in common formats
            # Pattern for YYYY-MM-DD format
            date_pattern = r"\b(\d{4}-\d{2}-\d{2})\b"
            dates = re.findall(date_pattern, llm_response)

            # Look for received date
            received_patterns = [
                r"received date.*?(\d{4}-\d{2}-\d{2})",
                r"email date.*?(\d{4}-\d{2}-\d{2})",
                r"date.*?(\d{4}-\d{2}-\d{2})",
            ]

            for pattern in received_patterns:
                match = re.search(pattern, llm_response, re.IGNORECASE)
                if match:
                    result["received_date"] = match.group(1)
                    break

            # Try to find "check-in" and "check-out" keywords near dates
            check_in_patterns = [
                r"check[ -]?in date.*?(\d{4}-\d{2}-\d{2})",
                r"check[ -]?in.*?(\d{4}-\d{2}-\d{2})",
                r"check[ -]?in.*?(\d{1,2}/\d{1,2}/\d{4})",
                r"check[ -]?in.*?(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
                r"(\d{4}-\d{2}-\d{2}).*?check[ -]?in",
            ]

            check_out_patterns = [
                r"check[ -]?out date.*?(\d{4}-\d{2}-\d{2})",
                r"check[ -]?out.*?(\d{4}-\d{2}-\d{2})",
                r"check[ -]?out.*?(\d{1,2}/\d{1,2}/\d{4})",
                r"check[ -]?out.*?(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
                r"(\d{4}-\d{2}-\d{2}).*?check[ -]?out",
            ]

            # Try to find check-in date
            for pattern in check_in_patterns:
                match = re.search(pattern, llm_response, re.IGNORECASE)
                if match:
                    result["check_in_date"] = self._normalize_date(match.group(1))
                    result["confidence"] = "high"
                    break

            # Try to find check-out date
            for pattern in check_out_patterns:
                match = re.search(pattern, llm_response, re.IGNORECASE)
                if match:
                    result["check_out_date"] = self._normalize_date(match.group(1))
                    result["confidence"] = "high"
                    break

            # If specific check-in/check-out dates not found but we have dates, use them in order
            if (not result["check_in_date"] or not result["check_out_date"]) and len(dates) >= 2:
                result["check_in_date"] = dates[0]
                result["check_out_date"] = dates[1]
                result["confidence"] = "medium"

            # Look for guest name
            guest_name_patterns = [
                r"guest name.*?([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
                r"guest.*?name.*?([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
                r"guest:?\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
                r"name of guest.*?([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
            ]

            for pattern in guest_name_patterns:
                match = re.search(pattern, llm_response, re.IGNORECASE)
                if match:
                    result["guest_name"] = match.group(1).strip()
                    break

            # Look for number of guests
            num_guests_patterns = [
                # English patterns
                r"number of guests:?\s*(\d+)",
                r"guests:?\s*(\d+)",
                r"(\d+)\s+guest(s)?",
                r"guest(s)?:?\s*(\d+)",
                r"party of\s*(\d+)",
                r"(\d+)\s+people",
                r"(\d+)\s+person(s)?",
                # Japanese patterns
                r"ゲスト人数\s*(?:大人)?(\d+)(?:人|名)",
                r"大人(\d+)(?:人|名)",
                r"成人(\d+)(?:人|名)",
                r"(\d+)(?:人|名)(?:の大人|のゲスト)?",
                # Direct from LLM output format
                r"number of guests:?\s*(\d+)",
            ]

            for pattern in num_guests_patterns:
                match = re.search(pattern, llm_response, re.IGNORECASE)
                if match:
                    # For the patterns where the number is in the second capturing group
                    if pattern == r"guest(s)?:?\s*(\d+)" or pattern == r"person(s)?:?\s*(\d+)":
                        result["num_guests"] = int(match.group(2))
                    else:
                        # For all other patterns, the number is in the first capturing group
                        result["num_guests"] = int(match.group(1))
                    break

            # Direct extraction from LLM response for number of guests
            # This is more reliable than trying to re-parse the original email
            num_guests_direct = re.search(r"Number of guests:?\s*(\d+)", llm_response, re.IGNORECASE)
            if num_guests_direct and result["num_guests"] is None:
                result["num_guests"] = int(num_guests_direct.group(1))

            # Look for property name
            property_name_patterns = [
                r"property name.*?([A-Za-z0-9].*?)(?:\n|$)",
                r"property:?\s+([A-Za-z0-9].*?)(?:\n|$)",
                r"listing:?\s+([A-Za-z0-9].*?)(?:\n|$)",
                r"name of property.*?([A-Za-z0-9].*?)(?:\n|$)",
                r"booked:?\s+([A-Za-z0-9].*?)(?:\n|$)",
            ]

            for pattern in property_name_patterns:
                match = re.search(pattern, llm_response, re.IGNORECASE)
                if match:
                    result["property_name"] = match.group(1).strip()
                    break

            # Check if dates are in proper format
            if result["check_in_date"] and result["check_out_date"]:
                # Validate dates
                try:
                    check_in = datetime.strptime(result["check_in_date"], "%Y-%m-%d")
                    check_out = datetime.strptime(result["check_out_date"], "%Y-%m-%d")

                    # Make sure check-out is after check-in
                    if check_out <= check_in:
                        # Swap if in wrong order
                        result["check_in_date"], result["check_out_date"] = result["check_out_date"], result["check_in_date"]
                except ValueError:
                    # If dates can't be parsed, set them to None
                    result["check_in_date"] = None
                    result["check_out_date"] = None
                    result["confidence"] = "low"

        except Exception as e:
            logger.warning(f"Error parsing LLM response: {e}")

        return result

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date string to YYYY-MM-DD format.

        Args:
            date_str: Date string in various possible formats

        Returns:
            Date string in YYYY-MM-DD format, or original string if parsing fails
        """
        try:
            # Try various date formats
            formats = [
                "%Y-%m-%d",  # 2023-04-15
                "%d/%m/%Y",  # 15/04/2023
                "%m/%d/%Y",  # 04/15/2023
                "%d %B %Y",  # 15 April 2023
                "%B %d, %Y",  # April 15, 2023
                "%B %d %Y",  # April 15 2023
                "%d %b %Y",  # 15 Apr 2023
                "%b %d, %Y",  # Apr 15, 2023
            ]

            for date_format in formats:
                try:
                    dt = datetime.strptime(date_str, date_format)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue

            # If all formats failed, return the original string
            return date_str

        except Exception:
            return date_str
