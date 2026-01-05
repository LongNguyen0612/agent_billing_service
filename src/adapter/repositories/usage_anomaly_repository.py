"""SQLAlchemy implementation of UsageAnomalyRepository

Provides persistence for UsageAnomaly entities.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession
from src.app.repositories.usage_anomaly_repository import UsageAnomalyRepository
from src.domain.usage_anomaly import UsageAnomaly, AnomalyStatus


class SqlAlchemyUsageAnomalyRepository(UsageAnomalyRepository):
    """
    SQLAlchemy implementation of UsageAnomalyRepository

    Features:
    - CRUD operations for usage anomalies
    - Status management with timestamp tracking
    - Duplicate detection for same tenant/period
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, anomaly: UsageAnomaly) -> UsageAnomaly:
        """
        Create a new usage anomaly record

        Args:
            anomaly: UsageAnomaly entity to persist

        Returns:
            Created UsageAnomaly with generated ID
        """
        self.session.add(anomaly)
        await self.session.flush()
        await self.session.refresh(anomaly)
        return anomaly

    async def get_by_id(self, anomaly_id: int) -> Optional[UsageAnomaly]:
        """
        Retrieve anomaly by ID

        Args:
            anomaly_id: Anomaly ID

        Returns:
            UsageAnomaly if found, None otherwise
        """
        stmt = select(UsageAnomaly).where(UsageAnomaly.id == anomaly_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

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
        # Get total count
        count_stmt = select(func.count()).select_from(UsageAnomaly).where(
            UsageAnomaly.tenant_id == tenant_id
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar()

        # Get paginated anomalies ordered by detected_at DESC
        stmt = (
            select(UsageAnomaly)
            .where(UsageAnomaly.tenant_id == tenant_id)
            .order_by(UsageAnomaly.detected_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        anomalies = list(result.scalars().all())

        return anomalies, total

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
        stmt = (
            select(UsageAnomaly)
            .where(UsageAnomaly.status == status)
            .order_by(UsageAnomaly.detected_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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
        anomaly = await self.get_by_id(anomaly_id)
        if not anomaly:
            return None

        anomaly.status = status

        if status in (AnomalyStatus.RESOLVED, AnomalyStatus.FALSE_POSITIVE):
            anomaly.resolved_at = datetime.utcnow()
            anomaly.resolved_by = resolved_by

        await self.session.flush()
        await self.session.refresh(anomaly)
        return anomaly

    async def mark_notified(self, anomaly_id: int) -> Optional[UsageAnomaly]:
        """
        Mark anomaly as notified

        Args:
            anomaly_id: Anomaly ID

        Returns:
            Updated UsageAnomaly if found, None otherwise
        """
        anomaly = await self.get_by_id(anomaly_id)
        if not anomaly:
            return None

        anomaly.notified_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(anomaly)
        return anomaly

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
        stmt = select(func.count()).select_from(UsageAnomaly).where(
            and_(
                UsageAnomaly.tenant_id == tenant_id,
                UsageAnomaly.period_start == period_start,
                UsageAnomaly.period_end == period_end
            )
        )
        result = await self.session.execute(stmt)
        count = result.scalar()
        return count > 0
