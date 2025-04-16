"""Simple CLI demo showing command structure without actual Gmail API calls."""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add project directory to path
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

# Sample email data to demonstrate output formatting
SAMPLE_EMAILS = [
    {
        "id": "1234567890",
        "subject": "予約リクエストを受け取りました - John Smith さんから",
        "from": "automated@airbnb.com",
        "date": "Wed, 15 Apr 2025 12:00:00 +0000",
        "body_text": "John Smith さんから予約リクエストが届きました。チェックイン: 2025年5月10日...",
    },
    {
        "id": "0987654321",
        "subject": "予約が確定しました - Jane Doe さんの予約",
        "from": "automated@airbnb.com",
        "date": "Mon, 13 Apr 2025 09:30:00 +0000",
        "body_text": "Jane Doe さんの予約が確定しました。チェックイン: 2025年6月5日...",
    },
]

# Sample parsed data
SAMPLE_PARSED = {
    "notification_type": "booking_request",
    "guest_name": "John Smith",
    "check_in": "2025-05-10",
    "check_out": "2025-05-15",
    "num_guests": 2,
    "message": "初めまして、5月に東京旅行を計画しています。",
}


def display_emails(
    emails: list[dict], output_format: str = "text", parse: bool = False
) -> str:
    """Format and display emails according to output format.

    Args:
        emails: List of email data dictionaries
        output_format: Output format (text, json, yaml)
        parse: Whether to include parsed data

    Returns:
        Formatted output string
    """
    # Add parsed data if requested
    if parse:
        for email in emails:
            if "sample parsed" not in email:
                email["parsed_data"] = SAMPLE_PARSED

    # Format according to requested output
    if output_format == "json":
        return json.dumps(emails, indent=2, ensure_ascii=False)

    elif output_format == "yaml":
        lines = ["---"]
        for i, email in enumerate(emails):
            lines.append(f"- id: {email['id']}")
            lines.append(f"  subject: '{email['subject']}'")
            lines.append(f"  from: {email['from']}")
            lines.append(f"  date: {email['date']}")
            if not parse:
                lines.append(f"  body_text: '{email['body_text']}'")
            else:
                lines.append("  parsed_data:")
                for key, value in email["parsed_data"].items():
                    lines.append(f"    {key}: {value}")

        return "\n".join(lines)

    else:  # Text format
        lines = []
        for i, email in enumerate(emails, 1):
            lines.append(f"Email {i}:")
            lines.append(f"  ID: {email['id']}")
            lines.append(f"  Subject: {email['subject']}")
            lines.append(f"  Date: {email['date']}")
            lines.append(f"  From: {email['from']}")

            if not parse:
                lines.append(f"  Preview: {email['body_text']}")
            else:
                lines.append("  Parsed Data: Successfully parsed")
                for key, value in email["parsed_data"].items():
                    lines.append(f"    {key}: {value}")
            lines.append("")

        return "\n".join(lines)


def demo_fetch(args: list[str] | None = None) -> None:
    """Demonstrate the fetch command functionality."""
    parser = argparse.ArgumentParser(description="Fetch emails demo")
    parser.add_argument(
        "--query",
        default="from:automated@airbnb.com is:unread",
        help="Gmail search query",
    )
    parser.add_argument(
        "--limit", type=int, default=10, help="Maximum number of emails to fetch"
    )
    parser.add_argument(
        "--mark-read", action="store_true", help="Mark fetched emails as read"
    )
    parser.add_argument(
        "--output",
        choices=["json", "yaml", "text"],
        default="text",
        help="Output format",
    )
    parser.add_argument("--save", type=str, help="Save output to specified file path")
    parser.add_argument(
        "--parse",
        action="store_true",
        help="Parse email content for Airbnb notification data",
    )

    args = parser.parse_args(args)

    print(f"Fetching emails with query: {args.query} (limit: {args.limit})")
    print(f"Output format: {args.output}")

    # In a real implementation, this would call the GmailService
    # For demo purposes, we'll use our sample data
    emails = SAMPLE_EMAILS[: args.limit]

    # Format the output
    output = display_emails(emails, args.output, args.parse)

    # Save or print output
    if args.save:
        print(f"Saving output to {args.save}")
        # In a real implementation, this would save to a file
        print(f"[File contents would be saved to {args.save}]")
    else:
        print("\nOutput:")
        print(output)

    if args.mark_read:
        print(f"\nMarked {len(emails)} emails as read.")


def demo_auth(args: list[str] | None = None) -> None:
    """Demonstrate the auth command functionality."""
    parser = argparse.ArgumentParser(description="Auth demo")
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to Gmail API credentials file",
    )
    parser.add_argument(
        "--token", default="token.json", help="Path to Gmail API token file"
    )

    args = parser.parse_args(args)

    print("Initiating Gmail API authentication...")
    print(f"Using credentials file: {args.credentials}")
    print(f"Token will be saved to: {args.token}")

    # In a real implementation, this would perform OAuth authentication
    print("\nAuthentication successful!")
    print("Successfully authenticated as: demo@example.com")
    print(f"Token saved to {args.token}")


def main() -> None:
    """Run the CLI demo."""
    print("=== Airbnb Mail to AI CLI Demo ===")
    print(
        "This is a demonstration of the CLI interface without actual Gmail API calls."
    )
    print("In a real environment, you would need valid Google API credentials.\n")

    while True:
        print("\nAvailable commands:")
        print("  1. fetch  - Demonstrate the fetch emails command")
        print("  2. auth   - Demonstrate the authentication command")
        print("  3. exit   - Exit the demo")

        choice = input("\nEnter command number: ")

        if choice == "1":
            print("\n=== FETCH COMMAND DEMO ===")
            demo_fetch(
                ["--query", "from:automated@airbnb.com is:unread", "--limit", "2"]
            )

            print("\n=== With JSON output ===")
            demo_fetch(["--output", "json", "--limit", "1"])

            print("\n=== With parsing ===")
            demo_fetch(["--parse", "--limit", "1"])

        elif choice == "2":
            print("\n=== AUTH COMMAND DEMO ===")
            demo_auth()

        elif choice == "3":
            break

        else:
            print("Invalid choice. Please try again.")

    print("\nDemo completed. In a real environment, you would use:")
    print("  poetry run airbnmail auth    - To authenticate with Gmail")
    print("  poetry run airbnmail fetch   - To fetch emails from automated@airbnb.com")
    print("See README.md for more details and options.")


if __name__ == "__main__":
    main()
