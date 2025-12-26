"""SQLAlchemy implementation of CreditLedgerRepository

Provides persistence for CreditLedger entities with pessimistic locking support
to prevent race conditions during concurrent credit operations.
"""

from typing import Optional
from decimal import Decimal
from datetime import datetime
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.app.repositories.credit_ledger_repository import CreditLedgerRepository
from src.domain.credit_ledger import CreditLedger


class SqlAlchemyCreditLedgerRepository(CreditLedgerRepository):
    """
    SQLAlchemy implementation of CreditLedgerRepository

    Features:
    - Pessimistic locking via SELECT FOR UPDATE
    - Atomic balance updates
    - Thread-safe concurrent operations
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tenant_id(self, tenant_id: str, for_update: bool = False) -> Optional[CreditLedger]:
        """
        Retrieve ledger by tenant ID with optional row-level locking

        Args:
            tenant_id: Tenant identifier
            for_update: If True, locks the row with SELECT FOR UPDATE (prevents concurrent modifications)

        Returns:
            CreditLedger if found, None otherwise
        """
        stmt = select(CreditLedger).where(CreditLedger.tenant_id == tenant_id)

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, ledger_id: int, for_update: bool = False) -> Optional[CreditLedger]:
        """
        Retrieve ledger by ID with optional row-level locking

        Args:
            ledger_id: Ledger ID
            for_update: If True, locks the row with SELECT FOR UPDATE

        Returns:
            CreditLedger if found, None otherwise
        """
        stmt = select(CreditLedger).where(CreditLedger.id == ledger_id)

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, ledger: CreditLedger) -> CreditLedger:
        """
        Create a new credit ledger

        Args:
            ledger: CreditLedger entity to persist

        Returns:
            Created CreditLedger with generated ID
        """
        self.session.add(ledger)
        await self.session.flush()
        await self.session.refresh(ledger)
        return ledger

    async def update_balance(self, ledger_id: int, new_balance: Decimal) -> None:
        """
        Update ledger balance and updated_at timestamp

        Args:
            ledger_id: Ledger ID
            new_balance: New balance value

        Note:
            Should be called within a transaction with the ledger already locked
        """
        ledger = await self.get_by_id(ledger_id, for_update=False)
        if ledger:
            ledger.balance = new_balance
            ledger.updated_at = datetime.utcnow()
            self.session.add(ledger)
            await self.session.flush()
