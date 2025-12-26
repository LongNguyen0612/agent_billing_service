"""Credit Transaction Repository Interface

Defines the contract for credit transaction persistence operations.
"""

from abc import ABC, abstractmethod
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
