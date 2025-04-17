"""Utility functions for CLI commands."""

from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


def list_commands() -> None:
    """Print available commands."""
    logger.info("Listing available commands")
    print("Available commands:")
    print("  fetch    - Fetch emails from automated@airbnb.com")
    print("  auth     - Authenticate with Gmail API")
    print("  calendar - Add Airbnb bookings to Google Calendar")
    print("  db       - Manage Airbnb notification database")
    print("\nFor more information on a command, use: <command> --help")
