"""Unit tests for CreateInvoice use case (UC-38)

Tests cover:
- AC-3.4.2: Invoice generation on allocation
- Successful invoice creation
- Duplicate invoice prevention
- Invoice number generation
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.app.use_cases.billing.create_invoice import CreateInvoice
from src.app.use_cases.billing.dtos import CreateInvoiceCommandDTO
from src.domain.invoice import Invoice, InvoiceStatus


@pytest.fixture
def mock_invoice_repo():
    """Mock invoice repository"""
    return MagicMock()


@pytest.fixture
def create_invoice_use_case(mock_uow, mock_invoice_repo):
    """CreateInvoice use case instance with mocked dependencies"""
    return CreateInvoice(
        uow=mock_uow,
        invoice_repo=mock_invoice_repo,
    )


@pytest.fixture
def sample_command():
    """Sample CreateInvoiceCommandDTO"""
    return CreateInvoiceCommandDTO(
        tenant_id="tenant_123",
        billing_period_start=datetime(2024, 1, 1, 0, 0, 0),
        billing_period_end=datetime(2024, 1, 31, 23, 59, 59),
        total_amount=Decimal("150.000000"),
        description="Monthly credit allocation - Pro Plan",
    )


@pytest.mark.asyncio
class TestCreateInvoiceSuccess:
    """Test successful invoice creation (AC-3.4.2)"""

    async def test_create_invoice_success(
        self, create_invoice_use_case, mock_invoice_repo, mock_uow, sample_command
    ):
        """
        Given: No existing invoice for the billing period
        When: create_invoice is called
        Then: Draft invoice is created with auto-generated number
        """
        # Arrange
        mock_invoice_repo.exists_for_period = AsyncMock(return_value=False)
        mock_invoice_repo.generate_invoice_number = AsyncMock(return_value="INV-2024-000001")
        mock_invoice_repo.create = AsyncMock(
            return_value=Invoice(
                id=1,
                tenant_id="tenant_123",
                invoice_number="INV-2024-000001",
                status=InvoiceStatus.DRAFT,
                total_amount=Decimal("150.000000"),
                currency="USD",
                billing_period_start=datetime(2024, 1, 1).date(),
                billing_period_end=datetime(2024, 1, 31).date(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
        )

        # Act
        result = await create_invoice_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response data
        assert response.invoice_id == 1
        assert response.tenant_id == "tenant_123"
        assert response.invoice_number == "INV-2024-000001"
        assert response.status == "draft"
        assert response.total_amount == Decimal("150.000000")
        assert response.currency == "USD"

        # Verify repository interactions
        mock_invoice_repo.exists_for_period.assert_called_once()
        mock_invoice_repo.generate_invoice_number.assert_called_once()
        mock_invoice_repo.create.assert_called_once()
        mock_uow.commit.assert_called_once()

    async def test_invoice_has_correct_billing_period(
        self, create_invoice_use_case, mock_invoice_repo, mock_uow
    ):
        """Test that invoice billing period dates are stored correctly"""
        # Arrange
        command = CreateInvoiceCommandDTO(
            tenant_id="tenant_123",
            billing_period_start=datetime(2024, 2, 1, 0, 0, 0),
            billing_period_end=datetime(2024, 2, 29, 23, 59, 59),
            total_amount=Decimal("200.000000"),
        )

        mock_invoice_repo.exists_for_period = AsyncMock(return_value=False)
        mock_invoice_repo.generate_invoice_number = AsyncMock(return_value="INV-2024-000002")

        created_invoice = None
        async def capture_invoice(invoice):
            nonlocal created_invoice
            created_invoice = invoice
            created_invoice.id = 2
            created_invoice.created_at = datetime.utcnow()
            created_invoice.updated_at = datetime.utcnow()
            return created_invoice

        mock_invoice_repo.create = AsyncMock(side_effect=capture_invoice)

        # Act
        result = await create_invoice_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert created_invoice.billing_period_start.month == 2
        assert created_invoice.billing_period_start.day == 1
        assert created_invoice.billing_period_end.month == 2
        assert created_invoice.billing_period_end.day == 29

    async def test_invoice_created_with_draft_status(
        self, create_invoice_use_case, mock_invoice_repo, mock_uow, sample_command
    ):
        """Test that invoice is always created with draft status"""
        # Arrange
        mock_invoice_repo.exists_for_period = AsyncMock(return_value=False)
        mock_invoice_repo.generate_invoice_number = AsyncMock(return_value="INV-2024-000003")

        created_invoice = None
        async def capture_invoice(invoice):
            nonlocal created_invoice
            created_invoice = invoice
            created_invoice.id = 3
            created_invoice.created_at = datetime.utcnow()
            created_invoice.updated_at = datetime.utcnow()
            return created_invoice

        mock_invoice_repo.create = AsyncMock(side_effect=capture_invoice)

        # Act
        result = await create_invoice_use_case.execute(sample_command)

        # Assert
        assert result.is_ok()
        assert created_invoice.status == InvoiceStatus.DRAFT


@pytest.mark.asyncio
class TestCreateInvoiceDuplicatePrevention:
    """Test duplicate invoice prevention"""

    async def test_duplicate_invoice_error(
        self, create_invoice_use_case, mock_invoice_repo, mock_uow, sample_command
    ):
        """
        Given: Invoice already exists for the billing period
        When: create_invoice is called
        Then: Error returned, no invoice created
        """
        # Arrange
        mock_invoice_repo.exists_for_period = AsyncMock(return_value=True)

        # Act
        result = await create_invoice_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        error = result.error

        assert error.code == "INVOICE_ALREADY_EXISTS"
        assert "tenant_123" in error.message

        # Verify no invoice created
        mock_invoice_repo.generate_invoice_number.assert_not_called()
        mock_invoice_repo.create.assert_not_called()
        mock_uow.commit.assert_not_called()


@pytest.mark.asyncio
class TestCreateInvoiceErrorHandling:
    """Test error handling and rollback"""

    async def test_rollback_on_exception(
        self, create_invoice_use_case, mock_invoice_repo, mock_uow, sample_command
    ):
        """Test that UoW rollback is called on exception"""
        # Arrange
        mock_invoice_repo.exists_for_period = AsyncMock(return_value=False)
        mock_invoice_repo.generate_invoice_number = AsyncMock(return_value="INV-2024-000004")
        mock_invoice_repo.create = AsyncMock(side_effect=Exception("Database error"))

        # Act
        result = await create_invoice_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        mock_uow.rollback.assert_called_once()
        assert result.error.code == "CREATE_INVOICE_FAILED"

    async def test_error_on_invoice_number_generation_failure(
        self, create_invoice_use_case, mock_invoice_repo, mock_uow, sample_command
    ):
        """Test error handling when invoice number generation fails"""
        # Arrange
        mock_invoice_repo.exists_for_period = AsyncMock(return_value=False)
        mock_invoice_repo.generate_invoice_number = AsyncMock(side_effect=Exception("Sequence error"))

        # Act
        result = await create_invoice_use_case.execute(sample_command)

        # Assert
        assert result.is_err()
        assert result.error.code == "CREATE_INVOICE_FAILED"
