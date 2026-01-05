"""Data Transfer Objects for Billing Use Cases

Pydantic models for command inputs and response outputs.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ConsumeCommandDTO(BaseModel):
    """
    Command DTO for consuming credits

    Used as input to ConsumeCredit use case.
    """

    tenant_id: str = Field(
        ...,
        description="Tenant identifier"
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Credit amount to consume (must be > 0)"
    )

    idempotency_key: str = Field(
        ...,
        description="Unique key for idempotent operations (e.g., pipeline_id:step_id)"
    )

    reference_type: Optional[str] = Field(
        default=None,
        description="Type of reference (e.g., 'pipeline_run', 'task')"
    )

    reference_id: Optional[str] = Field(
        default=None,
        description="ID of referenced entity (e.g., pipeline_run_id)"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata for audit trail"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "amount": "30.500000",
                "idempotency_key": "pipeline_456:step_789",
                "reference_type": "pipeline_run",
                "reference_id": "run_456",
                "metadata": {"model": "gpt-4", "tokens": 1500}
            }
        }


class RefundCommandDTO(BaseModel):
    """
    Command DTO for refunding credits

    Used as input to RefundCredit use case.
    Refunds credits back to tenant balance (compensation for failed operations).
    """

    tenant_id: str = Field(
        ...,
        description="Tenant identifier"
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Credit amount to refund (must be > 0)"
    )

    idempotency_key: str = Field(
        ...,
        description="Unique key for idempotent operations (e.g., refund:pipeline_id:step_id)"
    )

    reference_type: Optional[str] = Field(
        default=None,
        description="Type of reference (e.g., 'pipeline_run', 'failed_step')"
    )

    reference_id: Optional[str] = Field(
        default=None,
        description="ID of referenced entity (e.g., pipeline_run_id)"
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Metadata linking to original transaction (original_transaction_id, reason)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "amount": "30.500000",
                "idempotency_key": "refund:pipeline_456:step_789",
                "reference_type": "failed_step",
                "reference_id": "step_789",
                "metadata": {
                    "original_transaction_id": "123",
                    "pipeline_run_id": "run_456",
                    "reason": "AI service timeout"
                }
            }
        }


class CreditTransactionResponseDTO(BaseModel):
    """
    Response DTO for credit transaction operations

    Returned by ConsumeCredit, RefundCredit, etc.
    """

    transaction_id: int = Field(
        ...,
        description="Transaction ID"
    )

    tenant_id: str = Field(
        ...,
        description="Tenant identifier"
    )

    transaction_type: str = Field(
        ...,
        description="Type of transaction (consume, refund, allocate, adjust)"
    )

    amount: Decimal = Field(
        ...,
        description="Credit amount"
    )

    balance_before: Decimal = Field(
        ...,
        description="Balance before transaction"
    )

    balance_after: Decimal = Field(
        ...,
        description="Balance after transaction"
    )

    reference_type: Optional[str] = Field(
        default=None,
        description="Type of reference"
    )

    reference_id: Optional[str] = Field(
        default=None,
        description="ID of referenced entity"
    )

    idempotency_key: str = Field(
        ...,
        description="Idempotency key"
    )

    created_at: datetime = Field(
        ...,
        description="Transaction timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 123,
                "tenant_id": "tenant_xyz789",
                "transaction_type": "consume",
                "amount": "30.500000",
                "balance_before": "1000.000000",
                "balance_after": "969.500000",
                "reference_type": "pipeline_run",
                "reference_id": "run_456",
                "idempotency_key": "pipeline_456:step_789",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class BalanceResponseDTO(BaseModel):
    """
    Response DTO for get balance operation

    Returned by GetBalance use case.
    """

    tenant_id: str = Field(
        ...,
        description="Tenant identifier"
    )

    balance: Decimal = Field(
        ...,
        description="Current credit balance"
    )

    last_updated: datetime = Field(
        ...,
        description="Timestamp of last balance update"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "balance": "969.500000",
                "last_updated": "2024-01-01T00:00:00Z"
            }
        }


class EstimateCommandDTO(BaseModel):
    """
    Command DTO for estimating credits (UC-33)

    Used as input to EstimateCredit use case.
    """

    task_id: Optional[str] = Field(
        default=None,
        description="Task identifier (optional, for context)"
    )

    pipeline_steps: list[str] = Field(
        ...,
        description="List of pipeline step types to estimate"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "task_123",
                "pipeline_steps": ["ANALYSIS", "USER_STORIES", "CODE", "TEST"]
            }
        }


class EstimateResponseDTO(BaseModel):
    """
    Response DTO for credit estimation (UC-33)

    Returns estimated credits without mutating balance.
    """

    estimated_credits: Decimal = Field(
        ...,
        description="Total estimated credit cost"
    )

    breakdown: Dict[str, Decimal] = Field(
        ...,
        description="Cost breakdown by pipeline step"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "estimated_credits": "45.500000",
                "breakdown": {
                    "ANALYSIS": "10.000000",
                    "USER_STORIES": "12.500000",
                    "CODE": "15.000000",
                    "TEST": "8.000000"
                }
            }
        }


class TransactionDTO(BaseModel):
    """
    DTO for a single transaction (UC-36)
    """

    id: int = Field(..., description="Transaction ID")
    transaction_type: str = Field(..., description="Type of transaction")
    amount: Decimal = Field(..., description="Transaction amount")
    balance_after: Decimal = Field(..., description="Balance after transaction")
    reference_type: Optional[str] = Field(default=None, description="Reference type")
    reference_id: Optional[str] = Field(default=None, description="Reference ID")
    created_at: datetime = Field(..., description="Transaction timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "transaction_type": "consume",
                "amount": "-15.500000",
                "balance_after": "84.500000",
                "reference_type": "pipeline_run",
                "reference_id": "run_uuid",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class ListTransactionsResponseDTO(BaseModel):
    """
    Response DTO for listing transactions (UC-36)
    """

    transactions: list[TransactionDTO] = Field(
        ...,
        description="List of transactions"
    )
    total: int = Field(..., description="Total number of transactions")
    limit: int = Field(..., description="Requested limit")
    offset: int = Field(..., description="Requested offset")

    class Config:
        json_schema_extra = {
            "example": {
                "transactions": [
                    {
                        "id": 123,
                        "transaction_type": "consume",
                        "amount": "-15.500000",
                        "balance_after": "84.500000",
                        "reference_type": "pipeline_run",
                        "reference_id": "run_uuid",
                        "created_at": "2024-01-01T00:00:00Z"
                    }
                ],
                "total": 150,
                "limit": 20,
                "offset": 0
            }
        }


# ============================================================================
# Abnormal Usage Detection DTOs (UC-37)
# ============================================================================


class AnomalyDTO(BaseModel):
    """
    DTO for a single usage anomaly (UC-37)
    """

    id: int = Field(..., description="Anomaly ID")
    tenant_id: str = Field(..., description="Tenant that triggered the anomaly")
    anomaly_type: str = Field(..., description="Type of anomaly")
    status: str = Field(..., description="Current status")
    threshold_value: Decimal = Field(..., description="Threshold that was exceeded")
    actual_value: Decimal = Field(..., description="Actual usage value")
    period_start: datetime = Field(..., description="Start of measurement period")
    period_end: datetime = Field(..., description="End of measurement period")
    description: Optional[str] = Field(default=None, description="Human-readable description")
    detected_at: datetime = Field(..., description="When anomaly was detected")
    notified_at: Optional[datetime] = Field(default=None, description="When notification was sent")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "tenant_id": "tenant_xyz789",
                "anomaly_type": "hourly_threshold",
                "status": "detected",
                "threshold_value": "100.000000",
                "actual_value": "150.500000",
                "period_start": "2024-01-01T10:00:00Z",
                "period_end": "2024-01-01T11:00:00Z",
                "description": "Tenant exceeded hourly credit threshold",
                "detected_at": "2024-01-01T11:05:00Z",
                "notified_at": None
            }
        }


class DetectAnomaliesResponseDTO(BaseModel):
    """
    Response DTO for anomaly detection run (UC-37)
    """

    anomalies_detected: int = Field(..., description="Number of anomalies detected")
    anomalies: list[AnomalyDTO] = Field(..., description="List of detected anomalies")
    period_start: datetime = Field(..., description="Detection period start")
    period_end: datetime = Field(..., description="Detection period end")
    threshold_used: Decimal = Field(..., description="Threshold value used for detection")

    class Config:
        json_schema_extra = {
            "example": {
                "anomalies_detected": 2,
                "anomalies": [],
                "period_start": "2024-01-01T10:00:00Z",
                "period_end": "2024-01-01T11:00:00Z",
                "threshold_used": "100.000000"
            }
        }


class ListAnomaliesResponseDTO(BaseModel):
    """
    Response DTO for listing anomalies (UC-37)
    """

    anomalies: list[AnomalyDTO] = Field(..., description="List of anomalies")
    total: int = Field(..., description="Total number of anomalies")
    limit: int = Field(..., description="Requested limit")
    offset: int = Field(..., description="Requested offset")

    class Config:
        json_schema_extra = {
            "example": {
                "anomalies": [],
                "total": 10,
                "limit": 20,
                "offset": 0
            }
        }


# ============================================================================
# Monthly Credit Allocation DTOs (UC-38)
# ============================================================================


class AllocateCreditsCommandDTO(BaseModel):
    """
    Command DTO for allocating credits (UC-38)

    Used by AllocateCredits use case to add credits to tenant balance.
    """

    tenant_id: str = Field(..., description="Tenant identifier")
    amount: Decimal = Field(..., gt=0, description="Credit amount to allocate (must be > 0)")
    idempotency_key: str = Field(
        ...,
        description="Unique key for idempotent operations (e.g., allocation:tenant:2024-01)"
    )
    reference_type: Optional[str] = Field(
        default="subscription",
        description="Type of reference (e.g., 'subscription', 'purchase')"
    )
    reference_id: Optional[str] = Field(
        default=None,
        description="ID of referenced entity (e.g., subscription_id)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "amount": "10000.000000",
                "idempotency_key": "allocation:tenant_xyz789:2024-01",
                "reference_type": "subscription",
                "reference_id": "sub_123"
            }
        }


class AllocateCreditsResponseDTO(BaseModel):
    """
    Response DTO for credit allocation (UC-38)
    """

    transaction_id: int = Field(..., description="Transaction ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    amount: Decimal = Field(..., description="Allocated credit amount")
    balance_before: Decimal = Field(..., description="Balance before allocation")
    balance_after: Decimal = Field(..., description="Balance after allocation")
    idempotency_key: str = Field(..., description="Idempotency key")
    created_at: datetime = Field(..., description="Transaction timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "transaction_id": 123,
                "tenant_id": "tenant_xyz789",
                "amount": "10000.000000",
                "balance_before": "500.000000",
                "balance_after": "10500.000000",
                "idempotency_key": "allocation:tenant_xyz789:2024-01",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class CreateInvoiceCommandDTO(BaseModel):
    """
    Command DTO for creating invoice (UC-38)

    Used by CreateInvoice use case to generate draft invoice.
    """

    tenant_id: str = Field(..., description="Tenant identifier")
    billing_period_start: datetime = Field(..., description="Billing period start date")
    billing_period_end: datetime = Field(..., description="Billing period end date")
    total_amount: Decimal = Field(..., ge=0, description="Total invoice amount")
    description: str = Field(
        default="Monthly credit allocation",
        description="Invoice description"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "billing_period_start": "2024-01-01T00:00:00Z",
                "billing_period_end": "2024-01-31T23:59:59Z",
                "total_amount": "150.000000",
                "description": "Monthly credit allocation - Pro Plan"
            }
        }


class InvoiceResponseDTO(BaseModel):
    """
    Response DTO for invoice operations (UC-38)
    """

    invoice_id: int = Field(..., description="Invoice ID")
    tenant_id: str = Field(..., description="Tenant identifier")
    invoice_number: str = Field(..., description="Unique invoice number")
    status: str = Field(..., description="Invoice status")
    total_amount: Decimal = Field(..., description="Total invoice amount")
    currency: str = Field(..., description="Currency code")
    billing_period_start: datetime = Field(..., description="Billing period start")
    billing_period_end: datetime = Field(..., description="Billing period end")
    created_at: datetime = Field(..., description="Invoice creation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_id": 1,
                "tenant_id": "tenant_xyz789",
                "invoice_number": "INV-2024-000001",
                "status": "draft",
                "total_amount": "150.000000",
                "currency": "USD",
                "billing_period_start": "2024-01-01T00:00:00Z",
                "billing_period_end": "2024-01-31T23:59:59Z",
                "created_at": "2024-02-01T00:00:00Z"
            }
        }


class MonthlyAllocationResultDTO(BaseModel):
    """
    Response DTO for monthly allocation job (UC-38)

    Contains summary of allocation run.
    """

    total_subscriptions: int = Field(..., description="Total active subscriptions processed")
    successful_allocations: int = Field(..., description="Number of successful allocations")
    failed_allocations: int = Field(..., description="Number of failed allocations")
    invoices_created: int = Field(..., description="Number of invoices created")
    billing_period_start: datetime = Field(..., description="Billing period start")
    billing_period_end: datetime = Field(..., description="Billing period end")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "total_subscriptions": 100,
                "successful_allocations": 98,
                "failed_allocations": 2,
                "invoices_created": 98,
                "billing_period_start": "2024-01-01T00:00:00Z",
                "billing_period_end": "2024-01-31T23:59:59Z",
                "execution_time_ms": 5420
            }
        }


# ============================================================================
# Proforma Invoice DTOs (UC-39)
# ============================================================================


class InvoiceLineDTO(BaseModel):
    """
    DTO for an invoice line item (UC-39)
    """

    id: int = Field(..., description="Line item ID")
    description: str = Field(..., description="Line item description")
    quantity: Decimal = Field(..., description="Quantity")
    unit_price: Decimal = Field(..., description="Unit price")
    total_price: Decimal = Field(..., description="Total price")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "description": "Pipeline execution credits",
                "quantity": "1000.000000",
                "unit_price": "0.150000",
                "total_price": "150.000000"
            }
        }


class ProformaInvoiceResponseDTO(BaseModel):
    """
    Response DTO for proforma invoice generation (UC-39)

    Contains invoice metadata and PDF as base64-encoded bytes.
    """

    invoice_id: int = Field(..., description="Invoice ID")
    invoice_number: str = Field(..., description="Invoice number")
    tenant_id: str = Field(..., description="Tenant identifier")
    status: str = Field(..., description="Invoice status")
    total_amount: Decimal = Field(..., description="Total amount")
    currency: str = Field(..., description="Currency code")
    billing_period_start: datetime = Field(..., description="Billing period start")
    billing_period_end: datetime = Field(..., description="Billing period end")
    line_items: list[InvoiceLineDTO] = Field(..., description="Invoice line items")
    pdf_base64: str = Field(..., description="PDF document as base64-encoded string")
    generated_at: datetime = Field(..., description="PDF generation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "invoice_id": 1,
                "invoice_number": "INV-2024-000001",
                "tenant_id": "tenant_xyz789",
                "status": "draft",
                "total_amount": "150.000000",
                "currency": "USD",
                "billing_period_start": "2024-01-01T00:00:00Z",
                "billing_period_end": "2024-01-31T23:59:59Z",
                "line_items": [
                    {
                        "id": 1,
                        "description": "Pipeline execution credits",
                        "quantity": "1000.000000",
                        "unit_price": "0.150000",
                        "total_price": "150.000000"
                    }
                ],
                "pdf_base64": "JVBERi0xLjQKJeLjz9...",
                "generated_at": "2024-02-01T12:00:00Z"
            }
        }


# ============================================================================
# Credit Ledger Reconciliation DTOs (UC-40)
# ============================================================================


class LedgerDiscrepancyDTO(BaseModel):
    """
    DTO for a single ledger discrepancy (UC-40)
    """

    tenant_id: str = Field(..., description="Tenant identifier")
    ledger_id: int = Field(..., description="Ledger ID")
    ledger_balance: Decimal = Field(..., description="Current balance in ledger")
    calculated_balance: Decimal = Field(
        ..., description="Balance calculated from transaction sum"
    )
    discrepancy: Decimal = Field(
        ..., description="Difference (ledger_balance - calculated_balance)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "ledger_id": 123,
                "ledger_balance": "1000.000000",
                "calculated_balance": "985.500000",
                "discrepancy": "14.500000"
            }
        }


class ReconciliationResultDTO(BaseModel):
    """
    Response DTO for ledger reconciliation job (UC-40)

    Contains summary of reconciliation run and any discrepancies found.
    """

    total_ledgers_checked: int = Field(..., description="Total number of ledgers checked")
    discrepancies_found: int = Field(..., description="Number of discrepancies found")
    discrepancies: list[LedgerDiscrepancyDTO] = Field(
        ..., description="List of discrepancy details"
    )
    reconciliation_time: datetime = Field(..., description="When reconciliation was run")
    execution_time_ms: int = Field(..., description="Execution time in milliseconds")

    class Config:
        json_schema_extra = {
            "example": {
                "total_ledgers_checked": 100,
                "discrepancies_found": 2,
                "discrepancies": [
                    {
                        "tenant_id": "tenant_xyz789",
                        "ledger_id": 123,
                        "ledger_balance": "1000.000000",
                        "calculated_balance": "985.500000",
                        "discrepancy": "14.500000"
                    }
                ],
                "reconciliation_time": "2024-01-15T10:00:00Z",
                "execution_time_ms": 2345
            }
        }
