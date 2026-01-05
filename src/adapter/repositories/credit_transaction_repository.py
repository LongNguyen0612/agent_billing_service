"""SQLAlchemy implementation of CreditTransactionRepository

Provides persistence for CreditTransaction entities with idempotency enforcement
via unique constraint on idempotency_key.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlmodel import select, func, and_
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.exc import IntegrityError
from src.app.repositories.credit_transaction_repository import CreditTransactionRepository
from src.domain.credit_transaction import CreditTransaction, TransactionType


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
        from sqlmodel import func

        # Get total count
        count_stmt = select(func.count()).select_from(CreditTransaction).where(
            CreditTransaction.tenant_id == tenant_id
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar()

        # Get paginated transactions ordered by created_at DESC
        stmt = (
            select(CreditTransaction)
            .where(CreditTransaction.tenant_id == tenant_id)
            .order_by(CreditTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        transactions = list(result.scalars().all())

        return transactions, total

    async def get_consumption_by_period(
        self, start_time: datetime, end_time: datetime
    ) -> list[tuple[str, Decimal]]:
        """
        Get total consumption per tenant within a time period

        Only counts CONSUME transactions (not refunds/allocations).

        Args:
            start_time: Period start time
            end_time: Period end time

        Returns:
            List of (tenant_id, total_consumed) tuples
        """
        stmt = (
            select(
                CreditTransaction.tenant_id,
                func.sum(CreditTransaction.amount).label("total")
            )
            .where(
                and_(
                    CreditTransaction.transaction_type == TransactionType.CONSUME,
                    CreditTransaction.created_at >= start_time,
                    CreditTransaction.created_at < end_time
                )
            )
            .group_by(CreditTransaction.tenant_id)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [(row.tenant_id, row.total or Decimal("0")) for row in rows]

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
        stmt = select(func.sum(CreditTransaction.amount)).where(
            CreditTransaction.ledger_id == ledger_id
        )
        result = await self.session.execute(stmt)
        total = result.scalar()
        return total or Decimal("0")
