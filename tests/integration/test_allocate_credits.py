"""Integration tests for AllocateCredits use case (UC-38)

Tests cover:
- AC-3.4.1: Monthly allocation with real database
- Ledger creation for new tenants
- Idempotency with real database
"""

import pytest
from decimal import Decimal
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.credit_ledger import CreditLedger
from src.domain.credit_transaction import CreditTransaction, TransactionType
from src.app.use_cases.billing.allocate_credits import AllocateCredits
from src.app.use_cases.billing.dtos import AllocateCreditsCommandDTO
from src.adapter.repositories.credit_ledger_repository import SqlAlchemyCreditLedgerRepository
from src.adapter.repositories.credit_transaction_repository import SqlAlchemyCreditTransactionRepository
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
class TestAllocateCreditsIntegration:
    """Integration tests with real database"""

    async def test_end_to_end_credit_allocation(self, db_session: AsyncSession):
        """
        Test complete flow: create ledger, allocate credit, verify database state
        """
        # Arrange - create ledger with existing balance
        ledger = CreditLedger(
            tenant_id="tenant_alloc_1",
            balance=Decimal("500.000000"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Arrange - setup use case
        ledger_repo = SqlAlchemyCreditLedgerRepository(db_session)
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = AllocateCredits(uow, ledger_repo, transaction_repo)

        command = AllocateCreditsCommandDTO(
            tenant_id="tenant_alloc_1",
            amount=Decimal("10000.000000"),
            idempotency_key="allocation:tenant_alloc_1:2024-01",
            reference_type="subscription",
            reference_id="sub_123",
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.amount == Decimal("10000.000000")
        assert response.balance_before == Decimal("500.000000")
        assert response.balance_after == Decimal("10500.000000")

        # Verify ledger updated in database
        await db_session.refresh(ledger)
        assert ledger.balance == Decimal("10500.000000")

        # Verify transaction exists in database
        created_transaction = await transaction_repo.get_by_idempotency_key(
            "allocation:tenant_alloc_1:2024-01"
        )
        assert created_transaction is not None
        assert created_transaction.amount == Decimal("10000.000000")
        assert created_transaction.transaction_type == TransactionType.ALLOCATE
        assert created_transaction.reference_type == "subscription"
        assert created_transaction.reference_id == "sub_123"

    async def test_allocation_creates_ledger_for_new_tenant(self, db_session: AsyncSession):
        """
        Test that allocation creates a new ledger if tenant doesn't have one
        """
        # Arrange - no existing ledger for this tenant
        ledger_repo = SqlAlchemyCreditLedgerRepository(db_session)
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = AllocateCredits(uow, ledger_repo, transaction_repo)

        command = AllocateCreditsCommandDTO(
            tenant_id="new_tenant_1",
            amount=Decimal("5000.000000"),
            idempotency_key="allocation:new_tenant_1:2024-01",
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.balance_before == Decimal("0")
        assert response.balance_after == Decimal("5000.000000")

        # Verify ledger was created
        ledger = await ledger_repo.get_by_tenant_id("new_tenant_1")
        assert ledger is not None
        assert ledger.balance == Decimal("5000.000000")

    async def test_idempotency_with_real_database(self, db_session: AsyncSession):
        """
        Test that same idempotency_key returns same transaction without creating duplicates
        """
        # Arrange - create ledger
        ledger = CreditLedger(
            tenant_id="tenant_alloc_2",
            balance=Decimal("1000.000000"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Arrange - setup use case
        ledger_repo = SqlAlchemyCreditLedgerRepository(db_session)
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = AllocateCredits(uow, ledger_repo, transaction_repo)

        command = AllocateCreditsCommandDTO(
            tenant_id="tenant_alloc_2",
            amount=Decimal("3000.000000"),
            idempotency_key="idempotency_alloc_test",
        )

        # Act - call twice with same idempotency key
        result1 = await use_case.execute(command)
        result2 = await use_case.execute(command)

        # Assert - both calls succeed
        assert result1.is_ok()
        assert result2.is_ok()

        # Assert - responses are identical
        assert result1.value.transaction_id == result2.value.transaction_id
        assert result1.value.balance_before == result2.value.balance_before
        assert result1.value.balance_after == result2.value.balance_after

        # Assert - only one transaction in database
        stmt = select(CreditTransaction).where(
            CreditTransaction.idempotency_key == "idempotency_alloc_test"
        )
        result = await db_session.execute(stmt)
        transactions = result.scalars().all()
        assert len(transactions) == 1

        # Assert - ledger balance only incremented once
        await db_session.refresh(ledger)
        assert ledger.balance == Decimal("4000.000000")

    async def test_multiple_allocations_for_same_tenant(self, db_session: AsyncSession):
        """
        Test multiple monthly allocations accumulate correctly
        """
        # Arrange - create ledger
        ledger = CreditLedger(
            tenant_id="tenant_alloc_3",
            balance=Decimal("0"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Arrange - setup use case
        ledger_repo = SqlAlchemyCreditLedgerRepository(db_session)
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = AllocateCredits(uow, ledger_repo, transaction_repo)

        # Act - allocate for multiple months
        months = ["2024-01", "2024-02", "2024-03"]
        results = []
        for month in months:
            command = AllocateCreditsCommandDTO(
                tenant_id="tenant_alloc_3",
                amount=Decimal("1000.000000"),
                idempotency_key=f"allocation:tenant_alloc_3:{month}",
            )
            result = await use_case.execute(command)
            results.append(result)

        # Assert - all succeed
        assert all(r.is_ok() for r in results)

        # Assert - balance accumulated correctly
        await db_session.refresh(ledger)
        assert ledger.balance == Decimal("3000.000000")

        # Assert - balance progression is correct
        assert results[0].value.balance_before == Decimal("0")
        assert results[0].value.balance_after == Decimal("1000.000000")

        assert results[1].value.balance_before == Decimal("1000.000000")
        assert results[1].value.balance_after == Decimal("2000.000000")

        assert results[2].value.balance_before == Decimal("2000.000000")
        assert results[2].value.balance_after == Decimal("3000.000000")
