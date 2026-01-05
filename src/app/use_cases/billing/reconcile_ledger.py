"""ReconcileLedger Use Case (UC-40)

Reconciles credit ledger balances against transaction history to detect discrepancies.
"""

import logging
import time
from datetime import datetime
from decimal import Decimal
from libs.result import Result, Return, Error
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories.credit_ledger_repository import CreditLedgerRepository
from src.app.repositories.credit_transaction_repository import CreditTransactionRepository
from .dtos import LedgerDiscrepancyDTO, ReconciliationResultDTO

logger = logging.getLogger(__name__)


class ReconcileLedger:
    """
    Use Case: Reconcile credit ledger against transactions (UC-40)

    Business Rules:
    1. Retrieves all credit ledgers from the system
    2. For each ledger, calculates expected balance from transaction sum
    3. Compares ledger balance against calculated balance
    4. Records and logs any discrepancies found
    5. Does NOT modify any data (read-only reconciliation)

    Flow:
    1. Get all ledgers
    2. For each ledger:
       a. Get sum of all transactions for the ledger
       b. Compare with ledger's current balance
       c. If mismatch, record discrepancy
    3. Return reconciliation result with all discrepancies
    """

    def __init__(
        self,
        uow: UnitOfWork,
        ledger_repo: CreditLedgerRepository,
        transaction_repo: CreditTransactionRepository,
    ):
        self.uow = uow
        self.ledger_repo = ledger_repo
        self.transaction_repo = transaction_repo

    async def execute(self) -> Result[ReconciliationResultDTO]:
        """
        Execute ledger reconciliation

        Returns:
            Result[ReconciliationResultDTO]: Reconciliation result with any discrepancies
        """
        start_time = time.time()
        reconciliation_time = datetime.utcnow()

        try:
            logger.info("Starting credit ledger reconciliation")

            # Step 1: Get all ledgers
            ledgers = await self.ledger_repo.get_all()
            total_ledgers = len(ledgers)

            logger.info(f"Found {total_ledgers} ledgers to reconcile")

            # Step 2: Check each ledger for discrepancies
            discrepancies: list[LedgerDiscrepancyDTO] = []

            for ledger in ledgers:
                # Get sum of all transactions for this ledger
                transaction_sum = await self.transaction_repo.get_transaction_sum_by_ledger(
                    ledger.id
                )

                # Compare with ledger balance
                # Note: Transaction sum should equal ledger balance
                # Positive transactions (ALLOCATE, REFUND, ADJUST+) add to balance
                # Negative transactions (CONSUME, ADJUST-) subtract from balance
                if ledger.balance != transaction_sum:
                    discrepancy_amount = ledger.balance - transaction_sum

                    discrepancy = LedgerDiscrepancyDTO(
                        tenant_id=ledger.tenant_id,
                        ledger_id=ledger.id,
                        ledger_balance=ledger.balance,
                        calculated_balance=transaction_sum,
                        discrepancy=discrepancy_amount,
                    )
                    discrepancies.append(discrepancy)

                    logger.warning(
                        f"Discrepancy found for tenant {ledger.tenant_id} "
                        f"(ledger_id={ledger.id}): "
                        f"ledger_balance={ledger.balance}, "
                        f"transaction_sum={transaction_sum}, "
                        f"discrepancy={discrepancy_amount}"
                    )

            # Step 3: Build response
            execution_time_ms = int((time.time() - start_time) * 1000)

            response = ReconciliationResultDTO(
                total_ledgers_checked=total_ledgers,
                discrepancies_found=len(discrepancies),
                discrepancies=discrepancies,
                reconciliation_time=reconciliation_time,
                execution_time_ms=execution_time_ms,
            )

            if discrepancies:
                logger.warning(
                    f"Reconciliation complete. Found {len(discrepancies)} discrepancies "
                    f"out of {total_ledgers} ledgers in {execution_time_ms}ms"
                )
            else:
                logger.info(
                    f"Reconciliation complete. All {total_ledgers} ledgers balanced "
                    f"in {execution_time_ms}ms"
                )

            return Return.ok(response)

        except Exception as e:
            logger.error(f"Ledger reconciliation failed: {e}")
            return Return.err(
                Error(
                    code="RECONCILIATION_FAILED",
                    message="Failed to reconcile credit ledger",
                    reason=str(e),
                )
            )
