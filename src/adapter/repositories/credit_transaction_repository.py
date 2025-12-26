"""SQLAlchemy implementation of CreditTransactionRepository

Provides persistence for CreditTransaction entities with idempotency enforcement
via unique constraint on idempotency_key.
"""

from typing import Optional
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
from src.app.repositories.credit_transaction_repository import CreditTransactionRepository
from src.domain.credit_transaction import CreditTransaction


class SqlAlchemyCreditTransactionRepository(CreditTransactionRepository):
    """
    SQLAlchemy implementation of CreditTransactionRepository

    Features:
    - Idempotency enforcement via unique idempotency_key constraint
    - Immutable append-only transactions
    - Graceful handling of duplicate transaction attempts
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, transaction: CreditTransaction) -> CreditTransaction:
        """
        Create a new credit transaction

        Args:
            transaction: CreditTransaction entity to persist

        Returns:
            Created CreditTransaction with generated ID

        Raises:
            IntegrityError: If idempotency_key already exists (duplicate transaction attempt)
        """
        self.session.add(transaction)
        await self.session.flush()
        await self.session.refresh(transaction)
        return transaction

    async def get_by_idempotency_key(self, idempotency_key: str) -> Optional[CreditTransaction]:
        """
        Retrieve transaction by idempotency key

        Used to check if transaction already exists (idempotency check).

        Args:
            idempotency_key: Unique idempotency key

        Returns:
            CreditTransaction if found, None otherwise
        """
        stmt = select(CreditTransaction).where(
            CreditTransaction.idempotency_key == idempotency_key
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, transaction_id: int) -> Optional[CreditTransaction]:
        """
        Retrieve transaction by ID

        Args:
            transaction_id: Transaction ID

        Returns:
            CreditTransaction if found, None otherwise
        """
        stmt = select(CreditTransaction).where(CreditTransaction.id == transaction_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
