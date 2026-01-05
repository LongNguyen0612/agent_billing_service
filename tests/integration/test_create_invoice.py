"""Integration tests for CreateInvoice use case (UC-38)

Tests cover:
- AC-3.4.2: Invoice generation with real database
- Duplicate invoice prevention
- Invoice number generation
"""

import pytest
from decimal import Decimal
from datetime import datetime

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.invoice import Invoice, InvoiceStatus
from src.app.use_cases.billing.create_invoice import CreateInvoice
from src.app.use_cases.billing.dtos import CreateInvoiceCommandDTO
from src.adapter.repositories.invoice_repository import SqlAlchemyInvoiceRepository
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork


@pytest.mark.asyncio
class TestCreateInvoiceIntegration:
    """Integration tests with real database"""

    async def test_end_to_end_invoice_creation(self, db_session: AsyncSession):
        """
        Test complete flow: create invoice, verify database state
        """
        # Arrange - setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = CreateInvoice(uow, invoice_repo)

        command = CreateInvoiceCommandDTO(
            tenant_id="tenant_inv_1",
            billing_period_start=datetime(2024, 1, 1, 0, 0, 0),
            billing_period_end=datetime(2024, 1, 31, 23, 59, 59),
            total_amount=Decimal("150.000000"),
            description="Monthly credit allocation - Pro Plan",
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        response = result.value

        assert response.tenant_id == "tenant_inv_1"
        assert response.status == "draft"
        assert response.total_amount == Decimal("150.000000")
        assert response.currency == "USD"
        assert response.invoice_number.startswith("INV-")

        # Verify invoice exists in database
        invoice = await invoice_repo.get_by_id(response.invoice_id)
        assert invoice is not None
        assert invoice.invoice_number == response.invoice_number
        assert invoice.status == InvoiceStatus.DRAFT

    async def test_invoice_number_auto_generation(self, db_session: AsyncSession):
        """
        Test that invoice numbers are auto-generated with correct format
        """
        # Arrange - setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = CreateInvoice(uow, invoice_repo)

        # Act - create multiple invoices
        results = []
        for i in range(3):
            command = CreateInvoiceCommandDTO(
                tenant_id=f"tenant_inv_num_{i}",
                billing_period_start=datetime(2024, 1, 1, 0, 0, 0),
                billing_period_end=datetime(2024, 1, 31, 23, 59, 59),
                total_amount=Decimal("100.000000"),
            )
            result = await use_case.execute(command)
            results.append(result)

        # Assert - all succeed
        assert all(r.is_ok() for r in results)

        # Assert - invoice numbers are unique and sequential
        invoice_numbers = [r.value.invoice_number for r in results]
        assert len(set(invoice_numbers)) == 3  # All unique

        # Assert - format is correct (INV-YYYY-NNNNNN)
        for invoice_number in invoice_numbers:
            assert invoice_number.startswith("INV-")
            parts = invoice_number.split("-")
            assert len(parts) == 3
            assert parts[1].isdigit() and len(parts[1]) == 4  # Year
            assert parts[2].isdigit() and len(parts[2]) == 6  # Sequence

    async def test_duplicate_invoice_prevention(self, db_session: AsyncSession):
        """
        Test that duplicate invoices for same tenant/period are prevented
        """
        # Arrange - setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = CreateInvoice(uow, invoice_repo)

        command = CreateInvoiceCommandDTO(
            tenant_id="tenant_inv_dup",
            billing_period_start=datetime(2024, 2, 1, 0, 0, 0),
            billing_period_end=datetime(2024, 2, 29, 23, 59, 59),
            total_amount=Decimal("200.000000"),
        )

        # Act - create first invoice
        result1 = await use_case.execute(command)

        # Act - try to create duplicate
        result2 = await use_case.execute(command)

        # Assert - first succeeds
        assert result1.is_ok()

        # Assert - second fails with duplicate error
        assert result2.is_err()
        assert result2.error.code == "INVOICE_ALREADY_EXISTS"
        assert "tenant_inv_dup" in result2.error.message

        # Assert - only one invoice in database
        stmt = select(Invoice).where(Invoice.tenant_id == "tenant_inv_dup")
        result = await db_session.execute(stmt)
        invoices = result.scalars().all()
        assert len(invoices) == 1

    async def test_different_billing_periods_allowed(self, db_session: AsyncSession):
        """
        Test that same tenant can have invoices for different billing periods
        """
        # Arrange - setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = CreateInvoice(uow, invoice_repo)

        # Act - create invoices for different months
        results = []
        for month in [1, 2, 3]:
            command = CreateInvoiceCommandDTO(
                tenant_id="tenant_inv_multi",
                billing_period_start=datetime(2024, month, 1, 0, 0, 0),
                billing_period_end=datetime(2024, month, 28, 23, 59, 59),
                total_amount=Decimal("100.000000"),
            )
            result = await use_case.execute(command)
            results.append(result)

        # Assert - all succeed
        assert all(r.is_ok() for r in results)

        # Assert - three invoices in database
        stmt = select(Invoice).where(Invoice.tenant_id == "tenant_inv_multi")
        result = await db_session.execute(stmt)
        invoices = result.scalars().all()
        assert len(invoices) == 3

    async def test_invoice_has_draft_status(self, db_session: AsyncSession):
        """
        Test that all invoices are created with draft status
        """
        # Arrange - setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = CreateInvoice(uow, invoice_repo)

        command = CreateInvoiceCommandDTO(
            tenant_id="tenant_inv_status",
            billing_period_start=datetime(2024, 3, 1, 0, 0, 0),
            billing_period_end=datetime(2024, 3, 31, 23, 59, 59),
            total_amount=Decimal("300.000000"),
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.status == "draft"

        # Verify in database
        invoice = await invoice_repo.get_by_id(result.value.invoice_id)
        assert invoice.status == InvoiceStatus.DRAFT

    async def test_billing_period_dates_stored_correctly(self, db_session: AsyncSession):
        """
        Test that billing period dates are stored correctly
        """
        # Arrange - setup use case
        invoice_repo = SqlAlchemyInvoiceRepository(db_session)
        uow = SqlAlchemyUnitOfWork(db_session)

        use_case = CreateInvoice(uow, invoice_repo)

        command = CreateInvoiceCommandDTO(
            tenant_id="tenant_inv_dates",
            billing_period_start=datetime(2024, 4, 1, 0, 0, 0),
            billing_period_end=datetime(2024, 4, 30, 23, 59, 59),
            total_amount=Decimal("400.000000"),
        )

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()

        # Verify dates in database
        invoice = await invoice_repo.get_by_id(result.value.invoice_id)
        assert invoice.billing_period_start.month == 4
        assert invoice.billing_period_start.day == 1
        assert invoice.billing_period_end.month == 4
        assert invoice.billing_period_end.day == 30
