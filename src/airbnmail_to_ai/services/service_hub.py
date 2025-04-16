"""Service hub for dispatching notifications to external services."""

import importlib
from typing import Any, Callable, Dict, List, Optional

from loguru import logger

from airbnmail_to_ai.models.notification import AirbnbNotification
from airbnmail_to_ai.services import webhook_service


# Registry for service handlers
SERVICE_REGISTRY: Dict[str, Callable] = {
    "webhook": webhook_service.send_webhook,
    # Add more service handlers here as they are implemented
    # "slack": slack_service.send_to_slack,
    # "discord": discord_service.send_to_discord,
    # "sms": sms_service.send_sms,
}


def register_service(name: str, handler: Callable) -> None:
    """Register a new service handler.

    Args:
        name: The name of the service.
        handler: The function to handle sending to this service.
    """
    SERVICE_REGISTRY[name] = handler
    logger.info(f"Registered service handler: {name}")


def dispatch_to_services(
    notification: AirbnbNotification, service_config: Dict[str, Any]
) -> Dict[str, bool]:
    """Dispatch a notification to all configured services.

    Args:
        notification: The notification to dispatch.
        service_config: Configuration for services.

    Returns:
        Dictionary with service names as keys and success status as values.
    """
    results = {}

    if not service_config:
        logger.warning("No services configured. Notification not forwarded.")
        return results

    # Convert notification to dictionary for services
    notification_dict = notification.to_dict()

    # Get relevant service configurations based on notification type
    type_specific_configs = service_config.get(notification.notification_type.value, {})
    
    # Get global service configurations that apply to all notification types
    global_configs = service_config.get("all", {})
    
    # Combine configurations, with type-specific taking precedence
    combined_configs = {**global_configs, **type_specific_configs}

    if not combined_configs:
        logger.info(
            f"No services configured for notification type: {notification.notification_type.value}"
        )
        return results

    # Dispatch to each configured service
    for service_name, config in combined_configs.items():
        if not config.get("enabled", True):
            logger.debug(f"Service {service_name} is disabled. Skipping.")
            continue

        success = _send_to_service(service_name, notification, config)
        results[service_name] = success

    return results


def _send_to_service(
    service_name: str, notification: AirbnbNotification, config: Dict[str, Any]
) -> bool:
    """Send a notification to a specific service.

    Args:
        service_name: The name of the service.
        notification: The notification to send.
        config: Service-specific configuration.

    Returns:
        True if successful, False otherwise.
    """
    try:
        if service_name in SERVICE_REGISTRY:
            # Use registered service handler
            handler = SERVICE_REGISTRY[service_name]
            return handler(notification, config)
        else:
            # Try to dynamically load the service
            try:
                module_name = f"airbnmail_to_ai.services.{service_name}_service"
                module = importlib.import_module(module_name)
                
                if hasattr(module, f"send_to_{service_name}"):
                    handler = getattr(module, f"send_to_{service_name}")
                    # Register for future use
                    register_service(service_name, handler)
                    return handler(notification, config)
                else:
                    logger.error(f"Service module {module_name} exists but has no send function")
                    return False
            
            except ImportError:
                logger.error(f"Unknown service: {service_name}. No handler found.")
                return False

    except Exception as e:
        logger.exception(f"Error sending to {service_name}: {e}")
        return False
