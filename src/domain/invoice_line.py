"""Invoice Line Domain Entity

Tracks individual line items within an invoice.
"""

from datetime import datetime
from decimal import Decimal
from sqlmodel import Field, Column, Index
from sqlalchemy import BigInteger, ForeignKey, Numeric, String
from src.domain.base import BaseModel


class InvoiceLine(BaseModel, table=True):
    """
    Invoice Line - Individual line item within an invoice

    Domain Rules:
    - Each line item belongs to exactly one invoice
    - total_price = quantity * unit_price
    - Immutable once invoice is issued
    """

    __tablename__ = "invoice_lines"
    __table_args__ = (
        Index('ix_invoice_lines_invoice_id', 'invoice_id'),
    )

    id: int = Field(
        sa_column=Column(BigInteger, primary_key=True, autoincrement=True),
        description="Unique invoice line identifier (auto-increment)"
    )

    invoice_id: int = Field(
        sa_column=Column(BigInteger, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        description="Foreign key to Invoice"
    )

    description: str = Field(
        sa_column=Column(String(255), nullable=False),
        description="Line item description (e.g., 'Pipeline execution credits')"
    )

    quantity: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Quantity (e.g., number of credits, hours, units)"
    )

    unit_price: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Price per unit (precision: 18,6)"
    )

    total_price: Decimal = Field(
        sa_column=Column(Numeric(18, 6), nullable=False),
        description="Total price (quantity * unit_price)"
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Line item creation timestamp"
    )

    class Config:
        """SQLModel configuration"""
        json_schema_extra = {
            "example": {
                "id": 1,
                "invoice_id": 1,
                "description": "Pipeline execution credits",
                "quantity": "1000.000000",
                "unit_price": "0.150000",
                "total_price": "150.000000",
                "created_at": "2024-01-31T00:00:00Z"
            }
        }
