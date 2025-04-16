"""Tests for the CLI module."""

import argparse
from unittest.mock import MagicMock, patch

import pytest

from airbnmail_to_ai.cli.cli import create_parser, main
from airbnmail_to_ai.cli.commands import auth_command, fetch_command


@pytest.fixture
def mock_gmail_service():
    """Fixture for mocking GmailService."""
    with patch("airbnmail_to_ai.gmail.gmail_service.GmailService") as mock:
        service_mock = MagicMock()
        mock.return_value = service_mock
        service_mock.get_messages.return_value = []

        # Mock the users method and chain
        users_mock = MagicMock()
        service_mock.service.users.return_value = users_mock

        profile_mock = MagicMock()
        users_mock.getProfile.return_value = profile_mock

        profile_mock.execute.return_value = {"emailAddress": "test@example.com"}

        yield service_mock


def test_create_parser():
    """Test create_parser function."""
    parser = create_parser()
    assert isinstance(parser, argparse.ArgumentParser)

    # Test that fetch and auth commands are registered
    args = parser.parse_args(["fetch", "--query", "test"])
    assert args.command == "fetch"
    assert args.query == "test"

    args = parser.parse_args(["auth"])
    assert args.command == "auth"


def test_main_no_args():
    """Test main function with no args."""
    with (
        patch("airbnmail_to_ai.cli.cli.create_parser") as mock_create_parser,
        patch("airbnmail_to_ai.cli.cli.list_commands") as mock_list_commands,
    ):
        mock_parser = MagicMock()
        mock_create_parser.return_value = mock_parser

        mock_args = MagicMock()
        del mock_args.func  # Remove the func attribute to simulate no command
        mock_parser.parse_args.return_value = mock_args

        result = main([])

        assert result == 0
        mock_parser.print_help.assert_called_once()
        mock_list_commands.assert_called_once()


def test_main_with_command():
    """Test main function with a command."""
    with patch("airbnmail_to_ai.cli.cli.create_parser") as mock_create_parser:
        mock_parser = MagicMock()
        mock_create_parser.return_value = mock_parser

        mock_args = MagicMock()
        mock_func = MagicMock()
        mock_args.func = mock_func
        mock_parser.parse_args.return_value = mock_args

        result = main([])

        assert result == 0
        mock_func.assert_called_once_with(mock_args)


def test_fetch_command_no_emails(mock_gmail_service):
    """Test fetch_command with no emails found."""
    args = MagicMock()
    args.query = "test-query"
    args.limit = 10
    args.mark_read = False
    args.output = "text"
    args.save = None
    args.parse = False
    args.credentials = "creds.json"
    args.token = "token.json"

    with patch("builtins.print") as mock_print:
        fetch_command(args)

        mock_gmail_service.get_messages.assert_called_once_with(
            query="test-query", max_results=10
        )
        mock_print.assert_called_once_with("No emails found matching the query.")


def test_auth_command(mock_gmail_service):
    """Test auth_command."""
    args = MagicMock()
    args.credentials = "creds.json"
    args.token = "token.json"

    with patch("builtins.print") as mock_print:
        auth_command(args)

        assert mock_print.call_count >= 2
        # Check that the success message was printed
        success_call = any(
            call.args[0].startswith("Successfully authenticated as")
            for call in mock_print.call_args_list
        )
        assert success_call
