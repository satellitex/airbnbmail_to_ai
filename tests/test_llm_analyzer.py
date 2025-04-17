"""Tests for the LLM analyzer module."""

import unittest
from unittest.mock import patch, MagicMock

from airbnmail_to_ai.parser.llm import LLMAnalyzer
from airbnmail_to_ai.parser.llm.date_utils import normalize_date
from airbnmail_to_ai.parser.llm.response_parser import parse_llm_response


class TestLLMAnalyzer(unittest.TestCase):
    """Test the LLM analyzer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = LLMAnalyzer(api_key="test_key")
        self.sample_email = {
            "subject": "予約確定: Hideaway Chalet for Jun 15–20, 2025",
            "date": "2025-04-15",
            "from": "Airbnb <automated@airbnb.com>",
            "to": "guest@example.com",
            "body_text": """
            Hideaway Chalet
            東京都新宿区

            チェックイン: 2025年6月15日（日）
            チェックアウト: 2025年6月20日（金）
            ゲスト: 2名

            予約コード: ABCDEF123

            合計金額: ¥65,000

            ホストからのメッセージ:
            ご予約ありがとうございます。心からお待ちしております。
            """
        }

    @patch('requests.post')
    def test_analyze_reservation_with_api(self, mock_post):
        """Test analyzing reservation with API call."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {
                    "text": """
                    ```json
                    {
                      "notification_type": "booking_confirmation",
                      "check_in_date": "2025-06-15",
                      "check_out_date": "2025-06-20",
                      "received_date": "2025-04-15",
                      "guest_name": null,
                      "num_guests": 2,
                      "property_name": "Hideaway Chalet",
                      "confidence": "high"
                    }
                    ```
                    """
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Call the analyze_reservation method
        result = self.analyzer.analyze_reservation(self.sample_email)

        # Check that the API was called with correct parameters
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs['headers']['x-api-key'], 'test_key')
        self.assertEqual(kwargs['headers']['anthropic-version'], '2023-06-01')
        self.assertIn('messages', kwargs['json'])

        # Verify the results
        self.assertEqual(result['check_in_date'], '2025-06-15')
        self.assertEqual(result['check_out_date'], '2025-06-20')
        self.assertEqual(result['notification_type'], 'booking_confirmation')
        self.assertEqual(result['num_guests'], 2)
        self.assertEqual(result['property_name'], 'Hideaway Chalet')
        self.assertEqual(result['confidence'], 'high')
        self.assertIsNotNone(result['analysis'])

    @patch('requests.post')
    @patch('os.environ.get')
    def test_analyze_reservation_no_api_key(self, mock_env_get, mock_post):
        """Test analyzing reservation without API key (mock mode)."""
        # Ensure environment variable also returns None
        mock_env_get.return_value = None

        # Create analyzer with no API key
        analyzer = LLMAnalyzer(api_key=None)

        # Call the method - should use the mock response path
        result = analyzer.analyze_reservation(self.sample_email)

        # Verify mock_post was not called (no API call should be made)
        mock_post.assert_not_called()

        # In mock mode, we should get the placeholder response
        self.assertIsNone(result.get('check_in_date'))
        self.assertIsNone(result.get('check_out_date'))
        self.assertEqual(result.get('confidence', ''), 'low')
        self.assertEqual(result.get('notification_type', ''), 'unknown')
        self.assertIsNotNone(result.get('analysis'))

    def test_normalize_date(self):
        """Test date normalization function."""
        test_cases = [
            ("2025-06-15", "2025-06-15"),  # Already in correct format
            ("15/06/2025", "2025-06-15"),  # DD/MM/YYYY
            ("06/15/2025", "2025-06-15"),  # MM/DD/YYYY
            ("15 June 2025", "2025-06-15"),  # DD Month YYYY
            ("June 15, 2025", "2025-06-15"),  # Month DD, YYYY
            ("15 Jun 2025", "2025-06-15"),  # DD MMM YYYY
            ("Jun 15, 2025", "2025-06-15"),  # MMM DD, YYYY
            ("2025年6月15日", "2025-06-15"),  # Japanese format
        ]

        for input_date, expected_output in test_cases:
            result = normalize_date(input_date)
            self.assertEqual(result, expected_output, f"Failed to normalize {input_date}")

    def test_parse_llm_response(self):
        """Test parsing LLM response text."""
        # Test with JSON format
        response1 = """
        ```json
        {
          "notification_type": "booking_confirmation",
          "check_in_date": "2025-06-15",
          "check_out_date": "2025-06-20",
          "received_date": "2025-04-15",
          "guest_name": null,
          "num_guests": 2,
          "property_name": "Hideaway Chalet",
          "confidence": "high"
        }
        ```
        """
        result1 = parse_llm_response(response1)
        self.assertEqual(result1['check_in_date'], '2025-06-15')
        self.assertEqual(result1['check_out_date'], '2025-06-20')
        self.assertEqual(result1['notification_type'], 'booking_confirmation')
        self.assertEqual(result1['confidence'], 'high')

        # Test with clear check-in/check-out indicators but no JSON
        response2 = "Check-in date: 2025-06-15\nCheck-out date: 2025-06-20"
        result2 = parse_llm_response(response2)
        self.assertEqual(result2['check_in_date'], '2025-06-15')
        self.assertEqual(result2['check_out_date'], '2025-06-20')
        self.assertEqual(result2['confidence'], 'high')

        # Test with only YYYY-MM-DD dates, no clear indicators
        response3 = "I found dates in the email: 2025-06-15 to 2025-06-20"
        result3 = parse_llm_response(response3)
        self.assertIsNotNone(result3['check_in_date'])
        self.assertIsNotNone(result3['check_out_date'])
        self.assertIn(result3['confidence'], ['medium', 'low'])

        # Test with no dates
        response4 = "I couldn't find any specific dates in the email."
        result4 = parse_llm_response(response4)
        self.assertIsNone(result4['check_in_date'])
        self.assertIsNone(result4['check_out_date'])
        self.assertEqual(result4['confidence'], 'low')


if __name__ == '__main__':
    unittest.main()
