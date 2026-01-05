"""Integration tests for GenerateProforma use case (UC-39)

Tests the complete flow from use case through database to PDF generation.
"""

import pytest
import base64
from decimal import Decimal
from datetime import datetime, date

from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.invoice import Invoice, InvoiceStatus
from src.domain.invoice_line import InvoiceLine
from src.app.use_cases.billing.generate_proforma import GenerateProforma
from src.adapter.repositories.invoice_repository import SqlAlchemyInvoiceRepository
from src.adapter.repositories.invoice_line_repository import SqlAlchemyInvoiceLineRepository
from src.adapter.services.pdf_service import ReportLabPdfService


@pytest.mark.asyncio
class TestGenerateProformaIntegration:
    """Integration tests for GenerateProforma use case (UC-39)"""

    async def test_generate_proforma_with_line_items(self, db_session: AsyncSession):
        """
        Given: Draft invoice exists in database with line items
        When: GenerateProforma use case is executed
        Then: PDF is generated with invoice data
        """
        # Arrange - Create invoice
        invoice = Invoice(
            tenant_id="tenant_123",
            invoice_number="INV-2024-000001",
            status=InvoiceStatus.DRAFT,
            total_amount=Decimal("150.000000"),
            currency="USD",
            billing_period_start=date(2024, 1, 1),
            billing_period_end=date(2024, 1, 31),
        )
        db_session.add(invoice)
        await db_session.flush()
        await db_session.refresh(invoice)

        # Create invoice line items
        line1 = InvoiceLine(
            invoice_id=invoice.id,
            description="Pipeline execution credits",
            quantity=Decimal("1000.000000"),
            unit_price=Decimal("0.100000"),
            total_price=Decimal("100.000000"),
        )
        line2 = InvoiceLine(
            invoice_id=invoice.id,
            description="Premium model usage",
            quantity=Decimal("50.000000"),
            unit_price=Decimal("1.000000"),
            total_price=Decimal("50.000000"),
        )
        db_session.add_all([line1, line2])
        await db_session.commit()

        # Setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        invoice_line_repo = SqlAlchemyInvoiceLineRepository(db_session)
        pdf_service = ReportLabPdfService()
        use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)

        # Act
        result = await use_case.execute(invoice.id)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.invoice_id == invoice.id
        assert response.invoice_number == "INV-2024-000001"
        assert response.tenant_id == "tenant_123"
        assert response.status == "draft"
        assert response.currency == "USD"
        assert len(response.line_items) == 2

        # Verify PDF is valid base64
        pdf_bytes = base64.b64decode(response.pdf_base64)
        assert pdf_bytes.startswith(b"%PDF")

        # Verify generation timestamp
        assert response.generated_at is not None

    async def test_generate_proforma_without_line_items(self, db_session: AsyncSession):
        """
        Given: Draft invoice exists without line items
        When: GenerateProforma use case is executed
        Then: PDF is generated with invoice data
        """
        # Arrange
        invoice = Invoice(
            tenant_id="tenant_456",
            invoice_number="INV-2024-000002",
            status=InvoiceStatus.DRAFT,
            total_amount=Decimal("200.000000"),
            currency="USD",
            billing_period_start=date(2024, 2, 1),
            billing_period_end=date(2024, 2, 29),
        )
        db_session.add(invoice)
        await db_session.commit()
        await db_session.refresh(invoice)

        # Setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        invoice_line_repo = SqlAlchemyInvoiceLineRepository(db_session)
        pdf_service = ReportLabPdfService()
        use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)

        # Act
        result = await use_case.execute(invoice.id)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.invoice_id == invoice.id
        assert len(response.line_items) == 0

        # Verify PDF is valid
        pdf_bytes = base64.b64decode(response.pdf_base64)
        assert pdf_bytes.startswith(b"%PDF")

    async def test_invoice_not_found(self, db_session: AsyncSession):
        """
        Given: Invoice does not exist
        When: GenerateProforma use case is executed
        Then: Error is returned with INVOICE_NOT_FOUND code
        """
        # Setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        invoice_line_repo = SqlAlchemyInvoiceLineRepository(db_session)
        pdf_service = ReportLabPdfService()
        use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)

        # Act
        result = await use_case.execute(99999)

        # Assert
        assert result.is_err()
        assert result.error.code == "INVOICE_NOT_FOUND"
        assert "99999" in result.error.message

    async def test_invalid_status_issued(self, db_session: AsyncSession):
        """
        Given: Invoice exists with status=issued
        When: GenerateProforma use case is executed
        Then: Error is returned with INVALID_INVOICE_STATUS code
        """
        # Arrange
        invoice = Invoice(
            tenant_id="tenant_789",
            invoice_number="INV-2024-000003",
            status=InvoiceStatus.ISSUED,
            total_amount=Decimal("100.000000"),
            currency="USD",
            billing_period_start=date(2024, 3, 1),
            billing_period_end=date(2024, 3, 31),
            issued_at=datetime.utcnow(),
        )
        db_session.add(invoice)
        await db_session.commit()
        await db_session.refresh(invoice)

        # Setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        invoice_line_repo = SqlAlchemyInvoiceLineRepository(db_session)
        pdf_service = ReportLabPdfService()
        use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)

        # Act
        result = await use_case.execute(invoice.id)

        # Assert
        assert result.is_err()
        assert result.error.code == "INVALID_INVOICE_STATUS"
        assert "issued" in result.error.message

    async def test_invalid_status_paid(self, db_session: AsyncSession):
        """
        Given: Invoice exists with status=paid
        When: GenerateProforma use case is executed
        Then: Error is returned with INVALID_INVOICE_STATUS code
        """
        # Arrange
        invoice = Invoice(
            tenant_id="tenant_paid",
            invoice_number="INV-2024-000004",
            status=InvoiceStatus.PAID,
            total_amount=Decimal("100.000000"),
            currency="USD",
            billing_period_start=date(2024, 4, 1),
            billing_period_end=date(2024, 4, 30),
            issued_at=datetime.utcnow(),
            paid_at=datetime.utcnow(),
        )
        db_session.add(invoice)
        await db_session.commit()
        await db_session.refresh(invoice)

        # Setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        invoice_line_repo = SqlAlchemyInvoiceLineRepository(db_session)
        pdf_service = ReportLabPdfService()
        use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)

        # Act
        result = await use_case.execute(invoice.id)

        # Assert
        assert result.is_err()
        assert result.error.code == "INVALID_INVOICE_STATUS"

    async def test_invalid_status_cancelled(self, db_session: AsyncSession):
        """
        Given: Invoice exists with status=cancelled
        When: GenerateProforma use case is executed
        Then: Error is returned with INVALID_INVOICE_STATUS code
        """
        # Arrange
        invoice = Invoice(
            tenant_id="tenant_cancelled",
            invoice_number="INV-2024-000005",
            status=InvoiceStatus.CANCELLED,
            total_amount=Decimal("100.000000"),
            currency="USD",
            billing_period_start=date(2024, 6, 1),
            billing_period_end=date(2024, 6, 30),
        )
        db_session.add(invoice)
        await db_session.commit()
        await db_session.refresh(invoice)

        # Setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        invoice_line_repo = SqlAlchemyInvoiceLineRepository(db_session)
        pdf_service = ReportLabPdfService()
        use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)

        # Act
        result = await use_case.execute(invoice.id)

        # Assert
        assert result.is_err()
        assert result.error.code == "INVALID_INVOICE_STATUS"

    async def test_pdf_contains_invoice_details(self, db_session: AsyncSession):
        """
        Given: Draft invoice exists
        When: GenerateProforma use case is executed
        Then: PDF contains invoice number in content
        """
        # Arrange
        invoice = Invoice(
            tenant_id="tenant_pdf_test",
            invoice_number="INV-2024-PDF-TEST",
            status=InvoiceStatus.DRAFT,
            total_amount=Decimal("500.000000"),
            currency="USD",
            billing_period_start=date(2024, 7, 1),
            billing_period_end=date(2024, 7, 31),
        )
        db_session.add(invoice)
        await db_session.commit()
        await db_session.refresh(invoice)

        # Setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        invoice_line_repo = SqlAlchemyInvoiceLineRepository(db_session)
        pdf_service = ReportLabPdfService()
        use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)

        # Act
        result = await use_case.execute(invoice.id)

        # Assert
        assert result.is_ok()
        response = result.value

        # PDF should be valid
        pdf_bytes = base64.b64decode(response.pdf_base64)
        assert len(pdf_bytes) > 1000  # PDF should have reasonable size

        # Response should have correct data
        assert response.invoice_number == "INV-2024-PDF-TEST"
        assert response.total_amount == Decimal("500.000000")
