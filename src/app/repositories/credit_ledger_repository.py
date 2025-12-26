"""Credit Ledger Repository Interface

Defines the contract for credit ledger persistence operations.
"""

from abc import ABC, abstractmethod
from typing import Optional
from decimal import Decimal
from src.domain.credit_ledger import CreditLedger


class CreditLedgerRepository(ABC):
    """
    Repository interface for CreditLedger persistence

    Methods use pessimistic locking (SELECT FOR UPDATE) to ensure
    consistency during concurrent credit operations.
    """

    @abstractmethod
    async def get_by_tenant_id(self, tenant_id: str, for_update: bool = False) -> Optional[CreditLedger]:
        """
        Retrieve ledger by tenant ID

        Args:
            tenant_id: Tenant identifier
            for_update: If True, lock the row with SELECT FOR UPDATE (pessimistic lock)

        Returns:
            CreditLedger if found, None otherwise
        """
        pass

    @abstractmethod
    async def create(self, ledger: CreditLedger) -> CreditLedger:
        """
        Create a new credit ledger

        Args:
            ledger: CreditLedger entity to persist

        Returns:
            Created CreditLedger with generated ID
        """
        pass

    @abstractmethod
    async def update_balance(self, ledger_id: int, new_balance: Decimal) -> None:
        """
        Update ledger balance

        Args:
            ledger_id: Ledger ID
            new_balance: New balance value
        """
        pass

    @abstractmethod
    async def get_by_id(self, ledger_id: int, for_update: bool = False) -> Optional[CreditLedger]:
        """
        Retrieve ledger by ID

        Args:
            ledger_id: Ledger ID
            for_update: If True, lock the row with SELECT FOR UPDATE

        Returns:
            CreditLedger if found, None otherwise
        """
        pass
