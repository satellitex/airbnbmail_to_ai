"""Date utility functions for the LLM analyzer."""

from datetime import datetime
import re
from typing import Optional


def normalize_date(date_str: str, received_year: Optional[str] = None) -> str:
    """Normalize date string to YYYY-MM-DD format.

    Args:
        date_str: Date string in various possible formats
        received_year: Year when the email was received, to use for Japanese dates without year

    Returns:
        Date string in YYYY-MM-DD format, or original string if parsing fails
    """
    try:
        # If the input is already in YYYY-MM-DD format, return it
        if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
            return date_str

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

        # Japanese date with full year (2023年4月15日 -> 2023-04-15)
        jp_date_pattern = r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日"
        jp_match = re.search(jp_date_pattern, date_str)
        if jp_match:
            year = jp_match.group(1)
            month = jp_match.group(2).zfill(2)  # Pad single-digit month (4 -> 04)
            day = jp_match.group(3).zfill(2)    # Pad single-digit day (5 -> 05)
            return f"{year}-{month}-{day}"

        # Japanese date without year (4月15日 -> YYYY-04-15)
        # Optionally includes day of week in parentheses (4月15日(月) -> YYYY-04-15)
        jp_short_pattern = r"(\d{1,2})月\s*(\d{1,2})日(?:\([月火水木金土日]\))?"
        jp_short_match = re.search(jp_short_pattern, date_str)
        if jp_short_match and received_year:
            year = received_year
            month = jp_short_match.group(1).zfill(2)
            day = jp_short_match.group(2).zfill(2)
            return f"{year}-{month}-{day}"

        # Try standard formats
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


def validate_date_pair(check_in: str, check_out: str) -> tuple[str, str]:
    """Validate check-in and check-out dates and ensure proper order.

    Args:
        check_in: Check-in date in YYYY-MM-DD format
        check_out: Check-out date in YYYY-MM-DD format

    Returns:
        Tuple of (check_in, check_out) dates with proper ordering
    """
    try:
        in_date = datetime.strptime(check_in, "%Y-%m-%d")
        out_date = datetime.strptime(check_out, "%Y-%m-%d")

        # Make sure check-out is after check-in
        if out_date <= in_date:
            return check_out, check_in  # Swap if in wrong order

        return check_in, check_out
    except ValueError:
        # If dates can't be parsed, return as-is
        return check_in, check_out
