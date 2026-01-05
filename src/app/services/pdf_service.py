"""PDF Generation Service Interface

Defines the contract for PDF generation operations.
"""

from abc import ABC, abstractmethod
from typing import List
from src.domain.invoice import Invoice
from src.domain.invoice_line import InvoiceLine


class PdfService(ABC):
    """
    Service interface for PDF generation

    Provides PDF generation capabilities for invoices.
    """

    @abstractmethod
    def generate_proforma_invoice(
        self,
        invoice: Invoice,
        invoice_lines: List[InvoiceLine],
        company_name: str = "Super Agent Platform",
        company_address: str = "123 AI Street, Tech City, TC 12345",
    ) -> bytes:
        """
        Generate a proforma invoice PDF

        Args:
            invoice: Invoice entity with billing details
            invoice_lines: List of line items for the invoice
            company_name: Company name to display on invoice
            company_address: Company address to display on invoice

        Returns:
            PDF document as bytes
        """
        pass
