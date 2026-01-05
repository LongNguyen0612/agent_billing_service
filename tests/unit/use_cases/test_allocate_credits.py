"""Unit tests for AllocateCredits use case (UC-38)

Tests cover:
- AC-3.4.1: Monthly allocation based on subscription
- Successful credit allocation
- Idempotency guarantee
- Ledger creation for new tenants
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.app.use_cases.billing.allocate_credits import AllocateCredits
from src.app.use_cases.billing.dtos import AllocateCreditsCommandDTO
from src.domain.credit_ledger import CreditLedger
from src.domain.credit_transaction import CreditTransaction, TransactionType


@pytest.fixture
def mock_ledger_repo():
    """Mock credit ledger repository"""
    return MagicMock()


@pytest.fixture
def mock_transaction_repo():
    """Mock credit transaction repository"""
    return MagicMock()


@pytest.fixture
def allocate_use_case(mock_uow, mock_ledger_repo, mock_transaction_repo):
    """AllocateCredits use case instance with mocked dependencies"""
    return AllocateCredits(
        uow=mock_uow,
        ledger_repo=mock_ledger_repo,
        transaction_repo=mock_transaction_repo,
    )


@pytest.fixture
def sample_command():
    """Sample AllocateCreditsCommandDTO"""
    return AllocateCreditsCommandDTO(
        tenant_id="tenant_123",
        amount=Decimal("10000.000000"),
        idempotency_key="allocation:tenant_123:2024-01",
        reference_type="subscription",
        reference_id="sub_456",
    )


@pytest.fixture
def sample_ledger():
    """Sample credit ledger with existing balance"""
    return CreditLedger(
        id=1,
        tenant_id="tenant_123",
        balance=Decimal("500.000000"),
        monthly_limit=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
class TestAllocateCreditsSuccess:
    """Test successful credit allocation (AC-3.4.1)"""

    async def test_allocate_credits_to_existing_ledger(
        self, allocate_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command, sample_ledger
    ):
        """
        Given: Tenant has existing ledger with balance
        When: allocate_credits is called
        Then: Credits added to balance, transaction created
        """
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=sample_ledger)
        mock_transaction_repo.create = AsyncMock(
            return_value=CreditTransaction(
                id=123,
                tenant_id="tenant_123",
                ledger_id=1,
                transaction_type=TransactionType.ALLOCATE,
                amount=Decimal("10000.000000"),
                balance_before=Decimal("500.000000"),
                balance_after=Decimal("10500.000000"),
                reference_type="subscription",
                reference_id="sub_456",
                idempotency_key="allocation:tenant_123:2024-01",
                created_at=datetime.utcnow(),
            )
        )
        mock_ledger_repo.update_balance = AsyncMock()

        # Act
        result = await allocate_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response data
        assert response.transaction_id == 123
        assert response.tenant_id == "tenant_123"
        assert response.amount == Decimal("10000.000000")
        assert response.balance_before == Decimal("500.000000")
        assert response.balance_after == Decimal("10500.000000")
        assert response.idempotency_key == "allocation:tenant_123:2024-01"

        # Verify repository interactions
        mock_transaction_repo.get_by_idempotency_key.assert_called_once_with("allocation:tenant_123:2024-01")
        mock_ledger_repo.get_by_tenant_id.assert_called_once_with("tenant_123", for_update=True)
        mock_transaction_repo.create.assert_called_once()
        mock_ledger_repo.update_balance.assert_called_once_with(1, Decimal("10500.000000"))
        mock_uow.commit.assert_called_once()

    async def test_allocate_credits_creates_ledger_for_new_tenant(
        self, allocate_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command
    ):
        """
        Given: Tenant has no existing ledger
        When: allocate_credits is called
        Then: New ledger created, credits allocated
        """
        # Arrange
        new_ledger = CreditLedger(
            id=99,
            tenant_id="tenant_123",
            balance=Decimal("0"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        # First call returns None, second call (after create) returns the new ledger
        mock_ledger_repo.get_by_tenant_id = AsyncMock(side_effect=[None, new_ledger])
        mock_ledger_repo.create = AsyncMock(return_value=new_ledger)
        mock_transaction_repo.create = AsyncMock(
            return_value=CreditTransaction(
                id=123,
                tenant_id="tenant_123",
                ledger_id=99,
                transaction_type=TransactionType.ALLOCATE,
                amount=Decimal("10000.000000"),
                balance_before=Decimal("0"),
                balance_after=Decimal("10000.000000"),
                reference_type="subscription",
                reference_id="sub_456",
                idempotency_key="allocation:tenant_123:2024-01",
                created_at=datetime.utcnow(),
            )
        )
        mock_ledger_repo.update_balance = AsyncMock()

        # Act
        result = await allocate_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.balance_before == Decimal("0")
        assert response.balance_after == Decimal("10000.000000")

        # Verify ledger was created
        mock_ledger_repo.create.assert_called_once()

    async def test_balance_calculation_accuracy(
        self, allocate_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow
    ):
        """Test that balance calculations are accurate with various amounts"""
        # Arrange
        ledger = CreditLedger(
            id=1,
            tenant_id="tenant_123",
            balance=Decimal("100.123456"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        command = AllocateCreditsCommandDTO(
            tenant_id="tenant_123",
            amount=Decimal("5000.500000"),
            idempotency_key="test_key",
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=ledger)

        created_transaction = None
        async def capture_transaction(transaction):
            nonlocal created_transaction
            created_transaction = transaction
            created_transaction.id = 1
            created_transaction.created_at = datetime.utcnow()
            return created_transaction

        mock_transaction_repo.create = AsyncMock(side_effect=capture_transaction)
        mock_ledger_repo.update_balance = AsyncMock()

        # Act
        result = await allocate_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert created_transaction.balance_before == Decimal("100.123456")
        assert created_transaction.balance_after == Decimal("5100.623456")
        mock_ledger_repo.update_balance.assert_called_once_with(1, Decimal("5100.623456"))


@pytest.mark.asyncio
class TestAllocateCreditsIdempotency:
    """Test idempotency guarantee"""

    async def test_idempotency_returns_existing_transaction(
        self, allocate_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command
    ):
        """
        Given: Same idempotency_key is used multiple times
        When: allocate_credits is called repeatedly
        Then: First call creates transaction, subsequent calls return same transaction
        """
        # Arrange - existing transaction
        existing_transaction = CreditTransaction(
            id=999,
            tenant_id="tenant_123",
            ledger_id=1,
            transaction_type=TransactionType.ALLOCATE,
            amount=Decimal("10000.000000"),
            balance_before=Decimal("500.000000"),
            balance_after=Decimal("10500.000000"),
            reference_type="subscription",
            reference_id="sub_456",
            idempotency_key="allocation:tenant_123:2024-01",
            created_at=datetime.utcnow(),
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=existing_transaction)

        # Act
        result = await allocate_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response matches existing transaction
        assert response.transaction_id == 999
        assert response.balance_before == Decimal("500.000000")
        assert response.balance_after == Decimal("10500.000000")

        # Verify no new transaction created
        mock_ledger_repo.get_by_tenant_id.assert_not_called()
        mock_transaction_repo.create.assert_not_called()
        mock_ledger_repo.update_balance.assert_not_called()
        mock_uow.commit.assert_not_called()


@pytest.mark.asyncio
class TestAllocateCreditsErrorHandling:
    """Test error handling and rollback"""

    async def test_rollback_on_exception(
        self, allocate_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command, sample_ledger
    ):
        """Test that UoW rollback is called on exception"""
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=sample_ledger)
        mock_transaction_repo.create = AsyncMock(side_effect=Exception("Database error"))

        # Act
        result = await allocate_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        mock_uow.rollback.assert_called_once()
        assert result.error.code == "ALLOCATE_CREDIT_FAILED"
