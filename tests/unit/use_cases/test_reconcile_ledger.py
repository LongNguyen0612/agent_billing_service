"""Unit tests for ReconcileLedger use case (UC-40)

Tests cover:
- AC-3.6.1: Reconciliation check (ledger vs transactions comparison)
- Discrepancy detection and logging
- No discrepancies scenario
- Error handling
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from src.app.use_cases.billing.reconcile_ledger import ReconcileLedger
from src.domain.credit_ledger import CreditLedger


@pytest.fixture
def mock_ledger_repo():
    """Mock credit ledger repository"""
    return MagicMock()


@pytest.fixture
def mock_transaction_repo():
    """Mock credit transaction repository"""
    return MagicMock()


@pytest.fixture
def reconcile_use_case(mock_uow, mock_ledger_repo, mock_transaction_repo):
    """ReconcileLedger use case instance with mocked dependencies"""
    return ReconcileLedger(
        uow=mock_uow,
        ledger_repo=mock_ledger_repo,
        transaction_repo=mock_transaction_repo,
    )


@pytest.fixture
def sample_ledger():
    """Create a sample ledger for testing"""
    def _create_ledger(tenant_id: str, ledger_id: int, balance: Decimal):
        ledger = MagicMock(spec=CreditLedger)
        ledger.id = ledger_id
        ledger.tenant_id = tenant_id
        ledger.balance = balance
        return ledger
    return _create_ledger


@pytest.mark.asyncio
class TestReconcileLedgerReconciliationCheck:
    """Test reconciliation check (AC-3.6.1)"""

    async def test_detects_discrepancy_when_balance_differs(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Ledger balance differs from transaction sum
        When: Reconciliation job runs
        Then: Discrepancy is detected and logged
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("1000.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        # Transaction sum is different from ledger balance
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("985.500000")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.total_ledgers_checked == 1
        assert response.discrepancies_found == 1
        assert len(response.discrepancies) == 1

        discrepancy = response.discrepancies[0]
        assert discrepancy.tenant_id == "tenant_123"
        assert discrepancy.ledger_id == 1
        assert discrepancy.ledger_balance == Decimal("1000.000000")
        assert discrepancy.calculated_balance == Decimal("985.500000")
        assert discrepancy.discrepancy == Decimal("14.500000")

    async def test_no_discrepancy_when_balances_match(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Ledger balance equals transaction sum
        When: Reconciliation job runs
        Then: No discrepancy is reported
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("1000.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        # Transaction sum matches ledger balance
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("1000.000000")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.total_ledgers_checked == 1
        assert response.discrepancies_found == 0
        assert len(response.discrepancies) == 0

    async def test_reconciles_multiple_ledgers(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Multiple ledgers in the system
        When: Reconciliation job runs
        Then: All ledgers are checked and discrepancies reported for mismatches
        """
        # Arrange
        ledger1 = sample_ledger("tenant_123", 1, Decimal("1000.000000"))
        ledger2 = sample_ledger("tenant_456", 2, Decimal("500.000000"))
        ledger3 = sample_ledger("tenant_789", 3, Decimal("750.000000"))

        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger1, ledger2, ledger3])

        async def get_transaction_sum(ledger_id):
            sums = {
                1: Decimal("1000.000000"),  # Matches
                2: Decimal("480.000000"),   # Discrepancy: -20
                3: Decimal("750.000000"),   # Matches
            }
            return sums[ledger_id]

        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            side_effect=get_transaction_sum
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.total_ledgers_checked == 3
        assert response.discrepancies_found == 1
        assert len(response.discrepancies) == 1

        discrepancy = response.discrepancies[0]
        assert discrepancy.tenant_id == "tenant_456"
        assert discrepancy.ledger_id == 2
        assert discrepancy.discrepancy == Decimal("20.000000")


@pytest.mark.asyncio
class TestReconcileLedgerDiscrepancyTypes:
    """Test different types of discrepancies"""

    async def test_detects_positive_discrepancy(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Ledger balance is higher than transaction sum
        When: Reconciliation job runs
        Then: Positive discrepancy is reported
        """
        # Arrange - ledger shows more credits than transactions support
        ledger = sample_ledger("tenant_123", 1, Decimal("1000.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("900.000000")  # Less than ledger
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.discrepancies_found == 1
        discrepancy = response.discrepancies[0]
        assert discrepancy.discrepancy == Decimal("100.000000")  # Positive: inflated balance

    async def test_detects_negative_discrepancy(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Ledger balance is lower than transaction sum
        When: Reconciliation job runs
        Then: Negative discrepancy is reported
        """
        # Arrange - ledger shows fewer credits than transactions support
        ledger = sample_ledger("tenant_123", 1, Decimal("900.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("1000.000000")  # More than ledger
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.discrepancies_found == 1
        discrepancy = response.discrepancies[0]
        assert discrepancy.discrepancy == Decimal("-100.000000")  # Negative: missing credits

    async def test_handles_zero_balance_ledger(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Ledger has zero balance
        When: Reconciliation job runs
        Then: Correctly handles zero balance comparison
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("0.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("0.000000")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.total_ledgers_checked == 1
        assert response.discrepancies_found == 0


@pytest.mark.asyncio
class TestReconcileLedgerEmptySystem:
    """Test reconciliation with no ledgers"""

    async def test_handles_no_ledgers(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo
    ):
        """
        Given: No ledgers exist in the system
        When: Reconciliation job runs
        Then: Completes successfully with zero ledgers checked
        """
        # Arrange
        mock_ledger_repo.get_all = AsyncMock(return_value=[])

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.total_ledgers_checked == 0
        assert response.discrepancies_found == 0
        assert len(response.discrepancies) == 0
        assert response.execution_time_ms >= 0


@pytest.mark.asyncio
class TestReconcileLedgerResponseFormat:
    """Test response format and metadata"""

    async def test_includes_reconciliation_timestamp(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Reconciliation runs
        When: Result is returned
        Then: Contains valid reconciliation timestamp
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("100.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("100.000000")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.reconciliation_time is not None
        # Should be approximately now
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        assert abs((response.reconciliation_time - now).total_seconds()) < 5

    async def test_includes_execution_time(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Reconciliation runs
        When: Result is returned
        Then: Contains execution time in milliseconds
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("100.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("100.000000")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.execution_time_ms >= 0
        assert isinstance(response.execution_time_ms, int)


@pytest.mark.asyncio
class TestReconcileLedgerErrorHandling:
    """Test error handling"""

    async def test_returns_error_on_ledger_repo_failure(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo
    ):
        """
        Given: Ledger repository throws exception
        When: Reconciliation job runs
        Then: Returns error result
        """
        # Arrange
        mock_ledger_repo.get_all = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_err()
        assert result.error.code == "RECONCILIATION_FAILED"
        assert "Database connection failed" in result.error.reason

    async def test_returns_error_on_transaction_repo_failure(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Transaction repository throws exception
        When: Reconciliation job runs
        Then: Returns error result
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("100.000000"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            side_effect=Exception("Query failed")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_err()
        assert result.error.code == "RECONCILIATION_FAILED"
        assert "Query failed" in result.error.reason


@pytest.mark.asyncio
class TestReconcileLedgerPrecision:
    """Test decimal precision handling"""

    async def test_handles_six_decimal_precision(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Ledger and transactions have 6 decimal places
        When: Reconciliation job runs
        Then: Precision is preserved in discrepancy calculation
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("1000.123456"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("1000.123450")  # 0.000006 difference
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.discrepancies_found == 1
        discrepancy = response.discrepancies[0]
        assert discrepancy.discrepancy == Decimal("0.000006")

    async def test_no_discrepancy_with_exact_precision_match(
        self, reconcile_use_case, mock_ledger_repo, mock_transaction_repo, sample_ledger
    ):
        """
        Given: Ledger and transactions match exactly at 6 decimals
        When: Reconciliation job runs
        Then: No discrepancy reported
        """
        # Arrange
        ledger = sample_ledger("tenant_123", 1, Decimal("999.999999"))
        mock_ledger_repo.get_all = AsyncMock(return_value=[ledger])
        mock_transaction_repo.get_transaction_sum_by_ledger = AsyncMock(
            return_value=Decimal("999.999999")
        )

        # Act
        result = await reconcile_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.discrepancies_found == 0
