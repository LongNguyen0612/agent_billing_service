"""DetectAbnormalUsage Use Case (UC-37)

Detects abnormal credit usage patterns and creates anomaly records.
"""

from datetime import datetime, timedelta
from decimal import Decimal
import logging
from libs.result import Result, Return, Error
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories.credit_transaction_repository import CreditTransactionRepository
from src.app.repositories.usage_anomaly_repository import UsageAnomalyRepository
from src.domain.usage_anomaly import UsageAnomaly, AnomalyType, AnomalyStatus
from .dtos import AnomalyDTO, DetectAnomaliesResponseDTO

logger = logging.getLogger(__name__)


class DetectAbnormalUsage:
    """
    Use Case: Detect abnormal credit usage patterns (UC-37)

    Business Rules:
    1. Scans credit transactions within a time window
    2. Groups consumption by tenant
    3. Compares against configured threshold
    4. Creates anomaly records for tenants exceeding threshold
    5. Prevents duplicate anomalies for same tenant/period

    Flow:
    1. Calculate time window (previous hour by default)
    2. Get consumption per tenant for the period
    3. Compare each tenant's usage against threshold
    4. Create anomaly record for exceeding tenants
    5. Return list of detected anomalies
    """

    def __init__(
        self,
        uow: UnitOfWork,
        transaction_repo: CreditTransactionRepository,
        anomaly_repo: UsageAnomalyRepository,
        threshold: Decimal,
        anomaly_type: AnomalyType = AnomalyType.HOURLY_THRESHOLD,
    ):
        self.uow = uow
        self.transaction_repo = transaction_repo
        self.anomaly_repo = anomaly_repo
        self.threshold = threshold
        self.anomaly_type = anomaly_type

    async def execute(
        self,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> Result[DetectAnomaliesResponseDTO]:
        """
        Execute abnormal usage detection

        Args:
            period_start: Start of detection period (default: 1 hour ago)
            period_end: End of detection period (default: now)

        Returns:
            Result[DetectAnomaliesResponseDTO]: Detected anomalies
        """
        try:
            # Step 1: Determine time window
            now = datetime.utcnow()
            if period_end is None:
                period_end = now.replace(minute=0, second=0, microsecond=0)
            if period_start is None:
                period_start = period_end - timedelta(hours=1)

            logger.info(
                f"Running abnormal usage detection for period "
                f"{period_start.isoformat()} to {period_end.isoformat()}"
            )

            # Step 2: Get consumption per tenant for the period
            consumption_data = await self.transaction_repo.get_consumption_by_period(
                period_start, period_end
            )

            logger.info(f"Found {len(consumption_data)} tenants with consumption in period")

            # Step 3: Detect anomalies (usage exceeding threshold)
            detected_anomalies: list[UsageAnomaly] = []

            for tenant_id, total_consumed in consumption_data:
                if total_consumed > self.threshold:
                    # Check if anomaly already exists for this tenant/period
                    exists = await self.anomaly_repo.exists_for_tenant_period(
                        tenant_id, period_start, period_end
                    )
                    if exists:
                        logger.debug(
                            f"Anomaly already exists for tenant {tenant_id} in period"
                        )
                        continue

                    # Create anomaly record
                    anomaly = UsageAnomaly(
                        tenant_id=tenant_id,
                        anomaly_type=self.anomaly_type,
                        status=AnomalyStatus.DETECTED,
                        threshold_value=self.threshold,
                        actual_value=total_consumed,
                        period_start=period_start,
                        period_end=period_end,
                        description=(
                            f"Tenant {tenant_id} exceeded {self.anomaly_type.value} "
                            f"threshold. Consumed: {total_consumed}, Threshold: {self.threshold}"
                        ),
                    )

                    created_anomaly = await self.anomaly_repo.create(anomaly)
                    detected_anomalies.append(created_anomaly)

                    logger.warning(
                        f"Anomaly detected for tenant {tenant_id}: "
                        f"consumed {total_consumed} (threshold: {self.threshold})"
                    )

            # Step 4: Commit transaction
            await self.uow.commit()

            # Step 5: Build response
            anomaly_dtos = [self._to_dto(a) for a in detected_anomalies]

            response = DetectAnomaliesResponseDTO(
                anomalies_detected=len(detected_anomalies),
                anomalies=anomaly_dtos,
                period_start=period_start,
                period_end=period_end,
                threshold_used=self.threshold,
            )

            logger.info(f"Detection complete. Found {len(detected_anomalies)} new anomalies")
            return Return.ok(response)

        except Exception as e:
            await self.uow.rollback()
            logger.error(f"Abnormal usage detection failed: {e}")
            return Return.err(
                Error(
                    code="DETECTION_FAILED",
                    message="Failed to detect abnormal usage",
                    reason=str(e),
                )
            )

    def _to_dto(self, anomaly: UsageAnomaly) -> AnomalyDTO:
        """Convert UsageAnomaly entity to DTO"""
        return AnomalyDTO(
            id=anomaly.id,
            tenant_id=anomaly.tenant_id,
            anomaly_type=anomaly.anomaly_type.value,
            status=anomaly.status.value,
            threshold_value=anomaly.threshold_value,
            actual_value=anomaly.actual_value,
            period_start=anomaly.period_start,
            period_end=anomaly.period_end,
            description=anomaly.description,
            detected_at=anomaly.detected_at,
            notified_at=anomaly.notified_at,
        )
