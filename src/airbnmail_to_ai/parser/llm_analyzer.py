"""LLM-based analyzer for Airbnb reservation emails using Anthropic's Claude."""

import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

import requests
from loguru import logger

# Default system prompt for reservation analysis
DEFAULT_SYSTEM_PROMPT = """
You are an AI assistant specialized in analyzing Airbnb reservation emails.
Extract the exact check-in and check-out dates from the email content.
Format the dates as YYYY-MM-DD.
If you cannot determine the dates with certainty, indicate this clearly.
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
        self, email_content: str, system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze reservation email content using LLM.

        Args:
            email_content: Raw email content text
            system_prompt: Custom system prompt to use (defaults to reservation analysis)

        Returns:
            Dictionary with analysis results, including:
            - check_in_date: Extracted check-in date (YYYY-MM-DD format)
            - check_out_date: Extracted check-out date (YYYY-MM-DD format)
            - confidence: Confidence level of the extraction (high, medium, low)
            - analysis: Full analysis text from the LLM
        """
        if not system_prompt:
            system_prompt = DEFAULT_SYSTEM_PROMPT

        try:
            # Prepare messages for the LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract reservation details from this email:\n\n{email_content}"},
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
            "check_in_date": None,
            "check_out_date": None,
            "confidence": "low",
            "analysis": llm_response,
        }

        try:
            # Look for dates in common formats
            # Format: YYYY-MM-DD
            import re

            # Pattern for YYYY-MM-DD format
            date_pattern = r"\b(\d{4}-\d{2}-\d{2})\b"
            dates = re.findall(date_pattern, llm_response)

            # Alternative patterns for various date formats
            alt_patterns = [
                # DD/MM/YYYY
                r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
                # MM/DD/YYYY
                r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
                # DD Month YYYY
                r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
                # Month DD, YYYY
                r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
            ]

            # Try to find "check-in" and "check-out" keywords near dates
            check_in_patterns = [
                r"check[ -]?in.*?(\d{4}-\d{2}-\d{2})",
                r"check[ -]?in.*?(\d{1,2}/\d{1,2}/\d{4})",
                r"check[ -]?in.*?(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4})",
                r"(\d{4}-\d{2}-\d{2}).*?check[ -]?in",
            ]

            check_out_patterns = [
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
