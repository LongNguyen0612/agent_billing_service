"""Unit tests for GetBalance use case"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from decimal import Decimal

from src.app.use_cases.billing.get_balance import GetBalance
from src.domain.credit_ledger import CreditLedger


class TestGetBalance:
    """Test suite for GetBalance use case"""

    @pytest.fixture
    def mock_ledger_repo(self):
        """Create mock credit ledger repository"""
        return AsyncMock()

    @pytest.fixture
    def use_case(self, mock_ledger_repo):
        """Create GetBalance use case instance"""
        return GetBalance(ledger_repo=mock_ledger_repo)

    @pytest.mark.asyncio
    async def test_successful_balance_retrieval(self, use_case, mock_ledger_repo):
        """Test AC-1.4.1: Successful balance retrieval"""
        # Arrange
        tenant_id = "tenant_123"
        mock_ledger = MagicMock(spec=CreditLedger)
        mock_ledger.tenant_id = tenant_id
        mock_ledger.balance = Decimal("1000.50")
        mock_ledger.updated_at = datetime(2024, 1, 1, 12, 0, 0)

        mock_ledger_repo.get_by_tenant_id.return_value = mock_ledger

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        response = result.value
        assert response.tenant_id == tenant_id
        assert response.balance == Decimal("1000.50")
        assert response.last_updated == datetime(2024, 1, 1, 12, 0, 0)
        mock_ledger_repo.get_by_tenant_id.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_tenant_not_found(self, use_case, mock_ledger_repo):
        """Test AC-1.4.2: Tenant not found returns error"""
        # Arrange
        tenant_id = "nonexistent_tenant"
        mock_ledger_repo.get_by_tenant_id.return_value = None

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "LEDGER_NOT_FOUND"
        assert tenant_id in error.message
        mock_ledger_repo.get_by_tenant_id.assert_called_once_with(tenant_id)

    @pytest.mark.asyncio
    async def test_balance_value_accuracy(self, use_case, mock_ledger_repo):
        """Test that balance value is accurately returned"""
        # Arrange
        tenant_id = "tenant_456"
        expected_balance = Decimal("523.750000")
        mock_ledger = MagicMock(spec=CreditLedger)
        mock_ledger.tenant_id = tenant_id
        mock_ledger.balance = expected_balance
        mock_ledger.updated_at = datetime.now()

        mock_ledger_repo.get_by_tenant_id.return_value = mock_ledger

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        assert result.value.balance == expected_balance

    @pytest.mark.asyncio
    async def test_zero_balance(self, use_case, mock_ledger_repo):
        """Test that zero balance is handled correctly"""
        # Arrange
        tenant_id = "tenant_789"
        mock_ledger = MagicMock(spec=CreditLedger)
        mock_ledger.tenant_id = tenant_id
        mock_ledger.balance = Decimal("0.00")
        mock_ledger.updated_at = datetime.now()

        mock_ledger_repo.get_by_tenant_id.return_value = mock_ledger

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        assert result.value.balance == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_negative_balance(self, use_case, mock_ledger_repo):
        """Test that negative balance (overdraft) is handled correctly"""
        # Arrange
        tenant_id = "tenant_overdraft"
        mock_ledger = MagicMock(spec=CreditLedger)
        mock_ledger.tenant_id = tenant_id
        mock_ledger.balance = Decimal("-50.00")
        mock_ledger.updated_at = datetime.now()

        mock_ledger_repo.get_by_tenant_id.return_value = mock_ledger

        # Act
        result = await use_case.execute(tenant_id)

        # Assert
        assert result.is_ok()
        assert result.value.balance == Decimal("-50.00")
