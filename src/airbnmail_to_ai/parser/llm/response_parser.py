"""Parser for LLM response text."""

import json
import re
from typing import Any, Dict, Optional

from airbnmail_to_ai.parser.llm.date_utils import validate_date_pair
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
    # First attempt: try parsing the entire response as pure JSON
    # (This is the expected case with OpenAI's structured output parameter)
    try:
        # Clean response text by trimming whitespace
        clean_text = response_text.strip()
        return json.loads(clean_text)
    except json.JSONDecodeError:
        pass

    # Second attempt: Extract the JSON part if enclosed in ```json ... ``` or similar
    try:
        json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
            return json.loads(json_str)
    except (json.JSONDecodeError, AttributeError):
        pass

    # Third attempt: Handle potential mixed content with JSON by looking for { }
    try:
        # Find content between the first { and the last }
        match = re.search(r'({.+})', response_text, re.DOTALL)
        if match:
            json_candidate = match.group(1)
            return json.loads(json_candidate)
    except (json.JSONDecodeError, AttributeError):
        logger.warning(f"Failed to parse JSON response using all methods")
        return None


def parse_llm_response(llm_response: str) -> Dict[str, Any]:
    """Parse the LLM response to extract structured data.

    Args:
        llm_response: Raw text response from the LLM

    Returns:
        Dictionary with structured data extracted from the response
    """
    # Set up the default result structure
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

    # Try to extract JSON directly (primary method)
    parsed_json = extract_json_from_response(llm_response)
    if parsed_json:
        # Update the result with the parsed JSON data
        for key, value in parsed_json.items():
            if key in result:
                result[key] = value

        # Convert num_guests to integer if it's a string containing only digits
        if isinstance(result.get("num_guests"), str) and result["num_guests"] and result["num_guests"].isdigit():
            result["num_guests"] = int(result["num_guests"])

        # Validate dates if both are present
        if result["check_in_date"] and result["check_out_date"]:
            result["check_in_date"], result["check_out_date"] = validate_date_pair(
                result["check_in_date"], result["check_out_date"]
            )

        return result

    # If JSON parsing failed, log the error and return the default result
    logger.warning("JSON parsing failed completely, returning default values")
    return result
