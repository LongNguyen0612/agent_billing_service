"""AllocateCredits Use Case (UC-38)

Allocates credits to a tenant's balance based on subscription.
Used by monthly allocation job to add credits to tenant ledgers.
"""

from decimal import Decimal
from libs.result import Result, Return, Error
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories.credit_ledger_repository import CreditLedgerRepository
from src.app.repositories.credit_transaction_repository import CreditTransactionRepository
from src.domain.credit_transaction import CreditTransaction, TransactionType
from src.domain.credit_ledger import CreditLedger
from .dtos import AllocateCreditsCommandDTO, AllocateCreditsResponseDTO


class AllocateCredits:
    """
    Use Case: Allocate credits to tenant balance

    Business Rules:
    1. Idempotency: Same idempotency_key returns same transaction
    2. Ledger creation: If no ledger exists, create one with initial balance
    3. Atomic updates: Balance and transaction created in single transaction
    4. Pessimistic locking: SELECT FOR UPDATE prevents race conditions

    Flow:
    1. Check idempotency (return existing if found)
    2. Get or create ledger with lock
    3. Create transaction record
    4. Update ledger balance (add credits)
    5. Commit transaction
    6. Return response
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

    async def execute(self, command: AllocateCreditsCommandDTO) -> Result[AllocateCreditsResponseDTO]:
        """
        Execute credit allocation

        Args:
            command: AllocateCreditsCommandDTO with tenant_id, amount, idempotency_key

        Returns:
            Result[AllocateCreditsResponseDTO]: Success with allocation details or error
        """
        try:
            # Step 1: Check idempotency - if transaction exists, return it
            existing_transaction = await self.transaction_repo.get_by_idempotency_key(
                command.idempotency_key
            )
            if existing_transaction:
                # Idempotent response - return existing transaction
                return Return.ok(self._to_response_dto(existing_transaction))

            # Step 2: Get ledger with pessimistic lock, create if not exists
            ledger = await self.ledger_repo.get_by_tenant_id(
                command.tenant_id, for_update=True
            )

            if not ledger:
                # Create new ledger for tenant
                ledger = CreditLedger(
                    tenant_id=command.tenant_id,
                    balance=Decimal("0"),
                )
                ledger = await self.ledger_repo.create(ledger)
                # Re-fetch with lock
                ledger = await self.ledger_repo.get_by_tenant_id(
                    command.tenant_id, for_update=True
                )

            # Step 3: Calculate new balance (add credits)
            balance_before = ledger.balance
            balance_after = balance_before + command.amount

            # Step 4: Create transaction record with balance snapshots
            transaction = CreditTransaction(
                tenant_id=command.tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.ALLOCATE,
                amount=command.amount,
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

            # Step 7: Build response
            response = AllocateCreditsResponseDTO(
                transaction_id=created_transaction.id,
                tenant_id=created_transaction.tenant_id,
                amount=created_transaction.amount,
                balance_before=balance_before,
                balance_after=balance_after,
                idempotency_key=created_transaction.idempotency_key,
                created_at=created_transaction.created_at,
            )

            return Return.ok(response)

        except Exception as e:
            await self.uow.rollback()
            return Return.err(
                Error(
                    code="ALLOCATE_CREDIT_FAILED",
                    message="Failed to allocate credit",
                    reason=str(e),
                )
            )

    def _to_response_dto(self, transaction: CreditTransaction) -> AllocateCreditsResponseDTO:
        """
        Convert CreditTransaction entity to response DTO

        Balance snapshots are stored in the transaction for perfect idempotency.
        """
        return AllocateCreditsResponseDTO(
            transaction_id=transaction.id,
            tenant_id=transaction.tenant_id,
            amount=transaction.amount,
            balance_before=transaction.balance_before,
            balance_after=transaction.balance_after,
            idempotency_key=transaction.idempotency_key,
            created_at=transaction.created_at,
        )
