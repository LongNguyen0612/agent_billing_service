"""Notification Service Implementations

Provides concrete implementations for sending notifications.
"""

import json
import logging
from typing import Optional
import httpx
from src.app.services.notification_service import NotificationService
from src.domain.usage_anomaly import UsageAnomaly

logger = logging.getLogger(__name__)


class LoggingNotificationService(NotificationService):
    """
    Notification service that logs alerts

    Useful for development and testing, or as a fallback.
    """

    async def send_anomaly_alert(self, anomaly: UsageAnomaly) -> bool:
        """
        Log anomaly alert

        Args:
            anomaly: UsageAnomaly to alert about

        Returns:
            Always True (logging never fails)
        """
        logger.warning(
            f"[ANOMALY ALERT] Tenant: {anomaly.tenant_id}, "
            f"Type: {anomaly.anomaly_type.value}, "
            f"Actual: {anomaly.actual_value}, "
            f"Threshold: {anomaly.threshold_value}, "
            f"Period: {anomaly.period_start.isoformat()} - {anomaly.period_end.isoformat()}"
        )
        return True


class WebhookNotificationService(NotificationService):
    """
    Notification service that sends alerts via HTTP webhook

    Sends JSON payload to configured webhook URL.
    """

    def __init__(self, webhook_url: str, timeout: float = 10.0):
        """
        Initialize webhook notification service

        Args:
            webhook_url: URL to POST alerts to
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def send_anomaly_alert(self, anomaly: UsageAnomaly) -> bool:
        """
        Send anomaly alert via webhook

        Args:
            anomaly: UsageAnomaly to alert about

        Returns:
            True if webhook call succeeded, False otherwise
        """
        payload = {
            "type": "anomaly_alert",
            "anomaly_id": anomaly.id,
            "tenant_id": anomaly.tenant_id,
            "anomaly_type": anomaly.anomaly_type.value,
            "status": anomaly.status.value,
            "threshold_value": str(anomaly.threshold_value),
            "actual_value": str(anomaly.actual_value),
            "period_start": anomaly.period_start.isoformat(),
            "period_end": anomaly.period_end.isoformat(),
            "description": anomaly.description,
            "detected_at": anomaly.detected_at.isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                logger.info(
                    f"Webhook notification sent for anomaly {anomaly.id} to {self.webhook_url}"
                )
                return True
        except httpx.HTTPError as e:
            logger.error(
                f"Failed to send webhook notification for anomaly {anomaly.id}: {e}"
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error sending webhook notification for anomaly {anomaly.id}: {e}"
            )
            return False


class CompositeNotificationService(NotificationService):
    """
    Notification service that delegates to multiple services

    Useful for sending to multiple channels (e.g., log + webhook).
    """

    def __init__(self, services: list[NotificationService]):
        """
        Initialize composite notification service

        Args:
            services: List of notification services to delegate to
        """
        self.services = services

    async def send_anomaly_alert(self, anomaly: UsageAnomaly) -> bool:
        """
        Send anomaly alert to all configured services

        Args:
            anomaly: UsageAnomaly to alert about

        Returns:
            True if at least one service succeeded, False otherwise
        """
        success = False
        for service in self.services:
            try:
                if await service.send_anomaly_alert(anomaly):
                    success = True
            except Exception as e:
                logger.error(f"Notification service {type(service).__name__} failed: {e}")
        return success


def create_notification_service(webhook_url: Optional[str] = None) -> NotificationService:
    """
    Factory function to create appropriate notification service

    Args:
        webhook_url: Optional webhook URL. If provided, creates composite
                     service with logging + webhook. Otherwise, just logging.

    Returns:
        Configured NotificationService
    """
    services: list[NotificationService] = [LoggingNotificationService()]

    if webhook_url:
        services.append(WebhookNotificationService(webhook_url))

    if len(services) == 1:
        return services[0]

    return CompositeNotificationService(services)
