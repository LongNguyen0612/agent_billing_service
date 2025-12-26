"""Get Balance Use Case

Retrieves a tenant's current credit balance.
"""

from libs.result import Result, Return, Error
from src.app.repositories.credit_ledger_repository import CreditLedgerRepository
from src.app.use_cases.billing.dtos import BalanceResponseDTO


class GetBalance:
    """
    Get Balance Use Case

    Read-only operation that retrieves the current credit balance
    for a given tenant.

    AC-1.4.1: Successful Balance Retrieval
    AC-1.4.2: Tenant Not Found
    AC-1.4.3: Balance Consistency
    """

    def __init__(self, ledger_repo: CreditLedgerRepository):
        """
        Initialize GetBalance use case

        Args:
            ledger_repo: Repository for accessing credit ledgers
        """
        self.ledger_repo = ledger_repo

    async def execute(self, tenant_id: str) -> Result[BalanceResponseDTO]:
        """
        Execute get balance operation

        Args:
            tenant_id: The tenant identifier

        Returns:
            Result[BalanceResponseDTO]: Success with balance data or error

        Errors:
            LEDGER_NOT_FOUND: Tenant has no credit ledger
        """
        # Get ledger by tenant_id
        ledger = await self.ledger_repo.get_by_tenant_id(tenant_id)

        # AC-1.4.2: Tenant not found
        if not ledger:
            return Return.err(
                Error(
                    code="LEDGER_NOT_FOUND",
                    message=f"No credit ledger found for tenant {tenant_id}",
                )
            )

        # AC-1.4.1: Successful balance retrieval
        return Return.ok(
            BalanceResponseDTO(
                tenant_id=ledger.tenant_id,
                balance=ledger.balance,
                last_updated=ledger.updated_at,
            )
        )
