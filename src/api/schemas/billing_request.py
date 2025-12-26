"""Request schemas for Billing API

Pydantic models for validating incoming HTTP requests.
"""

from decimal import Decimal
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ConsumeRequestSchema(BaseModel):
    """
    Request schema for consuming credits

    Used for POST /billing/credits/consume endpoint.
    """

    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Tenant identifier (required, non-empty)"
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Credit amount to consume (must be > 0)"
    )

    idempotency_key: str = Field(
        ...,
        min_length=1,
        description="Unique key for idempotent operations (required, non-empty)"
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

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is positive and has reasonable precision"""
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "amount": "30.50",
                "idempotency_key": "pipeline_456:step_789",
                "reference_type": "pipeline_run",
                "reference_id": "run_456",
                "metadata": {"model": "gpt-4", "tokens": 1500}
            }
        }


class RefundRequestSchema(BaseModel):
    """
    Request schema for refunding credits

    Used for POST /billing/credits/refund endpoint.
    """

    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Tenant identifier (required, non-empty)"
    )

    amount: Decimal = Field(
        ...,
        gt=0,
        description="Credit amount to refund (must be > 0)"
    )

    idempotency_key: str = Field(
        ...,
        min_length=1,
        description="Unique key for idempotent operations (required, non-empty)"
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
        description="Metadata linking to original transaction (should include original_transaction_id, reason)"
    )

    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        """Ensure amount is positive"""
        if v <= 0:
            raise ValueError("Amount must be greater than 0")
        return v

    @field_validator('metadata')
    @classmethod
    def validate_metadata(cls, v):
        """Ensure metadata includes original_transaction_id if provided"""
        if v is not None and 'original_transaction_id' not in v:
            raise ValueError("Metadata must include 'original_transaction_id' for refunds")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "tenant_xyz789",
                "amount": "30.50",
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
