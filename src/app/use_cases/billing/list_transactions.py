"""
List Transactions Use Case (UC-36)

Retrieves credit transaction history for a tenant with pagination.
"""
from libs.result import Result, Return
from src.app.repositories.credit_transaction_repository import CreditTransactionRepository
from .dtos import ListTransactionsResponseDTO, TransactionDTO


class ListTransactions:
    """
    Use case: View Credit Transactions (UC-36)

    Retrieves paginated transaction history for a tenant.
    Transactions are ordered by created_at DESC (most recent first).
    """

    def __init__(self, transaction_repo: CreditTransactionRepository):
        """
        Initialize with transaction repository.

        Args:
            transaction_repo: CreditTransactionRepository instance
        """
        self.transaction_repo = transaction_repo

    async def execute(
        self, tenant_id: str, limit: int = 20, offset: int = 0
    ) -> Result[ListTransactionsResponseDTO]:
        """
        List transactions for a tenant with pagination.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of transactions to return (default 20)
            offset: Number of transactions to skip (default 0)

        Returns:
            Result[ListTransactionsResponseDTO]: Paginated transaction list
        """
        transactions, total = await self.transaction_repo.get_by_tenant_id(
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )

        # Convert to DTOs
        transaction_dtos = [
            TransactionDTO(
                id=txn.id,
                transaction_type=txn.transaction_type.value if hasattr(txn.transaction_type, "value") else txn.transaction_type,
                amount=txn.amount,
                balance_after=txn.balance_after,
                reference_type=txn.reference_type,
                reference_id=txn.reference_id,
                created_at=txn.created_at,
            )
            for txn in transactions
        ]

        return Return.ok(
            ListTransactionsResponseDTO(
                transactions=transaction_dtos,
                total=total,
                limit=limit,
                offset=offset,
            )
        )
