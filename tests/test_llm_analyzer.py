"""Tests for the LLM analyzer module."""

import os
import unittest
from unittest.mock import patch, MagicMock

from airbnmail_to_ai.parser.llm_analyzer import LLMAnalyzer


class TestLLMAnalyzer(unittest.TestCase):
    """Test the LLM analyzer functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.analyzer = LLMAnalyzer(api_key="test_key")
        self.sample_email = """
        予約確定: Hideaway Chalet for Jun 15–20, 2025

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

    @patch('requests.post')
    def test_analyze_reservation_with_api(self, mock_post):
        """Test analyzing reservation with API call."""
        # Mock the API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [
                {
                    "text": """
                    Based on the email content, I've extracted the following information:

                    Check-in date: 2025-06-15
                    Check-out date: 2025-06-20
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
        self.assertIsNotNone(result['confidence'])
        self.assertIsNotNone(result['analysis'])

    def test_analyze_reservation_no_api_key(self):
        """Test analyzing reservation without API key (mock mode)."""
        analyzer = LLMAnalyzer(api_key=None)
        result = analyzer.analyze_reservation(self.sample_email)

        # In mock mode, we should still get a response but with None dates
        self.assertIsNone(result['check_in_date'])
        self.assertIsNone(result['check_out_date'])
        self.assertEqual(result['confidence'], 'low')
        self.assertIsNotNone(result['analysis'])

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
        ]

        for input_date, expected_output in test_cases:
            result = self.analyzer._normalize_date(input_date)
            self.assertEqual(result, expected_output, f"Failed to normalize {input_date}")

    def test_parse_llm_response(self):
        """Test parsing LLM response text."""
        # Test with clear check-in/check-out indicators
        response1 = "Check-in date: 2025-06-15\nCheck-out date: 2025-06-20"
        result1 = self.analyzer._parse_llm_response(response1)
        self.assertEqual(result1['check_in_date'], '2025-06-15')
        self.assertEqual(result1['check_out_date'], '2025-06-20')
        self.assertEqual(result1['confidence'], 'high')

        # Test with only YYYY-MM-DD dates, no clear indicators
        response2 = "I found dates in the email: 2025-06-15 to 2025-06-20"
        result2 = self.analyzer._parse_llm_response(response2)
        self.assertIsNotNone(result2['check_in_date'])
        self.assertIsNotNone(result2['check_out_date'])

        # Test with no dates
        response3 = "I couldn't find any specific dates in the email."
        result3 = self.analyzer._parse_llm_response(response3)
        self.assertIsNone(result3['check_in_date'])
        self.assertIsNone(result3['check_out_date'])
        self.assertEqual(result3['confidence'], 'low')


if __name__ == '__main__':
    unittest.main()
