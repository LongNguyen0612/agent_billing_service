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
