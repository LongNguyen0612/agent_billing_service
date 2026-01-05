"""Invoice Domain Entity

Tracks billing invoices and payment status.
"""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from sqlmodel import Field, Column, Index
from sqlalchemy import BigInteger, Numeric, String, Date
from src.domain.base import BaseModel


class InvoiceStatus(str, Enum):
    """Invoice status types"""
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    CANCELLED = "cancelled"


class Invoice(BaseModel, table=True):
    """
    Invoice - Billing invoice for tenant usage

    Domain Rules:
    - invoice_number must be unique
    - Status transitions: draft -> issued -> paid (or cancelled)
    - total_amount is the sum of all invoice_lines.total_price
    - issued_at and paid_at are set when status changes
    """

    __tablename__ = "invoices"
    __table_args__ = (
        Index('ix_invoices_tenant_id', 'tenant_id'),
        Index('ix_invoices_status', 'status'),
        Index('ix_invoices_invoice_number', 'invoice_number', unique=True),
    )

    id: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
        description="Unique invoice identifier (auto-increment)"
    )

    tenant_id: str = Field(
        description="Tenant ID"
    )

    invoice_number: str = Field(
        sa_column=Column(String(50), nullable=False, unique=True),
        description="Unique invoice number (e.g., INV-2024-001)"
    )

    status: InvoiceStatus = Field(
        description="Invoice status (draft, issued, paid, cancelled)"
    )

    total_amount: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Total invoice amount (precision: 18,6)"
    )

    currency: str = Field(
        default="USD",
        sa_column=Column(String(3), nullable=False),
        description="Currency code (ISO 4217)"
    )

    billing_period_start: date = Field(
        sa_column=Column(Date, nullable=False),
        description="Billing period start date"
    )

    billing_period_end: date = Field(
        sa_column=Column(Date, nullable=False),
        description="Billing period end date"
    )

    issued_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when invoice was issued"
    )

    paid_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when invoice was paid"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Invoice creation timestamp"
    )

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp"
    )

    class Config:
        """SQLModel configuration"""
        json_schema_extra = {
            "example": {
                "id": 1,
                "tenant_id": "tenant_xyz789",
                "invoice_number": "INV-2024-001",
                "status": "issued",
                "total_amount": "150.500000",
                "currency": "USD",
                "billing_period_start": "2024-01-01",
                "billing_period_end": "2024-01-31",
                "issued_at": "2024-02-01T00:00:00Z",
                "paid_at": None,
                "created_at": "2024-01-31T00:00:00Z",
                "updated_at": "2024-02-01T00:00:00Z"
            }
        }
