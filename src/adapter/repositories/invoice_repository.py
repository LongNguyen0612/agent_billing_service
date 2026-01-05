"""SQLAlchemy Invoice Repository Implementation

Implements invoice persistence using SQLAlchemy async session.
"""

from typing import Optional, List
from datetime import date, datetime
from sqlmodel import select, func
from sqlmodel.ext.asyncio.session import AsyncSession
from src.app.repositories.invoice_repository import InvoiceRepository
from src.domain.invoice import Invoice, InvoiceStatus


class SqlAlchemyInvoiceRepository(InvoiceRepository):
    """
    SQLAlchemy implementation of InvoiceRepository

    Uses async session for database operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, invoice: Invoice) -> Invoice:
        """
        Create a new invoice

        Args:
            invoice: Invoice entity to persist

        Returns:
            Created Invoice with generated ID
        """
        self.session.add(invoice)
        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def get_by_id(self, invoice_id: int) -> Optional[Invoice]:
        """
        Retrieve invoice by ID

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice if found, None otherwise
        """
        statement = select(Invoice).where(Invoice.id == invoice_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_tenant_id(
        self,
        tenant_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Invoice]:
        """
        Retrieve invoices by tenant ID

        Args:
            tenant_id: Tenant identifier
            status: Optional filter by status
            limit: Maximum number of invoices to return
            offset: Offset for pagination

        Returns:
            List of invoices
        """
        statement = select(Invoice).where(Invoice.tenant_id == tenant_id)

        if status:
            statement = statement.where(Invoice.status == status)

        statement = statement.order_by(Invoice.created_at.desc())
        statement = statement.limit(limit).offset(offset)

        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_by_invoice_number(self, invoice_number: str) -> Optional[Invoice]:
        """
        Retrieve invoice by invoice number

        Args:
            invoice_number: Unique invoice number

        Returns:
            Invoice if found, None otherwise
        """
        statement = select(Invoice).where(Invoice.invoice_number == invoice_number)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def update(self, invoice: Invoice) -> Invoice:
        """
        Update an existing invoice

        Args:
            invoice: Invoice entity with updated values

        Returns:
            Updated Invoice
        """
        invoice.updated_at = datetime.utcnow()
        self.session.add(invoice)
        await self.session.flush()
        await self.session.refresh(invoice)
        return invoice

    async def exists_for_period(
        self, tenant_id: str, billing_period_start: date, billing_period_end: date
    ) -> bool:
        """
        Check if invoice already exists for the given billing period

        Args:
            tenant_id: Tenant identifier
            billing_period_start: Start of billing period
            billing_period_end: End of billing period

        Returns:
            True if invoice exists, False otherwise
        """
        statement = (
            select(func.count())
            .select_from(Invoice)
            .where(Invoice.tenant_id == tenant_id)
            .where(Invoice.billing_period_start == billing_period_start)
            .where(Invoice.billing_period_end == billing_period_end)
        )
        result = await self.session.execute(statement)
        count = result.scalar_one()
        return count > 0

    async def generate_invoice_number(self) -> str:
        """
        Generate a unique invoice number

        Format: INV-YYYY-NNNNNN (e.g., INV-2024-000001)

        Returns:
            Unique invoice number string
        """
        year = datetime.utcnow().year
        prefix = f"INV-{year}-"

        # Get the highest invoice number for this year
        statement = (
            select(func.max(Invoice.invoice_number))
            .where(Invoice.invoice_number.like(f"{prefix}%"))
        )
        result = await self.session.execute(statement)
        max_number = result.scalar_one_or_none()

        if max_number:
            # Extract the sequence number and increment
            sequence = int(max_number.split("-")[-1]) + 1
        else:
            sequence = 1

        return f"{prefix}{sequence:06d}"
