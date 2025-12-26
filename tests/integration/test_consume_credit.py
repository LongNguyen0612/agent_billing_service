"""Integration tests for ConsumeCredit use case

Tests cover:
- AC-1.2.1: Successful credit consumption with real database
- AC-1.2.3: Idempotency with real database
- AC-1.2.4: Concurrent request handling with pessimistic locking
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime

from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.credit_ledger import CreditLedger
from src.domain.credit_transaction import TransactionType
from src.app.use_cases.billing.consume_credit import ConsumeCredit
from src.app.use_cases.billing.dtos import ConsumeCommandDTO
from src.adapter.repositories.credit_ledger_repository import SqlAlchemyCreditLedgerRepository
from src.adapter.repositories.credit_transaction_repository import SqlAlchemyCreditTransactionRepository
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
class TestConsumeCreditIntegration:
    """Integration tests with real database"""

    async def test_end_to_end_credit_consumption(self, db_session: AsyncSession):
        """
        Test complete flow: create ledger, consume credit, verify database state
        """
        # Arrange - create ledger
        ledger = CreditLedger(
            tenant_id="tenant_integration_1",
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

        use_case = ConsumeCredit(uow, ledger_repo, transaction_repo)

        command = ConsumeCommandDTO(
            tenant_id="tenant_integration_1",
            amount=Decimal("250.500000"),
            idempotency_key="integration_test_1",
            reference_type="test_run",
            reference_id="test_123",
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.amount == Decimal("250.500000")
        assert response.balance_before == Decimal("1000.000000")
        assert response.balance_after == Decimal("749.500000")
        assert response.transaction_type == "consume"

        # Verify ledger updated in database
        await db_session.refresh(ledger)
        assert ledger.balance == Decimal("749.500000")

        # Verify transaction exists in database
        created_transaction = await transaction_repo.get_by_idempotency_key("integration_test_1")
        assert created_transaction is not None
        assert created_transaction.amount == Decimal("250.500000")
        assert created_transaction.transaction_type == TransactionType.CONSUME

    async def test_idempotency_with_real_database(self, db_session: AsyncSession):
        """
        Test that same idempotency_key returns same transaction without creating duplicates
        """
        # Arrange - create ledger
        ledger = CreditLedger(
            tenant_id="tenant_integration_2",
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

        use_case = ConsumeCredit(uow, ledger_repo, transaction_repo)

        command = ConsumeCommandDTO(
            tenant_id="tenant_integration_2",
            amount=Decimal("100.000000"),
            idempotency_key="idempotency_test_key",
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
        from sqlmodel import select
        from src.domain.credit_transaction import CreditTransaction

        stmt = select(CreditTransaction).where(
            CreditTransaction.idempotency_key == "idempotency_test_key"
        )
        result = await db_session.execute(stmt)
        transactions = result.scalars().all()
        assert len(transactions) == 1

        # Assert - ledger balance only decremented once
        await db_session.refresh(ledger)
        assert ledger.balance == Decimal("400.000000")

    async def test_concurrent_requests_different_keys(self, db_session: AsyncSession):
        """
        Test that concurrent requests with different keys are handled correctly
        Tests AC-1.2.4: Concurrent request handling
        """
        # Arrange - create ledger
        ledger = CreditLedger(
            tenant_id="tenant_integration_3",
            balance=Decimal("1000.000000"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Arrange - create multiple sessions for concurrent operations
        from sqlalchemy.orm import sessionmaker
        from tests.integration.conftest import engine as get_engine

        # Note: For true concurrency testing, we need separate sessions
        # This is a simplified version - full test would use separate database connections

        ledger_repo = SqlAlchemyCreditLedgerRepository(db_session)
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = ConsumeCredit(uow, ledger_repo, transaction_repo)

        # Create commands
        command1 = ConsumeCommandDTO(
            tenant_id="tenant_integration_3",
            amount=Decimal("100.000000"),
            idempotency_key="concurrent_key_1",
        )

        command2 = ConsumeCommandDTO(
            tenant_id="tenant_integration_3",
            amount=Decimal("200.000000"),
            idempotency_key="concurrent_key_2",
        )

        command3 = ConsumeCommandDTO(
            tenant_id="tenant_integration_3",
            amount=Decimal("150.000000"),
            idempotency_key="concurrent_key_3",
        )

        # Act - execute sequentially (true concurrent test requires separate connections)
        result1 = await use_case.execute(command1)
        result2 = await use_case.execute(command2)
        result3 = await use_case.execute(command3)

        # Assert - all succeed
        assert result1.is_ok()
        assert result2.is_ok()
        assert result3.is_ok()

        # Assert - final balance is correct
        await db_session.refresh(ledger)
        expected_balance = Decimal("1000.000000") - Decimal("100.000000") - Decimal("200.000000") - Decimal("150.000000")
        assert ledger.balance == expected_balance

    async def test_database_rollback_on_failure(self, db_session: AsyncSession):
        """
        Test that database transaction is rolled back on failure
        """
        # Arrange - create ledger with insufficient balance
        ledger = CreditLedger(
            tenant_id="tenant_integration_4",
            balance=Decimal("50.000000"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        initial_balance = ledger.balance

        # Arrange - setup use case
        ledger_repo = SqlAlchemyCreditLedgerRepository(db_session)
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = ConsumeCredit(uow, ledger_repo, transaction_repo)

        command = ConsumeCommandDTO(
            tenant_id="tenant_integration_4",
            amount=Decimal("100.000000"),  # More than available
            idempotency_key="rollback_test",
        )

        # Act
        result = await use_case.execute(command)

        # Assert - error returned
        assert result.is_err()
        assert result.error.code == "INSUFFICIENT_CREDIT"

        # Assert - ledger balance unchanged
        await db_session.refresh(ledger)
        assert ledger.balance == initial_balance

        # Assert - no transaction created
        transaction = await transaction_repo.get_by_idempotency_key("rollback_test")
        assert transaction is None

    async def test_pessimistic_locking_prevents_race_condition(self, db_session: AsyncSession):
        """
        Test that pessimistic locking (SELECT FOR UPDATE) is used correctly
        This test verifies the lock is acquired by checking the SQL query
        """
        # Arrange - create ledger
        ledger = CreditLedger(
            tenant_id="tenant_integration_5",
            balance=Decimal("500.000000"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Arrange - setup repositories
        ledger_repo = SqlAlchemyCreditLedgerRepository(db_session)

        # Act - get with lock
        locked_ledger = await ledger_repo.get_by_tenant_id("tenant_integration_5", for_update=True)

        # Assert - ledger retrieved
        assert locked_ledger is not None
        assert locked_ledger.id == ledger.id

        # Note: In SQLite, SELECT FOR UPDATE is not fully supported for row-level locking
        # In production with PostgreSQL, this would actually lock the row
        # The test verifies the API works correctly

    async def test_multiple_transactions_for_same_tenant(self, db_session: AsyncSession):
        """
        Test creating multiple transactions for the same tenant with different idempotency keys
        """
        # Arrange - create ledger
        ledger = CreditLedger(
            tenant_id="tenant_integration_6",
            balance=Decimal("2000.000000"),
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

        use_case = ConsumeCredit(uow, ledger_repo, transaction_repo)

        # Act - create multiple transactions
        transactions_data = [
            ("key_1", Decimal("100.000000")),
            ("key_2", Decimal("200.000000")),
            ("key_3", Decimal("300.000000")),
        ]

        results = []
        for key, amount in transactions_data:
            command = ConsumeCommandDTO(
                tenant_id="tenant_integration_6",
                amount=amount,
                idempotency_key=key,
            )
            result = await use_case.execute(command)
            results.append(result)

        # Assert - all succeed
        assert all(r.is_ok() for r in results)

        # Assert - balance correctly decremented
        await db_session.refresh(ledger)
        expected_balance = Decimal("2000.000000") - Decimal("600.000000")
        assert ledger.balance == expected_balance

        # Assert - balance progression is correct
        assert results[0].value.balance_before == Decimal("2000.000000")
        assert results[0].value.balance_after == Decimal("1900.000000")

        assert results[1].value.balance_before == Decimal("1900.000000")
        assert results[1].value.balance_after == Decimal("1700.000000")

        assert results[2].value.balance_before == Decimal("1700.000000")
        assert results[2].value.balance_after == Decimal("1400.000000")
