"""Invoice Line Repository Interface

Defines the contract for invoice line persistence operations.
"""

from abc import ABC, abstractmethod
from typing import List
from src.domain.invoice_line import InvoiceLine


class InvoiceLineRepository(ABC):
    """
    Repository interface for InvoiceLine persistence

    Provides access to invoice line items for billing operations.
    """

    @abstractmethod
    async def get_by_invoice_id(self, invoice_id: int) -> List[InvoiceLine]:
        """
        Retrieve all line items for an invoice

        Args:
            invoice_id: Invoice ID

        Returns:
            List of InvoiceLine items
        """
        pass

    @abstractmethod
    async def create(self, invoice_line: InvoiceLine) -> InvoiceLine:
        """
        Create a new invoice line item

        Args:
            invoice_line: InvoiceLine entity to persist

        Returns:
            Created InvoiceLine with generated ID
        """
        pass
