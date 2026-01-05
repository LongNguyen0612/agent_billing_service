"""Integration tests for ListTransactions use case (UC-36)"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from src.app.use_cases.billing.list_transactions import ListTransactions
from src.adapter.repositories.credit_transaction_repository import (
    SqlAlchemyCreditTransactionRepository,
)
from src.domain.credit_ledger import CreditLedger
from src.domain.credit_transaction import CreditTransaction, TransactionType


class TestListTransactionsIntegration:
    """Integration test suite for ListTransactions use case with real database"""

    @pytest.mark.asyncio
    async def test_end_to_end_transaction_listing(self, db_session):
        """Test AC-2.2.1: End-to-end transaction list retrieval with real database"""
        # Arrange
        tenant_id = "tenant_list_test_001"
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

        # Create transactions with different timestamps
        base_time = datetime(2024, 1, 15, 12, 0, 0)
        transactions = [
            CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.ALLOCATE,
                amount=Decimal("1000.00"),
                balance_before=Decimal("0.00"),
                balance_after=Decimal("1000.00"),
                reference_type="subscription",
                reference_id="sub_001",
                idempotency_key=f"{tenant_id}:allocate:001",
                created_at=base_time,
            ),
            CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-50.00"),
                balance_before=Decimal("1000.00"),
                balance_after=Decimal("950.00"),
                reference_type="pipeline_run",
                reference_id="run_001",
                idempotency_key=f"{tenant_id}:consume:001",
                created_at=base_time + timedelta(hours=1),
            ),
            CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-30.50"),
                balance_before=Decimal("950.00"),
                balance_after=Decimal("919.50"),
                reference_type="pipeline_run",
                reference_id="run_002",
                idempotency_key=f"{tenant_id}:consume:002",
                created_at=base_time + timedelta(hours=2),
            ),
        ]

        for txn in transactions:
            db_session.add(txn)
        await db_session.commit()

        # Create repository and use case
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.total == 3
        assert len(response.transactions) == 3

        # Verify ordered by created_at DESC (most recent first)
        assert response.transactions[0].reference_id == "run_002"
        assert response.transactions[1].reference_id == "run_001"
        assert response.transactions[2].reference_id == "sub_001"

        # Verify transaction data
        first_txn = response.transactions[0]
        assert first_txn.transaction_type == "consume"
        assert first_txn.amount == Decimal("-30.50")
        assert first_txn.balance_after == Decimal("919.50")

    @pytest.mark.asyncio
    async def test_empty_transaction_list(self, db_session):
        """Test AC-2.2.1: Empty list when tenant has no transactions"""
        # Arrange
        tenant_id = "tenant_no_transactions"

        # Create repository and use case without any transactions
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.total == 0
        assert len(response.transactions) == 0
        assert response.limit == 20
        assert response.offset == 0

    @pytest.mark.asyncio
    async def test_pagination_limit(self, db_session):
        """Test AC-2.2.2: Pagination with custom limit"""
        # Arrange
        tenant_id = "tenant_pagination_limit"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create 10 transactions
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        for i in range(10):
            txn = CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_before=Decimal(f"{1000 - i * 10}.00"),
                balance_after=Decimal(f"{990 - i * 10}.00"),
                reference_type="pipeline_run",
                reference_id=f"run_{i:03d}",
                idempotency_key=f"{tenant_id}:consume:{i:03d}",
                created_at=base_time + timedelta(hours=i),
            )
            db_session.add(txn)
        await db_session.commit()

        # Create repository and use case
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act - Request only 5 transactions
        result = await use_case.execute(tenant_id, limit=5)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.total == 10  # Total count is 10
        assert len(response.transactions) == 5  # But only 5 returned
        assert response.limit == 5
        assert response.offset == 0

        # Verify we got the 5 most recent (highest hours)
        assert response.transactions[0].reference_id == "run_009"
        assert response.transactions[4].reference_id == "run_005"

    @pytest.mark.asyncio
    async def test_pagination_offset(self, db_session):
        """Test AC-2.2.2: Pagination with offset"""
        # Arrange
        tenant_id = "tenant_pagination_offset"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create 10 transactions
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        for i in range(10):
            txn = CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_before=Decimal(f"{1000 - i * 10}.00"),
                balance_after=Decimal(f"{990 - i * 10}.00"),
                reference_type="pipeline_run",
                reference_id=f"run_{i:03d}",
                idempotency_key=f"{tenant_id}:consume:{i:03d}",
                created_at=base_time + timedelta(hours=i),
            )
            db_session.add(txn)
        await db_session.commit()

        # Create repository and use case
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act - Skip first 5 transactions
        result = await use_case.execute(tenant_id, limit=20, offset=5)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.total == 10
        assert len(response.transactions) == 5  # Only 5 remaining after offset
        assert response.limit == 20
        assert response.offset == 5

        # Verify we got transactions 5-9 (older ones)
        assert response.transactions[0].reference_id == "run_004"
        assert response.transactions[4].reference_id == "run_000"

    @pytest.mark.asyncio
    async def test_pagination_limit_and_offset(self, db_session):
        """Test AC-2.2.2: Pagination with both limit and offset"""
        # Arrange
        tenant_id = "tenant_pagination_both"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create 20 transactions
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        for i in range(20):
            txn = CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-5.00"),
                balance_before=Decimal(f"{1000 - i * 5}.00"),
                balance_after=Decimal(f"{995 - i * 5}.00"),
                reference_type="pipeline_run",
                reference_id=f"run_{i:03d}",
                idempotency_key=f"{tenant_id}:consume:{i:03d}",
                created_at=base_time + timedelta(hours=i),
            )
            db_session.add(txn)
        await db_session.commit()

        # Create repository and use case
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act - Get page 2 (offset 5, limit 5)
        result = await use_case.execute(tenant_id, limit=5, offset=5)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.total == 20
        assert len(response.transactions) == 5
        assert response.limit == 5
        assert response.offset == 5

        # Verify we got transactions 14-10 (sorted DESC by created_at)
        assert response.transactions[0].reference_id == "run_014"
        assert response.transactions[4].reference_id == "run_010"

    @pytest.mark.asyncio
    async def test_transactions_ordered_by_created_at_desc(self, db_session):
        """Test AC-2.2.1: Transactions are ordered by created_at DESC"""
        # Arrange
        tenant_id = "tenant_order_test"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("100.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create transactions in non-sequential order
        times = [
            datetime(2024, 1, 15, 10, 0, 0),  # Middle
            datetime(2024, 1, 15, 8, 0, 0),  # Oldest
            datetime(2024, 1, 15, 14, 0, 0),  # Newest
        ]

        for i, created_at in enumerate(times):
            txn = CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_before=Decimal(f"{100 - i * 10}.00"),
                balance_after=Decimal(f"{90 - i * 10}.00"),
                reference_type="pipeline_run",
                reference_id=f"run_{i}",
                idempotency_key=f"{tenant_id}:consume:{i}",
                created_at=created_at,
            )
            db_session.add(txn)
        await db_session.commit()

        # Create repository and use case
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 3

        # Verify DESC order by created_at
        assert response.transactions[0].created_at == datetime(2024, 1, 15, 14, 0, 0)
        assert response.transactions[1].created_at == datetime(2024, 1, 15, 10, 0, 0)
        assert response.transactions[2].created_at == datetime(2024, 1, 15, 8, 0, 0)

    @pytest.mark.asyncio
    async def test_different_transaction_types(self, db_session):
        """Test listing transactions with different types"""
        # Arrange
        tenant_id = "tenant_multi_type"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        base_time = datetime(2024, 1, 1, 0, 0, 0)

        # Create different transaction types
        txn_data = [
            (TransactionType.ALLOCATE, Decimal("1000.00"), "subscription", "sub_001"),
            (TransactionType.CONSUME, Decimal("-100.00"), "pipeline_run", "run_001"),
            (TransactionType.REFUND, Decimal("50.00"), "failed_step", "step_001"),
            (TransactionType.ADJUST, Decimal("-25.00"), None, None),
        ]

        for i, (txn_type, amount, ref_type, ref_id) in enumerate(txn_data):
            txn = CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=txn_type,
                amount=amount,
                balance_before=Decimal("100.00"),
                balance_after=Decimal("100.00") + amount,
                reference_type=ref_type,
                reference_id=ref_id,
                idempotency_key=f"{tenant_id}:{txn_type.value}:{i}",
                created_at=base_time + timedelta(hours=i),
            )
            db_session.add(txn)
        await db_session.commit()

        # Create repository and use case
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert len(response.transactions) == 4

        # Verify transaction types (DESC order - adjust is most recent)
        assert response.transactions[0].transaction_type == "adjust"
        assert response.transactions[1].transaction_type == "refund"
        assert response.transactions[2].transaction_type == "consume"
        assert response.transactions[3].transaction_type == "allocate"

    @pytest.mark.asyncio
    async def test_transactions_isolated_by_tenant(self, db_session):
        """Test that transactions are isolated by tenant"""
        # Arrange
        tenant_a = "tenant_isolated_a"
        tenant_b = "tenant_isolated_b"

        # Create ledgers for both tenants
        ledger_a = CreditLedger(
            tenant_id=tenant_a,
            balance=Decimal("500.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        ledger_b = CreditLedger(
            tenant_id=tenant_b,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger_a)
        db_session.add(ledger_b)
        await db_session.commit()
        await db_session.refresh(ledger_a)
        await db_session.refresh(ledger_b)

        # Create transactions for tenant A
        for i in range(3):
            txn = CreditTransaction(
                tenant_id=tenant_a,
                ledger_id=ledger_a.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_before=Decimal("500.00"),
                balance_after=Decimal("490.00"),
                reference_type="pipeline_run",
                reference_id=f"run_a_{i}",
                idempotency_key=f"{tenant_a}:consume:{i}",
                created_at=datetime.now(),
            )
            db_session.add(txn)

        # Create transactions for tenant B
        for i in range(5):
            txn = CreditTransaction(
                tenant_id=tenant_b,
                ledger_id=ledger_b.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-20.00"),
                balance_before=Decimal("1000.00"),
                balance_after=Decimal("980.00"),
                reference_type="pipeline_run",
                reference_id=f"run_b_{i}",
                idempotency_key=f"{tenant_b}:consume:{i}",
                created_at=datetime.now(),
            )
            db_session.add(txn)
        await db_session.commit()

        # Create repository and use case
        transaction_repo = SqlAlchemyCreditTransactionRepository(db_session)
        use_case = ListTransactions(transaction_repo)

        # Act - Get transactions for tenant A
        result_a = await use_case.execute(tenant_a)

        # Assert - Only tenant A's transactions
        assert result_a.is_ok()
        response_a = result_a.value
        assert response_a.total == 3
        assert len(response_a.transactions) == 3
        for txn in response_a.transactions:
            assert "run_a_" in txn.reference_id

        # Act - Get transactions for tenant B
        result_b = await use_case.execute(tenant_b)

        # Assert - Only tenant B's transactions
        assert result_b.is_ok()
        response_b = result_b.value
        assert response_b.total == 5
        assert len(response_b.transactions) == 5
        for txn in response_b.transactions:
            assert "run_b_" in txn.reference_id


class TestListTransactionsAPIIntegration:
    """Integration tests for the /billing/credits/transactions endpoint"""

    @pytest.mark.asyncio
    async def test_api_list_transactions(self, client, db_session):
        """Test GET /billing/credits/transactions endpoint"""
        # Arrange
        tenant_id = "tenant_api_list"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("500.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create transactions
        base_time = datetime(2024, 1, 15, 12, 0, 0)
        txn1 = CreditTransaction(
            tenant_id=tenant_id,
            ledger_id=ledger.id,
            transaction_type=TransactionType.CONSUME,
            amount=Decimal("-15.50"),
            balance_before=Decimal("515.50"),
            balance_after=Decimal("500.00"),
            reference_type="pipeline_run",
            reference_id="run_uuid_001",
            idempotency_key=f"{tenant_id}:consume:001",
            created_at=base_time,
        )
        txn2 = CreditTransaction(
            tenant_id=tenant_id,
            ledger_id=ledger.id,
            transaction_type=TransactionType.ALLOCATE,
            amount=Decimal("515.50"),
            balance_before=Decimal("0.00"),
            balance_after=Decimal("515.50"),
            reference_type="subscription",
            reference_id="sub_001",
            idempotency_key=f"{tenant_id}:allocate:001",
            created_at=base_time - timedelta(days=1),
        )
        db_session.add(txn1)
        db_session.add(txn2)
        await db_session.commit()

        # Act
        response = await client.get(
            f"/billing/credits/transactions?tenant_id={tenant_id}"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["transactions"]) == 2
        assert data["limit"] == 20
        assert data["offset"] == 0

        # Verify transaction data (most recent first)
        first_txn = data["transactions"][0]
        assert first_txn["transaction_type"] == "consume"
        assert Decimal(first_txn["amount"]) == Decimal("-15.50")
        assert Decimal(first_txn["balance_after"]) == Decimal("500.00")
        assert first_txn["reference_type"] == "pipeline_run"
        assert first_txn["reference_id"] == "run_uuid_001"

    @pytest.mark.asyncio
    async def test_api_list_transactions_with_pagination(self, client, db_session):
        """Test GET /billing/credits/transactions with pagination parameters"""
        # Arrange
        tenant_id = "tenant_api_pagination"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create 15 transactions
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        for i in range(15):
            txn = CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-10.00"),
                balance_before=Decimal("1000.00"),
                balance_after=Decimal("990.00"),
                reference_type="pipeline_run",
                reference_id=f"run_{i:03d}",
                idempotency_key=f"{tenant_id}:consume:{i:03d}",
                created_at=base_time + timedelta(hours=i),
            )
            db_session.add(txn)
        await db_session.commit()

        # Act - Request with custom limit and offset
        response = await client.get(
            f"/billing/credits/transactions?tenant_id={tenant_id}&limit=5&offset=5"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 15
        assert len(data["transactions"]) == 5
        assert data["limit"] == 5
        assert data["offset"] == 5

        # Verify we got the correct page (transactions 9-5 in DESC order)
        assert data["transactions"][0]["reference_id"] == "run_009"
        assert data["transactions"][4]["reference_id"] == "run_005"

    @pytest.mark.asyncio
    async def test_api_list_transactions_empty(self, client, db_session):
        """Test GET /billing/credits/transactions with no transactions"""
        # Arrange
        tenant_id = "tenant_api_empty"

        # Act
        response = await client.get(
            f"/billing/credits/transactions?tenant_id={tenant_id}"
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["transactions"]) == 0
        assert data["limit"] == 20
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_api_list_transactions_default_pagination(self, client, db_session):
        """Test GET /billing/credits/transactions uses default pagination"""
        # Arrange
        tenant_id = "tenant_api_defaults"

        # Create ledger
        ledger = CreditLedger(
            tenant_id=tenant_id,
            balance=Decimal("1000.00"),
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db_session.add(ledger)
        await db_session.commit()
        await db_session.refresh(ledger)

        # Create 25 transactions
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        for i in range(25):
            txn = CreditTransaction(
                tenant_id=tenant_id,
                ledger_id=ledger.id,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("-5.00"),
                balance_before=Decimal("1000.00"),
                balance_after=Decimal("995.00"),
                reference_type="pipeline_run",
                reference_id=f"run_{i:03d}",
                idempotency_key=f"{tenant_id}:consume:{i:03d}",
                created_at=base_time + timedelta(hours=i),
            )
            db_session.add(txn)
        await db_session.commit()

        # Act - No pagination parameters
        response = await client.get(
            f"/billing/credits/transactions?tenant_id={tenant_id}"
        )

        # Assert - Default limit is 20
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert len(data["transactions"]) == 20  # Default limit
        assert data["limit"] == 20
        assert data["offset"] == 0
