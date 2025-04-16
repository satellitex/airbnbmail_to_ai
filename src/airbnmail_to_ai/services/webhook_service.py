"""Webhook service for sending notifications to HTTP endpoints."""

import json
from typing import Any, Dict

import requests
from loguru import logger

from airbnmail_to_ai.models.notification import AirbnbNotification


def send_webhook(notification: AirbnbNotification, config: Dict[str, Any]) -> bool:
    """Send a notification to a webhook endpoint.

    Args:
        notification: The notification to send.
        config: Webhook configuration including url, headers, etc.

    Returns:
        True if successful, False otherwise.
    """
    try:
        url = config.get("url")
        if not url:
            logger.error("Webhook URL not provided in configuration")
            return False

        # Get additional configuration
        headers = config.get("headers", {"Content-Type": "application/json"})
        method = config.get("method", "POST").upper()
        timeout = config.get("timeout", 10)
        include_raw = config.get("include_raw", False)
        template = config.get("template")

        # Prepare the payload
        payload = notification.to_dict()
        
        # Remove raw content if not needed to reduce payload size
        if not include_raw:
            payload.pop("raw_text", None)
            payload.pop("raw_html", None)
        
        # Apply template if provided
        if template:
            try:
                # Template is expected to be a dictionary mapping with keys to include
                filtered_payload = {}
                for dest_key, source_path in template.items():
                    value = _get_nested_value(payload, source_path)
                    if value is not None:
                        filtered_payload[dest_key] = value
                payload = filtered_payload
            except Exception as e:
                logger.warning(f"Error applying webhook template: {e}")
                # Continue with the original payload
        
        # Make the request
        logger.info(f"Sending webhook to {url}")
        logger.debug(f"Webhook payload: {json.dumps(payload, default=str)}")
        
        response = requests.request(
            method,
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        
        # Check if the request was successful
        response.raise_for_status()
        
        logger.info(f"Webhook sent successfully: {response.status_code}")
        return True
    
    except requests.RequestException as e:
        logger.error(f"Webhook request failed: {e}")
        return False
    
    except Exception as e:
        logger.exception(f"Error sending webhook: {e}")
        return False


def _get_nested_value(data: Dict[str, Any], path: str) -> Any:
    """Get a value from a nested dictionary using a dot-separated path.

    Args:
        data: The dictionary to extract from.
        path: Dot-separated path to the value.

    Returns:
        The value at the specified path or None if not found.
    """
    keys = path.split(".")
    value = data
    
    for key in keys:
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return None
    
    return value
