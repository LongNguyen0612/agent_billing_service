"""GenerateProforma Use Case (UC-39)

Generates a proforma invoice PDF for preview purposes.
"""

import base64
from datetime import datetime
from libs.result import Result, Return, Error
from src.app.repositories.invoice_repository import InvoiceRepository
from src.app.repositories.invoice_line_repository import InvoiceLineRepository
from src.app.services.pdf_service import PdfService
from src.domain.invoice import InvoiceStatus
from .dtos import ProformaInvoiceResponseDTO, InvoiceLineDTO


class GenerateProforma:
    """
    Use Case: Generate proforma invoice PDF (UC-39)

    Business Rules:
    1. Invoice must exist
    2. Invoice must have status=draft (proforma is for preview)
    3. Generates PDF with invoice details and line items
    4. Returns PDF as base64-encoded string

    Flow:
    1. Retrieve invoice by ID
    2. Validate invoice status is draft
    3. Retrieve invoice line items
    4. Generate PDF using PDF service
    5. Return response with PDF as base64
    """

    def __init__(
        self,
        invoice_repo: InvoiceRepository,
        invoice_line_repo: InvoiceLineRepository,
        pdf_service: PdfService,
    ):
        self.invoice_repo = invoice_repo
        self.invoice_line_repo = invoice_line_repo
        self.pdf_service = pdf_service

    async def execute(self, invoice_id: int) -> Result[ProformaInvoiceResponseDTO]:
        """
        Execute proforma invoice generation

        Args:
            invoice_id: Invoice ID to generate proforma for

        Returns:
            Result[ProformaInvoiceResponseDTO]: Success with PDF or error
        """
        try:
            # Step 1: Retrieve invoice
            invoice = await self.invoice_repo.get_by_id(invoice_id)

            if not invoice:
                return Return.err(
                    Error(
                        code="INVOICE_NOT_FOUND",
                        message=f"Invoice with ID {invoice_id} not found",
                        reason="Invoice does not exist",
                    )
                )

            # Step 2: Validate status is draft
            if invoice.status != InvoiceStatus.DRAFT:
                return Return.err(
                    Error(
                        code="INVALID_INVOICE_STATUS",
                        message=f"Proforma can only be generated for draft invoices. "
                                f"Current status: {invoice.status.value}",
                        reason="Only draft invoices support proforma generation",
                    )
                )

            # Step 3: Retrieve invoice line items
            invoice_lines = await self.invoice_line_repo.get_by_invoice_id(invoice_id)

            # Step 4: Generate PDF
            pdf_bytes = self.pdf_service.generate_proforma_invoice(
                invoice=invoice,
                invoice_lines=invoice_lines,
            )

            # Encode PDF as base64
            pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

            # Step 5: Build response
            line_dtos = [
                InvoiceLineDTO(
                    id=line.id,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    total_price=line.total_price,
                )
                for line in invoice_lines
            ]

            response = ProformaInvoiceResponseDTO(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number,
                tenant_id=invoice.tenant_id,
                status=invoice.status.value,
                total_amount=invoice.total_amount,
                currency=invoice.currency,
                billing_period_start=datetime.combine(
                    invoice.billing_period_start,
                    datetime.min.time()
                ),
                billing_period_end=datetime.combine(
                    invoice.billing_period_end,
                    datetime.max.time().replace(microsecond=0)
                ),
                line_items=line_dtos,
                pdf_base64=pdf_base64,
                generated_at=datetime.utcnow(),
            )

            return Return.ok(response)

        except Exception as e:
            return Return.err(
                Error(
                    code="GENERATE_PROFORMA_FAILED",
                    message="Failed to generate proforma invoice",
                    reason=str(e),
                )
            )
