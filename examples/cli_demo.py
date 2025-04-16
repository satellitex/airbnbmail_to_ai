"""CLI demo script with mock data."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import airbnmail_to_ai.gmail.gmail_service
from airbnmail_to_ai.cli.cli import main

# Add parent directory to path so we can import local modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Sample mock email data
MOCK_EMAILS = [
    {
        "id": "1234567890",
        "thread_id": "abcdef123456",
        "subject": "予約リクエストを受け取りました - John Smith さんから",
        "from": "automated@airbnb.com",
        "to": "host@example.com",
        "date": "Wed, 15 Apr 2025 12:00:00 +0000",
        "body_text": """
Airbnbからのお知らせ

John Smith さんから予約リクエストが届きました。
チェックイン: 2025年5月10日
チェックアウト: 2025年5月15日
ゲスト数: 2名
金額: ¥50,000
メッセージ: 初めまして、5月に東京旅行を計画しています。お部屋を予約させていただきたいです。
        """,
        "body_html": "<html><body>予約リクエストが届きました...</body></html>",
        "labels": ["INBOX", "UNREAD"],
    },
    {
        "id": "0987654321",
        "thread_id": "fedcba654321",
        "subject": "予約が確定しました - Jane Doe さんの予約",
        "from": "automated@airbnb.com",
        "to": "host@example.com",
        "date": "Mon, 13 Apr 2025 09:30:00 +0000",
        "body_text": """
Airbnbからのお知らせ

Jane Doe さんの予約が確定しました。
チェックイン: 2025年6月5日
チェックアウト: 2025年6月10日
ゲスト数: 3名
金額: ¥75,000
予約番号: HMABCXYZ
        """,
        "body_html": "<html><body>予約が確定しました...</body></html>",
        "labels": ["INBOX", "UNREAD"],
    },
]


def run_demo():
    """Run the CLI demo with mocked Gmail service."""
    # Patch the GmailService.__init__ to avoid looking for credentials.json
    with patch(
        "airbnmail_to_ai.gmail.gmail_service.GmailService.__init__", return_value=None
    ) as mock_init:
        # Patch get_messages to return our mock emails
        with patch(
            "airbnmail_to_ai.gmail.gmail_service.GmailService.get_messages",
            return_value=MOCK_EMAILS,
        ):
            # Patch mark_as_read
            with patch(
                "airbnmail_to_ai.gmail.gmail_service.GmailService.mark_as_read",
                return_value=True,
            ):
                # Create a mock service attribute for the gmail service
                with patch.object(
                    airbnmail_to_ai.gmail.gmail_service.GmailService,
                    "service",
                    create=True,
                ) as mock_service:
                    # Mock users method chain for auth
                    mock_users = MagicMock()
                    mock_service.users.return_value = mock_users

                    mock_profile = MagicMock()
                    mock_users.getProfile.return_value = mock_profile

                    mock_profile.execute.return_value = {
                        "emailAddress": "demo@example.com"
                    }

        print("===== DEMO: Fetch emails with default settings =====")
        main(["fetch"])

        print("\n\n===== DEMO: Fetch emails with JSON output =====")
        main(["fetch", "--output", "json"])

        print("\n\n===== DEMO: Fetch emails with parsing =====")
        # For the parse demo, we need to mock the parse_email function
        with patch("airbnmail_to_ai.parser.email_parser.parse_email") as mock_parse:
            # Create mock parsed data
            class MockParsedData:
                def dict(self):
                    return {
                        "notification_type": "booking_request",
                        "guest_name": "John Smith",
                        "check_in": "2025-05-10",
                        "check_out": "2025-05-15",
                        "num_guests": 2,
                        "message": "初めまして、5月に東京旅行を計画しています。お部屋を予約させていただきたいです。",
                    }

            mock_parse.return_value = MockParsedData()
            main(["fetch", "--parse"])

        print("\n\n===== DEMO: Auth command =====")
        main(["auth"])


if __name__ == "__main__":
    print("=== Airbnb Mail to AI CLI Demo ===")
    print("This is a demo with mock data, no actual Gmail API calls are made.")
    print("In a real environment, you would need valid Google API credentials.")
    print("\nRunning demo with sample Airbnb emails...\n")
    run_demo()
    print("\nDemo completed. In a real environment, you would use:")
    print("  poetry run airbnmail auth    - To authenticate with Gmail")
    print("  poetry run airbnmail fetch   - To fetch emails from automated@airbnb.com")
    print("See README.md for more details and options.")
