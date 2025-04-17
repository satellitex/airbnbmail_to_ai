"""Parser for LLM response text."""

import json
import re
from typing import Any, Dict, Optional

from airbnmail_to_ai.parser.llm.date_utils import normalize_date, validate_date_pair
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


def extract_json_from_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Extract JSON from LLM response text.

    Args:
        response_text: Raw text response from the LLM

    Returns:
        Dictionary parsed from JSON or None if parsing fails
    """
    try:
        # Extract the JSON part if enclosed in ```json ... ``` or similar
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)

        if json_match:
            json_str = json_match.group(1)
            return json.loads(json_str)
        else:
            # If no code block markers, try parsing the entire response as JSON
            return json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse JSON response: {e}")
        return None


def parse_llm_response(llm_response: str) -> Dict[str, Any]:
    """Parse the LLM response to extract structured data.

    Args:
        llm_response: Raw text response from the LLM

    Returns:
        Dictionary with structured data extracted from the response
    """
    # First try to extract JSON directly
    parsed_json = extract_json_from_response(llm_response)
    if parsed_json:
        # Add the raw analysis
        parsed_json["analysis"] = llm_response
        return parsed_json

    # Initialize result with default values if JSON parsing failed
    logger.info("JSON parsing failed, falling back to regex parsing")
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
        # Extract notification type
        extract_notification_type(llm_response, result)

        # Extract dates
        extract_dates(llm_response, result)

        # Extract guest information
        extract_guest_info(llm_response, result)

        # Extract property information
        extract_property_info(llm_response, result)

        # Validate dates if both are present
        if result["check_in_date"] and result["check_out_date"]:
            result["check_in_date"], result["check_out_date"] = validate_date_pair(
                result["check_in_date"], result["check_out_date"]
            )

    except Exception as e:
        logger.exception(f"Error parsing LLM response: {e}")

    return result


def extract_notification_type(llm_response: str, result: Dict[str, Any]) -> None:
    """Extract notification type from LLM response.

    Args:
        llm_response: Raw text response from the LLM
        result: Result dictionary to update
    """
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


def extract_dates(llm_response: str, result: Dict[str, Any]) -> None:
    """Extract dates from LLM response.

    Args:
        llm_response: Raw text response from the LLM
        result: Result dictionary to update
    """
    # Find all dates in common formats
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
            result["check_in_date"] = normalize_date(match.group(1))
            result["confidence"] = "high"
            break

    # Try to find check-out date
    for pattern in check_out_patterns:
        match = re.search(pattern, llm_response, re.IGNORECASE)
        if match:
            result["check_out_date"] = normalize_date(match.group(1))
            result["confidence"] = "high"
            break

    # If specific check-in/check-out dates not found but we have dates, use them in order
    if (not result["check_in_date"] or not result["check_out_date"]) and len(dates) >= 2:
        result["check_in_date"] = dates[0]
        result["check_out_date"] = dates[1]
        result["confidence"] = "medium"


def extract_guest_info(llm_response: str, result: Dict[str, Any]) -> None:
    """Extract guest information from LLM response.

    Args:
        llm_response: Raw text response from the LLM
        result: Result dictionary to update
    """
    # Look for guest name
    guest_name_patterns = [
        # English patterns
        r"guest name.*?([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        r"guest.*?name.*?([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        r"guest:?\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        r"name of guest.*?([A-Z][a-z]+(?: [A-Z][a-z]+)+)",
        # Japanese patterns
        r"ゲスト名:?\s*([\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z]+(?:\s+[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z]+)*)",
        r"お客様:?\s*([\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z]+(?:\s+[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z]+)*)",
        r"予約者:?\s*([\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z]+(?:\s+[\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z]+)*)",
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
        r"num_guests:?\s*(\d+)",
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
    num_guests_direct = re.search(r"Number of guests:?\s*(\d+)", llm_response, re.IGNORECASE)
    if num_guests_direct and result["num_guests"] is None:
        result["num_guests"] = int(num_guests_direct.group(1))


def extract_property_info(llm_response: str, result: Dict[str, Any]) -> None:
    """Extract property information from LLM response.

    Args:
        llm_response: Raw text response from the LLM
        result: Result dictionary to update
    """
    # Look for property name
    property_name_patterns = [
        # English patterns
        r"property name.*?([A-Za-z0-9].*?)(?:\n|$)",
        r"property:?\s+([A-Za-z0-9].*?)(?:\n|$)",
        r"listing:?\s+([A-Za-z0-9].*?)(?:\n|$)",
        r"name of property.*?([A-Za-z0-9].*?)(?:\n|$)",
        r"booked:?\s+([A-Za-z0-9].*?)(?:\n|$)",
        # Japanese patterns
        r"物件名:?\s*([\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z0-9].*?)(?:\n|$)",
        r"宿泊先:?\s*([\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z0-9].*?)(?:\n|$)",
        r"リスティング:?\s*([\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Han}A-Za-z0-9].*?)(?:\n|$)",
    ]

    for pattern in property_name_patterns:
        match = re.search(pattern, llm_response, re.IGNORECASE)
        if match:
            result["property_name"] = match.group(1).strip()
            break
