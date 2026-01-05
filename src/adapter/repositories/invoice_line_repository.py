"""SQLAlchemy Invoice Line Repository Implementation

Implements invoice line persistence using SQLAlchemy async session.
"""

from typing import List
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.app.repositories.invoice_line_repository import InvoiceLineRepository
from src.domain.invoice_line import InvoiceLine


class SqlAlchemyInvoiceLineRepository(InvoiceLineRepository):
    """
    SQLAlchemy implementation of InvoiceLineRepository

    Uses async session for database operations.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_invoice_id(self, invoice_id: int) -> List[InvoiceLine]:
        """
        Retrieve all line items for an invoice

        Args:
            invoice_id: Invoice ID

        Returns:
            List of InvoiceLine items
        """
        statement = select(InvoiceLine).where(InvoiceLine.invoice_id == invoice_id)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def create(self, invoice_line: InvoiceLine) -> InvoiceLine:
        """
        Create a new invoice line item

        Args:
            invoice_line: InvoiceLine entity to persist

        Returns:
            Created InvoiceLine with generated ID
        """
        self.session.add(invoice_line)
        await self.session.flush()
        await self.session.refresh(invoice_line)
        return invoice_line
