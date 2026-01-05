"""Unit tests for AbnormalUsageDetectorWorker (UC-37)

Tests cover:
- Worker initialization with configuration
- run_once execution with anomaly detection
- Anomaly detection disabled scenario
- Notification sending for detected anomalies
- run_forever continuous execution
- Shutdown and cleanup
- Error handling scenarios
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from src.worker.anomaly_detector import AbnormalUsageDetectorWorker


@pytest.fixture
def mock_config():
    """Mock ApplicationConfig"""
    config = MagicMock()
    config.DB_URI = "postgresql+asyncpg://test:test@localhost:5432/test_db"
    config.ANOMALY_HOURLY_THRESHOLD = 100.0
    config.ANOMALY_NOTIFICATION_WEBHOOK = "https://webhook.example.com/alerts"
    config.ANOMALY_DETECTION_ENABLED = True
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
def mock_notification_service():
    """Mock notification service"""
    service = MagicMock()
    service.send_anomaly_alert = AsyncMock(return_value=True)
    return service


@pytest.mark.asyncio
class TestAbnormalUsageDetectorWorkerInit:
    """Test worker initialization"""

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    def test_initializes_with_default_config(
        self, mock_create_notification, mock_create_engine, mock_app_config
    ):
        """
        Given: No custom configuration provided
        When: Worker is initialized
        Then: Uses defaults from ApplicationConfig
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://default@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = "https://default.webhook"
        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        # Act
        worker = AbnormalUsageDetectorWorker()

        # Assert
        assert worker.db_uri == "postgresql+asyncpg://default@localhost/db"
        assert worker.hourly_threshold == Decimal("100.0")
        assert worker.webhook_url == "https://default.webhook"

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    def test_initializes_with_custom_config(
        self, mock_create_notification, mock_create_engine, mock_app_config
    ):
        """
        Given: Custom configuration provided
        When: Worker is initialized
        Then: Uses custom values
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://default@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None
        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        # Act
        worker = AbnormalUsageDetectorWorker(
            db_uri="postgresql+asyncpg://custom@localhost/custom_db",
            hourly_threshold=Decimal("200.0"),
            webhook_url="https://custom.webhook",
        )

        # Assert
        assert worker.db_uri == "postgresql+asyncpg://custom@localhost/custom_db"
        assert worker.hourly_threshold == Decimal("200.0")
        assert worker.webhook_url == "https://custom.webhook"


@pytest.mark.asyncio
class TestAbnormalUsageDetectorWorkerRunOnce:
    """Test run_once execution"""

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.DetectAbnormalUsage")
    @patch("src.worker.anomaly_detector.SqlAlchemyUnitOfWork")
    @patch("src.worker.anomaly_detector.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.anomaly_detector.SqlAlchemyUsageAnomalyRepository")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    @patch("src.worker.anomaly_detector.sessionmaker")
    async def test_run_once_detects_anomalies(
        self,
        mock_sessionmaker,
        mock_create_notification,
        mock_create_engine,
        mock_anomaly_repo_class,
        mock_transaction_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
    ):
        """
        Given: Anomaly detection is enabled
        When: run_once is called
        Then: Executes detection use case and returns anomaly count
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None
        mock_app_config.ANOMALY_DETECTION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        # Mock use case result
        mock_use_case = MagicMock()
        mock_result = MagicMock()
        mock_result.is_err.return_value = False
        mock_result.value.anomalies_detected = 2
        mock_result.value.anomalies = []
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        # Act
        worker = AbnormalUsageDetectorWorker()
        count = await worker.run_once()

        # Assert
        assert count == 2
        mock_use_case.execute.assert_called_once()

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    async def test_run_once_skips_when_disabled(
        self, mock_create_notification, mock_create_engine, mock_app_config
    ):
        """
        Given: Anomaly detection is disabled
        When: run_once is called
        Then: Returns 0 and skips detection
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None
        mock_app_config.ANOMALY_DETECTION_ENABLED = False

        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        # Act
        worker = AbnormalUsageDetectorWorker()
        count = await worker.run_once()

        # Assert
        assert count == 0

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.DetectAbnormalUsage")
    @patch("src.worker.anomaly_detector.SqlAlchemyUnitOfWork")
    @patch("src.worker.anomaly_detector.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.anomaly_detector.SqlAlchemyUsageAnomalyRepository")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    @patch("src.worker.anomaly_detector.sessionmaker")
    async def test_run_once_handles_use_case_error(
        self,
        mock_sessionmaker,
        mock_create_notification,
        mock_create_engine,
        mock_anomaly_repo_class,
        mock_transaction_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
    ):
        """
        Given: Detection use case returns error
        When: run_once is called
        Then: Returns 0 and logs error
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None
        mock_app_config.ANOMALY_DETECTION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        # Mock use case error result
        mock_use_case = MagicMock()
        mock_error = MagicMock()
        mock_error.message = "Database connection failed"
        mock_result = MagicMock()
        mock_result.is_err.return_value = True
        mock_result.error = mock_error
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        # Act
        worker = AbnormalUsageDetectorWorker()
        count = await worker.run_once()

        # Assert
        assert count == 0


@pytest.mark.asyncio
class TestAbnormalUsageDetectorWorkerNotifications:
    """Test notification sending for detected anomalies"""

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.DetectAbnormalUsage")
    @patch("src.worker.anomaly_detector.SqlAlchemyUnitOfWork")
    @patch("src.worker.anomaly_detector.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.anomaly_detector.SqlAlchemyUsageAnomalyRepository")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    @patch("src.worker.anomaly_detector.sessionmaker")
    async def test_sends_notification_for_each_anomaly(
        self,
        mock_sessionmaker,
        mock_create_notification,
        mock_create_engine,
        mock_anomaly_repo_class,
        mock_transaction_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
    ):
        """
        Given: Anomalies are detected
        When: run_once completes
        Then: Notification is sent for each anomaly
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = "https://webhook.test"
        mock_app_config.ANOMALY_DETECTION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()

        # Mock notification service
        mock_notification = MagicMock()
        mock_notification.send_anomaly_alert = AsyncMock(return_value=True)
        mock_create_notification.return_value = mock_notification

        # Mock use case result with anomalies
        mock_anomaly_dto = MagicMock()
        mock_anomaly_dto.id = 1

        mock_use_case = MagicMock()
        mock_result = MagicMock()
        mock_result.is_err.return_value = False
        mock_result.value.anomalies_detected = 1
        mock_result.value.anomalies = [mock_anomaly_dto]
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        # Mock anomaly repo
        mock_anomaly_repo = MagicMock()
        mock_anomaly = MagicMock()
        mock_anomaly.id = 1
        mock_anomaly_repo.get_by_id = AsyncMock(return_value=mock_anomaly)
        mock_anomaly_repo.mark_notified = AsyncMock()
        mock_anomaly_repo_class.return_value = mock_anomaly_repo

        # Mock UoW
        mock_uow = MagicMock()
        mock_uow.commit = AsyncMock()
        mock_uow_class.return_value = mock_uow

        # Act
        worker = AbnormalUsageDetectorWorker()
        count = await worker.run_once()

        # Assert
        assert count == 1
        mock_notification.send_anomaly_alert.assert_called_once_with(mock_anomaly)
        mock_anomaly_repo.mark_notified.assert_called_once_with(1)


@pytest.mark.asyncio
class TestAbnormalUsageDetectorWorkerShutdown:
    """Test shutdown and cleanup"""

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    async def test_shutdown_disposes_engine(
        self, mock_create_notification, mock_create_engine, mock_app_config
    ):
        """
        Given: Worker is running
        When: shutdown is called
        Then: Engine is disposed
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None

        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()
        mock_create_engine.return_value = mock_engine
        mock_create_notification.return_value = MagicMock()

        # Act
        worker = AbnormalUsageDetectorWorker()
        await worker.shutdown()

        # Assert
        mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
class TestAbnormalUsageDetectorWorkerRunForever:
    """Test run_forever continuous execution"""

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.asyncio.sleep")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    async def test_run_forever_calls_run_once_repeatedly(
        self, mock_create_notification, mock_create_engine, mock_sleep, mock_app_config
    ):
        """
        Given: Worker running in forever mode
        When: run_forever is called
        Then: Calls run_once at specified interval
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None
        mock_app_config.ANOMALY_DETECTION_ENABLED = False  # Skip actual detection

        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        # Make sleep raise StopIteration after 2 calls to break the loop
        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = AbnormalUsageDetectorWorker()
        with pytest.raises(KeyboardInterrupt):
            await worker.run_forever(interval_seconds=60)

        # Assert
        assert mock_sleep.call_count >= 1
        mock_sleep.assert_called_with(60)

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.asyncio.sleep")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    async def test_run_forever_handles_exception_and_continues(
        self, mock_create_notification, mock_create_engine, mock_sleep, mock_app_config
    ):
        """
        Given: Worker running in forever mode
        When: run_once raises exception
        Then: Logs error and continues
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None
        mock_app_config.ANOMALY_DETECTION_ENABLED = True

        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        call_count = 0
        async def limited_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("Test termination")

        mock_sleep.side_effect = limited_sleep

        # Act
        worker = AbnormalUsageDetectorWorker()
        # Patch run_once to raise exception
        worker.run_once = AsyncMock(side_effect=Exception("Test exception"))

        with pytest.raises(KeyboardInterrupt):
            await worker.run_forever(interval_seconds=30)

        # Assert - should have attempted to run and continue
        assert worker.run_once.call_count >= 1


@pytest.mark.asyncio
class TestAbnormalUsageDetectorWorkerPeriodConfiguration:
    """Test period configuration for detection"""

    @patch("src.worker.anomaly_detector.ApplicationConfig")
    @patch("src.worker.anomaly_detector.DetectAbnormalUsage")
    @patch("src.worker.anomaly_detector.SqlAlchemyUnitOfWork")
    @patch("src.worker.anomaly_detector.SqlAlchemyCreditTransactionRepository")
    @patch("src.worker.anomaly_detector.SqlAlchemyUsageAnomalyRepository")
    @patch("src.worker.anomaly_detector.create_async_engine")
    @patch("src.worker.anomaly_detector.create_notification_service")
    @patch("src.worker.anomaly_detector.sessionmaker")
    async def test_run_once_with_custom_period(
        self,
        mock_sessionmaker,
        mock_create_notification,
        mock_create_engine,
        mock_anomaly_repo_class,
        mock_transaction_repo_class,
        mock_uow_class,
        mock_use_case_class,
        mock_app_config,
    ):
        """
        Given: Custom period provided
        When: run_once is called with period_start and period_end
        Then: Passes custom period to use case
        """
        # Arrange
        mock_app_config.DB_URI = "postgresql+asyncpg://test@localhost/db"
        mock_app_config.ANOMALY_HOURLY_THRESHOLD = 100.0
        mock_app_config.ANOMALY_NOTIFICATION_WEBHOOK = None
        mock_app_config.ANOMALY_DETECTION_ENABLED = True

        # Mock session factory
        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()
        mock_session_factory = MagicMock(return_value=mock_session)
        mock_sessionmaker.return_value = mock_session_factory

        mock_create_engine.return_value = MagicMock()
        mock_create_notification.return_value = MagicMock()

        # Mock use case result
        mock_use_case = MagicMock()
        mock_result = MagicMock()
        mock_result.is_err.return_value = False
        mock_result.value.anomalies_detected = 0
        mock_result.value.anomalies = []
        mock_use_case.execute = AsyncMock(return_value=mock_result)
        mock_use_case_class.return_value = mock_use_case

        custom_start = datetime(2024, 1, 15, 10, 0, 0)
        custom_end = datetime(2024, 1, 15, 11, 0, 0)

        # Act
        worker = AbnormalUsageDetectorWorker()
        await worker.run_once(period_start=custom_start, period_end=custom_end)

        # Assert
        mock_use_case.execute.assert_called_once_with(
            period_start=custom_start,
            period_end=custom_end,
        )
