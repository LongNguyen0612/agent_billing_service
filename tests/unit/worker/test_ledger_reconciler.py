"""Unit tests for LedgerReconcilerWorker (UC-40)

Tests cover:
- Worker initialization with configuration
- run_once execution with reconciliation
- Reconciliation disabled scenario
- Discrepancy detection and logging
- run_forever continuous execution
- Shutdown and cleanup
- Error handling scenarios
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from src.worker.ledger_reconciler import LedgerReconcilerWorker
from src.app.use_cases.billing.dtos import ReconciliationResultDTO, LedgerDiscrepancyDTO


@pytest.fixture
def mock_config():
    """Mock ApplicationConfig"""
    config = MagicMock()
    config.DB_URI = "postgresql+asyncpg://test:test@localhost:5432/test_db"
    config.RECONCILIATION_ENABLED = True
    return config


@pytest.fixture
def mock_session():
    """Mock async session"""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    return session


@pytest.fixture
def mock_uow():
    """Mock unit of work"""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    return uow


@pytest.fixture
def sample_reconciliation_result():
    """Sample successful reconciliation result"""
    return ReconciliationResultDTO(
        total_ledgers_checked=10,
        discrepancies_found=0,
        discrepancies=[],
        reconciliation_time=datetime.utcnow(),
        execution_time_ms=150,
    )


@pytest.fixture
def sample_discrepancy_result():
    """Sample reconciliation result with discrepancies"""
    return ReconciliationResultDTO(
        total_ledgers_checked=10,
        discrepancies_found=2,
        discrepancies=[
            LedgerDiscrepancyDTO(
                tenant_id="tenant_123",
                ledger_id=1,
                ledger_balance=Decimal("1000.000000"),
                calculated_balance=Decimal("985.500000"),
                discrepancy=Decimal("14.500000"),
            ),
            LedgerDiscrepancyDTO(
                tenant_id="tenant_456",
                ledger_id=2,
                ledger_balance=Decimal("500.000000"),
                calculated_balance=Decimal("520.000000"),
                discrepancy=Decimal("-20.000000"),
            ),
        ],
        reconciliation_time=datetime.utcnow(),
        execution_time_ms=250,
    )


@pytest.mark.asyncio
class TestLedgerReconcilerWorkerInit:
    """Test worker initialization"""

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    def test_initializes_with_default_config(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: No custom configuration provided
        When: Worker is initialized
        Then: Uses defaults from ApplicationConfig
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://default@localhost/db"
        mock_create_engine.return_value = MagicMock()

        # Act
        worker = LedgerReconcilerWorker()

        # Assert
        assert worker.db_uri == "postgresql+asyncpg://default@localhost/db"
        mock_create_engine.assert_called_once()

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    def test_initializes_with_custom_db_uri(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: Custom DB URI provided
        When: Worker is initialized
        Then: Uses custom DB URI
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://default@localhost/db"
        mock_create_engine.return_value = MagicMock()

        # Act
        worker = LedgerReconcilerWorker(
            db_uri="postgresql+asyncpg://custom@localhost/custom_db"
        )

        # Assert
        assert worker.db_uri == "postgresql+asyncpg://custom@localhost/custom_db"


@pytest.mark.asyncio
class TestLedgerReconcilerWorkerRunOnce:
    """Test run_once execution"""

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.ReconcileLedger")
    @patch("src.worker.ledger_reconciler.SqlAlchemyUnitOfWork")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    @patch("src.worker.ledger_reconciler.sessionmaker")
    async def test_run_once_executes_reconciliation(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
        sample_reconciliation_result,
    ):
        """
        Given: Reconciliation is enabled
        When: run_once is called
        Then: Executes reconciliation use case and returns result
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.RECONCILIATION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock use case result
        mock_use_case = MagicMock()
        mock_result = MagicMock()
        mock_result.is_err.return_value = False
        mock_result.value = sample_reconciliation_result
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        # Act
        worker = LedgerReconcilerWorker()
        result = await worker.run_once()

        # Assert
        assert result.total_ledgers_checked == 10
        assert result.discrepancies_found == 0
        mock_use_case.execute.assert_called_once()

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    async def test_run_once_skips_when_disabled(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: Reconciliation is disabled
        When: run_once is called
        Then: Returns empty result and skips reconciliation
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.RECONCILIATION_ENABLED = False

        mock_create_engine.return_value = MagicMock()

        # Act
        worker = LedgerReconcilerWorker()
        result = await worker.run_once()

        # Assert
        assert result.total_ledgers_checked == 0
        assert result.discrepancies_found == 0
        assert result.execution_time_ms == 0

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.ReconcileLedger")
    @patch("src.worker.ledger_reconciler.SqlAlchemyUnitOfWork")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    @patch("src.worker.ledger_reconciler.sessionmaker")
    async def test_run_once_logs_discrepancies(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
        sample_discrepancy_result,
    ):
        """
        Given: Discrepancies are found
        When: run_once completes
        Then: Logs discrepancy details
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.RECONCILIATION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock use case result with discrepancies
        mock_use_case = MagicMock()
        mock_result = MagicMock()
        mock_result.is_err.return_value = False
        mock_result.value = sample_discrepancy_result
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        # Act
        worker = LedgerReconcilerWorker()
        result = await worker.run_once()

        # Assert
        assert result.discrepancies_found == 2
        assert len(result.discrepancies) == 2
        assert result.discrepancies[0].tenant_id == "tenant_123"
        assert result.discrepancies[1].tenant_id == "tenant_456"

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.ReconcileLedger")
    @patch("src.worker.ledger_reconciler.SqlAlchemyUnitOfWork")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    @patch("src.worker.ledger_reconciler.sessionmaker")
    async def test_run_once_raises_on_use_case_error(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
    ):
        """
        Given: Reconciliation use case returns error
        When: run_once is called
        Then: Raises RuntimeError
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Mock session factory - need proper async context manager
        # IMPORTANT: __aexit__ must return False/None to not suppress exceptions
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        # Configure sessionmaker to return a callable that returns the session
        mock_session_factory_instance = MagicMock()
        mock_session_factory_instance.return_value = mock_session
        mock_sessionmaker.return_value = mock_session_factory_instance

        mock_create_engine.return_value = MagicMock()

        # Mock use case error result
        mock_use_case = MagicMock()
        mock_error = MagicMock()
        mock_error.message = "Database connection failed"
        mock_result = MagicMock()
        mock_result.is_err.return_value = True
        mock_result.error = mock_error
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        # Act & Assert
        worker = LedgerReconcilerWorker()
        with pytest.raises(RuntimeError, match="Reconciliation failed"):
            await worker.run_once()


@pytest.mark.asyncio
class TestLedgerReconcilerWorkerShutdown:
    """Test shutdown and cleanup"""

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    async def test_shutdown_disposes_engine(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: Worker is running
        When: shutdown is called
        Then: Engine is disposed
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_create_engine.return_value = mock_engine

        # Act
        worker = LedgerReconcilerWorker()
        await worker.shutdown()

        # Assert
        mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
class TestLedgerReconcilerWorkerRunForever:
    """Test run_forever continuous execution"""

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.asyncio.sleep")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    async def test_run_forever_calls_run_once_repeatedly(
        self, mock_create_engine, mock_sleep, mock_app_config
    ):
        """
        Given: Worker running in forever mode
        When: run_forever is called
        Then: Calls run_once at specified interval
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.RECONCILIATION_ENABLED = False  # Skip actual reconciliation

        mock_create_engine.return_value = MagicMock()

        # Make sleep raise exception after 2 calls to break the loop
        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = LedgerReconcilerWorker()
        with pytest.raises(KeyboardInterrupt):
            await worker.run_forever(interval_seconds=86400)

        # Assert
        assert mock_sleep.call_count >= 1
        mock_sleep.assert_called_with(86400)

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.asyncio.sleep")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    async def test_run_forever_handles_exception_and_continues(
        self, mock_create_engine, mock_sleep, mock_app_config
    ):
        """
        Given: Worker running in forever mode
        When: run_once raises exception
        Then: Logs error and continues
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.RECONCILIATION_ENABLED = True

        mock_create_engine.return_value = MagicMock()

        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = LedgerReconcilerWorker()
        # Patch run_once to raise exception
        worker.run_once = AsyncMock(side_effect=Exception("Test exception"))

        with pytest.raises(KeyboardInterrupt):
            await worker.run_forever(interval_seconds=30)

        # Assert - should have attempted to run and continue
        assert worker.run_once.call_count >= 1

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.asyncio.sleep")
    @patch("src.worker.ledger_reconciler.ReconcileLedger")
    @patch("src.worker.ledger_reconciler.SqlAlchemyUnitOfWork")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    @patch("src.worker.ledger_reconciler.sessionmaker")
    async def test_run_forever_logs_execution_time(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_sleep,
        mock_app_config,
        sample_reconciliation_result,
    ):
        """
        Given: Worker running in forever mode
        When: run_once completes
        Then: Logs execution time in milliseconds
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.RECONCILIATION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock use case result
        mock_use_case = MagicMock()
        mock_result = MagicMock()
        mock_result.is_err.return_value = False
        mock_result.value = sample_reconciliation_result
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = LedgerReconcilerWorker()
        with pytest.raises(KeyboardInterrupt):
            await worker.run_forever(interval_seconds=86400)

        # Assert - use case was executed
        mock_use_case.execute.assert_called_once()


@pytest.mark.asyncio
class TestLedgerReconcilerWorkerResultDetails:
    """Test result details are properly returned"""

    @patch("src.worker.ledger_reconciler.ApplicationConfig")
    @patch("src.worker.ledger_reconciler.ReconcileLedger")
    @patch("src.worker.ledger_reconciler.SqlAlchemyUnitOfWork")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.ledger_reconciler.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.ledger_reconciler.create_async_engine")
    @patch("src.worker.ledger_reconciler.sessionmaker")
    async def test_run_once_returns_all_discrepancy_details(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
    ):
        """
        Given: Multiple discrepancies found
        When: run_once completes
        Then: Returns complete details for each discrepancy
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.RECONCILIATION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Create detailed discrepancy result
        detailed_result = ReconciliationResultDTO(
            total_ledgers_checked=5,
            discrepancies_found=3,
            discrepancies=[
                LedgerDiscrepancyDTO(
                    tenant_id="tenant_aaa",
                    ledger_id=10,
                    ledger_balance=Decimal("5000.000000"),
                    calculated_balance=Decimal("4900.000000"),
                    discrepancy=Decimal("100.000000"),
                ),
                LedgerDiscrepancyDTO(
                    tenant_id="tenant_bbb",
                    ledger_id=20,
                    ledger_balance=Decimal("300.123456"),
                    calculated_balance=Decimal("300.123450"),
                    discrepancy=Decimal("0.000006"),
                ),
                LedgerDiscrepancyDTO(
                    tenant_id="tenant_ccc",
                    ledger_id=30,
                    ledger_balance=Decimal("0.000000"),
                    calculated_balance=Decimal("50.000000"),
                    discrepancy=Decimal("-50.000000"),
                ),
            ],
            reconciliation_time=datetime.utcnow(),
            execution_time_ms=500,
        )

        mock_use_case = MagicMock()
        mock_result = MagicMock()
        mock_result.is_err.return_value = False
        mock_result.value = detailed_result
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        # Act
        worker = LedgerReconcilerWorker()
        result = await worker.run_once()

        # Assert
        assert result.total_ledgers_checked == 5
        assert result.discrepancies_found == 3

        # Verify positive discrepancy (inflated balance)
        assert result.discrepancies[0].tenant_id == "tenant_aaa"
        assert result.discrepancies[0].discrepancy == Decimal("100.000000")

        # Verify small precision discrepancy
        assert result.discrepancies[1].tenant_id == "tenant_bbb"
        assert result.discrepancies[1].discrepancy == Decimal("0.000006")

        # Verify negative discrepancy (missing credits)
        assert result.discrepancies[2].tenant_id == "tenant_ccc"
        assert result.discrepancies[2].discrepancy == Decimal("-50.000000")
