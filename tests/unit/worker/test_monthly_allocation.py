"""Unit tests for MonthlyAllocationWorker (UC-38)

Tests cover:
- Worker initialization with configuration
- Billing period calculation
- Idempotency key generation
- run_once execution with allocation and invoice creation
- Handling allocation and invoice errors
- run_forever continuous execution
- Shutdown and cleanup
- Error handling scenarios
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date

from src.worker.monthly_allocation import MonthlyAllocationWorker
from src.app.use_cases.billing.dtos import (
    MonthlyAllocationResultDTO,
    AllocateCreditsResponseDTO,
    InvoiceResponseDTO,
)
from src.domain.subscription import Subscription, SubscriptionStatus


@pytest.fixture
def mock_config():
    """Mock ApplicationConfig"""
    config = MagicMock()
    config.DB_URI = "postgresql+asyncpg://test:test@localhost:5432/test_db"
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
def sample_subscription():
    """Sample active subscription"""
    return MagicMock(
        id=1,
        tenant_id="tenant_123",
        status=SubscriptionStatus.ACTIVE,
        plan_name="Pro Plan",
        monthly_credits=Decimal("10000.000000"),
        start_date=date(2024, 1, 1),
        end_date=None,
    )


@pytest.fixture
def sample_allocation_result():
    """Sample successful allocation result"""
    return MonthlyAllocationResultDTO(
        total_subscriptions=5,
        successful_allocations=5,
        failed_allocations=0,
        invoices_created=5,
        billing_period_start=datetime(2024, 1, 1, 0, 0, 0),
        billing_period_end=datetime(2024, 1, 31, 23, 59, 59),
        execution_time_ms=1500,
    )


@pytest.mark.asyncio
class TestMonthlyAllocationWorkerInit:
    """Test worker initialization"""

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
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
        worker = MonthlyAllocationWorker()

        # Assert
        assert worker.db_uri == "postgresql+asyncpg://default@localhost/db"
        mock_create_engine.assert_called_once()

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
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
        worker = MonthlyAllocationWorker(
            db_uri="postgresql+asyncpg://custom@localhost/custom_db"
        )

        # Assert
        assert worker.db_uri == "postgresql+asyncpg://custom@localhost/custom_db"


@pytest.mark.asyncio
class TestMonthlyAllocationWorkerBillingPeriod:
    """Test billing period calculation"""

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
    def test_get_billing_period_with_explicit_month(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: Explicit year and month provided
        When: _get_billing_period is called
        Then: Returns correct period start and end
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_create_engine.return_value = MagicMock()

        worker = MonthlyAllocationWorker()

        # Act
        period_start, period_end = worker._get_billing_period(year=2024, month=1)

        # Assert
        assert period_start == datetime(2024, 1, 1, 0, 0, 0)
        assert period_end == datetime(2024, 1, 31, 23, 59, 59)

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
    def test_get_billing_period_february_leap_year(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: February of leap year
        When: _get_billing_period is called
        Then: Returns correct 29 days
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_create_engine.return_value = MagicMock()

        worker = MonthlyAllocationWorker()

        # Act
        period_start, period_end = worker._get_billing_period(year=2024, month=2)

        # Assert
        assert period_start == datetime(2024, 2, 1, 0, 0, 0)
        assert period_end == datetime(2024, 2, 29, 23, 59, 59)

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
    def test_get_billing_period_february_non_leap_year(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: February of non-leap year
        When: _get_billing_period is called
        Then: Returns correct 28 days
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_create_engine.return_value = MagicMock()

        worker = MonthlyAllocationWorker()

        # Act
        period_start, period_end = worker._get_billing_period(year=2023, month=2)

        # Assert
        assert period_start == datetime(2023, 2, 1, 0, 0, 0)
        assert period_end == datetime(2023, 2, 28, 23, 59, 59)

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.datetime")
    def test_get_billing_period_defaults_to_previous_month(
        self, mock_datetime, mock_create_engine, mock_app_config
    ):
        """
        Given: No year/month provided
        When: _get_billing_period is called
        Then: Returns previous month's period
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_create_engine.return_value = MagicMock()

        # Mock datetime.utcnow to return Feb 15, 2024
        mock_now = datetime(2024, 2, 15, 10, 30, 0)
        mock_datetime.utcnow.return_value = mock_now
        # Allow datetime() constructor to work normally
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        worker = MonthlyAllocationWorker()

        # Act
        period_start, period_end = worker._get_billing_period()

        # Assert - should be January 2024
        assert period_start == datetime(2024, 1, 1, 0, 0, 0)
        assert period_end == datetime(2024, 1, 31, 23, 59, 59)

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.datetime")
    def test_get_billing_period_handles_january(
        self, mock_datetime, mock_create_engine, mock_app_config
    ):
        """
        Given: Current month is January
        When: _get_billing_period is called without parameters
        Then: Returns December of previous year
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_create_engine.return_value = MagicMock()

        # Mock datetime.utcnow to return Jan 15, 2024
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.utcnow.return_value = mock_now
        mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        worker = MonthlyAllocationWorker()

        # Act
        period_start, period_end = worker._get_billing_period()

        # Assert - should be December 2023
        assert period_start == datetime(2023, 12, 1, 0, 0, 0)
        assert period_end == datetime(2023, 12, 31, 23, 59, 59)


@pytest.mark.asyncio
class TestMonthlyAllocationWorkerIdempotencyKey:
    """Test idempotency key generation"""

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
    def test_generates_correct_idempotency_key(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: Tenant ID and period start
        When: _generate_idempotency_key is called
        Then: Returns correctly formatted key
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_create_engine.return_value = MagicMock()

        worker = MonthlyAllocationWorker()
        period_start = datetime(2024, 1, 1, 0, 0, 0)

        # Act
        key = worker._generate_idempotency_key("tenant_xyz", period_start)

        # Assert
        assert key == "allocation:tenant_xyz:2024-01"

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
    def test_idempotency_key_format_december(
        self, mock_create_engine, mock_app_config
    ):
        """
        Given: December billing period
        When: _generate_idempotency_key is called
        Then: Returns key with 12 month
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_create_engine.return_value = MagicMock()

        worker = MonthlyAllocationWorker()
        period_start = datetime(2023, 12, 1, 0, 0, 0)

        # Act
        key = worker._generate_idempotency_key("tenant_abc", period_start)

        # Assert
        assert key == "allocation:tenant_abc:2023-12"


@pytest.mark.asyncio
class TestMonthlyAllocationWorkerRunOnce:
    """Test run_once execution"""

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.AllocateCredits")
    @patch("src.worker.monthly_allocation.CreateInvoice")
    @patch("src.worker.monthly_allocation.SqlAlchemyUnitOfWork")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemySubscriptionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyInvoiceRepository")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.sessionmaker")
    async def test_run_once_allocates_credits_for_each_subscription(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_invoice_repo_class,
        mock_subscription_repo_class,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_create_invoice_class,
        mock_allocate_class,
        mock_app_config,
        sample_subscription,
    ):
        """
        Given: Active subscriptions exist
        When: run_once is called
        Then: Allocates credits and creates invoice for each subscription
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock subscription repository
        mock_subscription_repo = MagicMock()
        mock_subscription_repo.get_active_subscriptions = AsyncMock(
            return_value=[sample_subscription]
        )
        mock_subscription_repo_class.return_value = mock_subscription_repo

        # Mock allocate use case
        mock_allocate = MagicMock()
        mock_allocate_result = MagicMock()
        mock_allocate_result.is_err.return_value = False
        mock_allocate_result.value = AllocateCreditsResponseDTO(
            transaction_id=1,
            tenant_id="tenant_123",
            amount=Decimal("10000.000000"),
            balance_before=Decimal("0"),
            balance_after=Decimal("10000.000000"),
            idempotency_key="allocation:tenant_123:2024-01",
            created_at=datetime.utcnow(),
        )
        mock_allocate.execute = AsyncMock(return_value=mock_allocate_result)
        mock_allocate_class.return_value = mock_allocate

        # Mock create invoice use case
        mock_create_invoice = MagicMock()
        mock_invoice_result = MagicMock()
        mock_invoice_result.is_err.return_value = False
        mock_invoice_result.value = InvoiceResponseDTO(
            invoice_id=1,
            tenant_id="tenant_123",
            invoice_number="INV-2024-000001",
            status="draft",
            total_amount=Decimal("150.000000"),
            currency="USD",
            billing_period_start=datetime(2024, 1, 1),
            billing_period_end=datetime(2024, 1, 31),
            created_at=datetime.utcnow(),
        )
        mock_create_invoice.execute = AsyncMock(return_value=mock_invoice_result)
        mock_create_invoice_class.return_value = mock_create_invoice

        # Act
        worker = MonthlyAllocationWorker()
        result = await worker.run_once(year=2024, month=1)

        # Assert
        assert result.total_subscriptions == 1
        assert result.successful_allocations == 1
        assert result.failed_allocations == 0
        assert result.invoices_created == 1
        mock_allocate.execute.assert_called_once()
        mock_create_invoice.execute.assert_called_once()

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.AllocateCredits")
    @patch("src.worker.monthly_allocation.SqlAlchemyUnitOfWork")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemySubscriptionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyInvoiceRepository")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.sessionmaker")
    async def test_run_once_handles_allocation_error(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_invoice_repo_class,
        mock_subscription_repo_class,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_allocate_class,
        mock_app_config,
        sample_subscription,
    ):
        """
        Given: Allocation fails for a subscription
        When: run_once is called
        Then: Counts as failed allocation, skips invoice
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock subscription repository
        mock_subscription_repo = MagicMock()
        mock_subscription_repo.get_active_subscriptions = AsyncMock(
            return_value=[sample_subscription]
        )
        mock_subscription_repo_class.return_value = mock_subscription_repo

        # Mock allocate use case to fail
        mock_allocate = MagicMock()
        mock_error = MagicMock()
        mock_error.message = "Allocation failed"
        mock_allocate_result = MagicMock()
        mock_allocate_result.is_err.return_value = True
        mock_allocate_result.error = mock_error
        mock_allocate.execute = AsyncMock(return_value=mock_allocate_result)
        mock_allocate_class.return_value = mock_allocate

        # Act
        worker = MonthlyAllocationWorker()
        result = await worker.run_once(year=2024, month=1)

        # Assert
        assert result.total_subscriptions == 1
        assert result.successful_allocations == 0
        assert result.failed_allocations == 1
        assert result.invoices_created == 0

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.SqlAlchemySubscriptionRepository")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.sessionmaker")
    async def test_run_once_handles_no_subscriptions(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_subscription_repo_class,
        mock_app_config,
    ):
        """
        Given: No active subscriptions
        When: run_once is called
        Then: Returns result with zero totals
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock subscription repository with empty list
        mock_subscription_repo = MagicMock()
        mock_subscription_repo.get_active_subscriptions = AsyncMock(return_value=[])
        mock_subscription_repo_class.return_value = mock_subscription_repo

        # Act
        worker = MonthlyAllocationWorker()
        result = await worker.run_once(year=2024, month=1)

        # Assert
        assert result.total_subscriptions == 0
        assert result.successful_allocations == 0
        assert result.failed_allocations == 0
        assert result.invoices_created == 0

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.AllocateCredits")
    @patch("src.worker.monthly_allocation.CreateInvoice")
    @patch("src.worker.monthly_allocation.SqlAlchemyUnitOfWork")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemySubscriptionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyInvoiceRepository")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.sessionmaker")
    async def test_run_once_handles_invoice_already_exists(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_invoice_repo_class,
        mock_subscription_repo_class,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_create_invoice_class,
        mock_allocate_class,
        mock_app_config,
        sample_subscription,
    ):
        """
        Given: Invoice already exists for tenant
        When: run_once is called
        Then: Allocation succeeds but invoice count unchanged
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock subscription repository
        mock_subscription_repo = MagicMock()
        mock_subscription_repo.get_active_subscriptions = AsyncMock(
            return_value=[sample_subscription]
        )
        mock_subscription_repo_class.return_value = mock_subscription_repo

        # Mock allocate use case - success
        mock_allocate = MagicMock()
        mock_allocate_result = MagicMock()
        mock_allocate_result.is_err.return_value = False
        mock_allocate_result.value = AllocateCreditsResponseDTO(
            transaction_id=1,
            tenant_id="tenant_123",
            amount=Decimal("10000.000000"),
            balance_before=Decimal("0"),
            balance_after=Decimal("10000.000000"),
            idempotency_key="allocation:tenant_123:2024-01",
            created_at=datetime.utcnow(),
        )
        mock_allocate.execute = AsyncMock(return_value=mock_allocate_result)
        mock_allocate_class.return_value = mock_allocate

        # Mock create invoice to return "already exists" error
        mock_create_invoice = MagicMock()
        mock_invoice_error = MagicMock()
        mock_invoice_error.code = "INVOICE_ALREADY_EXISTS"
        mock_invoice_error.message = "Invoice already exists"
        mock_invoice_result = MagicMock()
        mock_invoice_result.is_err.return_value = True
        mock_invoice_result.error = mock_invoice_error
        mock_create_invoice.execute = AsyncMock(return_value=mock_invoice_result)
        mock_create_invoice_class.return_value = mock_create_invoice

        # Act
        worker = MonthlyAllocationWorker()
        result = await worker.run_once(year=2024, month=1)

        # Assert
        assert result.total_subscriptions == 1
        assert result.successful_allocations == 1
        assert result.failed_allocations == 0
        assert result.invoices_created == 0  # Not incremented due to duplicate


@pytest.mark.asyncio
class TestMonthlyAllocationWorkerShutdown:
    """Test shutdown and cleanup"""

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.create_async_engine")
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
        worker = MonthlyAllocationWorker()
        await worker.shutdown()

        # Assert
        mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
class TestMonthlyAllocationWorkerRunForever:
    """Test run_forever continuous execution"""

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.asyncio.sleep")
    @patch("src.worker.monthly_allocation.SqlAlchemySubscriptionRepository")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.sessionmaker")
    @patch("src.worker.monthly_allocation.datetime")
    async def test_run_forever_processes_on_first_days_of_month(
        self,
        mock_datetime_module,
        mock_sessionmaker,
        mock_create_engine,
        mock_subscription_repo_class,
        mock_sleep,
        mock_app_config,
    ):
        """
        Given: First 3 days of month
        When: run_forever is called
        Then: Processes allocation for previous month
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Mock datetime.utcnow to return Feb 2, 2024
        mock_now = datetime(2024, 2, 2, 10, 30, 0)
        mock_datetime_module.utcnow.return_value = mock_now
        mock_datetime_module.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

        mock_create_engine.return_value = MagicMock()

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        # Mock subscription repository with empty list
        mock_subscription_repo = MagicMock()
        mock_subscription_repo.get_active_subscriptions = AsyncMock(return_value=[])
        mock_subscription_repo_class.return_value = mock_subscription_repo

        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = MonthlyAllocationWorker()
        with pytest.raises(KeyboardInterrupt):
            await worker.run_forever(check_interval_seconds=86400)

        # Assert - should have called run_once
        mock_subscription_repo.get_active_subscriptions.assert_called_once()

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.asyncio.sleep")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.datetime")
    async def test_run_forever_skips_after_day_3(
        self,
        mock_datetime_module,
        mock_create_engine,
        mock_sleep,
        mock_app_config,
    ):
        """
        Given: After day 3 of month
        When: run_forever is called
        Then: Skips allocation processing
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Mock datetime.utcnow to return Feb 15, 2024 (after day 3)
        mock_now = datetime(2024, 2, 15, 10, 30, 0)
        mock_datetime_module.utcnow.return_value = mock_now

        mock_create_engine.return_value = MagicMock()

        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = MonthlyAllocationWorker()
        # Patch run_once to track if it was called
        worker.run_once = AsyncMock()

        with pytest.raises(KeyboardInterrupt):
            await worker.run_forever(check_interval_seconds=86400)

        # Assert - run_once should not have been called
        worker.run_once.assert_not_called()

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.asyncio.sleep")
    @patch("src.worker.monthly_allocation.create_async_engine")
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
        mock_create_engine.return_value = MagicMock()

        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = MonthlyAllocationWorker()
        # Patch run_once to raise exception
        worker.run_once = AsyncMock(side_effect=Exception("Test exception"))

        # Patch the date check to allow run_once to be called
        with patch("src.worker.monthly_allocation.datetime") as mock_dt:
            mock_dt.utcnow.return_value = datetime(2024, 2, 1, 10, 0, 0)
            with pytest.raises(KeyboardInterrupt):
                await worker.run_forever(check_interval_seconds=30)

        # Assert - should have attempted to run and continue
        assert worker.run_once.call_count >= 1


@pytest.mark.asyncio
class TestMonthlyAllocationWorkerMultipleSubscriptions:
    """Test handling multiple subscriptions"""

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.AllocateCredits")
    @patch("src.worker.monthly_allocation.CreateInvoice")
    @patch("src.worker.monthly_allocation.SqlAlchemyUnitOfWork")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemySubscriptionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyInvoiceRepository")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.sessionmaker")
    async def test_run_once_processes_all_subscriptions(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_invoice_repo_class,
        mock_subscription_repo_class,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_create_invoice_class,
        mock_allocate_class,
        mock_app_config,
    ):
        """
        Given: Multiple active subscriptions
        When: run_once is called
        Then: Processes each subscription independently
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Create multiple subscriptions
        subscriptions = [
            MagicMock(
                id=i,
                tenant_id=f"tenant_{i}",
                plan_name="Pro Plan",
                monthly_credits=Decimal("10000.000000"),
            )
            for i in range(3)
        ]

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock subscription repository
        mock_subscription_repo = MagicMock()
        mock_subscription_repo.get_active_subscriptions = AsyncMock(
            return_value=subscriptions
        )
        mock_subscription_repo_class.return_value = mock_subscription_repo

        # Mock allocate use case - success for all
        allocation_count = 0
        def make_allocation_result(*args, **kwargs):
            nonlocal allocation_count
            allocation_count += 1
            mock_result = MagicMock()
            mock_result.is_err.return_value = False
            mock_result.value = AllocateCreditsResponseDTO(
                transaction_id=allocation_count,
                tenant_id=f"tenant_{allocation_count}",
                amount=Decimal("10000.000000"),
                balance_before=Decimal("0"),
                balance_after=Decimal("10000.000000"),
                idempotency_key=f"allocation:tenant_{allocation_count}:2024-01",
                created_at=datetime.utcnow(),
            )
            return mock_result

        mock_allocate = MagicMock()
        mock_allocate.execute = AsyncMock(side_effect=make_allocation_result)
        mock_allocate_class.return_value = mock_allocate

        # Mock create invoice use case - success for all
        invoice_count = 0
        def make_invoice_result(*args, **kwargs):
            nonlocal invoice_count
            invoice_count += 1
            mock_result = MagicMock()
            mock_result.is_err.return_value = False
            mock_result.value = InvoiceResponseDTO(
                invoice_id=invoice_count,
                tenant_id=f"tenant_{invoice_count}",
                invoice_number=f"INV-2024-{invoice_count:06d}",
                status="draft",
                total_amount=Decimal("150.000000"),
                currency="USD",
                billing_period_start=datetime(2024, 1, 1),
                billing_period_end=datetime(2024, 1, 31),
                created_at=datetime.utcnow(),
            )
            return mock_result

        mock_create_invoice = MagicMock()
        mock_create_invoice.execute = AsyncMock(side_effect=make_invoice_result)
        mock_create_invoice_class.return_value = mock_create_invoice

        # Act
        worker = MonthlyAllocationWorker()
        result = await worker.run_once(year=2024, month=1)

        # Assert
        assert result.total_subscriptions == 3
        assert result.successful_allocations == 3
        assert result.failed_allocations == 0
        assert result.invoices_created == 3

    @patch("src.worker.monthly_allocation.ApplicationConfig")
    @patch("src.worker.monthly_allocation.AllocateCredits")
    @patch("src.worker.monthly_allocation.CreateInvoice")
    @patch("src.worker.monthly_allocation.SqlAlchemyUnitOfWork")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditLedgerRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemySubscriptionRepository")
    @patch("src.worker.monthly_allocation.SqlAlchemyInvoiceRepository")
    @patch("src.worker.monthly_allocation.create_async_engine")
    @patch("src.worker.monthly_allocation.sessionmaker")
    async def test_run_once_continues_after_individual_failure(
        self,
        mock_sessionmaker,
        mock_create_engine,
        mock_invoice_repo_class,
        mock_subscription_repo_class,
        mock_transaction_repo_class,
        mock_ledger_repo_class,
        mock_uow_class,
        mock_create_invoice_class,
        mock_allocate_class,
        mock_app_config,
    ):
        """
        Given: One subscription fails during allocation
        When: run_once is called
        Then: Continues processing remaining subscriptions
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"

        # Create multiple subscriptions
        subscriptions = [
            MagicMock(
                id=i,
                tenant_id=f"tenant_{i}",
                plan_name="Pro Plan",
                monthly_credits=Decimal("10000.000000"),
            )
            for i in range(3)
        ]

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock subscription repository
        mock_subscription_repo = MagicMock()
        mock_subscription_repo.get_active_subscriptions = AsyncMock(
            return_value=subscriptions
        )
        mock_subscription_repo_class.return_value = mock_subscription_repo

        # Mock allocate use case - fail for tenant_1, succeed for others
        allocation_count = 0
        def make_allocation_result(*args, **kwargs):
            nonlocal allocation_count
            allocation_count += 1
            mock_result = MagicMock()

            if allocation_count == 2:  # Fail for second subscription
                mock_result.is_err.return_value = True
                mock_error = MagicMock()
                mock_error.message = "Allocation failed for tenant"
                mock_result.error = mock_error
            else:
                mock_result.is_err.return_value = False
                mock_result.value = AllocateCreditsResponseDTO(
                    transaction_id=allocation_count,
                    tenant_id=f"tenant_{allocation_count}",
                    amount=Decimal("10000.000000"),
                    balance_before=Decimal("0"),
                    balance_after=Decimal("10000.000000"),
                    idempotency_key=f"allocation:tenant_{allocation_count}:2024-01",
                    created_at=datetime.utcnow(),
                )
            return mock_result

        mock_allocate = MagicMock()
        mock_allocate.execute = AsyncMock(side_effect=make_allocation_result)
        mock_allocate_class.return_value = mock_allocate

        # Mock create invoice use case - success for all (called only for successful allocations)
        mock_create_invoice = MagicMock()
        mock_invoice_result = MagicMock()
        mock_invoice_result.is_err.return_value = False
        mock_invoice_result.value = InvoiceResponseDTO(
            invoice_id=1,
            tenant_id="tenant_x",
            invoice_number="INV-2024-000001",
            status="draft",
            total_amount=Decimal("150.000000"),
            currency="USD",
            billing_period_start=datetime(2024, 1, 1),
            billing_period_end=datetime(2024, 1, 31),
            created_at=datetime.utcnow(),
        )
        mock_create_invoice.execute = AsyncMock(return_value=mock_invoice_result)
        mock_create_invoice_class.return_value = mock_create_invoice

        # Act
        worker = MonthlyAllocationWorker()
        result = await worker.run_once(year=2024, month=1)

        # Assert
        assert result.total_subscriptions == 3
        assert result.successful_allocations == 2  # 2 succeeded
        assert result.failed_allocations == 1  # 1 failed
        assert result.invoices_created == 2  # Only for successful allocations
