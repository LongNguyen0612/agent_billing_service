"""RefundCredit Use Case

Refunds credits to a tenant's balance for compensation of failed operations.
Implements idempotency guarantees and pessimistic locking.
"""

from decimal import Decimal
from libs.result import Result, Return, Error
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories.credit_ledger_repository import CreditLedgerRepository
from src.app.repositories.credit_transaction_repository import CreditTransactionRepository
from src.domain.credit_transaction import CreditTransaction, TransactionType
from .dtos import RefundCommandDTO, CreditTransactionResponseDTO


class RefundCredit:
    """
    Use Case: Refund credits to tenant balance

    Business Rules:
    1. Idempotency: Same idempotency_key returns same transaction
    2. Balance increment: balance += amount (refunds are always positive)
    3. Atomic updates: Balance and transaction created in single transaction
    4. Pessimistic locking: SELECT FOR UPDATE prevents race conditions
    5. No maximum limit: Refunds can exceed previous balance

    Flow:
    1. Check idempotency (return existing if found)
    2. Get ledger with lock (SELECT FOR UPDATE)
    3. Calculate new balance (balance + amount)
    4. Create transaction record (type=REFUND)
    5. Update ledger balance
    6. Commit transaction
    7. Return response
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

    async def execute(self, command: RefundCommandDTO) -> Result[CreditTransactionResponseDTO]:
        """
        Execute credit refund

        Args:
            command: RefundCommandDTO with tenant_id, amount, idempotency_key

        Returns:
            Result[CreditTransactionResponseDTO]: Success with transaction details or error
        """
        try:
            # Step 1: Check idempotency - if transaction exists, return it
            existing_transaction = await self.transaction_repo.get_by_idempotency_key(
                command.idempotency_key
            )
            if existing_transaction:
                # Idempotent response - return existing transaction
                return Return.ok(self._to_response_dto(existing_transaction))

            # Step 2: Get ledger with pessimistic lock (SELECT FOR UPDATE)
            ledger = await self.ledger_repo.get_by_tenant_id(
                command.tenant_id, for_update=True
            )

            if not ledger:
                return Return.err(
                    Error(
                        code="LEDGER_NOT_FOUND",
                        message=f"Credit ledger not found for tenant {command.tenant_id}",
                        reason="Tenant may not exist or ledger not initialized",
                    )
                )

            # Step 3: Calculate new balance (increment for refund)
            balance_before = ledger.balance
            balance_after = balance_before + command.amount

            # Step 4: Create transaction record with balance snapshots
            transaction = CreditTransaction(
                tenant_id=command.tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.REFUND,
                amount=command.amount,  # Stored as positive value
                balance_before=balance_before,
                balance_after=balance_after,
                reference_type=command.reference_type,
                reference_id=command.reference_id,
                idempotency_key=command.idempotency_key,
            )

            created_transaction = await self.transaction_repo.create(transaction)

            # Step 5: Update ledger balance
            await self.ledger_repo.update_balance(ledger.id, balance_after)

            # Step 6: Commit transaction
            await self.uow.commit()

            # Step 7: Build response with balance snapshots
            response = CreditTransactionResponseDTO(
                transaction_id=created_transaction.id,
                tenant_id=created_transaction.tenant_id,
                transaction_type=created_transaction.transaction_type.value,
                amount=created_transaction.amount,
                balance_before=balance_before,
                balance_after=balance_after,
                reference_type=created_transaction.reference_type,
                reference_id=created_transaction.reference_id,
                idempotency_key=created_transaction.idempotency_key,
                created_at=created_transaction.created_at,
            )

            return Return.ok(response)

        except Exception as e:
            await self.uow.rollback()
            return Return.err(
                Error(
                    code="REFUND_CREDIT_FAILED",
                    message="Failed to refund credit",
                    reason=str(e),
                )
            )

    def _to_response_dto(self, transaction: CreditTransaction) -> CreditTransactionResponseDTO:
        """
        Convert CreditTransaction entity to response DTO

        Balance snapshots are stored in the transaction for perfect idempotency.
        """
        return CreditTransactionResponseDTO(
            transaction_id=transaction.id,
            tenant_id=transaction.tenant_id,
            transaction_type=transaction.transaction_type.value,
            amount=transaction.amount,
            balance_before=transaction.balance_before,
            balance_after=transaction.balance_after,
            reference_type=transaction.reference_type,
            reference_id=transaction.reference_id,
            idempotency_key=transaction.idempotency_key,
            created_at=transaction.created_at,
        )
