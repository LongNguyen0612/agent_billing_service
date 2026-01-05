"""CreateInvoice Use Case (UC-38)

Creates a draft invoice for monthly credit allocation.
Used by monthly allocation job to generate invoices.
"""

from datetime import datetime
from libs.result import Result, Return, Error
from src.app.services.unit_of_work import UnitOfWork
from src.app.repositories.invoice_repository import InvoiceRepository
from src.domain.invoice import Invoice, InvoiceStatus
from .dtos import CreateInvoiceCommandDTO, InvoiceResponseDTO


class CreateInvoice:
    """
    Use Case: Create draft invoice for billing period

    Business Rules:
    1. No duplicate invoices for same tenant/period
    2. Invoice number is auto-generated (INV-YYYY-NNNNNN)
    3. Invoice is created with status=draft
    4. Billing period dates are validated

    Flow:
    1. Check for duplicate invoice (same tenant, same period)
    2. Generate unique invoice number
    3. Create invoice with status=draft
    4. Commit transaction
    5. Return response
    """

    def __init__(
        self,
        uow: UnitOfWork,
        invoice_repo: InvoiceRepository,
    ):
        self.uow = uow
        self.invoice_repo = invoice_repo

    async def execute(self, command: CreateInvoiceCommandDTO) -> Result[InvoiceResponseDTO]:
        """
        Execute invoice creation

        Args:
            command: CreateInvoiceCommandDTO with tenant_id, billing period, amount

        Returns:
            Result[InvoiceResponseDTO]: Success with invoice details or error
        """
        try:
            # Step 1: Check for duplicate invoice
            exists = await self.invoice_repo.exists_for_period(
                tenant_id=command.tenant_id,
                billing_period_start=command.billing_period_start.date(),
                billing_period_end=command.billing_period_end.date(),
            )

            if exists:
                return Return.err(
                    Error(
                        code="INVOICE_ALREADY_EXISTS",
                        message=f"Invoice already exists for tenant {command.tenant_id} "
                                f"for period {command.billing_period_start.date()} to "
                                f"{command.billing_period_end.date()}",
                        reason="Duplicate invoice prevention",
                    )
                )

            # Step 2: Generate unique invoice number
            invoice_number = await self.invoice_repo.generate_invoice_number()

            # Step 3: Create invoice with status=draft
            invoice = Invoice(
                tenant_id=command.tenant_id,
                invoice_number=invoice_number,
                status=InvoiceStatus.DRAFT,
                total_amount=command.total_amount,
                currency="USD",
                billing_period_start=command.billing_period_start.date(),
                billing_period_end=command.billing_period_end.date(),
            )

            created_invoice = await self.invoice_repo.create(invoice)

            # Step 4: Commit transaction
            await self.uow.commit()

            # Step 5: Build response
            response = InvoiceResponseDTO(
                invoice_id=created_invoice.id,
                tenant_id=created_invoice.tenant_id,
                invoice_number=created_invoice.invoice_number,
                status=created_invoice.status.value,
                total_amount=created_invoice.total_amount,
                currency=created_invoice.currency,
                billing_period_start=datetime.combine(
                    created_invoice.billing_period_start,
                    datetime.min.time()
                ),
                billing_period_end=datetime.combine(
                    created_invoice.billing_period_end,
                    datetime.max.time().replace(microsecond=0)
                ),
                created_at=created_invoice.created_at,
            )

            return Return.ok(response)

        except Exception as e:
            await self.uow.rollback()
            return Return.err(
                Error(
                    code="CREATE_INVOICE_FAILED",
                    message="Failed to create invoice",
                    reason=str(e),
                )
            )
