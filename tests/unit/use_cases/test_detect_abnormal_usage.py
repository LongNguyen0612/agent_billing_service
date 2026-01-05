"""Unit tests for DetectAbnormalUsage use case (UC-37)

Tests cover:
- AC-3.3.1: Threshold detection
- AC-3.3.2: Configurable thresholds
- Duplicate anomaly prevention
- Error handling
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta

from src.app.use_cases.billing.detect_abnormal_usage import DetectAbnormalUsage
from src.domain.usage_anomaly import UsageAnomaly, AnomalyType, AnomalyStatus


@pytest.fixture
def mock_transaction_repo():
    """Mock credit transaction repository"""
    return MagicMock()


@pytest.fixture
def mock_anomaly_repo():
    """Mock usage anomaly repository"""
    return MagicMock()


@pytest.fixture
def detect_use_case(mock_uow, mock_transaction_repo, mock_anomaly_repo):
    """DetectAbnormalUsage use case instance with mocked dependencies"""
    return DetectAbnormalUsage(
        uow=mock_uow,
        transaction_repo=mock_transaction_repo,
        anomaly_repo=mock_anomaly_repo,
        threshold=Decimal("100.000000"),
        anomaly_type=AnomalyType.HOURLY_THRESHOLD,
    )


@pytest.fixture
def sample_period():
    """Sample detection period (last hour)"""
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    return {
        "start": now - timedelta(hours=1),
        "end": now,
    }


@pytest.mark.asyncio
class TestDetectAbnormalUsageThresholdDetection:
    """Test threshold detection (AC-3.3.1)"""

    async def test_detects_tenant_exceeding_threshold(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow, sample_period
    ):
        """
        Given: Tenant's hourly usage exceeds threshold
        When: Detection job runs
        Then: Anomaly is created and alert is logged
        """
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_123", Decimal("150.500000")),  # Exceeds threshold
            ]
        )
        mock_anomaly_repo.exists_for_tenant_period = AsyncMock(return_value=False)

        created_anomaly = None
        async def capture_anomaly(anomaly):
            nonlocal created_anomaly
            created_anomaly = anomaly
            created_anomaly.id = 1
            return created_anomaly

        mock_anomaly_repo.create = AsyncMock(side_effect=capture_anomaly)

        # Act
        result = await detect_use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.anomalies_detected == 1
        assert len(response.anomalies) == 1
        assert response.anomalies[0].tenant_id == "tenant_123"
        assert response.anomalies[0].actual_value == Decimal("150.500000")
        assert response.anomalies[0].threshold_value == Decimal("100.000000")
        assert response.threshold_used == Decimal("100.000000")

        # Verify anomaly was created
        mock_anomaly_repo.create.assert_called_once()
        assert created_anomaly.tenant_id == "tenant_123"
        assert created_anomaly.anomaly_type == AnomalyType.HOURLY_THRESHOLD
        assert created_anomaly.status == AnomalyStatus.DETECTED

        mock_uow.commit.assert_called_once()

    async def test_ignores_tenant_below_threshold(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow, sample_period
    ):
        """
        Given: Tenant's hourly usage is below threshold
        When: Detection job runs
        Then: No anomaly is created
        """
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_123", Decimal("50.000000")),  # Below threshold
                ("tenant_456", Decimal("99.999999")),  # Just below threshold
            ]
        )

        # Act
        result = await detect_use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.anomalies_detected == 0
        assert len(response.anomalies) == 0

        mock_anomaly_repo.create.assert_not_called()
        mock_uow.commit.assert_called_once()

    async def test_detects_multiple_tenants_exceeding_threshold(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow, sample_period
    ):
        """
        Given: Multiple tenants exceed threshold
        When: Detection job runs
        Then: Anomalies created for all exceeding tenants
        """
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_123", Decimal("150.000000")),  # Exceeds
                ("tenant_456", Decimal("80.000000")),   # Below
                ("tenant_789", Decimal("200.000000")),  # Exceeds
            ]
        )
        mock_anomaly_repo.exists_for_tenant_period = AsyncMock(return_value=False)

        anomaly_id = 0
        async def create_anomaly(anomaly):
            nonlocal anomaly_id
            anomaly_id += 1
            anomaly.id = anomaly_id
            return anomaly

        mock_anomaly_repo.create = AsyncMock(side_effect=create_anomaly)

        # Act
        result = await detect_use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.anomalies_detected == 2
        assert len(response.anomalies) == 2

        tenant_ids = [a.tenant_id for a in response.anomalies]
        assert "tenant_123" in tenant_ids
        assert "tenant_789" in tenant_ids
        assert "tenant_456" not in tenant_ids

        assert mock_anomaly_repo.create.call_count == 2


@pytest.mark.asyncio
class TestDetectAbnormalUsageConfigurableThresholds:
    """Test configurable thresholds (AC-3.3.2)"""

    async def test_uses_custom_threshold(
        self, mock_uow, mock_transaction_repo, mock_anomaly_repo, sample_period
    ):
        """
        Given: Admin sets custom usage threshold
        When: Detection is run with new threshold
        Then: New threshold applies to detection
        """
        # Arrange - create use case with custom threshold
        use_case = DetectAbnormalUsage(
            uow=mock_uow,
            transaction_repo=mock_transaction_repo,
            anomaly_repo=mock_anomaly_repo,
            threshold=Decimal("50.000000"),  # Lower threshold
            anomaly_type=AnomalyType.HOURLY_THRESHOLD,
        )

        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_123", Decimal("75.000000")),  # Exceeds 50, below 100
            ]
        )
        mock_anomaly_repo.exists_for_tenant_period = AsyncMock(return_value=False)

        async def create_anomaly(anomaly):
            anomaly.id = 1
            return anomaly

        mock_anomaly_repo.create = AsyncMock(side_effect=create_anomaly)

        # Act
        result = await use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.anomalies_detected == 1
        assert response.threshold_used == Decimal("50.000000")

    async def test_different_anomaly_types(
        self, mock_uow, mock_transaction_repo, mock_anomaly_repo, sample_period
    ):
        """Test that anomaly type is configurable"""
        # Arrange
        use_case = DetectAbnormalUsage(
            uow=mock_uow,
            transaction_repo=mock_transaction_repo,
            anomaly_repo=mock_anomaly_repo,
            threshold=Decimal("500.000000"),
            anomaly_type=AnomalyType.DAILY_THRESHOLD,
        )

        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_123", Decimal("600.000000")),
            ]
        )
        mock_anomaly_repo.exists_for_tenant_period = AsyncMock(return_value=False)

        created_anomaly = None
        async def capture_anomaly(anomaly):
            nonlocal created_anomaly
            created_anomaly = anomaly
            created_anomaly.id = 1
            return created_anomaly

        mock_anomaly_repo.create = AsyncMock(side_effect=capture_anomaly)

        # Act
        result = await use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        assert created_anomaly.anomaly_type == AnomalyType.DAILY_THRESHOLD


@pytest.mark.asyncio
class TestDetectAbnormalUsageDuplicatePrevention:
    """Test duplicate anomaly prevention"""

    async def test_skips_existing_anomaly_for_same_period(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow, sample_period
    ):
        """
        Given: Anomaly already exists for tenant in the period
        When: Detection job runs
        Then: No duplicate anomaly is created
        """
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_123", Decimal("150.000000")),
            ]
        )
        # Anomaly already exists
        mock_anomaly_repo.exists_for_tenant_period = AsyncMock(return_value=True)

        # Act
        result = await detect_use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.anomalies_detected == 0
        mock_anomaly_repo.create.assert_not_called()

    async def test_creates_anomaly_for_different_period(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow
    ):
        """
        Given: Anomaly exists for a different period
        When: Detection runs for new period
        Then: New anomaly is created
        """
        # Arrange - new period
        now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        new_period_start = now - timedelta(hours=1)
        new_period_end = now

        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_123", Decimal("150.000000")),
            ]
        )
        # No anomaly for this period
        mock_anomaly_repo.exists_for_tenant_period = AsyncMock(return_value=False)

        async def create_anomaly(anomaly):
            anomaly.id = 1
            return anomaly

        mock_anomaly_repo.create = AsyncMock(side_effect=create_anomaly)

        # Act
        result = await detect_use_case.execute(
            period_start=new_period_start,
            period_end=new_period_end,
        )

        # Assert
        assert result.is_ok()
        assert result.value.anomalies_detected == 1
        mock_anomaly_repo.create.assert_called_once()


@pytest.mark.asyncio
class TestDetectAbnormalUsageDefaultPeriod:
    """Test default period calculation"""

    async def test_uses_previous_hour_as_default_period(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow
    ):
        """
        Given: No period specified
        When: Detection is run
        Then: Uses previous hour as default period
        """
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(return_value=[])

        # Act
        result = await detect_use_case.execute()

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify period is approximately previous hour
        now = datetime.utcnow()
        expected_end = now.replace(minute=0, second=0, microsecond=0)
        expected_start = expected_end - timedelta(hours=1)

        # Allow some tolerance for execution time
        assert abs((response.period_end - expected_end).total_seconds()) < 10
        assert abs((response.period_start - expected_start).total_seconds()) < 10


@pytest.mark.asyncio
class TestDetectAbnormalUsageErrorHandling:
    """Test error handling and rollback"""

    async def test_rollback_on_exception(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow, sample_period
    ):
        """Test that UoW rollback is called on exception"""
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            side_effect=Exception("Database error")
        )

        # Act
        result = await detect_use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_err()
        mock_uow.rollback.assert_called_once()
        assert result.error.code == "DETECTION_FAILED"

    async def test_handles_empty_consumption_data(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow, sample_period
    ):
        """Test detection with no consumption data"""
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(return_value=[])

        # Act
        result = await detect_use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.anomalies_detected == 0
        assert len(response.anomalies) == 0
        mock_anomaly_repo.create.assert_not_called()


@pytest.mark.asyncio
class TestDetectAbnormalUsageAnomalyDescription:
    """Test anomaly description generation"""

    async def test_anomaly_has_descriptive_message(
        self, detect_use_case, mock_transaction_repo, mock_anomaly_repo, mock_uow, sample_period
    ):
        """Test that created anomaly has a descriptive message"""
        # Arrange
        mock_transaction_repo.get_consumption_by_period = AsyncMock(
            return_value=[
                ("tenant_xyz", Decimal("175.500000")),
            ]
        )
        mock_anomaly_repo.exists_for_tenant_period = AsyncMock(return_value=False)

        created_anomaly = None
        async def capture_anomaly(anomaly):
            nonlocal created_anomaly
            created_anomaly = anomaly
            created_anomaly.id = 1
            return created_anomaly

        mock_anomaly_repo.create = AsyncMock(side_effect=capture_anomaly)

        # Act
        result = await detect_use_case.execute(
            period_start=sample_period["start"],
            period_end=sample_period["end"],
        )

        # Assert
        assert result.is_ok()
        assert created_anomaly.description is not None
        assert "tenant_xyz" in created_anomaly.description
        assert "175.500000" in created_anomaly.description or "175.5" in created_anomaly.description
        assert "100.000000" in created_anomaly.description or "100" in created_anomaly.description
