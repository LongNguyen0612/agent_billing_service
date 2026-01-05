"""Unit tests for GenerateProforma use case (UC-39)

Tests cover:
- AC-3.5.1: Generate PDF for draft invoice
- Invoice not found error
- Invalid status error (non-draft)
- PDF generation with line items
- PDF generation without line items
"""

import pytest
import base64
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, date

from src.app.use_cases.billing.generate_proforma import GenerateProforma
from src.domain.invoice import Invoice, InvoiceStatus
from src.domain.invoice_line import InvoiceLine


@pytest.fixture
def mock_invoice_repo():
    """Mock invoice repository"""
    return MagicMock()


@pytest.fixture
def mock_invoice_line_repo():
    """Mock invoice line repository"""
    return MagicMock()


@pytest.fixture
def mock_pdf_service():
    """Mock PDF service"""
    return MagicMock()


@pytest.fixture
def generate_proforma_use_case(mock_invoice_repo, mock_invoice_line_repo, mock_pdf_service):
    """GenerateProforma use case instance with mocked dependencies"""
    return GenerateProforma(
        invoice_repo=mock_invoice_repo,
        invoice_line_repo=mock_invoice_line_repo,
        pdf_service=mock_pdf_service,
    )


@pytest.fixture
def sample_draft_invoice():
    """Sample draft invoice for testing"""
    return Invoice(
        id=1,
        tenant_id="tenant_123",
        invoice_number="INV-2024-000001",
        status=InvoiceStatus.DRAFT,
        total_amount=Decimal("150.000000"),
        currency="USD",
        billing_period_start=date(2024, 1, 1),
        billing_period_end=date(2024, 1, 31),
        created_at=datetime(2024, 1, 31, 12, 0, 0),
        updated_at=datetime(2024, 1, 31, 12, 0, 0),
    )


@pytest.fixture
def sample_invoice_lines():
    """Sample invoice line items for testing"""
    return [
        InvoiceLine(
            id=1,
            invoice_id=1,
            description="Pipeline execution credits",
            quantity=Decimal("1000.000000"),
            unit_price=Decimal("0.100000"),
            total_price=Decimal("100.000000"),
            created_at=datetime(2024, 1, 31, 12, 0, 0),
        ),
        InvoiceLine(
            id=2,
            invoice_id=1,
            description="Premium model usage",
            quantity=Decimal("50.000000"),
            unit_price=Decimal("1.000000"),
            total_price=Decimal("50.000000"),
            created_at=datetime(2024, 1, 31, 12, 0, 0),
        ),
    ]


@pytest.fixture
def sample_pdf_bytes():
    """Sample PDF bytes for testing"""
    return b"%PDF-1.4\nTest PDF content"


@pytest.mark.asyncio
class TestGenerateProformaSuccess:
    """Test successful proforma invoice generation (AC-3.5.1)"""

    async def test_generate_proforma_with_line_items(
        self,
        generate_proforma_use_case,
        mock_invoice_repo,
        mock_invoice_line_repo,
        mock_pdf_service,
        sample_draft_invoice,
        sample_invoice_lines,
        sample_pdf_bytes,
    ):
        """
        Given: Draft invoice exists with line items
        When: generate_proforma is called
        Then: PDF is generated with invoice data and returned as base64
        """
        # Arrange
        mock_invoice_repo.get_by_id = AsyncMock(return_value=sample_draft_invoice)
        mock_invoice_line_repo.get_by_invoice_id = AsyncMock(return_value=sample_invoice_lines)
        mock_pdf_service.generate_proforma_invoice = MagicMock(return_value=sample_pdf_bytes)

        # Act
        result = await generate_proforma_use_case.execute(invoice_id=1)

        # Assert
        assert result.is_ok()
        response = result.value

        # Verify response data
        assert response.invoice_id == 1
        assert response.invoice_number == "INV-2024-000001"
        assert response.tenant_id == "tenant_123"
        assert response.status == "draft"
        assert response.total_amount == Decimal("150.000000")
        assert response.currency == "USD"
        assert len(response.line_items) == 2
        assert response.line_items[0].description == "Pipeline execution credits"
        assert response.line_items[1].description == "Premium model usage"

        # Verify PDF is base64 encoded
        decoded_pdf = base64.b64decode(response.pdf_base64)
        assert decoded_pdf == sample_pdf_bytes

        # Verify generation timestamp is set
        assert response.generated_at is not None

        # Verify repository interactions
        mock_invoice_repo.get_by_id.assert_called_once_with(1)
        mock_invoice_line_repo.get_by_invoice_id.assert_called_once_with(1)
        mock_pdf_service.generate_proforma_invoice.assert_called_once()

    async def test_generate_proforma_without_line_items(
        self,
        generate_proforma_use_case,
        mock_invoice_repo,
        mock_invoice_line_repo,
        mock_pdf_service,
        sample_draft_invoice,
        sample_pdf_bytes,
    ):
        """
        Given: Draft invoice exists without line items
        When: generate_proforma is called
        Then: PDF is generated with invoice data (empty line items)
        """
        # Arrange
        mock_invoice_repo.get_by_id = AsyncMock(return_value=sample_draft_invoice)
        mock_invoice_line_repo.get_by_invoice_id = AsyncMock(return_value=[])
        mock_pdf_service.generate_proforma_invoice = MagicMock(return_value=sample_pdf_bytes)

        # Act
        result = await generate_proforma_use_case.execute(invoice_id=1)

        # Assert
        assert result.is_ok()
        response = result.value

        assert len(response.line_items) == 0
        assert response.invoice_id == 1

        # Verify PDF was generated
        decoded_pdf = base64.b64decode(response.pdf_base64)
        assert decoded_pdf == sample_pdf_bytes

    async def test_pdf_service_receives_correct_data(
        self,
        generate_proforma_use_case,
        mock_invoice_repo,
        mock_invoice_line_repo,
        mock_pdf_service,
        sample_draft_invoice,
        sample_invoice_lines,
        sample_pdf_bytes,
    ):
        """Test that PDF service receives invoice and line items correctly"""
        # Arrange
        mock_invoice_repo.get_by_id = AsyncMock(return_value=sample_draft_invoice)
        mock_invoice_line_repo.get_by_invoice_id = AsyncMock(return_value=sample_invoice_lines)
        mock_pdf_service.generate_proforma_invoice = MagicMock(return_value=sample_pdf_bytes)

        # Act
        await generate_proforma_use_case.execute(invoice_id=1)

        # Assert
        call_args = mock_pdf_service.generate_proforma_invoice.call_args
        assert call_args.kwargs["invoice"] == sample_draft_invoice
        assert call_args.kwargs["invoice_lines"] == sample_invoice_lines


@pytest.mark.asyncio
class TestGenerateProformaInvoiceNotFound:
    """Test invoice not found error"""

    async def test_invoice_not_found_error(
        self,
        generate_proforma_use_case,
        mock_invoice_repo,
        mock_invoice_line_repo,
        mock_pdf_service,
    ):
        """
        Given: Invoice does not exist
        When: generate_proforma is called
        Then: Error is returned with INVOICE_NOT_FOUND code
        """
        # Arrange
        mock_invoice_repo.get_by_id = AsyncMock(return_value=None)

        # Act
        result = await generate_proforma_use_case.execute(invoice_id=999)

        # Assert
        assert result.is_err()
        error = result.error

        assert error.code == "INVOICE_NOT_FOUND"
        assert "999" in error.message

        # Verify no further processing
        mock_invoice_line_repo.get_by_invoice_id.assert_not_called()
        mock_pdf_service.generate_proforma_invoice.assert_not_called()


@pytest.mark.asyncio
class TestGenerateProformaInvalidStatus:
    """Test invalid invoice status errors"""

    @pytest.mark.parametrize(
        "status",
        [InvoiceStatus.ISSUED, InvoiceStatus.PAID, InvoiceStatus.CANCELLED],
    )
    async def test_non_draft_invoice_error(
        self,
        generate_proforma_use_case,
        mock_invoice_repo,
        mock_invoice_line_repo,
        mock_pdf_service,
        status,
    ):
        """
        Given: Invoice exists but is not in draft status
        When: generate_proforma is called
        Then: Error is returned with INVALID_INVOICE_STATUS code
        """
        # Arrange
        non_draft_invoice = Invoice(
            id=1,
            tenant_id="tenant_123",
            invoice_number="INV-2024-000001",
            status=status,
            total_amount=Decimal("150.000000"),
            currency="USD",
            billing_period_start=date(2024, 1, 1),
            billing_period_end=date(2024, 1, 31),
            created_at=datetime(2024, 1, 31, 12, 0, 0),
            updated_at=datetime(2024, 1, 31, 12, 0, 0),
        )
        mock_invoice_repo.get_by_id = AsyncMock(return_value=non_draft_invoice)

        # Act
        result = await generate_proforma_use_case.execute(invoice_id=1)

        # Assert
        assert result.is_err()
        error = result.error

        assert error.code == "INVALID_INVOICE_STATUS"
        assert status.value in error.message

        # Verify no PDF generation attempted
        mock_invoice_line_repo.get_by_invoice_id.assert_not_called()
        mock_pdf_service.generate_proforma_invoice.assert_not_called()


@pytest.mark.asyncio
class TestGenerateProformaErrorHandling:
    """Test error handling"""

    async def test_pdf_generation_failure(
        self,
        generate_proforma_use_case,
        mock_invoice_repo,
        mock_invoice_line_repo,
        mock_pdf_service,
        sample_draft_invoice,
        sample_invoice_lines,
    ):
        """Test error handling when PDF generation fails"""
        # Arrange
        mock_invoice_repo.get_by_id = AsyncMock(return_value=sample_draft_invoice)
        mock_invoice_line_repo.get_by_invoice_id = AsyncMock(return_value=sample_invoice_lines)
        mock_pdf_service.generate_proforma_invoice = MagicMock(
            side_effect=Exception("PDF generation error")
        )

        # Act
        result = await generate_proforma_use_case.execute(invoice_id=1)

        # Assert
        assert result.is_err()
        assert result.error.code == "GENERATE_PROFORMA_FAILED"
        assert "PDF generation error" in result.error.reason

    async def test_repository_failure(
        self,
        generate_proforma_use_case,
        mock_invoice_repo,
        mock_invoice_line_repo,
        mock_pdf_service,
    ):
        """Test error handling when repository fails"""
        # Arrange
        mock_invoice_repo.get_by_id = AsyncMock(side_effect=Exception("Database error"))

        # Act
        result = await generate_proforma_use_case.execute(invoice_id=1)

        # Assert
        assert result.is_err()
        assert result.error.code == "GENERATE_PROFORMA_FAILED"
