"""Integration tests for GetBalance use case"""

import pytest
from datetime import datetime
from decimal import Decimal

from src.app.use_cases.billing.get_balance import GetBalance
from src.adapter.repositories.credit_ledger_repository import CreditLedgerRepository
from src.domain.credit_ledger import CreditLedger
from src.domain.credit_transaction import CreditTransaction


class TestGetBalanceIntegration:
    """Integration test suite for GetBalance use case with real database"""

    @pytest.mark.asyncio
    async def test_end_to_end_balance_retrieval(self, db_session):
        """Test AC-1.4.1: End-to-end balance retrieval with real database"""
        # Arrange
        tenant_id = "tenant_test_123"
        initial_balance = Decimal("1500.75")

        # Create credit ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=initial_balance,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create repository and use case
        ledger_repo = CreditLedgerRepository(db_session)
        use_case = GetBalance(ledger_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.tenant_id == tenant_id
        assert response.balance == initial_balance
        assert isinstance(response.last_updated, datetime)

    @pytest.mark.asyncio
    async def test_balance_reflects_recent_transactions(self, db_session):
        """Test AC-1.4.4: Balance reflects recent transactions"""
        # Arrange
        tenant_id = "tenant_test_456"
        initial_balance = Decimal("1000.00")

        # Create credit ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=initial_balance,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create transactions
        transaction1 = CreditTransaction(
            tenant_id=tenant_id,
            ledger_id=ledger.id,
            transaction_type="consume",
            amount=Decimal("50.00"),
            balance_before=initial_balance,
            balance_after=Decimal("950.00"),
            idempotency_key="test_key_1",
            created_at=datetime.now(),
        )
        db_session.add(transaction1)

        # Update ledger balance
        ledger.balance = Decimal("950.00")
        ledger.updated_at = datetime.now()
        db_session.add(ledger)
        await db_session.commit()

        # Create repository and use case
        ledger_repo = CreditLedgerRepository(db_session)
        use_case = GetBalance(ledger_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.balance == Decimal("950.00")

    @pytest.mark.asyncio
    async def test_tenant_not_found_real_db(self, db_session):
        """Test AC-1.4.2: Tenant not found with real database"""
        # Arrange
        tenant_id = "nonexistent_tenant"
        ledger_repo = CreditLedgerRepository(db_session)
        use_case = GetBalance(ledger_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "LEDGER_NOT_FOUND"
        assert tenant_id in error.message

    @pytest.mark.asyncio
    async def test_concurrent_reads_do_not_block(self, db_session):
        """Test AC-1.4.5: Concurrent reads do not block each other"""
        # Arrange
        tenant_id = "tenant_concurrent"
        initial_balance = Decimal("5000.00")

        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=initial_balance,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        ledger_repo = CreditLedgerRepository(db_session)
        use_case = GetBalance(ledger_repo)

        # Act - Execute multiple concurrent reads
        import asyncio

        results = await asyncio.gather(
            use_case.execute(tenant_id),
            use_case.execute(tenant_id),
            use_case.execute(tenant_id),
        )

        # Assert - All reads should succeed
        for result in results:
            assert result.is_ok()
            assert result.value.balance == initial_balance

    @pytest.mark.asyncio
    async def test_zero_balance_retrieval(self, db_session):
        """Test retrieving zero balance"""
        # Arrange
        tenant_id = "tenant_zero"
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("0.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        ledger_repo = CreditLedgerRepository(db_session)
        use_case = GetBalance(ledger_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        assert result.value.balance == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_large_balance_retrieval(self, db_session):
        """Test retrieving large balance values"""
        # Arrange
        tenant_id = "tenant_large"
        large_balance = Decimal("999999999.999999")

        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=large_balance,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()

        ledger_repo = CreditLedgerRepository(db_session)
        use_case = GetBalance(ledger_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        assert result.value.balance == large_balance
