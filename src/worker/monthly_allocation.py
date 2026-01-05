"""Monthly Credit Allocation Background Worker (UC-38)

Allocates monthly credits to tenants based on their subscription plans.
Creates draft invoices for each allocation.
Can be run as a standalone script or integrated with a scheduler.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from calendar import monthrange
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from config import ApplicationConfig
from src.adapter.repositories.credit_ledger_repository import SqlAlchemyCreditLedgerRepository
from src.adapter.repositories.credit_transaction_repository import SqlAlchemyCreditTransactionRepository
from src.adapter.repositories.subscription_repository import SqlAlchemySubscriptionRepository
from src.adapter.repositories.invoice_repository import SqlAlchemyInvoiceRepository
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
from src.app.use_cases.billing import (
    AllocateCredits,
    CreateInvoice,
    AllocateCreditsCommandDTO,
    CreateInvoiceCommandDTO,
    MonthlyAllocationResultDTO,
)

logger = logging.getLogger(__name__)


class MonthlyAllocationWorker:
    """
    Background worker for monthly credit allocation

    Features:
    - Runs monthly at the start of each billing period
    - Allocates credits based on subscription.monthly_credits
    - Creates draft invoices for each allocation
    - Idempotent: safe to re-run without duplicate allocations
    - Can run once or continuously

    Usage:
        # Run once for specific month
        worker = MonthlyAllocationWorker()
        result = await worker.run_once(year=2024, month=1)

        # Run for previous month (typical cron usage)
        worker = MonthlyAllocationWorker()
        result = await worker.run_once()

        # Run continuously (checks daily if new month started)
        worker = MonthlyAllocationWorker()
        await worker.run_forever()
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

        logger.info("MonthlyAllocationWorker initialized")

    def _get_billing_period(
        self, year: Optional[int] = None, month: Optional[int] = None
    ) -> tuple[datetime, datetime]:
        """
        Get billing period start and end dates

        If year/month not provided, uses previous month.

        Args:
            year: Year (optional)
            month: Month (optional)

        Returns:
            Tuple of (period_start, period_end)
        """
        if year is None or month is None:
            # Default to previous month
            today = datetime.utcnow()
            if today.month == 1:
                year = today.year - 1
                month = 12
            else:
                year = today.year
                month = today.month - 1

        # First day of month at 00:00:00
        period_start = datetime(year, month, 1, 0, 0, 0)

        # Last day of month at 23:59:59
        _, last_day = monthrange(year, month)
        period_end = datetime(year, month, last_day, 23, 59, 59)

        return period_start, period_end

    def _generate_idempotency_key(self, tenant_id: str, period_start: datetime) -> str:
        """
        Generate idempotency key for allocation

        Format: allocation:{tenant_id}:{YYYY-MM}

        Args:
            tenant_id: Tenant identifier
            period_start: Billing period start

        Returns:
            Idempotency key string
        """
        period_str = period_start.strftime("%Y-%m")
        return f"allocation:{tenant_id}:{period_str}"

    async def run_once(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
    ) -> MonthlyAllocationResultDTO:
        """
        Run allocation once for the specified billing period

        Args:
            year: Year (optional, defaults to previous month)
            month: Month (optional, defaults to previous month)

        Returns:
            MonthlyAllocationResultDTO with summary
        """
        start_time = time.time()
        period_start, period_end = self._get_billing_period(year, month)

        logger.info(
            f"Starting monthly allocation for period "
            f"{period_start.strftime('%Y-%m-%d')} to {period_end.strftime('%Y-%m-%d')}"
        )

        successful_allocations = 0
        failed_allocations = 0
        invoices_created = 0

        async with self.async_session_factory() as session:
            subscription_repo = SqlAlchemySubscriptionRepository(session)

            # Get all active subscriptions
            subscriptions = await subscription_repo.get_active_subscriptions()
            total_subscriptions = len(subscriptions)

            logger.info(f"Found {total_subscriptions} active subscriptions")

            for subscription in subscriptions:
                try:
                    # Create a new session for each tenant to isolate transactions
                    async with self.async_session_factory() as tenant_session:
                        uow = SqlAlchemyUnitOfWork(tenant_session)
                        ledger_repo = SqlAlchemyCreditLedgerRepository(tenant_session)
                        transaction_repo = SqlAlchemyCreditTransactionRepository(tenant_session)
                        invoice_repo = SqlAlchemyInvoiceRepository(tenant_session)

                        # Step 1: Allocate credits
                        allocate_uc = AllocateCredits(
                            uow=uow,
                            ledger_repo=ledger_repo,
                            transaction_repo=transaction_repo,
                        )

                        allocate_command = AllocateCreditsCommandDTO(
                            tenant_id=subscription.tenant_id,
                            amount=subscription.monthly_credits,
                            idempotency_key=self._generate_idempotency_key(
                                subscription.tenant_id, period_start
                            ),
                            reference_type="subscription",
                            reference_id=str(subscription.id),
                        )

                        allocate_result = await allocate_uc.execute(allocate_command)

                        if allocate_result.is_err():
                            logger.error(
                                f"Failed to allocate credits for tenant {subscription.tenant_id}: "
                                f"{allocate_result.error.message}"
                            )
                            failed_allocations += 1
                            continue

                        successful_allocations += 1
                        logger.info(
                            f"Allocated {subscription.monthly_credits} credits to "
                            f"tenant {subscription.tenant_id}"
                        )

                        # Step 2: Create invoice
                        # Calculate invoice amount (credits * price per credit)
                        # For now, using a simple calculation - could be enhanced with pricing tiers
                        credit_price = Decimal("0.015")  # $0.015 per credit
                        invoice_amount = subscription.monthly_credits * credit_price

                        create_invoice_uc = CreateInvoice(
                            uow=uow,
                            invoice_repo=invoice_repo,
                        )

                        invoice_command = CreateInvoiceCommandDTO(
                            tenant_id=subscription.tenant_id,
                            billing_period_start=period_start,
                            billing_period_end=period_end,
                            total_amount=invoice_amount,
                            description=f"Monthly credit allocation - {subscription.plan_name}",
                        )

                        invoice_result = await create_invoice_uc.execute(invoice_command)

                        if invoice_result.is_err():
                            # Invoice already exists is not an error for idempotency
                            if invoice_result.error.code == "INVOICE_ALREADY_EXISTS":
                                logger.info(
                                    f"Invoice already exists for tenant {subscription.tenant_id}"
                                )
                            else:
                                logger.warning(
                                    f"Failed to create invoice for tenant {subscription.tenant_id}: "
                                    f"{invoice_result.error.message}"
                                )
                        else:
                            invoices_created += 1
                            logger.info(
                                f"Created invoice {invoice_result.value.invoice_number} for "
                                f"tenant {subscription.tenant_id}"
                            )

                except Exception as e:
                    logger.error(
                        f"Unexpected error processing tenant {subscription.tenant_id}: {e}"
                    )
                    failed_allocations += 1

        execution_time_ms = int((time.time() - start_time) * 1000)

        result = MonthlyAllocationResultDTO(
            total_subscriptions=total_subscriptions,
            successful_allocations=successful_allocations,
            failed_allocations=failed_allocations,
            invoices_created=invoices_created,
            billing_period_start=period_start,
            billing_period_end=period_end,
            execution_time_ms=execution_time_ms,
        )

        logger.info(
            f"Monthly allocation complete: "
            f"{successful_allocations}/{total_subscriptions} successful, "
            f"{invoices_created} invoices created, "
            f"{execution_time_ms}ms"
        )

        return result

    async def run_forever(self, check_interval_seconds: int = 86400):
        """
        Run allocation continuously, checking daily if new month started

        Args:
            check_interval_seconds: Seconds between checks (default: 24 hours)
        """
        logger.info(
            f"Starting continuous monthly allocation with {check_interval_seconds}s interval"
        )

        last_processed_month = None

        while True:
            try:
                today = datetime.utcnow()
                current_month = (today.year, today.month)

                # Only process if we're in a new month and haven't processed yet
                if today.day <= 3 and last_processed_month != current_month:
                    # Process previous month's allocation
                    result = await self.run_once()
                    last_processed_month = current_month
                    logger.info(
                        f"Processed month allocation: "
                        f"{result.successful_allocations} successful"
                    )
                else:
                    logger.debug(
                        f"Skipping allocation check - not first 3 days or already processed"
                    )

            except Exception as e:
                logger.error(f"Allocation cycle failed: {e}")

            await asyncio.sleep(check_interval_seconds)

    async def shutdown(self):
        """Cleanup resources"""
        await self.engine.dispose()
        logger.info("MonthlyAllocationWorker shutdown complete")


async def main():
    """
    Entry point for running the worker as a standalone script

    Usage:
        # Run for previous month
        python -m src.worker.monthly_allocation

        # Run for specific month
        python -m src.worker.monthly_allocation --year 2024 --month 1

        # Run continuously
        python -m src.worker.monthly_allocation --continuous
    """
    import sys
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(description="Monthly Credit Allocation Worker")
    parser.add_argument("--year", type=int, help="Year for allocation")
    parser.add_argument("--month", type=int, help="Month for allocation")
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuously"
    )
    args = parser.parse_args()

    worker = MonthlyAllocationWorker()

    try:
        if args.continuous:
            await worker.run_forever()
        else:
            result = await worker.run_once(year=args.year, month=args.month)
            print(f"Allocation complete:")
            print(f"  Total subscriptions: {result.total_subscriptions}")
            print(f"  Successful allocations: {result.successful_allocations}")
            print(f"  Failed allocations: {result.failed_allocations}")
            print(f"  Invoices created: {result.invoices_created}")
            print(f"  Execution time: {result.execution_time_ms}ms")
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await worker.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
