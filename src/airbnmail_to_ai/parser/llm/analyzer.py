"""LLM-based analyzer for Airbnb reservation emails."""

import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

import requests

from airbnmail_to_ai.parser.llm.prompts import DEFAULT_SYSTEM_PROMPT
from airbnmail_to_ai.parser.llm.response_parser import parse_llm_response
from airbnmail_to_ai.parser.llm.date_utils import normalize_date
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


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
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.api_url = api_url
        self.model = model

        logger.debug("Initialized LLM analyzer with Claude model: {}", model)
        logger.debug("Anthropic API URL: {}", api_url)
        logger.debug("Anthropic API key provided: {}", bool(self.api_key))

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
            # Extract the received year from the email date if available
            received_year = None
            if email_data.get('date'):
                date_match = re.search(r'(\d{4})', email_data.get('date', ''))
                if date_match:
                    received_year = date_match.group(1)

            # Clean HTML from body if it contains HTML tags
            body_text = email_data.get('body_text', '')
            if re.search(r'<[^>]+>', body_text):
                logger.debug("HTML detected in email body, cleaning...")
                body_text = self._clean_html(body_text)

            # Prepare a comprehensive email summary with all available metadata
            email_summary = self._prepare_email_summary(email_data, body_text)

            # Prepare messages for the LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"<<EMAIL_HTML>>\n{email_summary}"},
            ]

            # Call Claude API
            result = self._call_anthropic_api(messages)

            # Parse the response
            parsed_result = parse_llm_response(result)

            # Normalize dates with received year context
            if 'check_in_date' in parsed_result and parsed_result['check_in_date']:
                parsed_result['check_in_date'] = normalize_date(
                    parsed_result['check_in_date'],
                    received_year
                )

            if 'check_out_date' in parsed_result and parsed_result['check_out_date']:
                parsed_result['check_out_date'] = normalize_date(
                    parsed_result['check_out_date'],
                    received_year
                )

            if 'received_date' in parsed_result and parsed_result['received_date']:
                parsed_result['received_date'] = normalize_date(
                    parsed_result['received_date'],
                    received_year
                )

            return parsed_result

        except Exception as e:
            logger.exception("Error in LLM analysis: {}", e)
            return {
                "notification_type": "unknown",
                "check_in_date": None,
                "check_out_date": None,
                "received_date": None,
                "guest_name": None,
                "num_guests": None,
                "property_name": None,
                "confidence": "low",
                "analysis": f"Error occurred during analysis: {str(e)}",
                "error": str(e),
            }

    def _clean_html(self, html_text: str) -> str:
        """Clean HTML content to plain text.

        Args:
            html_text: HTML content to clean

        Returns:
            Plain text with all HTML tags removed and whitespace normalized
        """
        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', html_text)

        # Decode common HTML entities
        entities = {
            '&nbsp;': ' ',
            '&amp;': '&',
            '&lt;': '<',
            '&gt;': '>',
            '&quot;': '"',
            '&apos;': "'",
            '&yen;': '¥',
            '&euro;': '€',
            '&pound;': '£',
            '&copy;': '©',
            '&reg;': '®',
            '&trade;': '™',
        }

        for entity, replacement in entities.items():
            text = text.replace(entity, replacement)

        # Normalize whitespace - replace consecutive whitespace with a single space
        text = re.sub(r'\s+', ' ', text)

        return text.strip()

    def _prepare_email_summary(self, email_data: Dict[str, Any], body_text: Optional[str] = None) -> str:
        """Prepare a comprehensive email summary with metadata for analysis.

        Args:
            email_data: Email data dictionary containing metadata and content
            body_text: Optional pre-cleaned body text

        Returns:
            Formatted email summary string
        """
        email_summary = f"Subject: {email_data.get('subject', '')}\n"
        email_summary += f"Date: {email_data.get('date', '')}\n"
        email_summary += f"From: {email_data.get('from', '')}\n"
        email_summary += f"To: {email_data.get('to', '')}\n\n"
        email_summary += f"Email Body:\n{body_text or email_data.get('body_text', '')}"

        return email_summary

    def _call_anthropic_api(self, messages: list) -> str:
        """Call the Anthropic Claude API with the given messages.

        Args:
            messages: List of message dictionaries for the LLM

        Returns:
            Text response from Claude
        """
        # If no API key is provided, return a placeholder response for development/testing
        if not self.api_key:
            logger.warning("No API key provided, using mock Claude response")
            # Return a response that will ensure no dates are extracted
            # and will parse correctly as JSON
            return """
            {
              "notification_type": "unknown",
              "check_in_date": null,
              "check_out_date": null,
              "received_date": null,
              "guest_name": null,
              "num_guests": null,
              "property_name": null,
              "confidence": "low"
            }
            """

        # Convert OpenAI-style messages format to Anthropic format
        system_content = ""
        user_content = ""

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] == "user":
                user_content = msg["content"]

        # Make API request to Anthropic
        logger.debug("Calling Anthropic API with model: {}", self.model)

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
            "temperature": 0.0,  # Zero temperature for deterministic results
            "max_tokens": 1000,
        }

        response = requests.post(self.api_url, headers=headers, json=data)
        response.raise_for_status()

        logger.debug("Received response from Anthropic API")

        return response.json()["content"][0]["text"]
