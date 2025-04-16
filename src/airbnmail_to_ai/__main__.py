"""Main entry point for the Airbnb Mail to AI bot."""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import schedule
import yaml
from loguru import logger

from airbnmail_to_ai.gmail import gmail_service
from airbnmail_to_ai.parser import email_parser
from airbnmail_to_ai.services import service_hub


def setup_logging(log_level: str = "INFO") -> None:
    """Configure application logging.

    Args:
        log_level: The logging level to use. Defaults to "INFO".
    """
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    
    # Add file handler
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logger.add(
        log_dir / "airbnmail_to_ai_{time:YYYY-MM-DD}.log",
        rotation="00:00",  # Create a new file at midnight
        retention="30 days",  # Keep logs for 30 days
        level=log_level,
        compression="zip",
    )


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load the application configuration.

    Args:
        config_path: Path to the configuration file. Defaults to "config.yaml".

    Returns:
        Dict containing configuration values.

    Raises:
        FileNotFoundError: If the configuration file doesn't exist.
    """
    config_file = Path(config_path)
    
    if not config_file.exists():
        example_config = Path("config.example.yaml")
        if example_config.exists():
            logger.warning(
                f"Config file {config_path} not found. Please copy from {example_config} and configure."
            )
        else:
            logger.error(f"Config file {config_path} not found and no example config exists.")
        raise FileNotFoundError(f"Configuration file {config_path} not found")
    
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    return config


def process_emails(config: Dict[str, Any]) -> None:
    """Process emails according to the configuration.

    Args:
        config: Application configuration dictionary.
    """
    try:
        logger.info("Starting email processing")
        
        # Initialize Gmail service
        gmail = gmail_service.GmailService(
            credentials_path=config.get("credentials_path", "credentials.json"),
            token_path=config.get("token_path", "token.json"),
        )
        
        # Get emails matching configured query
        query = config.get("gmail_query", "from:airbnb.com is:unread")
        emails = gmail.get_messages(query=query)
        
        if not emails:
            logger.info("No new Airbnb emails found")
            return
        
        logger.info(f"Found {len(emails)} new Airbnb emails to process")
        
        # Process each email
        for email in emails:
            # Parse the email
            parsed_data = email_parser.parse_email(email)
            
            if not parsed_data:
                logger.warning(f"Failed to parse email with subject: {email.get('subject', 'Unknown')}")
                continue
            
            # Send to configured services
            service_hub.dispatch_to_services(parsed_data, config.get("services", {}))
            
            # Mark as read if configured to do so
            if config.get("mark_as_read", True):
                gmail.mark_as_read(email["id"])
        
        logger.info("Email processing completed")
    
    except Exception as e:
        logger.exception(f"Error processing emails: {e}")


def run_scheduled(config: Dict[str, Any]) -> None:
    """Run the bot on a schedule.

    Args:
        config: Application configuration dictionary.
    """
    schedule_config = config.get("schedule", {})
    schedule_interval = schedule_config.get("interval", "30")
    schedule_unit = schedule_config.get("unit", "minutes")
    
    logger.info(f"Setting up scheduled runs every {schedule_interval} {schedule_unit}")
    
    if schedule_unit == "minutes":
        schedule.every(int(schedule_interval)).minutes.do(process_emails, config=config)
    elif schedule_unit == "hours":
        schedule.every(int(schedule_interval)).hours.do(process_emails, config=config)
    elif schedule_unit == "days":
        schedule.every(int(schedule_interval)).days.do(process_emails, config=config)
    else:
        logger.error(f"Invalid schedule unit: {schedule_unit}. Using default: minutes")
        schedule.every(int(schedule_interval)).minutes.do(process_emails, config=config)
    
    # Run immediately once
    process_emails(config)
    
    logger.info("Scheduled bot is running. Press Ctrl+C to stop.")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Scheduled bot stopped by user")


def main() -> None:
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(description="Airbnb Mail to AI Bot")
    parser.add_argument(
        "--config", 
        default="config.yaml", 
        help="Path to configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--log-level", 
        default="INFO", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set the logging level (default: INFO)"
    )
    parser.add_argument(
        "--schedule", 
        action="store_true", 
        help="Run the bot on a schedule defined in the config"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        if args.schedule:
            run_scheduled(config)
        else:
            # Run once
            process_emails(config)
    
    except Exception as e:
        logger.exception(f"Error in main application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
