"""Invoice API Routes

FastAPI routes for invoice operations including proforma generation (UC-39).
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
import base64
from sqlmodel.ext.asyncio.session import AsyncSession

from src.app.use_cases.billing.dtos import ProformaInvoiceResponseDTO
from src.app.use_cases.billing.generate_proforma import GenerateProforma
from src.adapter.repositories.invoice_repository import SqlAlchemyInvoiceRepository
from src.adapter.repositories.invoice_line_repository import SqlAlchemyInvoiceLineRepository
from src.adapter.services.pdf_service import ReportLabPdfService
from src.depends import get_session
from src.api.error import ClientError

router = APIRouter(prefix="/billing/invoices", tags=["Invoices"])


@router.get(
    "/{invoice_id}/proforma",
    response_model=ProformaInvoiceResponseDTO,
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "description": "Invoice not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVOICE_NOT_FOUND",
                            "message": "Invoice with ID 123 not found"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid invoice status",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_INVOICE_STATUS",
                            "message": "Proforma can only be generated for draft invoices"
                        }
                    }
                }
            }
        }
    }
)
async def get_proforma_invoice(
    invoice_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Generate a proforma invoice PDF (UC-39).

    This endpoint generates a proforma (preview) invoice PDF for draft invoices.
    The proforma allows tenant admins to preview charges before finalization.

    **Path parameters:**
    - `invoice_id` (required): Invoice ID

    **Example response:**
    ```json
    {
      "invoice_id": 1,
      "invoice_number": "INV-2024-000001",
      "tenant_id": "tenant_xyz789",
      "status": "draft",
      "total_amount": "150.00",
      "currency": "USD",
      "billing_period_start": "2024-01-01T00:00:00Z",
      "billing_period_end": "2024-01-31T23:59:59Z",
      "line_items": [...],
      "pdf_base64": "JVBERi0xLjQKJeLjz9...",
      "generated_at": "2024-02-01T12:00:00Z"
    }
    ```

    **Returns:**
    - 200: Proforma invoice generated successfully
    - 400: Invoice is not in draft status
    - 404: Invoice not found
    """
    # Create repositories and services
    invoice_repo = SqlAlchemyInvoiceRepository(session)
    invoice_line_repo = SqlAlchemyInvoiceLineRepository(session)
    pdf_service = ReportLabPdfService()

    # Execute use case
    use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)
    result = await use_case.execute(invoice_id)

    # Handle errors
    if result.is_err():
        if result.error.code == "INVOICE_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        raise ClientError(result.error)

    # Return successful response
    return result.value


@router.get(
    "/{invoice_id}/proforma/pdf",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "PDF document"
        },
        404: {
            "description": "Invoice not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVOICE_NOT_FOUND",
                            "message": "Invoice with ID 123 not found"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid invoice status",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_INVOICE_STATUS",
                            "message": "Proforma can only be generated for draft invoices"
                        }
                    }
                }
            }
        }
    }
)
async def download_proforma_invoice_pdf(
    invoice_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Download proforma invoice as PDF file (UC-39).

    This endpoint generates and directly returns a PDF file for download.
    Use this endpoint for direct browser download or PDF viewer display.

    **Path parameters:**
    - `invoice_id` (required): Invoice ID

    **Returns:**
    - 200: PDF file as binary response
    - 400: Invoice is not in draft status
    - 404: Invoice not found
    """
    # Create repositories and services
    invoice_repo = SqlAlchemyInvoiceRepository(session)
    invoice_line_repo = SqlAlchemyInvoiceLineRepository(session)
    pdf_service = ReportLabPdfService()

    # Execute use case
    use_case = GenerateProforma(invoice_repo, invoice_line_repo, pdf_service)
    result = await use_case.execute(invoice_id)

    # Handle errors
    if result.is_err():
        if result.error.code == "INVOICE_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        raise ClientError(result.error)

    # Decode PDF from base64 and return as binary response
    pdf_bytes = base64.b64decode(result.value.pdf_base64)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=proforma_{result.value.invoice_number}.pdf"
        }
    )
