"""Notification Service Interface

Defines the contract for sending notifications about anomalies.
"""

from abc import ABC, abstractmethod
from src.domain.usage_anomaly import UsageAnomaly


class NotificationService(ABC):
    """
    Abstract notification service for sending alerts

    Implementations can send notifications via:
    - Webhook (HTTP POST)
    - Email
    - Slack
    - PagerDuty
    - etc.
    """

    @abstractmethod
    async def send_anomaly_alert(self, anomaly: UsageAnomaly) -> bool:
        """
        Send alert for detected anomaly

        Args:
            anomaly: UsageAnomaly to alert about

        Returns:
            True if notification sent successfully, False otherwise
        """
        pass
