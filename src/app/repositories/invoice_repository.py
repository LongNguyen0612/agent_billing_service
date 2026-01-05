"""Invoice Repository Interface

Defines the contract for invoice persistence operations.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import date
from src.domain.invoice import Invoice, InvoiceStatus


class InvoiceRepository(ABC):
    """
    Repository interface for Invoice persistence

    Provides access to invoice data for billing operations.
    """

    @abstractmethod
    async def create(self, invoice: Invoice) -> Invoice:
        """
        Create a new invoice

        Args:
            invoice: Invoice entity to persist

        Returns:
            Created Invoice with generated ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, invoice_id: int) -> Optional[Invoice]:
        """
        Retrieve invoice by ID

        Args:
            invoice_id: Invoice ID

        Returns:
            Invoice if found, None otherwise
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_by_invoice_number(self, invoice_number: str) -> Optional[Invoice]:
        """
        Retrieve invoice by invoice number

        Args:
            invoice_number: Unique invoice number

        Returns:
            Invoice if found, None otherwise
        """
        pass

    @abstractmethod
    async def update(self, invoice: Invoice) -> Invoice:
        """
        Update an existing invoice

        Args:
            invoice: Invoice entity with updated values

        Returns:
            Updated Invoice
        """
        pass

    @abstractmethod
    async def exists_for_period(
        self, tenant_id: str, billing_period_start: date, billing_period_end: date
    ) -> bool:
        """
        Check if invoice already exists for the given billing period

        Used to prevent duplicate invoice generation.

        Args:
            tenant_id: Tenant identifier
            billing_period_start: Start of billing period
            billing_period_end: End of billing period

        Returns:
            True if invoice exists, False otherwise
        """
        pass

    @abstractmethod
    async def generate_invoice_number(self) -> str:
        """
        Generate a unique invoice number

        Format: INV-YYYY-NNNNNN (e.g., INV-2024-000001)

        Returns:
            Unique invoice number string
        """
        pass
