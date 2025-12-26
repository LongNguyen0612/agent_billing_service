"""Unit tests for ConsumeCredit use case

Tests cover:
- AC-1.2.1: Successful credit consumption
- AC-1.2.2: Insufficient credits
- AC-1.2.3: Idempotency guarantee
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.app.use_cases.billing.consume_credit import ConsumeCredit
from src.app.use_cases.billing.dtos import ConsumeCommandDTO
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
def consume_use_case(mock_uow, mock_ledger_repo, mock_transaction_repo):
    """ConsumeCredit use case instance with mocked dependencies"""
    return ConsumeCredit(
        uow=mock_uow,
        ledger_repo=mock_ledger_repo,
        transaction_repo=mock_transaction_repo,
    )


@pytest.fixture
def sample_command():
    """Sample ConsumeCommandDTO"""
    return ConsumeCommandDTO(
        tenant_id="tenant_123",
        amount=Decimal("50.000000"),
        idempotency_key="pipeline_456:step_789",
        reference_type="pipeline_run",
        reference_id="run_456",
    )


@pytest.fixture
def sample_ledger():
    """Sample credit ledger with sufficient balance"""
    return CreditLedger(
        id=1,
        tenant_id="tenant_123",
        balance=Decimal("1000.000000"),
        monthly_limit=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
class TestConsumeCreditSuccess:
    """Test successful credit consumption (AC-1.2.1)"""

    async def test_consume_credit_with_sufficient_balance(
        self, consume_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command, sample_ledger
    ):
        """
        Given: Tenant has sufficient credits (balance >= amount)
        When: consume_credit is called with valid idempotency_key
        Then: Transaction created, balance decremented, response includes snapshots
        """
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=sample_ledger)
        mock_transaction_repo.create = AsyncMock(
            return_value=CreditTransaction(
                id=123,
                tenant_id="tenant_123",
                ledger_id=1,
                transaction_type=TransactionType.CONSUME,
                amount=Decimal("50.000000"),
                balance_before=Decimal("1000.000000"),
                balance_after=Decimal("950.000000"),
                reference_type="pipeline_run",
                reference_id="run_456",
                idempotency_key="pipeline_456:step_789",
                created_at=datetime.utcnow(),
            )
        )
        mock_ledger_repo.update_balance = AsyncMock()

        # Act
        result = await consume_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response data
        assert response.transaction_id == 123
        assert response.tenant_id == "tenant_123"
        assert response.transaction_type == "consume"
        assert response.amount == Decimal("50.000000")
        assert response.balance_before == Decimal("1000.000000")
        assert response.balance_after == Decimal("950.000000")
        assert response.idempotency_key == "pipeline_456:step_789"

        # Verify repository interactions
        mock_transaction_repo.get_by_idempotency_key.assert_called_once_with("pipeline_456:step_789")
        mock_ledger_repo.get_by_tenant_id.assert_called_once_with("tenant_123", for_update=True)
        mock_transaction_repo.create.assert_called_once()
        mock_ledger_repo.update_balance.assert_called_once_with(1, Decimal("950.000000"))
        mock_uow.commit.assert_called_once()

    async def test_balance_calculation_accuracy(
        self, consume_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow
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

        command = ConsumeCommandDTO(
            tenant_id="tenant_123",
            amount=Decimal("30.500000"),
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
        result = await consume_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert created_transaction.balance_before == Decimal("100.123456")
        assert created_transaction.balance_after == Decimal("69.623456")
        mock_ledger_repo.update_balance.assert_called_once_with(1, Decimal("69.623456"))

    async def test_metadata_is_stored_correctly(
        self, consume_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_ledger
    ):
        """Test that reference_type and reference_id are stored correctly"""
        # Arrange
        command = ConsumeCommandDTO(
            tenant_id="tenant_123",
            amount=Decimal("10.000000"),
            idempotency_key="test_key",
            reference_type="custom_event",
            reference_id="event_999",
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=sample_ledger)

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
        result = await consume_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert created_transaction.reference_type == "custom_event"
        assert created_transaction.reference_id == "event_999"


@pytest.mark.asyncio
class TestConsumeCreditInsufficientBalance:
    """Test insufficient credits scenario (AC-1.2.2)"""

    async def test_insufficient_credits_error(
        self, consume_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow
    ):
        """
        Given: Tenant has insufficient credits (balance < amount)
        When: consume_credit is called
        Then: No transaction created, balance unchanged, error returned
        """
        # Arrange
        ledger = CreditLedger(
            id=1,
            tenant_id="tenant_123",
            balance=Decimal("30.000000"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        command = ConsumeCommandDTO(
            tenant_id="tenant_123",
            amount=Decimal("50.000000"),
            idempotency_key="test_key",
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=ledger)

        # Act
        result = await consume_use_case.execute(command)

        # Assert
        assert result.is_err()
        error = result.error

        assert error.code == "INSUFFICIENT_CREDIT"
        assert "30.000000" in error.message  # Current balance mentioned
        assert "50.000000" in error.message  # Required amount mentioned

        # Verify no transaction created
        mock_transaction_repo.create.assert_not_called()
        mock_ledger_repo.update_balance.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_ledger_not_found_error(
        self, consume_use_case, mock_ledger_repo, mock_transaction_repo, sample_command
    ):
        """
        Given: Ledger does not exist for tenant
        When: consume_credit is called
        Then: Error returned with appropriate message
        """
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=None)

        # Act
        result = await consume_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        error = result.error

        assert error.code == "LEDGER_NOT_FOUND"
        assert "tenant_123" in error.message


@pytest.mark.asyncio
class TestConsumeCreditIdempotency:
    """Test idempotency guarantee (AC-1.2.3)"""

    async def test_idempotency_returns_existing_transaction(
        self, consume_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command
    ):
        """
        Given: Same idempotency_key is used multiple times
        When: consume_credit is called repeatedly
        Then: First call creates transaction, subsequent calls return same transaction
        """
        # Arrange - existing transaction
        existing_transaction = CreditTransaction(
            id=999,
            tenant_id="tenant_123",
            ledger_id=1,
            transaction_type=TransactionType.CONSUME,
            amount=Decimal("50.000000"),
            balance_before=Decimal("1000.000000"),
            balance_after=Decimal("950.000000"),
            reference_type="pipeline_run",
            reference_id="run_456",
            idempotency_key="pipeline_456:step_789",
            created_at=datetime.utcnow(),
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=existing_transaction)

        # Act
        result = await consume_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response matches existing transaction
        assert response.transaction_id == 999
        assert response.balance_before == Decimal("1000.000000")
        assert response.balance_after == Decimal("950.000000")

        # Verify no new transaction created
        mock_ledger_repo.get_by_tenant_id.assert_not_called()
        mock_transaction_repo.create.assert_not_called()
        mock_ledger_repo.update_balance.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_response_identical_across_idempotent_calls(
        self, consume_use_case, mock_transaction_repo, sample_command
    ):
        """Test that idempotent responses are byte-for-byte identical"""
        # Arrange
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        existing_transaction = CreditTransaction(
            id=123,
            tenant_id="tenant_123",
            ledger_id=1,
            transaction_type=TransactionType.CONSUME,
            amount=Decimal("50.000000"),
            balance_before=Decimal("1000.000000"),
            balance_after=Decimal("950.000000"),
            reference_type="pipeline_run",
            reference_id="run_456",
            idempotency_key="pipeline_456:step_789",
            created_at=created_at,
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=existing_transaction)

        # Act - call twice
        result1 = await consume_use_case.execute(sample_command)
        result2 = await consume_use_case.execute(sample_command)

        # Assert - responses are identical
        assert result1.is_ok() and result2.is_ok()
        resp1 = result1.value
        resp2 = result2.value

        assert resp1.transaction_id == resp2.transaction_id
        assert resp1.amount == resp2.amount
        assert resp1.balance_before == resp2.balance_before
        assert resp1.balance_after == resp2.balance_after
        assert resp1.created_at == resp2.created_at
        assert resp1.idempotency_key == resp2.idempotency_key


@pytest.mark.asyncio
class TestConsumeCreditErrorHandling:
    """Test error handling and rollback"""

    async def test_rollback_on_exception(
        self, consume_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command, sample_ledger
    ):
        """Test that UoW rollback is called on exception"""
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=sample_ledger)
        mock_transaction_repo.create = AsyncMock(side_effect=Exception("Database error"))

        # Act
        result = await consume_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        mock_uow.rollback.assert_called_once()
        assert result.error.code == "CONSUME_CREDIT_FAILED"
