"""Email fetch commands for Airbnb Mail to AI."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

from airbnmail_to_ai.gmail.gmail_service import GmailService
from airbnmail_to_ai.parser import email_parser
from airbnmail_to_ai.utils.logging import get_logger

# Initialize logger
logger = get_logger(__name__)


def setup_fetch_parser(subparsers: Any) -> None:
    """Set up the parser for the fetch command.

    Args:
        subparsers: Subparser object to add the fetch command to.
    """
    fetch_parser = subparsers.add_parser(
        "fetch", help="Fetch emails from automated@airbnb.com"
    )

    # Add arguments specific to fetch command
    fetch_parser.add_argument(
        "--query",
        default="from:automated@airbnb.com is:unread",
        help="Gmail search query (default: 'from:automated@airbnb.com is:unread')",
    )
    fetch_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of emails to fetch (default: 10)",
    )
    fetch_parser.add_argument(
        "--mark-read",
        action="store_true",
        help="Mark fetched emails as read",
    )
    fetch_parser.add_argument(
        "--output",
        choices=["json", "yaml", "text"],
        default="text",
        help="Output format (default: text)",
    )
    fetch_parser.add_argument(
        "--save",
        type=str,
        help="Save output to specified file path",
    )
    fetch_parser.add_argument(
        "--parse",
        action="store_true",
        help="Parse email content for Airbnb notification data",
    )
    fetch_parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to Gmail API credentials file (default: credentials.json)",
    )
    fetch_parser.add_argument(
        "--token",
        default="token.json",
        help="Path to Gmail API token file (default: token.json)",
    )
    fetch_parser.set_defaults(func=fetch_command)


def fetch_command(args: argparse.Namespace) -> None:
    """Execute the fetch command.

    Args:
        args: Command line arguments.
    """
    try:
        logger.info("Fetching emails with query: {}", args.query)
        logger.info("Max results: {}", args.limit)

        # Initialize Gmail service
        gmail = GmailService(
            credentials_path=args.credentials,
            token_path=args.token,
        )

        # Fetch messages
        messages = gmail.get_messages(query=args.query, max_results=args.limit)

        if not messages:
            logger.info("No emails found matching the query")
            print("No emails found matching the query.")
            return

        logger.info("Found {} emails matching the query", len(messages))

        # Process messages
        results = process_messages(messages, args, gmail)

        # Format the output according to requested format
        output = format_output(results, args)

        # Save or print output
        if args.save:
            save_path = Path(args.save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(output)
            logger.info("Saved output to {}", args.save)
            print(f"Saved output to {args.save}")
        else:
            print(output)

        if args.mark_read:
            print(f"Marked {len(messages)} emails as read.")

    except Exception as e:
        logger.exception("Error fetching emails: {}", e)
        print(f"Error: {e}")
        sys.exit(1)


def process_messages(
    messages: List[Dict[str, Any]], args: argparse.Namespace, gmail: GmailService
) -> List[Dict[str, Any]]:
    """Process fetched email messages.

    Args:
        messages: List of email message dictionaries
        args: Command line arguments
        gmail: GmailService instance

    Returns:
        List of processed message dictionaries
    """
    results = []
    for msg in messages:
        if args.parse:
            # Parse email with LLM analysis
            parsed_data = email_parser.parse_email(msg)
            if parsed_data:
                results.append(
                    {
                        "id": msg["id"],
                        "subject": msg["subject"],
                        "date": msg["date"],
                        "from": msg["from"],
                        "parsed_data": parsed_data.dict(),
                    }
                )
            else:
                results.append(
                    {
                        "id": msg["id"],
                        "subject": msg["subject"],
                        "date": msg["date"],
                        "from": msg["from"],
                        "parsed_data": None,
                    }
                )
        else:
            results.append(
                {
                    "id": msg["id"],
                    "subject": msg["subject"],
                    "date": msg["date"],
                    "from": msg["from"],
                    "body_text": msg["body_text"][:200] + "..."
                    if len(msg["body_text"]) > 200
                    else msg["body_text"],
                }
            )

        # Mark as read if requested
        if args.mark_read:
            gmail.mark_as_read(msg["id"])
            logger.debug("Marked email {} as read", msg["id"])

    return results


def format_output(results: List[Dict[str, Any]], args: argparse.Namespace) -> str:
    """Format the output according to the specified format.

    Args:
        results: List of processed message dictionaries
        args: Command line arguments

    Returns:
        Formatted output string
    """
    if args.output == "json":
        return json.dumps(results, indent=2)
    elif args.output == "yaml":
        return yaml.dump(results, default_flow_style=False)
    else:  # text
        output = ""
        for i, msg in enumerate(results, 1):
            output += f"Email {i}:\n"
            output += f"  ID: {msg['id']}\n"
            output += f"  Subject: {msg['subject']}\n"
            output += f"  Date: {msg['date']}\n"
            output += f"  From: {msg['from']}\n"
            if not args.parse:
                output += f"  Preview: {msg['body_text']}\n"
            else:
                output += f"  Parsed Data: {'Successfully parsed' if msg['parsed_data'] else 'Failed to parse'}\n"
                if msg["parsed_data"]:
                    # Add general parsed data
                    for key, value in msg["parsed_data"].items():
                        if key not in ['llm_analysis'] and value is not None:  # Skip the raw analysis text
                            output += f"    {key}: {value}\n"

                    # Add reservation analysis section
                    if 'llm_analysis' in msg['parsed_data'] and msg['parsed_data']['llm_analysis']:
                        llm_analysis = msg['parsed_data']['llm_analysis']
                        check_in_date = llm_analysis.get('check_in_date')
                        check_out_date = llm_analysis.get('check_out_date')
                        if check_in_date or check_out_date:
                            output += f"  Reservation Analysis:\n"
                            if check_in_date:
                                output += f"    Check-In Date: {check_in_date}\n"
                            if check_out_date:
                                output += f"    Check-Out Date: {check_out_date}\n"
                            if 'llm_confidence' in msg['parsed_data']:
                                output += f"    Confidence: {msg['parsed_data']['llm_confidence']}\n"
            output += "\n"

        return output
