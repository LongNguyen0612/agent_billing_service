"""Abnormal Usage Detector Background Worker (UC-37)

Periodically scans for abnormal credit usage patterns.
Can be run as a standalone script or integrated with a scheduler.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from config import ApplicationConfig
from src.adapter.repositories.credit_transaction_repository import SqlAlchemyCreditTransactionRepository
from src.adapter.repositories.usage_anomaly_repository import SqlAlchemyUsageAnomalyRepository
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
from src.adapter.services.notification_service import create_notification_service
from src.app.use_cases.billing import DetectAbnormalUsage
from src.domain.usage_anomaly import AnomalyType

logger = logging.getLogger(__name__)


class AbnormalUsageDetectorWorker:
    """
    Background worker for detecting abnormal credit usage

    Features:
    - Runs hourly detection by default
    - Configurable thresholds from ApplicationConfig
    - Sends notifications for detected anomalies
    - Can run once or continuously

    Usage:
        # Run once
        worker = AbnormalUsageDetectorWorker()
        await worker.run_once()

        # Run continuously
        worker = AbnormalUsageDetectorWorker()
        await worker.run_forever(interval_seconds=3600)
    """

    def __init__(
        self,
        db_uri: Optional[str] = None,
        hourly_threshold: Optional[Decimal] = None,
        webhook_url: Optional[str] = None,
    ):
        """
        Initialize the worker

        Args:
            db_uri: Database URI (defaults to ApplicationConfig.DB_URI)
            hourly_threshold: Credit threshold per hour (defaults to config)
            webhook_url: Notification webhook URL (defaults to config)
        """
        self.db_uri = db_uri or ApplicationConfig.DB_URI
        self.hourly_threshold = Decimal(str(
            hourly_threshold or ApplicationConfig.ANOMALY_HOURLY_THRESHOLD
        ))
        self.webhook_url = webhook_url or ApplicationConfig.ANOMALY_NOTIFICATION_WEBHOOK

        # Create engine and session factory
        self.engine = create_async_engine(self.db_uri, echo=False, future=True)
        self.async_session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )

        # Create notification service
        self.notification_service = create_notification_service(self.webhook_url)

        logger.info(
            f"AbnormalUsageDetectorWorker initialized with "
            f"hourly_threshold={self.hourly_threshold}"
        )

    async def run_once(
        self,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> int:
        """
        Run detection once for the specified period

        Args:
            period_start: Start of detection period (default: 1 hour ago)
            period_end: End of detection period (default: now, truncated to hour)

        Returns:
            Number of anomalies detected
        """
        if not ApplicationConfig.ANOMALY_DETECTION_ENABLED:
            logger.info("Anomaly detection is disabled, skipping")
            return 0

        async with self.async_session_factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            transaction_repo = SqlAlchemyCreditTransactionRepository(session)
            anomaly_repo = SqlAlchemyUsageAnomalyRepository(session)

            use_case = DetectAbnormalUsage(
                uow=uow,
                transaction_repo=transaction_repo,
                anomaly_repo=anomaly_repo,
                threshold=self.hourly_threshold,
                anomaly_type=AnomalyType.HOURLY_THRESHOLD,
            )

            result = await use_case.execute(
                period_start=period_start,
                period_end=period_end,
            )

            if result.is_err():
                logger.error(f"Detection failed: {result.error.message}")
                return 0

            response = result.value

            # Send notifications for detected anomalies
            for anomaly_dto in response.anomalies:
                # Fetch the full entity to send notification
                anomaly = await anomaly_repo.get_by_id(anomaly_dto.id)
                if anomaly:
                    success = await self.notification_service.send_anomaly_alert(anomaly)
                    if success:
                        await anomaly_repo.mark_notified(anomaly.id)
                        await uow.commit()

            return response.anomalies_detected

    async def run_forever(self, interval_seconds: int = 3600):
        """
        Run detection continuously at specified interval

        Args:
            interval_seconds: Seconds between detection runs (default: 1 hour)
        """
        logger.info(
            f"Starting continuous anomaly detection with {interval_seconds}s interval"
        )

        while True:
            try:
                count = await self.run_once()
                logger.info(f"Detection cycle complete. Found {count} anomalies")
            except Exception as e:
                logger.error(f"Detection cycle failed: {e}")

            await asyncio.sleep(interval_seconds)

    async def shutdown(self):
        """Cleanup resources"""
        await self.engine.dispose()
        logger.info("AbnormalUsageDetectorWorker shutdown complete")


async def main():
    """
    Entry point for running the worker as a standalone script

    Usage:
        python -m src.worker.anomaly_detector
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    worker = AbnormalUsageDetectorWorker()

    # Check for --once flag to run single detection
    if "--once" in sys.argv:
        count = await worker.run_once()
        print(f"Detection complete. Found {count} anomalies.")
        await worker.shutdown()
    else:
        try:
            await worker.run_forever()
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        finally:
            await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
