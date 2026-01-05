"""Usage Anomaly Repository Interface

Defines the contract for usage anomaly persistence operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from src.domain.usage_anomaly import UsageAnomaly, AnomalyStatus


class UsageAnomalyRepository(ABC):
    """
    Repository interface for UsageAnomaly persistence

    Used for storing and retrieving detected usage anomalies.
    """

    @abstractmethod
    async def create(self, anomaly: UsageAnomaly) -> UsageAnomaly:
        """
        Create a new usage anomaly record

        Args:
            anomaly: UsageAnomaly entity to persist

        Returns:
            Created UsageAnomaly with generated ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, anomaly_id: int) -> Optional[UsageAnomaly]:
        """
        Retrieve anomaly by ID

        Args:
            anomaly_id: Anomaly ID

        Returns:
            UsageAnomaly if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_tenant_id(
        self, tenant_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[UsageAnomaly], int]:
        """
        Retrieve anomalies for a tenant with pagination

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of anomalies to return
            offset: Number of anomalies to skip

        Returns:
            Tuple of (list of UsageAnomaly, total count)
        """
        pass

    @abstractmethod
    async def get_by_status(
        self, status: AnomalyStatus, limit: int = 100
    ) -> list[UsageAnomaly]:
        """
        Retrieve anomalies by status

        Args:
            status: Anomaly status to filter by
            limit: Maximum number of anomalies to return

        Returns:
            List of UsageAnomaly matching status
        """
        pass

    @abstractmethod
    async def update_status(
        self,
        anomaly_id: int,
        status: AnomalyStatus,
        resolved_by: Optional[str] = None
    ) -> Optional[UsageAnomaly]:
        """
        Update anomaly status

        Args:
            anomaly_id: Anomaly ID
            status: New status
            resolved_by: User who resolved (for RESOLVED status)

        Returns:
            Updated UsageAnomaly if found, None otherwise
        """
        pass

    @abstractmethod
    async def mark_notified(self, anomaly_id: int) -> Optional[UsageAnomaly]:
        """
        Mark anomaly as notified

        Args:
            anomaly_id: Anomaly ID

        Returns:
            Updated UsageAnomaly if found, None otherwise
        """
        pass

    @abstractmethod
    async def exists_for_tenant_period(
        self,
        tenant_id: str,
        period_start: datetime,
        period_end: datetime
    ) -> bool:
        """
        Check if an anomaly already exists for tenant in given period

        Used to prevent duplicate anomaly creation for same detection window.

        Args:
            tenant_id: Tenant identifier
            period_start: Period start time
            period_end: Period end time

        Returns:
            True if anomaly exists, False otherwise
        """
        pass
