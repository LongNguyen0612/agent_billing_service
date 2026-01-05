"""Ledger Reconciliation Background Worker (UC-40)

Periodically reconciles credit ledger balances against transaction history.
Can be run as a standalone script or integrated with a scheduler.
"""

import asyncio
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from config import ApplicationConfig
from src.adapter.repositories.credit_ledger_repository import SqlAlchemyCreditLedgerRepository
from src.adapter.repositories.credit_transaction_repository import SqlAlchemyCreditTransactionRepository
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
from src.app.use_cases.billing import ReconcileLedger, ReconciliationResultDTO

logger = logging.getLogger(__name__)


class LedgerReconcilerWorker:
    """
    Background worker for credit ledger reconciliation

    Features:
    - Compares ledger balances against transaction sums
    - Logs discrepancies for investigation
    - Can run once or continuously
    - Configurable interval (default: daily)

    Usage:
        # Run once
        worker = LedgerReconcilerWorker()
        result = await worker.run_once()

        # Run continuously
        worker = LedgerReconcilerWorker()
        await worker.run_forever(interval_seconds=86400)  # Daily
    """

    def __init__(
        self,
        db_uri: Optional[str] = None,
    ):
        """
        Initialize the worker

        Args:
            db_uri: Database URI (defaults to ApplicationConfig.DB_URI)
        """
        self.db_uri = db_uri or ApplicationConfig.DB_URI

        # Create engine and session factory
        self.engine = create_async_engine(self.db_uri, echo=False, future=True)
        self.async_session_factory = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )

        logger.info("LedgerReconcilerWorker initialized")

    async def run_once(self) -> ReconciliationResultDTO:
        """
        Run reconciliation once

        Returns:
            ReconciliationResultDTO with reconciliation results
        """
        reconciliation_enabled = getattr(
            ApplicationConfig, "RECONCILIATION_ENABLED", True
        )
        if not reconciliation_enabled:
            logger.info("Ledger reconciliation is disabled, skipping")
            return ReconciliationResultDTO(
                total_ledgers_checked=0,
                discrepancies_found=0,
                discrepancies=[],
                reconciliation_time=__import__("datetime").datetime.utcnow(),
                execution_time_ms=0,
            )

        async with self.async_session_factory() as session:
            uow = SqlAlchemyUnitOfWork(session)
            ledger_repo = SqlAlchemyCreditLedgerRepository(session)
            transaction_repo = SqlAlchemyCreditTransactionRepository(session)

            use_case = ReconcileLedger(
                uow=uow,
                ledger_repo=ledger_repo,
                transaction_repo=transaction_repo,
            )

            result = await use_case.execute()

            if result.is_err():
                logger.error(f"Reconciliation failed: {result.error.message}")
                raise RuntimeError(f"Reconciliation failed: {result.error.message}")

            response = result.value

            # Log discrepancies with severity
            if response.discrepancies_found > 0:
                logger.error(
                    f"ALERT: {response.discrepancies_found} ledger discrepancies found!"
                )
                for d in response.discrepancies:
                    logger.error(
                        f"  - Tenant {d.tenant_id} (ledger_id={d.ledger_id}): "
                        f"expected={d.calculated_balance}, actual={d.ledger_balance}, "
                        f"diff={d.discrepancy}"
                    )

            return response

    async def run_forever(self, interval_seconds: int = 86400):
        """
        Run reconciliation continuously at specified interval

        Args:
            interval_seconds: Seconds between reconciliation runs (default: 24 hours)
        """
        logger.info(
            f"Starting continuous ledger reconciliation with {interval_seconds}s interval"
        )

        while True:
            try:
                result = await self.run_once()
                logger.info(
                    f"Reconciliation cycle complete. "
                    f"Checked {result.total_ledgers_checked} ledgers, "
                    f"found {result.discrepancies_found} discrepancies "
                    f"in {result.execution_time_ms}ms"
                )
            except Exception as e:
                logger.error(f"Reconciliation cycle failed: {e}")

            await asyncio.sleep(interval_seconds)

    async def shutdown(self):
        """Cleanup resources"""
        await self.engine.dispose()
        logger.info("LedgerReconcilerWorker shutdown complete")


async def main():
    """
    Entry point for running the worker as a standalone script

    Usage:
        # Run once
        python -m src.worker.ledger_reconciler --once

        # Run continuously (default: daily)
        python -m src.worker.ledger_reconciler

        # Run continuously with custom interval (in seconds)
        python -m src.worker.ledger_reconciler --interval 3600
    """
    import sys
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Ledger Reconciliation Worker")
    parser.add_argument(
        "--once", action="store_true", help="Run once and exit"
    )
    parser.add_argument(
        "--interval", type=int, default=86400,
        help="Interval between runs in seconds (default: 86400 = 24 hours)"
    )
    args = parser.parse_args()

    worker = LedgerReconcilerWorker()

    try:
        if args.once:
            result = await worker.run_once()
            print(f"Reconciliation complete:")
            print(f"  Total ledgers checked: {result.total_ledgers_checked}")
            print(f"  Discrepancies found: {result.discrepancies_found}")
            print(f"  Execution time: {result.execution_time_ms}ms")
            if result.discrepancies:
                print("\nDiscrepancies:")
                for d in result.discrepancies:
                    print(
                        f"  - Tenant {d.tenant_id}: "
                        f"expected={d.calculated_balance}, "
                        f"actual={d.ledger_balance}, "
                        f"diff={d.discrepancy}"
                    )
        else:
            await worker.run_forever(interval_seconds=args.interval)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
