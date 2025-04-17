"""Command modules for the Airbnb Mail to AI CLI."""

from airbnmail_to_ai.cli.commands.auth_commands import auth_command, setup_auth_parser
from airbnmail_to_ai.cli.commands.calendar_commands import calendar_command, setup_calendar_parser
from airbnmail_to_ai.cli.commands.db_commands import db_command, setup_db_parser
from airbnmail_to_ai.cli.commands.fetch_commands import fetch_command, setup_fetch_parser
from airbnmail_to_ai.cli.commands.utils import list_commands

__all__ = [
    "auth_command",
    "setup_auth_parser",
    "calendar_command",
    "setup_calendar_parser",
    "db_command",
    "setup_db_parser",
    "fetch_command",
    "setup_fetch_parser",
    "list_commands",
]
