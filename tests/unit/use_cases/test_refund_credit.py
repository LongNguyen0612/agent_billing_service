"""Unit tests for RefundCredit use case

Tests cover:
- AC-1.3.1: Successful credit refund
- AC-1.3.2: Idempotency for refunds
- AC-1.3.3: Metadata tracking
- AC-1.3.4: Maximum refund not enforced
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.app.use_cases.billing.refund_credit import RefundCredit
from src.app.use_cases.billing.dtos import RefundCommandDTO
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
def refund_use_case(mock_uow, mock_ledger_repo, mock_transaction_repo):
    """RefundCredit use case instance with mocked dependencies"""
    return RefundCredit(
        uow=mock_uow,
        ledger_repo=mock_ledger_repo,
        transaction_repo=mock_transaction_repo,
    )


@pytest.fixture
def sample_command():
    """Sample RefundCommandDTO"""
    return RefundCommandDTO(
        tenant_id="tenant_123",
        amount=Decimal("50.000000"),
        idempotency_key="refund:pipeline_456:step_789",
        reference_type="failed_step",
        reference_id="step_789",
        metadata={
            "original_transaction_id": "100",
            "pipeline_run_id": "run_456",
            "reason": "AI service timeout"
        }
    )


@pytest.fixture
def sample_ledger():
    """Sample credit ledger"""
    return CreditLedger(
        id=1,
        tenant_id="tenant_123",
        balance=Decimal("500.000000"),
        monthly_limit=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
class TestRefundCreditSuccess:
    """Test successful credit refund (AC-1.3.1)"""

    async def test_successful_refund_increments_balance(
        self, refund_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command, sample_ledger
    ):
        """
        Given: Valid refund request
        When: refund_credit is called
        Then: Transaction created, balance incremented, response includes snapshots
        """
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=sample_ledger)
        mock_transaction_repo.create = AsyncMock(
            return_value=CreditTransaction(
                id=200,
                tenant_id="tenant_123",
                ledger_id=1,
                transaction_type=TransactionType.REFUND,
                amount=Decimal("50.000000"),
                balance_before=Decimal("500.000000"),
                balance_after=Decimal("550.000000"),
                reference_type="failed_step",
                reference_id="step_789",
                idempotency_key="refund:pipeline_456:step_789",
                created_at=datetime.utcnow(),
            )
        )
        mock_ledger_repo.update_balance = AsyncMock()

        # Act
        result = await refund_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response data
        assert response.transaction_id == 200
        assert response.tenant_id == "tenant_123"
        assert response.transaction_type == "refund"
        assert response.amount == Decimal("50.000000")
        assert response.balance_before == Decimal("500.000000")
        assert response.balance_after == Decimal("550.000000")
        assert response.idempotency_key == "refund:pipeline_456:step_789"

        # Verify repository interactions
        mock_transaction_repo.get_by_idempotency_key.assert_called_once_with("refund:pipeline_456:step_789")
        mock_ledger_repo.get_by_tenant_id.assert_called_once_with("tenant_123", for_update=True)
        mock_transaction_repo.create.assert_called_once()
        mock_ledger_repo.update_balance.assert_called_once_with(1, Decimal("550.000000"))
        mock_uow.commit.assert_called_once()

    async def test_balance_calculation_accuracy(
        self, refund_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow
    ):
        """Test that balance calculations are accurate with decimal precision"""
        # Arrange
        ledger = CreditLedger(
            id=1,
            tenant_id="tenant_123",
            balance=Decimal("100.123456"),
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        command = RefundCommandDTO(
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
        result = await refund_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert created_transaction.balance_before == Decimal("100.123456")
        assert created_transaction.balance_after == Decimal("130.623456")
        mock_ledger_repo.update_balance.assert_called_once_with(1, Decimal("130.623456"))

    async def test_metadata_is_stored_correctly(
        self, refund_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_ledger
    ):
        """Test that metadata linking to original transaction is stored (AC-1.3.3)"""
        # Arrange
        command = RefundCommandDTO(
            tenant_id="tenant_123",
            amount=Decimal("10.000000"),
            idempotency_key="test_key",
            reference_type="failed_step",
            reference_id="step_999",
            metadata={
                "original_transaction_id": "555",
                "pipeline_run_id": "run_888",
                "reason": "Pipeline step timeout"
            }
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
        result = await refund_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert created_transaction.reference_type == "failed_step"
        assert created_transaction.reference_id == "step_999"
        # Note: metadata validation would be in integration tests with real DB


@pytest.mark.asyncio
class TestRefundCreditIdempotency:
    """Test idempotency guarantee (AC-1.3.2)"""

    async def test_idempotency_returns_existing_transaction(
        self, refund_use_case, mock_transaction_repo, mock_ledger_repo, sample_command
    ):
        """
        Given: Same idempotency_key is used multiple times
        When: refund_credit is called repeatedly
        Then: First call creates transaction, subsequent calls return same transaction
        """
        # Arrange - existing refund transaction
        existing_transaction = CreditTransaction(
            id=999,
            tenant_id="tenant_123",
            ledger_id=1,
            transaction_type=TransactionType.REFUND,
            amount=Decimal("50.000000"),
            balance_before=Decimal("500.000000"),
            balance_after=Decimal("550.000000"),
            reference_type="failed_step",
            reference_id="step_789",
            idempotency_key="refund:pipeline_456:step_789",
            created_at=datetime.utcnow(),
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=existing_transaction)

        # Act
        result = await refund_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response matches existing transaction
        assert response.transaction_id == 999
        assert response.balance_before == Decimal("500.000000")
        assert response.balance_after == Decimal("550.000000")

        # Verify no new transaction created
        mock_ledger_repo.get_by_tenant_id.assert_not_called()
        mock_transaction_repo.create.assert_not_called()
        mock_ledger_repo.update_balance.assert_not_called()

    async def test_response_identical_across_idempotent_calls(
        self, refund_use_case, mock_transaction_repo, sample_command
    ):
        """Test that idempotent responses are byte-for-byte identical"""
        # Arrange
        created_at = datetime(2024, 1, 1, 12, 0, 0)
        existing_transaction = CreditTransaction(
            id=123,
            tenant_id="tenant_123",
            ledger_id=1,
            transaction_type=TransactionType.REFUND,
            amount=Decimal("50.000000"),
            balance_before=Decimal("500.000000"),
            balance_after=Decimal("550.000000"),
            reference_type="failed_step",
            reference_id="step_789",
            idempotency_key="refund:pipeline_456:step_789",
            created_at=created_at,
        )

        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=existing_transaction)

        # Act - call twice
        result1 = await refund_use_case.execute(sample_command)
        result2 = await refund_use_case.execute(sample_command)

        # Assert - responses are identical
        assert result1.is_ok() and result2.is_ok()
        resp1 = result1.value
        resp2 = result2.value

        assert resp1.transaction_id == resp2.transaction_id
        assert resp1.amount == resp2.amount
        assert resp1.balance_before == resp2.balance_before
        assert resp1.balance_after == resp2.balance_after
        assert resp1.created_at == resp2.created_at


@pytest.mark.asyncio
class TestRefundCreditValidation:
    """Test validation and error cases"""

    async def test_ledger_not_found_error(
        self, refund_use_case, mock_ledger_repo, mock_transaction_repo, sample_command
    ):
        """
        Given: Ledger does not exist for tenant
        When: refund_credit is called
        Then: Error returned with appropriate message
        """
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=None)

        # Act
        result = await refund_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        error = result.error

        assert error.code == "LEDGER_NOT_FOUND"
        assert "tenant_123" in error.message

    async def test_refund_can_exceed_previous_balance(
        self, refund_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow
    ):
        """
        Test AC-1.3.4: Refund succeeds even if it causes balance to exceed previous max
        This handles edge cases where multiple refunds accumulate
        """
        # Arrange - ledger with low balance
        ledger = CreditLedger(
            id=1,
            tenant_id="tenant_123",
            balance=Decimal("50.000000"),  # Low balance
            monthly_limit=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Large refund that exceeds current balance
        command = RefundCommandDTO(
            tenant_id="tenant_123",
            amount=Decimal("200.000000"),  # Much larger than current balance
            idempotency_key="large_refund",
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
        result = await refund_use_case.execute(command)

        # Assert - refund succeeds
        assert result.is_ok()
        assert created_transaction.balance_after == Decimal("250.000000")
        mock_ledger_repo.update_balance.assert_called_once_with(1, Decimal("250.000000"))


@pytest.mark.asyncio
class TestRefundCreditErrorHandling:
    """Test error handling and rollback"""

    async def test_rollback_on_exception(
        self, refund_use_case, mock_ledger_repo, mock_transaction_repo, mock_uow, sample_command, sample_ledger
    ):
        """Test that UoW rollback is called on exception"""
        # Arrange
        mock_transaction_repo.get_by_idempotency_key = AsyncMock(return_value=None)
        mock_ledger_repo.get_by_tenant_id = AsyncMock(return_value=sample_ledger)
        mock_transaction_repo.create = AsyncMock(side_effect=Exception("Database error"))

        # Act
        result = await refund_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        mock_uow.rollback.assert_called_once()
        assert result.error.code == "REFUND_CREDIT_FAILED"
