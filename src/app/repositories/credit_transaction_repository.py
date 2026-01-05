"""Credit Transaction Repository Interface

Defines the contract for credit transaction persistence operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Optional
from src.domain.credit_transaction import CreditTransaction


class CreditTransactionRepository(ABC):
    """
    Repository interface for CreditTransaction persistence

    Transactions are immutable and append-only for audit trail.
    Idempotency is enforced via unique idempotency_key.
    """

    @abstractmethod
    async def create(self, transaction: CreditTransaction) -> CreditTransaction:
        """
        Create a new credit transaction

        Args:
            transaction: CreditTransaction entity to persist

        Returns:
            Created CreditTransaction with generated ID

        Raises:
            IntegrityError: If idempotency_key already exists (duplicate transaction)
        """
        pass

    @abstractmethod
    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[CreditTransaction]:
        """
        Retrieve transaction by idempotency key

        Used to check if transaction already exists (idempotency check).

        Args:
            idempotency_key: Unique idempotency key

        Returns:
            CreditTransaction if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_id(self, transaction_id: int) -> Optional[CreditTransaction]:
        """
        Retrieve transaction by ID

        Args:
            transaction_id: Transaction ID

        Returns:
            CreditTransaction if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_tenant_id(
        self, tenant_id: str, limit: int = 20, offset: int = 0
    ) -> tuple[list[CreditTransaction], int]:
        """
        Retrieve transactions for a tenant with pagination

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of transactions to return
            offset: Number of transactions to skip

        Returns:
            Tuple of (list of CreditTransaction, total count)
        """
        pass

    @abstractmethod
    async def get_consumption_by_period(
        self, start_time: datetime, end_time: datetime
    ) -> list[tuple[str, Decimal]]:
        """
        Get total consumption per tenant within a time period

        Used for abnormal usage detection.

        Args:
            start_time: Period start time
            end_time: Period end time

        Returns:
            List of (tenant_id, total_consumed) tuples
        """
        pass

    @abstractmethod
    async def get_transaction_sum_by_ledger(self, ledger_id: int) -> Decimal:
        """
        Get sum of all transaction amounts for a specific ledger

        Used for reconciliation to compare against ledger balance.
        Sums all transaction types (CONSUME, REFUND, ALLOCATE, ADJUST).

        Args:
            ledger_id: Ledger ID

        Returns:
            Sum of all transaction amounts (can be negative, zero, or positive)
        """
        pass
