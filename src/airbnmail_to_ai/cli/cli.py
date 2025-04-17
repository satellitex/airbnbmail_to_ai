"""Command line interface for Airbnb Mail to AI."""

import argparse
import sys
from typing import List, Optional

from airbnmail_to_ai.cli.commands import (
    list_commands,
    setup_auth_parser,
    setup_calendar_parser,
    setup_db_parser,
    setup_fetch_parser,
)
from airbnmail_to_ai.utils.logging import get_logger, setup_logger

# Initialize logger
logger = get_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create the command line argument parser.

    Returns:
        An argparse.ArgumentParser object.
    """
    parser = argparse.ArgumentParser(
        prog="airbnmail",
        description="Airbnb Mail to AI - Gmail email fetcher for automated@airbnb.com",
    )

    # Global arguments
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)",
    )

    # Subparsers for commands
    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        help="Command to execute",
        required=False,
    )

    # Setup command subparsers
    setup_fetch_parser(subparsers)
    setup_auth_parser(subparsers)
    setup_calendar_parser(subparsers)
    setup_db_parser(subparsers)

    return parser


def main(args: list[str] | None = None) -> int:
    """Main entry point for the CLI.

    Args:
        args: Command line arguments. If None, sys.argv[1:] is used.

    Returns:
        Exit code.
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    # Setup logging
    setup_logger(log_level=parsed_args.log_level)

    # If no command provided, show help
    if not hasattr(parsed_args, "func"):
        parser.print_help()
        list_commands()
        return 0

    # Execute the command
    try:
        parsed_args.func(parsed_args)
        return 0
    except Exception as e:
        logger.exception(f"Error executing command: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
